import os
import uuid
import threading
import logging
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Document
from .services import process_document

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "txt"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@csrf_exempt
@require_http_methods(["POST"])
def upload_document(request):
    try:
        file = request.FILES.get("file")
        session_id = request.POST.get("session_id")

        if not file:
            return JsonResponse({"error": "No file provided."}, status=400)

        if not session_id:
            return JsonResponse({"error": "session_id is required."}, status=400)

        ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
        if ext not in ALLOWED_EXTENSIONS:
            return JsonResponse(
                {"error": f"Unsupported file type. Accepted: {', '.join(ALLOWED_EXTENSIONS)}"},
                status=400,
            )

        if file.size > MAX_FILE_SIZE:
            return JsonResponse(
                {"error": "File exceeds the 20 MB size limit."},
                status=400,
            )

        # Save file to MEDIA_ROOT
        media_root = settings.MEDIA_ROOT
        os.makedirs(media_root, exist_ok=True)
        unique_name = f"{uuid.uuid4()}_{file.name}"
        file_path = os.path.join(media_root, unique_name)
        with open(file_path, "wb") as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        doc = Document.objects.create(
            session_id=session_id,
            filename=file.name,
            file_path=file_path,
            status="pending",
        )

        # Kick off processing in a background thread
        t = threading.Thread(target=process_document, args=(str(doc.id),), daemon=True)
        t.start()

        return JsonResponse(
            {"document_id": str(doc.id), "filename": doc.filename, "status": doc.status},
            status=200,
        )
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        return JsonResponse({"error": f"Upload failed: {str(e)}"}, status=500)


@require_http_methods(["GET"])
def document_status(request, document_id):
    try:
        doc = Document.objects.get(id=document_id)
    except (Document.DoesNotExist, Exception):
        return JsonResponse({"error": "Document not found."}, status=404)

    return JsonResponse({"status": doc.status, "error_message": doc.error_message})
