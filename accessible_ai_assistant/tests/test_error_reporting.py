import json
import logging
from pathlib import Path
import smtplib
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from actions.action_models import AIReply
from pydantic import ValidationError
from utils.error_reporting import ErrorReporter, ErrorReportHandler, install_exception_hooks, unprotect
from utils.logger import SafeFormatter


class ErrorReportingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.now = 10000
        self.reporter = ErrorReporter(Path(self.folder.name), clock=lambda: self.now)

    def configure(self):
        self.reporter.settings_path.write_text(json.dumps({'enabled': True, 'sender': 'sender@example.com', 'recipient': 'owner@example.com', 'host': 'smtp.gmail.com', 'port': 587, 'password_protected': 'dummy'}), encoding='utf-8')

    def test_exception_messages_and_arguments_never_enter_reports(self):
        secret = 'SECRET_TOKEN_and_private_conversation'
        try:
            raise RuntimeError(secret)
        except RuntimeError as exc:
            self.reporter.capture(exc, stage='test', event='test_failure')
        report = self.reporter.reports()[0]
        self.assertNotIn(secret, json.dumps(report))
        self.assertNotIn(str(Path(self.folder.name)), json.dumps(report))
        self.assertEqual(report['diagnostic']['exception'], 'RuntimeError')
        self.assertTrue(report['diagnostic']['frames'])

    def test_validation_report_keeps_field_name_without_input(self):
        try:
            AIReply(type='response', spoken_response='')
        except ValidationError as exc:
            self.reporter.capture(exc)
        validation = self.reporter.reports()[0]['diagnostic']['validation']
        self.assertEqual(validation[0]['fields'], ['spoken_response'])
        self.assertEqual(validation[0]['type'], 'string_too_short')

    def test_repeated_errors_are_grouped_and_survive_restart(self):
        self.reporter.capture(ValueError('one'), stage='worker')
        self.reporter.capture(ValueError('two'), stage='worker')
        other = ErrorReporter(Path(self.folder.name), clock=lambda: self.now)
        self.assertEqual(other.reports()[0]['occurrences'], 2)

    def test_failed_delivery_keeps_outbox_and_backs_off(self):
        self.configure()
        self.reporter.capture(ValueError())
        with patch.object(self.reporter, '_send', side_effect=OSError('offline')) as send:
            with self.assertRaises(OSError):
                self.reporter.send_pending()
            self.assertEqual(self.reporter.send_pending(), 0)
            self.assertEqual(send.call_count, 1)
        self.assertEqual(len(self.reporter.reports(pending_only=True)), 1)

    def test_delivery_acknowledges_snapshot_without_losing_concurrent_errors(self):
        self.configure()
        self.reporter.capture(ValueError(), stage='worker')
        with patch.object(self.reporter, '_send', side_effect=lambda *_: self.reporter.capture(ValueError(), stage='worker')):
            self.reporter.send_pending()
        report = self.reporter.reports(pending_only=True)[0]
        self.assertEqual(report['occurrences'], 2)
        self.assertEqual(report['sent_occurrences'], 1)

    def test_hourly_limit_and_disabled_reporting(self):
        self.reporter.capture(ValueError())
        with patch.object(self.reporter, '_send') as send:
            self.assertEqual(self.reporter.send_pending(), 0)
            send.assert_not_called()
            self.configure()
            self.assertEqual(self.reporter.send_pending(), 1)
            self.reporter.capture(TypeError())
            self.assertEqual(self.reporter.send_pending(), 0)
            self.now += 3601
            self.assertEqual(self.reporter.send_pending(), 1)

    def test_password_protection_and_blank_field_preserve_secret(self):
        settings = {'enabled': True, 'sender': 'sender@example.com', 'recipient': 'owner@example.com', 'host': 'smtp.gmail.com', 'port': 587}
        self.reporter.save_settings(settings, 'dummy-password-for-test')
        text = self.reporter.settings_path.read_text()
        self.assertNotIn('dummy-password-for-test', text)
        self.assertEqual(unprotect(self.reporter.settings()['password_protected']), 'dummy-password-for-test')
        self.reporter.save_settings(settings, '')
        self.assertEqual(unprotect(self.reporter.settings()['password_protected']), 'dummy-password-for-test')

    def test_smtp_tls_precedes_login_and_password_is_not_in_body(self):
        self.configure()
        with patch('utils.error_reporting.unprotect', return_value='test-password'), patch('utils.error_reporting.smtplib.SMTP') as smtp:
            self.reporter.send_test()
        server = smtp.return_value.__enter__.return_value
        # Connection object enters its context before any authentication.
        server = smtp.return_value
        methods = [call[0] for call in server.method_calls]
        self.assertLess(methods.index('starttls'), methods.index('login'))
        self.assertNotIn('test-password', server.send_message.call_args.args[0].get_content())

    def test_logging_handler_omits_arbitrary_messages(self):
        handler = ErrorReportHandler(self.reporter)
        record = logging.LogRecord('test', logging.ERROR, __file__, 1, 'PRIVATE_TEXT=%s', ('SECRET_VALUE',), None)
        handler.emit(record)
        self.assertNotIn('SECRET_VALUE', json.dumps(self.reporter.reports()))
        self.assertNotIn('SECRET_VALUE', SafeFormatter().format(record))

    def test_global_hooks_cover_main_and_background_failures(self):
        fake = Mock()
        with patch('utils.error_reporting.get_reporter', return_value=fake), patch('sys.excepthook'), patch('threading.excepthook'), patch('sys.__excepthook__'):
            import sys
            import threading
            install_exception_hooks()
            error = RuntimeError('private')
            sys.excepthook(RuntimeError, error, None)
            threading.excepthook(SimpleNamespace(exc_value=error, exc_traceback=None))
        self.assertEqual(fake.capture.call_count, 2)
        fake.start.assert_called_once()

    def test_header_injection_is_rejected_before_saving(self):
        with self.assertRaises(ValueError):
            self.reporter.save_settings({'sender': 'a@example.com\nCc: other@example.com'})
        self.assertFalse(self.reporter.settings_path.exists())

    def test_broken_report_storage_does_not_block_startup(self):
        with patch('utils.error_reporting.get_reporter', side_effect=OSError('unwritable')):
            self.assertIsNone(install_exception_hooks())
