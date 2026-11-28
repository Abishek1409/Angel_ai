import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def default_expiry():
    """Uploaded documents are kept for DOCUMENT_RETENTION_HOURS (2 days by default)."""
    return timezone.now() + timedelta(hours=settings.DOCUMENT_RETENTION_HOURS)


class DocumentQuerySet(models.QuerySet):
    def active(self):
        return self.filter(expires_at__gt=timezone.now())

    def expired(self):
        return self.filter(expires_at__lte=timezone.now())


class Document(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing_ocr", "Processing (OCR)"),
        ("ready", "Ready"),
        ("error", "Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )
    session_id = models.UUIDField()
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expiry, db_index=True)

    objects = DocumentQuerySet.as_manager()

    def __str__(self):
        return f"{self.filename} ({self.status})"


class DocumentChunk(models.Model):
    """
    Durable copy of a document's text chunks and embeddings.

    The web host's disk (media/ and chroma_db/) is wiped on every restart,
    so the database is the source of truth and ChromaDB is rebuilt from here.
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()
    # float32 vector bytes; collection says which embedding model produced it
    embedding = models.BinaryField()
    collection = models.CharField(max_length=64)

    class Meta:
        ordering = ["chunk_index"]
        constraints = [
            models.UniqueConstraint(fields=["document", "chunk_index"], name="uniq_document_chunk"),
        ]
