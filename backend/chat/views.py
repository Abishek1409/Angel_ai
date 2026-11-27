import json
import os
import uuid
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from documents.models import Document
from documents.services import delete_document_from_chromadb
from .models import ChatMessage, ChatSession
from .services import retrieve_chunks, generate_answer
from .steering import build_steered_prompt, normalize_steering, repair_mojibake, stream_llm


def _message_list(session):
    messages = list(session.messages.values("id", "role", "content", "created_at"))
    for message in messages:
        message["content"] = repair_mojibake(message["content"])
    return messages


class ChatRequestError(Exception):
    def __init__(self, response):
        self.response = response


def _prepare_chat(request, body):
    """
    Validate a chat request and load its session and recent history.
    Returns (session, document_id, question, conversation_history).
    Raises ChatRequestError carrying the error response.
    """
    document_id = body.get("document_id")  # Optional
    session_id = body.get("session_id")
    question = body.get("question")

    if not session_id or not question:
        raise ChatRequestError(JsonResponse(
            {"error": "session_id and question are required."},
            status=400,
        ))

    doc = None
    if document_id:
        try:
            doc = Document.objects.get(id=document_id, user=request.user)
        except Document.DoesNotExist:
            raise ChatRequestError(JsonResponse({"error": f"Document {document_id} not found in database."}, status=404))
        except Exception as e:
            raise ChatRequestError(JsonResponse({"error": f"Database error: {e}"}, status=500))

        if doc.status != "ready":
            raise ChatRequestError(JsonResponse({"error": f"Document status is '{doc.status}'. Error: {doc.error_message}"}, status=404))

    try:
        session_uuid = uuid.UUID(str(session_id))
    except ValueError:
        raise ChatRequestError(JsonResponse({"error": "Invalid session_id."}, status=400))

    session = ChatSession.objects.filter(id=session_uuid, user=request.user).first()
    if session is None:
        if ChatSession.objects.filter(id=session_uuid).exists():
            raise ChatRequestError(JsonResponse({"error": "Session does not belong to this user."}, status=403))
        session = ChatSession.objects.create(
            id=session_uuid,
            user=request.user,
            document=doc,
            title=question[:255],
        )
    elif doc is not None and session.document_id != doc.id:
        raise ChatRequestError(JsonResponse({"error": "Session does not belong to this document."}, status=400))

    previous_messages = list(
        session.messages.order_by("-created_at").values("role", "content")[:10]
    )
    previous_messages.reverse()
    history_lines = []
    history_length = 0
    for message in reversed(previous_messages):
        line = f"{message['role'].capitalize()}: {repair_mojibake(message['content'])}\n"
        if history_length + len(line) > 8000:
            break
        history_lines.insert(0, line)
        history_length += len(line)
    conversation_history = "Previous conversation:\n" + "".join(history_lines) + "\n" if history_lines else ""

    return session, document_id, question, conversation_history


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def query(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    try:
        session, document_id, question, conversation_history = _prepare_chat(request, body)
    except ChatRequestError as e:
        return e.response

    try:
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def stream_query(request):
    """
    Stream a steerable answer as plain text.

    Body: session_id, question, optional document_id, steering ({axis: 0-100}) and
    partial_answer (text already shown; the model continues it under the new steering).
    The client aborts and calls again with partial_answer whenever a dial moves. Only a
    segment that runs to completion saves the exchange, so aborted segments save nothing.
    The X-Sources response header carries the source filenames as JSON.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    try:
        session, document_id, question, conversation_history = _prepare_chat(request, body)
    except ChatRequestError as e:
        return e.response

    partial_answer = body.get("partial_answer") or ""
    if not isinstance(partial_answer, str):
        partial_answer = ""
    partial_answer = partial_answer[:12000]
    steering = normalize_steering(body.get("steering"))

    try:
        chunks, metadatas, _chunk_ids, _cached = retrieve_chunks(question, document_id=document_id)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=502)

    sources = list(dict.fromkeys(meta.get("source", "Unknown") for meta in metadatas))

    if not chunks:
        tokens = iter([
            "No relevant information found in your documents. "
            "Please try rephrasing your question or upload relevant documents."
        ])
    else:
        prompt = build_steered_prompt(
            question,
            "\n\n---\n\n".join(chunks),
            conversation_history,
            steering,
            partial_answer=partial_answer,
        )
        try:
            tokens = stream_llm(prompt)
        except RuntimeError as e:
            return JsonResponse({"error": str(e)}, status=502)

    def body_stream():
        produced = []
        for token in tokens:
            produced.append(token)
            yield token
        # Reached only when the segment finishes; an aborted request closes the
        # generator early and nothing is saved.
        full_answer = (partial_answer + "".join(produced)).strip()
        ChatMessage.objects.bulk_create([
            ChatMessage(session=session, role="user", content=question),
            ChatMessage(session=session, role="assistant", content=full_answer),
        ])

    response = StreamingHttpResponse(body_stream(), content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    response["X-Sources"] = json.dumps(sources, ensure_ascii=True)
    response["Access-Control-Expose-Headers"] = "X-Sources"
    return response


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

    return JsonResponse({"messages": _message_list(session)}, json_dumps_params={"default": str})


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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_session(request, document_id):
    try:
        document = Document.objects.get(id=document_id, user=request.user)
    except Document.DoesNotExist:
        return JsonResponse({"error": "Document not found or access denied."}, status=404)

    session = ChatSession.objects.filter(
        user=request.user,
        document=document,
    ).order_by("-created_at").first()

    if session is None:
        session = ChatSession.objects.create(
            user=request.user,
            document=document,
            title=document.filename,
        )

    return JsonResponse({
        "id": str(session.id),
        "title": session.title,
        "document_id": str(document.id),
        "created_at": session.created_at,
    }, json_dumps_params={"default": str})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def session_messages(request, session_id):
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({"error": "Session not found."}, status=404)

    return JsonResponse({
        "messages": _message_list(session),
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
