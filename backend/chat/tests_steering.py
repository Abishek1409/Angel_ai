import json
import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from chat.models import ChatMessage
from chat.steering import build_steered_prompt, normalize_steering, steering_instructions
from chat.tests import authenticate_client


class SteeringPromptTests(TestCase):
    def test_normalize_clamps_and_defaults(self):
        steering = normalize_steering({"depth": 150, "tone": "bad", "level": -4, "unknown": 9})
        self.assertEqual(steering["depth"], 100)
        self.assertEqual(steering["level"], 0)
        self.assertEqual(steering["tone"], 50)
        self.assertNotIn("unknown", steering)

    def test_neutral_dials_add_no_instructions(self):
        self.assertEqual(steering_instructions(normalize_steering({})), "")

    def test_extreme_dials_pick_their_pole(self):
        text = steering_instructions(normalize_steering({"depth": 0, "level": 100}))
        self.assertIn("Strongly: Be very brief", text)
        self.assertIn("Strongly: Write for an expert", text)

    def test_partial_answer_asks_for_continuation(self):
        prompt = build_steered_prompt("Q?", "ctx", "", normalize_steering({}), partial_answer="So far")
        self.assertIn("So far", prompt)
        self.assertIn("Continue the answer", prompt)


class TextCleanupTests(TestCase):
    def test_groq_stream_decodes_utf8_without_charset(self):
        from unittest.mock import MagicMock
        from chat.steering import _groq_stream

        delta = json.dumps({"choices": [{"delta": {"content": "cross‑platform ’s"}}]})
        fake = MagicMock(ok=True)
        fake.iter_lines.return_value = [f"data: {delta}".encode("utf-8"), b"", b"data: [DONE]"]
        with patch("chat.steering.requests.post", return_value=fake), \
             patch("chat.steering.settings") as mock_settings:
            mock_settings.GROQ_API_KEY = "k"
            mock_settings.GROQ_MODEL = "m"
            text = "".join(_groq_stream("prompt"))
        self.assertEqual(text, "cross-platform ’s")

    def test_repair_mojibake_fixes_latin1_decoded_text(self):
        from chat.steering import repair_mojibake

        garbled = "cross‑platform and learner’s".encode("utf-8").decode("latin-1")
        self.assertEqual(repair_mojibake(garbled), "cross-platform and learner’s")

    def test_repair_mojibake_leaves_normal_text_alone(self):
        from chat.steering import repair_mojibake

        for text in ["plain answer", "pâté recipe", "already fine ’ —"]:
            self.assertEqual(repair_mojibake(text), text)


class StreamQueryViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, "stream-user")
        self.url = "/api/chat/stream/"
        self.session_id = str(uuid.uuid4())

    def _post(self, **extra):
        body = {"session_id": self.session_id, "question": "What is X?", **extra}
        return self.client.post(self.url, json.dumps(body), content_type="application/json")

    def test_requires_question(self):
        response = self.client.post(
            self.url, json.dumps({"session_id": self.session_id}), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    @patch("chat.views.stream_llm")
    @patch("chat.views.retrieve_chunks")
    def test_streams_and_saves_full_answer(self, mock_retrieve, mock_stream):
        mock_retrieve.return_value = (["chunk"], [{"source": "a.pdf"}], ["id1"], False)
        mock_stream.return_value = iter(["and the", " rest."])

        response = self._post(partial_answer="Start ", steering={"depth": 90})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response["X-Sources"]), ["a.pdf"])
        text = b"".join(response.streaming_content).decode()
        self.assertEqual(text, "and the rest.")
        prompt = mock_stream.call_args[0][0]
        self.assertIn("Start", prompt)
        self.assertIn("Be thorough", prompt)
        saved = ChatMessage.objects.get(role="assistant")
        self.assertEqual(saved.content, "Start and the rest.")

    @patch("chat.views.stream_llm")
    @patch("chat.views.retrieve_chunks")
    def test_aborted_stream_saves_nothing(self, mock_retrieve, mock_stream):
        mock_retrieve.return_value = (["chunk"], [{"source": "a.pdf"}], ["id1"], False)
        mock_stream.return_value = iter(["one", " two"])

        response = self._post()
        stream = iter(response.streaming_content)
        next(stream)
        response.close()

        self.assertFalse(ChatMessage.objects.exists())

    @patch("chat.views.stream_llm", side_effect=RuntimeError("down"))
    @patch("chat.views.retrieve_chunks")
    def test_provider_failure_returns_502(self, mock_retrieve, _mock_stream):
        mock_retrieve.return_value = (["chunk"], [{"source": "a.pdf"}], ["id1"], False)
        self.assertEqual(self._post().status_code, 502)
