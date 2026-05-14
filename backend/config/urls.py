from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health),
    path("api/documents/", include("documents.urls")),
    path("api/chat/", include("chat.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
