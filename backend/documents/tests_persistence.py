import shutil
import tempfile
import uuid
from datetime import timedelta
from unittest.mock import patch

import chromadb
from chromadb.config import Settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .models import Document, DocumentChunk


def _client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


class DocumentPersistenceTests(TestCase):
    """Chunks live in the database so a wiped ChromaDB disk can be rebuilt."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="persist-user", password="pw-12345678")
        self.chroma_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.chroma_dir, ignore_errors=True)
        self._patch_chroma(self.chroma_dir)
        services._indexed_documents.clear()
        self.doc = Document.objects.create(
            user=self.user, session_id=uuid.uuid4(), filename="notes.txt", file_path="", status="ready",
        )

    def _patch_chroma(self, path):
        client = chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))
        patcher = patch.object(services, "get_chroma_client", return_value=client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _store(self, chunks):
        vectors = [[float(i), 1.0, 0.5] for i in range(len(chunks))]
        with patch.object(services, "embed_chunks", return_value=(services.LOCAL_COLLECTION, vectors)):
            services.embed_and_store(str(self.doc.id), chunks, self.doc.filename, self.doc.created_at.isoformat())

    def test_embed_and_store_saves_chunks_to_database(self):
        self._store(["first chunk", "second chunk"])

        stored = list(DocumentChunk.objects.filter(document=self.doc))
        self.assertEqual([c.text for c in stored], ["first chunk", "second chunk"])
        self.assertEqual(services._unpack_embedding(stored[1].embedding), [1.0, 1.0, 0.5])
        self.assertEqual(services.get_document_text(str(self.doc.id)), "first chunk\n\nsecond chunk")

    def test_wiped_chroma_is_rebuilt_from_database(self):
        self._store(["alpha", "beta"])

        # Simulate a restart: fresh empty disk, fresh process cache
        services._indexed_documents.clear()
        self._patch_chroma(tempfile.mkdtemp(dir=self.chroma_dir))
        self.assertFalse(services._chroma_has_document(str(self.doc.id)))

        services.ensure_documents_indexed([self.doc])

        collection = services.get_chroma_client().get_collection(services.LOCAL_COLLECTION)
        result = collection.get(where={"doc_id": {"$eq": str(self.doc.id)}})
        self.assertEqual(sorted(result["documents"]), ["alpha", "beta"])

    def test_legacy_document_in_chroma_is_backfilled_to_database(self):
        services._upsert_chroma(
            services.LOCAL_COLLECTION, str(self.doc.id), ["old text"], [[0.1, 0.2, 0.3]],
            self.doc.filename, self.doc.created_at.isoformat(),
        )

        services.ensure_documents_indexed([self.doc])

        self.assertEqual(services.get_document_text(str(self.doc.id)), "old text")


class DocumentRetentionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="retention-user", password="pw-12345678")
        self.client = _client(self.user)
        services._last_purge = float("-inf")

    def _doc(self, **kwargs):
        return Document.objects.create(
            user=self.user, session_id=uuid.uuid4(), filename="a.txt", file_path="", status="ready", **kwargs,
        )

    def test_new_document_expires_after_two_days(self):
        doc = self._doc()
        self.assertAlmostEqual(
            (doc.expires_at - timezone.now()).total_seconds(), timedelta(hours=48).total_seconds(), delta=60,
        )

    @patch("documents.services.delete_document_from_chromadb")
    def test_expired_documents_are_hidden_and_purged(self, mock_chroma_delete):
        kept = self._doc()
        expired = self._doc(expires_at=timezone.now() - timedelta(minutes=1))

        response = self.client.get("/api/documents/list/")

        ids = [d["id"] for d in response.json()["documents"]]
        self.assertEqual(ids, [str(kept.id)])
        self.assertIn("expires_at", response.json()["documents"][0])
        self.assertFalse(Document.objects.filter(id=expired.id).exists())
        mock_chroma_delete.assert_called_once_with(str(expired.id))

    def test_expired_document_status_returns_404(self):
        expired = self._doc(expires_at=timezone.now() - timedelta(minutes=1))
        services._last_purge = 10**12  # skip the purge so the row still exists
        response = self.client.get(f"/api/documents/{expired.id}/status/")
        self.assertEqual(response.status_code, 404)


class GeneralChatScopeTests(TestCase):
    """A chat without a selected document only searches the user's own documents."""

    def setUp(self):
        User = get_user_model()
        self.me = User.objects.create_user(username="scope-me", password="pw-12345678")
        self.other = User.objects.create_user(username="scope-other", password="pw-12345678")
        self.mine = Document.objects.create(
            user=self.me, session_id=uuid.uuid4(), filename="mine.txt", file_path="", status="ready",
        )
        Document.objects.create(
            user=self.other, session_id=uuid.uuid4(), filename="theirs.txt", file_path="", status="ready",
        )

    @patch("chat.views.generate_answer", return_value=("ok", [], [], False))
    @patch("chat.views.ensure_documents_indexed")
    @patch("chat.views.retrieve_chunks", return_value=([], [], [], False))
    def test_general_chat_searches_only_own_documents(self, mock_retrieve, _indexed, _answer):
        response = _client(self.me).post(
            "/api/chat/query/", {"session_id": str(uuid.uuid4()), "question": "hi"}, format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_retrieve.call_args.kwargs["document_ids"], [str(self.mine.id)])

    def test_retrieve_chunks_with_no_own_documents_returns_nothing(self):
        from chat.services import retrieve_chunks

        with patch("chat.services._get_chroma_client") as mock_client:
            self.assertEqual(retrieve_chunks("q", document_ids=[]), ([], [], [], False))
            mock_client.assert_not_called()
