"""Offline behavior tests: no real recordings, credentials, or paid API calls."""

import base64
import io
import json
import ssl
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import wave

from voice_service import Settings, answer, format_answer, pcm_to_wav, speak, transcribe, validate_recording, voice_ssl_context


class VoiceServiceTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(api_key="test-only-key")

    def test_voice_tls_has_trusted_roots_and_verifies_certificates(self):
        context = voice_ssl_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreater(context.cert_store_stats()["x509_ca"], 0)

    def test_recording_validation_rejects_silence_and_malformed_audio(self):
        for audio in (b"not a wav", pcm_to_wav(b""), pcm_to_wav(b"\x00\x00" * 2400)):
            with self.subTest(size=len(audio)), self.assertRaises(ValueError):
                validate_recording(audio)

    def test_transcript_is_trimmed_and_empty_transcript_rejected(self):
        client = MagicMock()
        client.audio.transcriptions.create.return_value = SimpleNamespace(text="  Hello  ")
        recording = pcm_to_wav(b"\x10\x00" * 2400)
        self.assertEqual(transcribe(client, self.settings, recording), "Hello")
        client.audio.transcriptions.create.return_value = SimpleNamespace(text="  ")
        with self.assertRaises(ValueError):
            transcribe(client, self.settings, recording)

    def test_context_is_bounded_and_never_sends_audio(self):
        client = MagicMock()
        client.responses.create.return_value = SimpleNamespace(output_text="A reply")
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": str(i), "audio": b"secret"}
            for i in range(30)
        ]
        self.assertEqual(answer(client, self.settings, history, "Next?").text, "A reply")
        sent = client.responses.create.call_args.kwargs
        self.assertEqual(len(sent["input"]), 21)
        self.assertEqual(sent["input"][0]["content"], "10")
        self.assertFalse(sent["store"])
        self.assertEqual(sent["tools"], [{"type": "web_search"}])
        self.assertEqual(sent["tool_choice"], "auto")
        self.assertTrue(all("audio" not in item for item in sent["input"]))

    def test_web_citations_are_clickable_but_not_spoken(self):
        marker = "citeturn0search0"
        text = "The answer is 42. " + marker
        citation = SimpleNamespace(type="url_citation", start_index=18,
                                   end_index=len(text), url="https://example.org/facts")
        result = SimpleNamespace(output_text=text, output=[
            SimpleNamespace(type="web_search_call"),
            SimpleNamespace(type="message", content=[
                SimpleNamespace(type="output_text", text=text, annotations=[citation])])])
        reply = format_answer(result)
        self.assertTrue(reply.searched)
        self.assertEqual(reply.text, "The answer is 42.")
        self.assertEqual(reply.markdown, "The answer is 42. [Source](https://example.org/facts)")

    def test_plain_answer_does_not_claim_a_search(self):
        reply = format_answer(SimpleNamespace(output_text="Hello", output=[]))
        self.assertEqual(reply.text, "Hello")
        self.assertFalse(reply.searched)

    @patch("voice_service.websocket.create_connection")
    def test_speech_assembles_audio_and_closes_socket(self, connect):
        socket = connect.return_value
        pcm = b"\x10\x00" * 240
        socket.recv.side_effect = [
            json.dumps({"type": "session.updated"}),
            json.dumps({"type": "response.output_audio.delta", "delta": base64.b64encode(pcm).decode()}),
            json.dumps({"type": "response.done", "response": {"status": "completed"}}),
        ]
        result = speak(self.settings, "Hello")
        context = connect.call_args.kwargs["sslopt"]["context"]
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        with wave.open(io.BytesIO(result), "rb") as wav:
            self.assertEqual(wav.getframerate(), 24000)
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.readframes(240), pcm)
        socket.close.assert_called_once()

    @patch("voice_service.websocket.create_connection")
    def test_speech_failures_close_socket_and_hide_raw_error(self, connect):
        for event in [
            {"type": "error", "error": {"message": "sensitive data"}},
            {"type": "response.done", "response": {"status": "failed"}},
            {"type": "response.done", "response": {"status": "completed"}},
        ]:
            with self.subTest(event=event):
                socket = connect.return_value
                socket.reset_mock()
                socket.recv.return_value = json.dumps(event)
                with self.assertRaises(RuntimeError) as raised:
                    speak(self.settings, "Hello")
                self.assertNotIn("sensitive data", str(raised.exception))
                socket.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
