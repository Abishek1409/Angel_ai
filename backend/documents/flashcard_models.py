"""
Models for AI-generated flashcards and roadmaps/diagrams.
"""
import uuid
from django.db import models
from django.conf import settings
from .models import Document


class Flashcard(models.Model):
    """Generated flashcards for a document."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="flashcards"
    )
    question = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['document', 'created_at']),
        ]

    def __str__(self):
        return f"Flashcard for {self.document.filename}: {self.question[:50]}..."


class Roadmap(models.Model):
    """Generated Mermaid diagram/roadmap for a document."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name="roadmap"
    )
    mermaid_definition = models.TextField(
        help_text="Mermaid.js diagram syntax (flowchart, graph, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Roadmap for {self.document.filename}"
