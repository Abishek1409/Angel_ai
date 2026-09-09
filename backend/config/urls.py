from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .health import health_check


urlpatterns = [
    path("health/", health_check),
    path("api/documents/", include("documents.urls")),
    path("api/chat/", include("chat.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
