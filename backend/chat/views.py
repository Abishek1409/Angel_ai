import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from documents.models import Document
from .services import retrieve_chunks, generate_answer


@csrf_exempt
@require_http_methods(["POST"])
def query(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    document_id = body.get("document_id")
    session_id = body.get("session_id")
    question = body.get("question")

    if not document_id or not session_id or not question:
        return JsonResponse(
            {"error": "document_id, session_id, and question are required."},
            status=400,
        )

    try:
        doc = Document.objects.get(id=document_id)
    except (Document.DoesNotExist, Exception):
        return JsonResponse({"error": "Document not found or not ready."}, status=404)

    if doc.status != "ready":
        return JsonResponse({"error": "Document not found or not ready."}, status=404)

    try:
        chunks = retrieve_chunks(document_id, question)
        answer = generate_answer(question, chunks)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=502)

    return JsonResponse({"answer": answer, "sources": chunks})
