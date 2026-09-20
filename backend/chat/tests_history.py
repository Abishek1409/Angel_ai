import json
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from documents.models import Document
from .models import ChatMessage, ChatSession


class AuthenticatedHistoryTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="history-user", password="strong-password")
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.document = Document.objects.create(
            user=self.user,
            session_id=uuid.uuid4(),
            filename="guide.txt",
            file_path="/tmp/guide.txt",
            status="ready",
        )

    def test_session_endpoints_are_user_scoped(self):
        session = ChatSession.objects.create(user=self.user, document=self.document, title="First question")
        ChatMessage.objects.create(session=session, role="user", content="What is page one?")
        ChatMessage.objects.create(session=session, role="assistant", content="Page one explains the setup.")

        response = self.client.get("/api/sessions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sessions"][0]["id"], str(session.id))

        response = self.client.get(f"/api/sessions/{session.id}/messages/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["role"] for item in response.json()["messages"]], ["user", "assistant"])

    @patch("chat.views.retrieve_chunks", return_value=([], [], [], False))
    @patch("chat.views.generate_answer", return_value=("Remembered answer", [], [], False))
    def test_query_persists_both_roles(self, generate_answer, retrieve_chunks):
        session_id = str(uuid.uuid4())
        response = self.client.post(
            "/api/chat/query/",
            data=json.dumps({
                "document_id": str(self.document.id),
                "session_id": session_id,
                "question": "What is page one?",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(ChatMessage.objects.values_list("role", "content")),
            [("user", "What is page one?"), ("assistant", "Remembered answer")],
        )

    @patch("chat.views.retrieve_chunks", return_value=([], [], [], False))
    @patch("chat.views.generate_answer", return_value=("Follow-up answer", [], [], False))
    def test_query_passes_previous_messages_to_answer_generator(self, generate_answer, retrieve_chunks):
        session = ChatSession.objects.create(user=self.user, document=self.document, title="Memory")
        ChatMessage.objects.create(session=session, role="user", content="Explain page one")
        ChatMessage.objects.create(session=session, role="assistant", content="It covers the setup")

        response = self.client.post(
            "/api/chat/query/",
            data=json.dumps({
                "document_id": str(self.document.id),
                "session_id": str(session.id),
                "question": "What about page three?",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        history = generate_answer.call_args.kwargs["conversation_history"]
        self.assertIn("User: Explain page one", history)
        self.assertIn("Assistant: It covers the setup", history)

    @patch("chat.views.retrieve_chunks", return_value=([], [], [], False))
    @patch("chat.views.generate_answer", return_value=("Persistent answer", [], [], False))
    @patch("documents.views.process_document")
    def test_full_auth_upload_query_logout_login_flow(self, process_document, generate_answer, retrieve_chunks):
        username = "flow-user"
        password = "strong-password"
        register = self.client.post("/api/auth/register/", {"username": username, "password": password}, format="json")
        self.assertEqual(register.status_code, 201)

        login = self.client.post("/api/auth/login/", {"username": username, "password": password}, format="json")
        self.assertEqual(login.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")

        upload = self.client.post(
            "/api/documents/upload/",
            {"session_id": str(uuid.uuid4()), "file": SimpleUploadedFile("flow.txt", b"AngelAI flow")},
            format="multipart",
        )
        self.assertEqual(upload.status_code, 200)
        document = Document.objects.get(id=upload.json()["document_id"])
        self.assertEqual(document.user.username, username)
        document.status = "ready"
        document.save(update_fields=["status"])

        session_id = str(uuid.uuid4())
        query = self.client.post(
            "/api/chat/query/",
            {"document_id": str(document.id), "session_id": session_id, "question": "What is this?"},
            format="json",
        )
        self.assertEqual(query.status_code, 200)

        logout = self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(logout.status_code, 200)
        relogin = self.client.post("/api/auth/login/", {"username": username, "password": password}, format="json")
        self.assertEqual(relogin.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {relogin.json()['access']}")

        sessions = self.client.get("/api/sessions/")
        self.assertEqual(sessions.status_code, 200)
        self.assertEqual(len(sessions.json()["sessions"]), 1)
        messages = self.client.get(f"/api/sessions/{session_id}/messages/")
        self.assertEqual(messages.status_code, 200)
        self.assertEqual(len(messages.json()["messages"]), 2)