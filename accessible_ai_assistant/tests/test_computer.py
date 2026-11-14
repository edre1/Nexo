import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ai.computer_session import ComputerSession
from ai.instructions import SPOKEN_STYLE
from windows.computer_driver import ComputerDriver, normalized_keys


def item(data):
    return SimpleNamespace(type=data['type'], call_id=data.get('call_id'), model_dump=lambda **_kwargs: data)


def response(actions=None, safety=None, text='Tarea terminada.'):
    return SimpleNamespace(status='completed', output=[] if actions is None else [item({'type': 'computer_call', 'call_id': 'call_test', 'actions': actions, 'pending_safety_checks': safety or []})], output_text=text)


class ComputerTests(unittest.TestCase):
    def setup_session(self, replies, confirm=True, **kwargs):
        provider = Mock()
        provider.model = 'gpt-6-luna'
        provider.reasoning_for.return_value = {'effort': 'medium'}
        provider.client.responses.create.side_effect = replies
        driver = Mock()
        driver.capture.return_value = b'fake PNG'
        driver.describe.return_value = 'escribir Hola'
        cancel = threading.Event()
        session = ComputerSession(provider, driver, cancel, Mock(return_value=confirm), Mock(), **kwargs)
        return session, provider, driver

    def test_native_loop_returns_screenshot_and_finishes(self):
        session, provider, driver = self.setup_session([response([{'type': 'type', 'text': 'Hola'}]), response(text='**Tarea terminada.**')])
        self.assertEqual(session.run('Escribe Hola'), 'Tarea terminada.')
        driver.execute.assert_called_once_with({'type': 'type', 'text': 'Hola'})
        self.assertEqual(driver.capture.call_count, 2)
        kwargs = provider.client.responses.create.call_args.kwargs
        self.assertEqual(kwargs['tools'], [{'type': 'computer'}])
        self.assertEqual(kwargs['reasoning'], {'effort': 'medium'})
        self.assertEqual(kwargs['input'][-1]['type'], 'computer_call_output')
        self.assertIn(SPOKEN_STYLE, kwargs['instructions'])
        self.assertFalse(kwargs['store'])

    def test_declining_confirmation_never_executes(self):
        session, _, driver = self.setup_session([response([{'type': 'click', 'x': 10, 'y': 10}])], confirm=False)
        with self.assertRaises(InterruptedError):
            session.run('Haz clic')
        driver.execute.assert_not_called()

    def test_without_confirmation_visual_actions_are_validated_and_executed(self):
        action = {'type': 'click', 'x': 10, 'y': 10}
        session, provider, driver = self.setup_session([response([action]), response()])
        session.confirm = None
        session.run('Haz clic')
        self.assertIn('sin confirmación', provider.client.responses.create.call_args.kwargs['instructions'])
        driver.validate.assert_called_once_with(action)
        driver.execute.assert_called_once_with(action)
        driver.describe.assert_not_called()

    def test_cancellation_after_confirmation_still_prevents_execution(self):
        session, _, driver = self.setup_session([response([{'type': 'type', 'text': 'Hola'}])])
        def confirm(_text):
            session.cancel.set()
            return True
        session.confirm = confirm
        with self.assertRaises(InterruptedError):
            session.run('Escribe')
        driver.execute.assert_not_called()

    def test_pending_safety_review_stops_execution(self):
        session, _, driver = self.setup_session([response([{'type': 'click', 'x': 1, 'y': 1}], safety=[{'id': 'review', 'message': 'Review'}])])
        session.confirm = None
        with self.assertRaisesRegex(ValueError, 'revisión'):
            session.run('Haz clic')
        driver.execute.assert_not_called()

    def test_turn_limit_stops_loop(self):
        session, _, driver = self.setup_session([response([{'type': 'screenshot'}])], max_turns=1)
        with self.assertRaisesRegex(RuntimeError, 'límite de pasos'):
            session.run('Revisa')

    def test_visual_steps_request_escalation_after_four_turns(self):
        session, provider, _ = self.setup_session([response([{'type': 'screenshot'}]) for _ in range(5)] + [response()])
        session.run('Mueve el puntero')
        calls = provider.reasoning_for.call_args_list
        self.assertFalse(calls[0].kwargs['escalate'])
        self.assertTrue(calls[4].kwargs['escalate'])

    def test_old_single_action_shape_is_accepted(self):
        session, provider, driver = self.setup_session([SimpleNamespace(status='completed', output=[item({'type': 'computer_call', 'call_id': 'c', 'action': {'type': 'move', 'x': 1, 'y': 2}})], output_text=''), response()])
        session.run('Mueve')
        driver.execute.assert_called_once()


class ActionValidationTests(unittest.TestCase):
    def setUp(self):
        self.driver = object.__new__(ComputerDriver)
        self.driver.rect = (-100, 20, 500, 420)

    def test_coordinates_map_without_rescaling_and_outside_is_rejected(self):
        self.assertEqual(self.driver._point({'x': 50, 'y': 100}), (-50, 120))
        for point in ({'x': -1, 'y': 0}, {'x': 600, 'y': 0}, {'x': float('nan'), 'y': 2}):
            with self.assertRaises(ValueError):
                self.driver.validate({'type': 'move', **point})

    def test_arbitrary_tools_and_keys_are_rejected(self):
        for action in ({'type': 'shell', 'code': 'dir'}, {'type': 'keypress', 'keys': ['WIN', 'R']}, {'type': 'keypress', 'keys': ['DELETE']}, {'type': 'type', 'text': 'javascript:alert(1)'}):
            with self.assertRaises(ValueError):
                self.driver.validate(action)
        self.assertEqual(normalized_keys(['Control', 'a']), 'CTRL+A')

    def test_drag_path_is_bounded(self):
        with self.assertRaises(ValueError):
            self.driver.validate({'type': 'drag', 'path': [{'x': 1, 'y': 1}, {'x': 999, 'y': 1}]})

    def test_integrated_terminal_and_password_field_are_blocked(self):
        field = Mock()
        field.element_info.name = 'Terminal de Visual Studio Code'
        field.element_info.element.CurrentIsPassword = False
        with patch('windows.computer_driver.UIAutomation._focused', return_value=field):
            with self.assertRaisesRegex(ValueError, 'terminales'):
                self.driver._check_keyboard_focus()
            field.element_info.name = 'Usuario'
            field.element_info.element.CurrentIsPassword = True
            with self.assertRaisesRegex(ValueError, 'contraseña'):
                self.driver._check_keyboard_focus()
