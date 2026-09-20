import io
import json
import uuid
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from documents.models import Document
from chat.services import retrieve_chunks, generate_answer


def authenticate_client(client, username):
    user = get_user_model().objects.create_user(username=username, password="test-password")
    access_token = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return user


class UploadDocumentViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, "chat-upload-user")
        self.session_id = str(uuid.uuid4())
        self.upload_url = "/api/documents/upload/"

    def _make_file(self, name, content=b"hello", size=None):
        data = content
        if size:
            data = b"x" * size
        return io.BytesIO(data), name

    def test_unsupported_format_rejected(self):
        buf = io.BytesIO(b"data")
        buf.name = "file.exe"
        response = self.client.post(
            self.upload_url,
            {"file": buf, "session_id": self.session_id},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file type", response.json()["error"])

    def test_file_exceeding_size_limit_rejected(self):
        large_data = b"x" * (20 * 1024 * 1024 + 1)
        buf = io.BytesIO(large_data)
        buf.name = "big.pdf"
        response = self.client.post(
            self.upload_url,
            {"file": buf, "session_id": self.session_id},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("20 MB", response.json()["error"])

    def test_successful_txt_upload_returns_document_id(self):
        buf = io.BytesIO(b"Some text content")
        buf.name = "sample.txt"
        response = self.client.post(
            self.upload_url,
            {"file": buf, "session_id": self.session_id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("document_id", data)
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["filename"], "sample.txt")

    def test_successful_pdf_upload_returns_document_id(self):
        buf = io.BytesIO(b"%PDF-1.4 fake pdf content")
        buf.name = "report.pdf"
        response = self.client.post(
            self.upload_url,
            {"file": buf, "session_id": self.session_id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("document_id", data)
        self.assertEqual(data["status"], "pending")


class DocumentStatusViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, "chat-status-user")
        self.doc = Document.objects.create(
            user=self.user,
            session_id=uuid.uuid4(),
            filename="test.txt",
            file_path="/tmp/test.txt",
            status="pending",
        )

    def test_status_returns_correct_status(self):
        response = self.client.get(f"/api/documents/{self.doc.id}/status/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending")

    def test_status_returns_404_for_unknown_id(self):
        response = self.client.get(f"/api/documents/{uuid.uuid4()}/status/")
        self.assertEqual(response.status_code, 404)

    def test_status_reflects_ready_state(self):
        self.doc.status = "ready"
        self.doc.save()
        response = self.client.get(f"/api/documents/{self.doc.id}/status/")
        self.assertEqual(response.json()["status"], "ready")


class ChunkTextTests(TestCase):
    def test_empty_text_returns_empty_list(self):
        from documents.services import chunk_text
        self.assertEqual(chunk_text(""), [])

    def test_short_text_returns_single_chunk(self):
        from documents.services import chunk_text
        text = "Hello world"
        chunks = chunk_text(text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)

    def test_chunk_count_for_known_length(self):
        from documents.services import chunk_text
        text = "a" * 5400
        chunks = chunk_text(text)
        self.assertEqual(len(chunks), 3)

    def test_overlap_between_consecutive_chunks(self):
        from documents.services import chunk_text
        text = "".join(chr(ord("a") + (i % 26)) for i in range(5400))
        chunks = chunk_text(text)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0][-200:], chunks[1][:200])


class ExtractTextTests(TestCase):
    def test_extract_txt_file(self):
        from documents.services import extract_text
        import tempfile
        content = "This is a test document."
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            result = extract_text(path, "test.txt")
            self.assertEqual(result, content)
        finally:
            import os
            os.unlink(path)

    def test_unsupported_extension_raises_value_error(self):
        from documents.services import extract_text
        with self.assertRaises(ValueError):
            extract_text("/tmp/file.docx", "file.docx")

    def test_missing_txt_file_raises_runtime_error(self):
        from documents.services import extract_text
        with self.assertRaises(RuntimeError):
            extract_text("/nonexistent/path/file.txt", "file.txt")


class RetrieveChunksTests(TestCase):
    def test_returns_empty_on_missing_collection(self):
        from chromadb import PersistentClient
        with patch("chat.services._get_chroma_client") as mock_get:
            mock_client = MagicMock()
            mock_client.get_collection.side_effect = Exception("Collection not found")
            mock_get.return_value = mock_client

            result = retrieve_chunks("any question")
            self.assertEqual(result, ([], [], [], False))

    @patch("chat.services.get_cached_embedding", return_value=None)
    @patch("chat.services.cache_embedding")
    @patch("chat.services._embed_text", return_value=[0.1, 0.2, 0.3])
    @patch("chat.services._get_chroma_client")
    def test_queries_chromadb_with_embedding(self, mock_get_chroma, mock_embed, mock_cache, mock_get_cache):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 5
        mock_collection.query.return_value = {
            "documents": [["chunk1", "chunk2"]],
            "metadatas": [[{"source": "a.pdf", "doc_id": "uuid1", "chunk_index": 0}]],
            "ids": [["uuid1_chunk_0", "uuid1_chunk_1"]],
        }
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_get_chroma.return_value = mock_client

        chunks, metadatas, ids, cache_hit = retrieve_chunks("what is this?")
        self.assertEqual(chunks, ["chunk1", "chunk2"])
        self.assertEqual(metadatas[0]["source"], "a.pdf")
        self.assertFalse(cache_hit)
        mock_collection.query.assert_called_once()

    @patch("chat.services.get_cached_embedding", return_value=[0.1, 0.2, 0.3])
    def test_uses_cached_embedding(self, mock_get_cache):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 5
        mock_collection.query.return_value = {
            "documents": [["chunk1"]],
            "metadatas": [[{"source": "a.pdf"}]],
            "ids": [["uuid1_chunk_0"]],
        }
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection

        with patch("chat.services._get_chroma_client", return_value=mock_client):
            chunks, metadatas, ids, cache_hit = retrieve_chunks("cached question")
            self.assertTrue(cache_hit)
            self.assertEqual(chunks, ["chunk1"])


class GenerateAnswerTests(TestCase):
    def test_empty_chunks_returns_informational_message(self):
        answer, sources, citations, cache_hit = generate_answer("Any question?", [], [], [])
        self.assertIn("No relevant information found", answer)
        self.assertEqual(sources, [])
        self.assertEqual(citations, [])
        self.assertFalse(cache_hit)

    @patch("chat.services.cache_response")
    @patch("chat.services.get_cached_response", return_value=None)
    @patch("chat.services._generate_gemini_answer", return_value="Generated answer.")
    def test_chunks_provided_calls_gemini_and_returns_text(self, mock_generate, mock_get_cached, mock_cache):

        answer, sources, citations, cache_hit = generate_answer(
            "What is X?",
            ["Context about X."],
            [{"source": "doc.pdf", "doc_id": "uuid1", "chunk_index": 0}],
            ["uuid1_chunk_0"],
        )
        self.assertEqual(answer, "Generated answer.")
        self.assertEqual(sources, ["doc.pdf"])
        self.assertEqual(citations[0]["source"], "doc.pdf")
        self.assertFalse(cache_hit)
        mock_generate.assert_called_once()


class QueryViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, "chat-query-user")
        self.url = "/api/chat/query/"
        self.session_id = str(uuid.uuid4())
        self.doc = Document.objects.create(
            user=self.user,
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

    @patch("chat.views.generate_answer", return_value=("The answer is 42.", ["doc.pdf"], [], False))
    @patch("chat.views.retrieve_chunks", return_value=(["chunk one", "chunk two"], [{"source": "doc.pdf"}], ["uuid1_chunk_0"], False))
    def test_successful_query_returns_answer_and_sources(self, mock_retrieve, mock_generate):
        response = self._post({
            "document_id": str(self.doc.id),
            "session_id": self.session_id,
            "question": "What is the answer?",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answer"], "The answer is 42.")
        self.assertEqual(data["sources"], ["doc.pdf"])
        self.assertIn("citations", data)
        self.assertIn("cached", data)
        self.assertIn("cache_details", data)

    @patch("chat.views.generate_answer", return_value=("No relevant info found.", [], [], False))
    @patch("chat.views.retrieve_chunks", return_value=([], [], [], False))
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

    @patch("chat.views.generate_answer", return_value=("Multi answer.", ["doc.pdf"], [], False))
    @patch("chat.views.retrieve_chunks", return_value=([], [], [], False))
    def test_cross_document_query_without_document_id(self, mock_retrieve, mock_generate):
        response = self._post({
            "session_id": self.session_id,
            "question": "What is this?",
        })
        self.assertEqual(response.status_code, 200)

    @patch("chat.views.generate_answer", return_value=("Multi answer.", ["a.pdf", "b.pdf"], [], False))
    @patch("chat.views.retrieve_chunks", return_value=(["c1"], [{"source": "a.pdf"}], ["uuid1_chunk_0"], False))
    def test_multi_doc_response_includes_citations(self, mock_retrieve, mock_generate):
        response = self._post({
            "session_id": self.session_id,
            "question": "Summarize everything",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answer"], "Multi answer.")
        self.assertIn("citations", data)


class HealthEndpointTests(TestCase):
    def test_health_returns_200(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")


class DocumentDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, "chat-delete-user")
        self.session_id = str(uuid.uuid4())
        self.doc = Document.objects.create(
            user=self.user,
            session_id=self.session_id,
            filename="todelete.pdf",
            file_path="/tmp/todelete.pdf",
            status="ready",
        )

    def test_delete_document(self):
        response = self.client.delete(f"/api/documents/{self.doc.id}/delete/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Document.objects.filter(id=self.doc.id).exists())

    def test_delete_unknown_returns_404(self):
        response = self.client.delete(f"/api/documents/{uuid.uuid4()}/delete/")
        self.assertEqual(response.status_code, 404)


class ListDocumentsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, "chat-list-user")
        self.session_id = str(uuid.uuid4())
        Document.objects.create(
            user=self.user,
            session_id=self.session_id,
            filename="a.pdf",
            file_path="/tmp/a.pdf",
            status="ready",
        )
        Document.objects.create(
            user=self.user,
            session_id=uuid.uuid4(),
            filename="other.pdf",
            file_path="/tmp/other.pdf",
            status="ready",
        )

    def test_list_documents_for_session(self):
        response = self.client.get("/api/documents/list/", {"session_id": self.session_id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["documents"]), 1)
        self.assertEqual(data["documents"][0]["filename"], "a.pdf")

    def test_list_requires_session_id(self):
        response = self.client.get("/api/documents/list/")
        self.assertEqual(response.status_code, 400)
