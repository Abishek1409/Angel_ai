import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from documents.models import Document
from .models import ChatMessage
from .services import retrieve_chunks, generate_answer


@csrf_exempt
@require_http_methods(["POST"])
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
            doc = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return JsonResponse({"error": f"Document {document_id} not found in database."}, status=404)
        except Exception as e:
            return JsonResponse({"error": f"Database error: {e}"}, status=500)

        if doc.status != "ready":
            return JsonResponse({"error": f"Document status is '{doc.status}'. Error: {doc.error_message}"}, status=404)

    try:
        chunks, metadatas, chunk_ids, embedding_cached = retrieve_chunks(question, document_id=document_id)
        answer, sources, citations, response_cached = generate_answer(question, chunks, metadatas, chunk_ids)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=502)

    # Persist to database
    ChatMessage.objects.create(
        document_id=document_id,
        session_id=session_id,
        question=question,
        answer=answer,
    )

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


@csrf_exempt
@require_http_methods(["GET"])
def history(request, document_id):
    session_id = request.GET.get("session_id")
    if not session_id:
        return JsonResponse({"error": "session_id is required."}, status=400)

    history_filter = {"document_id__isnull": True} if document_id == "multi" else {"document_id": document_id}
    messages = ChatMessage.objects.filter(
        session_id=session_id,
        **history_filter,
    ).values("id", "question", "answer", "created_at")

    return JsonResponse({"messages": list(messages)}, json_dumps_params={"default": str})
