import os
import unittest

from speech.audio_process import audio_process, receive_audio


def exit_during_audio(_connection):
    os._exit(7)


def send_audio(connection):
    connection.send(b"audio")


class AudioProcessTests(unittest.TestCase):
    def test_audio_process_can_send_data(self):
        with audio_process(send_audio) as (connection, process):
            self.assertEqual(receive_audio(connection, process, 10), b"audio")

    def test_crashed_audio_process_does_not_close_nexo(self):
        with audio_process(exit_during_audio) as (connection, process):
            with self.assertRaisesRegex(RuntimeError, "dejó de responder"):
                receive_audio(connection, process, 10)
