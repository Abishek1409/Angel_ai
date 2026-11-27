from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .health import db_health_check, health_check


urlpatterns = [
    path("", health_check),
    path("health/", health_check),
    path("health/db/", db_health_check),
    path("api/auth/", include("auth.urls")),
    path("api/documents/", include("documents.urls")),
    path("api/chat/", include("chat.urls")),
    path("api/sessions/", include("chat.session_urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
