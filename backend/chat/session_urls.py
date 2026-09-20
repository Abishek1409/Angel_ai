from django.urls import path

from . import views


urlpatterns = [
    path("", views.list_sessions, name="session-list"),
    path("<uuid:session_id>/messages/", views.session_messages, name="session-messages"),
    path("<uuid:session_id>/", views.delete_session, name="session-delete"),
]