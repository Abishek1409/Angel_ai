from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.upload_document, name="document-upload"),
    path("list/", views.list_documents, name="document-list"),
    path("<uuid:document_id>/status/", views.document_status, name="document-status"),
    path("<uuid:document_id>/delete/", views.delete_document, name="document-delete"),
]
