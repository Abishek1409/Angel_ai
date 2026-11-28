import io
import os
import sys
import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch
import fitz
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Document
from .services import chunk_text, extract_text


def authenticate_client(client, username):
    user = get_user_model().objects.create_user(username=username, password="test-password")
    access_token = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return user


class UploadDocumentViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = authenticate_client(self.client, "documents-upload-user")
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
        self.user = authenticate_client(self.client, "documents-status-user")
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

    def _pdf(self, *page_texts):
        """PDF with one page per entry; an empty string makes an image-only (scanned-like) page."""
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        pdf = fitz.open()
        for text in page_texts:
            page = pdf.new_page()
            if text:
                page.insert_text((60, 90), text, fontsize=14)
        pdf.save(path)
        pdf.close()
        self.addCleanup(os.unlink, path)
        return path

    def test_scanned_pdf_falls_back_to_ocr(self):
        path = self._pdf("")
        status_callback = Mock()
        with patch("documents.services._ocr_pages", return_value={0: "Scanned document text"}) as mock_ocr:
            result = extract_text(path, "scanned.pdf", status_callback=status_callback)
        self.assertEqual(result, "Scanned document text")
        mock_ocr.assert_called_once_with(path, [0])
        status_callback.assert_called_once()

    def test_only_pages_without_text_are_ocred(self):
        path = self._pdf("This page already has a real text layer.", "")
        with patch("documents.services._ocr_pages", return_value={1: "Scanned second page"}) as mock_ocr:
            result = extract_text(path, "mixed.pdf")
        mock_ocr.assert_called_once_with(path, [1])
        self.assertIn("real text layer", result)
        self.assertIn("Scanned second page", result)

    def test_text_pdf_never_starts_ocr(self):
        path = self._pdf("A normal digital PDF with plenty of text.")
        with patch("documents.services._ocr_pages") as mock_ocr:
            extract_text(path, "digital.pdf")
        mock_ocr.assert_not_called()

    def test_blank_scan_raises_runtime_error(self):
        path = self._pdf("")
        with patch("documents.services._ocr_pages", return_value={0: ""}):
            with self.assertRaises(RuntimeError):
                extract_text(path, "blank.pdf")

    def test_ocr_worker_failure_becomes_runtime_error(self):
        path = self._pdf("")
        failed = SimpleNamespace(returncode=1, stdout="", stderr="OCR failed: model missing")
        with patch("subprocess.run", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "model missing"):
                extract_text(path, "scanned.pdf")

    def test_ocr_worker_killed_for_memory_reports_it(self):
        path = self._pdf("")
        killed = SimpleNamespace(returncode=-9, stdout="", stderr="")
        with patch("subprocess.run", return_value=killed):
            with self.assertRaisesRegex(RuntimeError, "out of memory"):
                extract_text(path, "scanned.pdf")

    def test_worker_uses_tesseract_when_rapidocr_fails(self):
        from . import ocr_worker

        path = self._pdf("")
        with patch.object(ocr_worker, "_rapidocr", side_effect=RuntimeError("model error")),              patch.object(ocr_worker, "_tesseract", return_value="Text read by Tesseract OCR") as mock_tess,              fitz.open(path) as doc:
            self.assertEqual(ocr_worker.ocr_page(doc[0]), "Text read by Tesseract OCR")
        mock_tess.assert_called_once()

    def test_rapidocr_reads_real_scanned_page(self):
        try:
            import rapidocr  # noqa: F401
        except ImportError:
            self.skipTest("rapidocr not installed")
        # Rasterise a text page into an image-only PDF, as a scanner would produce
        source = fitz.open()
        page = source.new_page()
        page.insert_text((60, 90), "Photosynthesis converts light energy", fontsize=18)
        png = page.get_pixmap(dpi=150).tobytes("png")
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        self.addCleanup(os.unlink, path)
        scan = fitz.open()
        scan.new_page(width=page.rect.width, height=page.rect.height).insert_image(page.rect, stream=png)
        scan.save(path)
        scan.close()

        result = extract_text(path, "scan.pdf")

        self.assertIn("photosynthesis", result.lower())
        self.assertIn("light energy", result.lower())
