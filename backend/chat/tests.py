import json
import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client

from documents.models import Document


class QueryViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/api/chat/query/"
        self.session_id = str(uuid.uuid4())
        self.doc = Document.objects.create(
            session_id=self.session_id,
            filename="test.txt",
            file_path="/tmp/test.txt",
            status="ready",
        )

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_missing_fields_returns_400(self):
        response = self._post({"document_id": str(self.doc.id)})
        self.assertEqual(response.status_code, 400)
        self.assertIn("required", response.json()["error"])

    def test_unknown_document_returns_404(self):
        response = self._post({
            "document_id": str(uuid.uuid4()),
            "session_id": self.session_id,
            "question": "What is this?",
        })
        self.assertEqual(response.status_code, 404)

    def test_document_not_ready_returns_404(self):
        self.doc.status = "pending"
        self.doc.save()
        response = self._post({
            "document_id": str(self.doc.id),
            "session_id": self.session_id,
            "question": "What is this?",
        })
        self.assertEqual(response.status_code, 404)

    @patch("chat.views.generate_answer", return_value="The answer is 42.")
    @patch("chat.views.retrieve_chunks", return_value=["chunk one", "chunk two"])
    def test_successful_query_returns_answer_and_sources(self, mock_retrieve, mock_generate):
        response = self._post({
            "document_id": str(self.doc.id),
            "session_id": self.session_id,
            "question": "What is the answer?",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answer"], "The answer is 42.")
        self.assertEqual(data["sources"], ["chunk one", "chunk two"])

    @patch("chat.views.generate_answer", return_value="No relevant info found.")
    @patch("chat.views.retrieve_chunks", return_value=[])
    def test_empty_chunks_still_returns_answer(self, mock_retrieve, mock_generate):
        response = self._post({
            "document_id": str(self.doc.id),
            "session_id": self.session_id,
            "question": "Something unrelated?",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("answer", data)
        self.assertEqual(data["sources"], [])


class GenerateAnswerTests(TestCase):
    def test_empty_chunks_returns_informational_message(self):
        from chat.services import generate_answer
        result = generate_answer("Any question?", [])
        self.assertIn("does not appear to contain", result)

    @patch("chat.services.genai.GenerativeModel")
    def test_chunks_provided_calls_gemini_and_returns_text(self, mock_model_cls):
        from chat.services import generate_answer
        mock_response = MagicMock()
        mock_response.text = "Generated answer."
        mock_model_cls.return_value.generate_content.return_value = mock_response

        result = generate_answer("What is X?", ["Context about X."])
        self.assertEqual(result, "Generated answer.")
