import json
import os
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from documents.models import Document
from documents.services import delete_document_from_chromadb
from .models import ChatMessage, ChatSession
from .services import retrieve_chunks, generate_answer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def query(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    document_id = body.get("document_id")  # Now optional
    session_id = body.get("session_id")
    question = body.get("question")

    if not session_id or not question:
        return JsonResponse(
            {"error": "session_id and question are required."},
            status=400,
        )

    # If document_id is provided, verify it exists and is ready
    if document_id:
        try:
            doc = Document.objects.get(id=document_id, user=request.user)
        except Document.DoesNotExist:
            return JsonResponse({"error": f"Document {document_id} not found in database."}, status=404)
        except Exception as e:
            return JsonResponse({"error": f"Database error: {e}"}, status=500)

        if doc.status != "ready":
            return JsonResponse({"error": f"Document status is '{doc.status}'. Error: {doc.error_message}"}, status=404)

    try:
        session_uuid = uuid.UUID(str(session_id))
        session = ChatSession.objects.filter(id=session_uuid, user=request.user).first()
        if session is None:
            if ChatSession.objects.filter(id=session_uuid).exists():
                return JsonResponse({"error": "Session does not belong to this user."}, status=403)
            session = ChatSession.objects.create(
                id=session_uuid,
                user=request.user,
                document=doc if document_id else None,
                title=question[:255],
            )
            created = True
        else:
            created = False
        if not created and document_id and session.document_id != doc.id:
            return JsonResponse({"error": "Session does not belong to this document."}, status=400)

        previous_messages = list(
            session.messages.order_by("-created_at").values("role", "content")[:10]
        )
        previous_messages.reverse()
        history_lines = []
        history_length = 0
        for message in reversed(previous_messages):
            line = f"{message['role'].capitalize()}: {message['content']}\n"
            if history_length + len(line) > 8000:
                break
            history_lines.insert(0, line)
            history_length += len(line)
        conversation_history = "Previous conversation:\n" + "".join(history_lines) + "\n" if history_lines else ""

        chunks, metadatas, chunk_ids, embedding_cached = retrieve_chunks(question, document_id=document_id)
        answer, sources, citations, response_cached = generate_answer(
            question,
            chunks,
            metadatas,
            chunk_ids,
            conversation_history=conversation_history,
            cache_scope=f"user:{request.user.id}:session:{session.id}:" ,
        )
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=502)

    # Persist to database
    ChatMessage.objects.bulk_create([
        ChatMessage(session=session, role="user", content=question),
        ChatMessage(session=session, role="assistant", content=answer),
    ])

    return JsonResponse({
        "answer": answer,
        "sources": sources,
        "citations": citations,
        "cached": response_cached or embedding_cached,
        "cache_details": {
            "embedding_cached": embedding_cached,
            "response_cached": response_cached,
        },
        "chunks": chunks,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def history(request, document_id):
    session_id = request.GET.get("session_id")
    if not session_id:
        return JsonResponse({"error": "session_id is required."}, status=400)

    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except (ChatSession.DoesNotExist, ValueError):
        return JsonResponse({"messages": []})

    messages = session.messages.values("id", "role", "content", "created_at")

    return JsonResponse({"messages": list(messages)}, json_dumps_params={"default": str})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_sessions(request):
    sessions = ChatSession.objects.filter(user=request.user).select_related("document")
    return JsonResponse({
        "sessions": [
            {
                "id": str(session.id),
                "title": session.title or (session.document.filename if session.document else "New conversation"),
                "document_id": str(session.document_id) if session.document_id else None,
                "created_at": session.created_at,
            }
            for session in sessions
        ],
        }, json_dumps_params={"default": str})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def session_messages(request, session_id):
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({"error": "Session not found."}, status=404)

    return JsonResponse({
        "messages": list(session.messages.values("id", "role", "content", "created_at")),
    }, json_dumps_params={"default": str})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_session(request, session_id):
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({"error": "Session not found."}, status=404)

    document = session.document
    if document is not None:
        try:
            delete_document_from_chromadb(str(document.id))
            if document.file_path and os.path.exists(document.file_path):
                os.remove(document.file_path)
        except Exception:
            pass
        document.delete()

    session.delete()
    return JsonResponse({"message": "Session deleted."})
