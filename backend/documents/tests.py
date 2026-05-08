import io
import os
import tempfile
import uuid
from django.test import TestCase, Client
from django.urls import reverse

from .models import Document
from .services import chunk_text, extract_text


class UploadDocumentViewTests(TestCase):
    def setUp(self):
        self.client = Client()
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
        self.client = Client()
        self.doc = Document.objects.create(
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
        self.assertEqual(chunk_text(""), [])

    def test_short_text_returns_single_chunk(self):
        text = "Hello world"
        chunks = chunk_text(text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)

    def test_chunk_count_for_known_length(self):
        # 2000-char chunk, 200-char overlap → step = 1800 chars
        # 5400 chars → ceil(5400 / 1800) = 3 chunks
        text = "a" * 5400
        chunks = chunk_text(text)
        self.assertEqual(len(chunks), 3)

    def test_overlap_between_consecutive_chunks(self):
        # Each chunk is 2000 chars, step is 1800, so last 200 chars of chunk N
        # should equal first 200 chars of chunk N+1
        text = "".join(chr(ord("a") + (i % 26)) for i in range(5400))
        chunks = chunk_text(text)
        self.assertGreater(len(chunks), 1)
        # tail of first chunk == head of second chunk
        self.assertEqual(chunks[0][-200:], chunks[1][:200])


class ExtractTextTests(TestCase):
    def test_extract_txt_file(self):
        content = "This is a test document."
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            result = extract_text(path, "test.txt")
            self.assertEqual(result, content)
        finally:
            os.unlink(path)

    def test_unsupported_extension_raises_value_error(self):
        with self.assertRaises(ValueError):
            extract_text("/tmp/file.docx", "file.docx")

    def test_missing_txt_file_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            extract_text("/nonexistent/path/file.txt", "file.txt")
