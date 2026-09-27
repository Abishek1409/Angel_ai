from django.urls import path
from . import views
from . import ai_views

urlpatterns = [
    path("upload/", views.upload_document, name="document-upload"),
    path("list/", views.list_documents, name="document-list"),
    path("<uuid:document_id>/status/", views.document_status, name="document-status"),
    path("<uuid:document_id>/delete/", views.delete_document, name="document-delete"),
    
    # AI-generated features
    path("<uuid:document_id>/flashcards/", ai_views.get_flashcards, name="get-flashcards"),
    path("<uuid:document_id>/flashcards/generate/", ai_views.create_flashcards, name="create-flashcards"),
    path("<uuid:document_id>/flashcards/delete/", ai_views.delete_flashcards, name="delete-flashcards"),
    path("<uuid:document_id>/roadmap/", ai_views.get_roadmap, name="get-roadmap"),
    path("<uuid:document_id>/roadmap/generate/", ai_views.create_roadmap, name="create-roadmap"),
    path("<uuid:document_id>/roadmap/delete/", ai_views.delete_roadmap, name="delete-roadmap"),
]
