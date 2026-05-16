from django.urls import path
from . import views

urlpatterns = [
    path("query/", views.query, name="chat-query"),
    path("history/<str:document_id>/", views.history, name="chat-history"),
]
