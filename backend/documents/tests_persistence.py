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


class ChildProcessMemoryTests(TestCase):
    """Heavy models run in child processes so the web worker's memory stays flat."""

    def test_offline_embedding_runs_in_child_process(self):
        with patch.object(services, "_run_child", return_value=[[0.1, 0.2], [0.3, 0.4]]) as mock_child:
            vectors = services._onnx_embed(["a", "b"])
        self.assertEqual(vectors, [[0.1, 0.2], [0.3, 0.4]])
        self.assertEqual(mock_child.call_args.args[0], "embed_worker.py")

    def test_offline_embedding_rejects_wrong_vector_count(self):
        with patch.object(services, "_run_child", return_value=[[0.1]]):
            with self.assertRaises(RuntimeError):
                services._onnx_embed(["a", "b"])

    def test_embed_worker_returns_vectors(self):
        import os
        import subprocess
        import sys

        model_dir = os.path.join(os.path.expanduser("~"), ".cache", "chroma", "onnx_models", "all-MiniLM-L6-v2")
        if not os.path.isdir(model_dir):
            self.skipTest("offline embedding model not downloaded on this machine")
        worker = os.path.join(os.path.dirname(services.__file__), "embed_worker.py")
        out = subprocess.run([sys.executable, worker], input='["hello world", "cells"]',
                             capture_output=True, text=True, encoding="utf-8", timeout=300).stdout
        line = [l for l in out.splitlines() if l.startswith("__EMBED_RESULT__")][-1]
        import json
        vectors = json.loads(line[len("__EMBED_RESULT__"):])
        self.assertEqual(len(vectors), 2)
        self.assertEqual(len(vectors[0]), 384)


class RetrievalSkipsUnusedCollectionsTests(TestCase):
    def test_collection_without_the_document_is_not_queried(self):
        from unittest.mock import MagicMock
        from chat import services as chat_services

        gemini, local = MagicMock(), MagicMock()
        gemini.count.return_value = 5
        gemini.get.return_value = {"ids": ["doc_chunk_0"]}
        gemini.query.return_value = {"documents": [["text"]], "metadatas": [[{"source": "a.pdf"}]], "ids": [["doc_chunk_0"]]}
        local.count.return_value = 5
        local.get.return_value = {"ids": []}  # this document isn't in the local collection
        client = MagicMock()
        client.get_collection.side_effect = lambda name: gemini if name == chat_services.GEMINI_COLLECTION else local

        with patch.object(chat_services, "_get_chroma_client", return_value=client), \
             patch.object(chat_services, "get_cached_embedding", return_value=[0.1, 0.2]), \
             patch.object(chat_services, "_local_embed") as local_embed:
            chunks, _, _, _ = chat_services.retrieve_chunks("q", document_id="doc")

        self.assertEqual(chunks, ["text"])
        local_embed.assert_not_called()
        local.query.assert_not_called()
