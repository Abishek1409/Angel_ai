from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.upload_document, name="document-upload"),
    path("<uuid:document_id>/status/", views.document_status, name="document-status"),
]
