"""
API endpoints for AI-generated flashcards and roadmaps.
"""
import logging
from django.http import JsonResponse
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import Document
from .flashcard_models import Flashcard, Roadmap
from .ai_services import generate_flashcards, generate_roadmap

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_flashcards(request, document_id):
    """
    Generate flashcards for a document using AI.
    Creates and caches flashcards in the database.
    """
    try:
        # Get document (verify ownership)
        try:
            document = Document.objects.get(id=document_id, user=request.user)
        except Document.DoesNotExist:
            return JsonResponse({"error": "Document not found or access denied."}, status=404)
        
        # Check if document is ready
        if document.status != "ready":
            return JsonResponse(
                {"error": f"Document is not ready (status: {document.status}). Please wait for processing to complete."},
                status=400
            )
        
        # Check if flashcards already exist
        existing_count = Flashcard.objects.filter(document=document).count()
        if existing_count > 0:
            return JsonResponse(
                {
                    "message": "Flashcards already exist for this document. Use GET endpoint to retrieve them or DELETE to regenerate.",
                    "count": existing_count
                },
                status=200
            )
        
        # Generate flashcards using AI
        logger.info(f"Starting flashcard generation for document {document_id}")
        flashcard_data = generate_flashcards(str(document.id), document.filename)
        
        # Save to database in a transaction
        with transaction.atomic():
            flashcard_objects = [
                Flashcard(
                    document=document,
                    question=card["question"],
                    answer=card["answer"]
                )
                for card in flashcard_data
            ]
            Flashcard.objects.bulk_create(flashcard_objects)
        
        logger.info(f"✓ Saved {len(flashcard_objects)} flashcards for document {document_id}")
        
        return JsonResponse({
            "message": "Flashcards generated successfully",
            "count": len(flashcard_objects),
            "flashcards": [
                {
                    "id": str(fc.id),
                    "question": fc.question,
                    "answer": fc.answer,
                    "created_at": fc.created_at.isoformat()
                }
                for fc in flashcard_objects
            ]
        }, status=201)
        
    except Exception as e:
        logger.error(f"Flashcard generation error: {str(e)}", exc_info=True)
        return JsonResponse(
            {"error": f"Failed to generate flashcards: {str(e)}"},
            status=500
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_flashcards(request, document_id):
    """
    Retrieve cached flashcards for a document.
    """
    try:
        # Get document (verify ownership)
        try:
            document = Document.objects.get(id=document_id, user=request.user)
        except Document.DoesNotExist:
            return JsonResponse({"error": "Document not found or access denied."}, status=404)
        
        # Get flashcards
        flashcards = Flashcard.objects.filter(document=document).order_by('created_at')
        
        if not flashcards.exists():
            return JsonResponse({
                "message": "No flashcards found. Use POST endpoint to generate them.",
                "flashcards": []
            }, status=200)
        
        return JsonResponse({
            "count": flashcards.count(),
            "flashcards": [
                {
                    "id": str(fc.id),
                    "question": fc.question,
                    "answer": fc.answer,
                    "created_at": fc.created_at.isoformat()
                }
                for fc in flashcards
            ]
        })
        
    except Exception as e:
        logger.error(f"Error retrieving flashcards: {str(e)}", exc_info=True)
        return JsonResponse({"error": f"Failed to retrieve flashcards: {str(e)}"}, status=500)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_flashcards(request, document_id):
    """
    Delete cached flashcards (allows regeneration).
    """
    try:
        document = Document.objects.get(id=document_id, user=request.user)
        deleted_count, _ = Flashcard.objects.filter(document=document).delete()
        return JsonResponse({"message": f"Deleted {deleted_count} flashcards"})
    except Document.DoesNotExist:
        return JsonResponse({"error": "Document not found or access denied."}, status=404)
    except Exception as e:
        logger.error(f"Error deleting flashcards: {str(e)}", exc_info=True)
        return JsonResponse({"error": f"Failed to delete flashcards: {str(e)}"}, status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_roadmap(request, document_id):
    """
    Generate a Mermaid roadmap/diagram for a document using AI.
    Creates and caches the roadmap in the database.
    """
    try:
        # Get document (verify ownership)
        try:
            document = Document.objects.get(id=document_id, user=request.user)
        except Document.DoesNotExist:
            return JsonResponse({"error": "Document not found or access denied."}, status=404)
        
        # Check if document is ready
        if document.status != "ready":
            return JsonResponse(
                {"error": f"Document is not ready (status: {document.status}). Please wait for processing to complete."},
                status=400
            )
        
        # Check if roadmap already exists
        try:
            existing_roadmap = Roadmap.objects.get(document=document)
            return JsonResponse({
                "message": "Roadmap already exists for this document. Use GET endpoint to retrieve it or DELETE to regenerate.",
                "roadmap": {
                    "id": str(existing_roadmap.id),
                    "mermaid_definition": existing_roadmap.mermaid_definition,
                    "created_at": existing_roadmap.created_at.isoformat(),
                    "updated_at": existing_roadmap.updated_at.isoformat()
                }
            }, status=200)
        except Roadmap.DoesNotExist:
            pass
        
        # Generate roadmap using AI
        logger.info(f"Starting roadmap generation for document {document_id}")
        mermaid_def = generate_roadmap(str(document.id), document.filename)
        
        # Save to database
        roadmap = Roadmap.objects.create(
            document=document,
            mermaid_definition=mermaid_def
        )
        
        logger.info(f"✓ Saved roadmap for document {document_id}")
        
        return JsonResponse({
            "message": "Roadmap generated successfully",
            "roadmap": {
                "id": str(roadmap.id),
                "mermaid_definition": roadmap.mermaid_definition,
                "created_at": roadmap.created_at.isoformat(),
                "updated_at": roadmap.updated_at.isoformat()
            }
        }, status=201)
        
    except Exception as e:
        logger.error(f"Roadmap generation error: {str(e)}", exc_info=True)
        return JsonResponse(
            {"error": f"Failed to generate roadmap: {str(e)}"},
            status=500
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_roadmap(request, document_id):
    """
    Retrieve cached roadmap for a document.
    """
    try:
        # Get document (verify ownership)
        try:
            document = Document.objects.get(id=document_id, user=request.user)
        except Document.DoesNotExist:
            return JsonResponse({"error": "Document not found or access denied."}, status=404)
        
        # Get roadmap
        try:
            roadmap = Roadmap.objects.get(document=document)
            return JsonResponse({
                "roadmap": {
                    "id": str(roadmap.id),
                    "mermaid_definition": roadmap.mermaid_definition,
                    "created_at": roadmap.created_at.isoformat(),
                    "updated_at": roadmap.updated_at.isoformat()
                }
            })
        except Roadmap.DoesNotExist:
            return JsonResponse({
                "message": "No roadmap found. Use POST endpoint to generate one.",
                "roadmap": None
            }, status=200)
        
    except Exception as e:
        logger.error(f"Error retrieving roadmap: {str(e)}", exc_info=True)
        return JsonResponse({"error": f"Failed to retrieve roadmap: {str(e)}"}, status=500)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_roadmap(request, document_id):
    """
    Delete cached roadmap (allows regeneration).
    """
    try:
        document = Document.objects.get(id=document_id, user=request.user)
        roadmap = Roadmap.objects.get(document=document)
        roadmap.delete()
        return JsonResponse({"message": "Roadmap deleted successfully"})
    except Document.DoesNotExist:
        return JsonResponse({"error": "Document not found or access denied."}, status=404)
    except Roadmap.DoesNotExist:
        return JsonResponse({"error": "No roadmap found for this document."}, status=404)
    except Exception as e:
        logger.error(f"Error deleting roadmap: {str(e)}", exc_info=True)
        return JsonResponse({"error": f"Failed to delete roadmap: {str(e)}"}, status=500)
