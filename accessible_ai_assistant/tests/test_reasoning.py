import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from ai.reasoning_policy import choose_reasoning
from ai.openai_provider import OpenAIProvider, ActionParameters, StructuredReply


class ReasoningTests(unittest.TestCase):
    def test_simple_commands_use_low(self):
        for text in ('Abre la calculadora', 'Mueve el puntero al centro', 'Guarda el archivo', 'Hola', 'Sube el volumen'):
            with self.subTest(text=text):
                self.assertEqual(choose_reasoning(text).effort, 'low')

    def test_complex_commands_use_high_even_when_starting_with_abre(self):
        for text in ('Abre Word y busca la fecha de entrega', 'Analiza el error de esta pantalla', 'Compara estas dos respuestas', 'Explícame por qué no funciona', 'Busca el nombre y después escribe la respuesta', 'Ayúdame a resolver el problema'):
            with self.subTest(text=text):
                self.assertEqual(choose_reasoning(text).effort, 'high')

    def test_default_and_visual_tasks_have_medium_floor(self):
        self.assertEqual(choose_reasoning('Qué significa HTML').effort, 'medium')
        self.assertEqual(choose_reasoning('Qué hora aparece', 'vision').effort, 'medium')
        self.assertEqual(choose_reasoning('Mueve el puntero', 'computer').effort, 'medium')

    def test_followup_inherits_complexity_but_unrelated_command_does_not(self):
        recent = 'Usuario: Compara estas dos alternativas'
        self.assertEqual(choose_reasoning('Sí, hazlo', recent=recent).effort, 'high')
        self.assertEqual(choose_reasoning('Abre la calculadora', recent=recent).effort, 'low')

    def test_visual_escalation_is_high(self):
        self.assertEqual(choose_reasoning('Mueve el puntero', 'computer', escalate=True).effort, 'high')

    def test_provider_sends_effort_and_notifies_interface(self):
        provider = object.__new__(OpenAIProvider)
        provider.model = 'gpt-6-luna'
        provider.client = Mock()
        provider.on_reasoning = Mock()
        provider.client.responses.parse.return_value = SimpleNamespace(output_parsed=StructuredReply(type='response', action=None, parameters=ActionParameters(application='', name='', text='', key=''), spoken_response='Hola.'))
        provider.interpret('Hola', 'Ventana de pruebas', [], True)
        self.assertEqual(provider.client.responses.parse.call_args.kwargs['reasoning'], {'effort': 'low'})
        self.assertEqual(provider.on_reasoning.call_args.args[0].effort, 'low')
        provider.interpret('Compara las opciones', '', [], True)
        self.assertEqual(provider.client.responses.parse.call_args.kwargs['reasoning'], {'effort': 'high'})
        provider.client.responses.create.return_value = SimpleNamespace(output_text='Descripción')
        provider.describe_image(b'PNG', '', 'Qué aparece')
        self.assertEqual(provider.client.responses.create.call_args.kwargs['reasoning'], {'effort': 'medium'})
        provider.describe_image(b'PNG', '', 'Analiza el error')
        self.assertEqual(provider.client.responses.create.call_args.kwargs['reasoning'], {'effort': 'high'})
