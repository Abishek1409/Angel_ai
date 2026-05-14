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
    except Document.DoesNotExist:
        return JsonResponse({"error": f"Document {document_id} not found in database."}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"Database error: {e}"}, status=500)

    if doc.status != "ready":
        return JsonResponse({"error": f"Document status is '{doc.status}'. Error: {doc.error_message}"}, status=404)

    try:
        chunks = retrieve_chunks(document_id, question)
        answer = generate_answer(question, chunks)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=502)

    return JsonResponse({"answer": answer, "sources": chunks})
