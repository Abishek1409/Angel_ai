from django.http import JsonResponse
from django.conf import settings
import os


def health_check(request):
    """Health check endpoint that validates configuration"""
    status = {
        "status": "healthy",
        "database": "configured" if "DATABASE_URL" in os.environ else "sqlite",
        "media_dir": str(settings.MEDIA_ROOT),
        "media_writable": os.access(settings.MEDIA_ROOT, os.W_OK) if settings.MEDIA_ROOT.exists() else False,
        "gemini_key": "configured" if settings.GEMINI_API_KEY else "missing",
        "debug": settings.DEBUG,
    }
    return JsonResponse(status)
