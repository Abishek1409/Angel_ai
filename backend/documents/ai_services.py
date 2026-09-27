"""
AI-powered services for generating flashcards and roadmaps using Gemini.
"""
import json
import logging
import re
import requests
from django.conf import settings
from .services import _get_gemini_api_key
from config.chroma import get_chroma_client

logger = logging.getLogger(__name__)


def _call_gemini_json(prompt: str, max_retries: int = 2) -> dict:
    """
    Call Gemini API with JSON mode for structured output.
    
    Args:
        prompt: The prompt to send to Gemini.
        max_retries: Number of retry attempts for malformed JSON.
        
    Returns:
        Parsed JSON dict from Gemini response.
        
    Raises:
        RuntimeError: If generation fails after retries.
    """
    model = settings.GEMINI_CHAT_MODEL.removeprefix("models/")
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": _get_gemini_api_key()},
                json={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 2048,
                        "responseMimeType": "application/json"  # Force JSON output
                    },
                },
                timeout=60,
            )
            
            if not response.ok:
                raise RuntimeError(f"Gemini API error {response.status_code}: {response.text}")
            
            candidates = response.json().get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini returned no candidates")
            
            text_content = "".join(
                part.get("text", "")
                for part in candidates[0].get("content", {}).get("parts", [])
            ).strip()
            
            # Parse JSON
            parsed = json.loads(text_content)
            logger.info(f"✓ Gemini JSON generation successful (attempt {attempt + 1})")
            return parsed
            
        except json.JSONDecodeError as e:
            logger.warning(f"Gemini returned malformed JSON (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise RuntimeError(f"Gemini failed to generate valid JSON after {max_retries} attempts")
        except Exception as e:
            logger.error(f"Gemini generation error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed to generate content: {str(e)}")
    
    raise RuntimeError("Unexpected error in Gemini JSON generation")


def _get_document_text_from_chromadb(document_id: str) -> str:
    """
    Retrieve all chunks for a document from ChromaDB and concatenate them.
    
    Args:
        document_id: UUID of the document.
        
    Returns:
        Full concatenated text from all chunks.
        
    Raises:
        RuntimeError: If document not found or ChromaDB access fails.
    """
    try:
        chroma_client = get_chroma_client()
        collection = chroma_client.get_collection(name="all_documents")
        
        # Get all chunks for this document
        results = collection.get(
            where={"doc_id": {"$eq": document_id}},
            include=["documents", "metadatas"]
        )
        
        if not results["documents"]:
            raise RuntimeError(f"No text chunks found for document {document_id}")
        
        # Sort by chunk_index to maintain order
        chunks_with_index = []
        for doc, meta in zip(results["documents"], results["metadatas"]):
            chunk_index = meta.get("chunk_index", 0)
            chunks_with_index.append((chunk_index, doc))
        
        chunks_with_index.sort(key=lambda x: x[0])
        full_text = "\n\n".join(chunk for _, chunk in chunks_with_index)
        
        logger.info(f"Retrieved {len(chunks_with_index)} chunks for document {document_id}")
        return full_text
        
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve document text: {e}") from e


def generate_flashcards(document_id: str, document_filename: str) -> list[dict]:
    """
    Generate flashcards from a document using Gemini.
    
    Args:
        document_id: UUID of the document.
        document_filename: Name of the document for context.
        
    Returns:
        List of dicts with 'question' and 'answer' keys.
        
    Raises:
        RuntimeError: If generation fails.
    """
    logger.info(f"Generating flashcards for document: {document_filename}")
    
    # Get full document text
    full_text = _get_document_text_from_chromadb(document_id)
    
    # Construct prompt
    prompt = f"""You are an expert educator. Based on the following document content, generate 10 to 15 high-quality flashcards for studying.

Document: {document_filename}

Content:
{full_text[:15000]}  

Instructions:
- Create flashcards that cover the key concepts, definitions, facts, and important details
- Each flashcard should have a clear question and a concise answer
- Questions should be specific and test understanding, not just memorization
- Answers should be complete but brief (1-3 sentences)
- Return ONLY a JSON array in this exact format, no additional text:
[
  {{"question": "What is...", "answer": "..."}},
  {{"question": "How does...", "answer": "..."}},
  ...
]

Generate between 10 and 15 flashcards as a JSON array."""

    # Call Gemini with JSON mode
    result = _call_gemini_json(prompt, max_retries=2)
    
    # Validate structure
    if not isinstance(result, list):
        raise RuntimeError("Gemini did not return a list of flashcards")
    
    flashcards = []
    for item in result:
        if not isinstance(item, dict) or "question" not in item or "answer" not in item:
            logger.warning(f"Skipping malformed flashcard: {item}")
            continue
        flashcards.append({
            "question": str(item["question"]).strip(),
            "answer": str(item["answer"]).strip()
        })
    
    if len(flashcards) < 5:
        raise RuntimeError(f"Generated only {len(flashcards)} valid flashcards, minimum is 5")
    
    logger.info(f"✓ Generated {len(flashcards)} flashcards successfully")
    return flashcards


def _validate_mermaid_syntax(mermaid_def: str) -> bool:
    """
    Basic validation that Mermaid syntax starts with a valid diagram type.
    
    Args:
        mermaid_def: Mermaid diagram definition string.
        
    Returns:
        True if valid, False otherwise.
    """
    if not mermaid_def or not isinstance(mermaid_def, str):
        return False
    
    mermaid_def = mermaid_def.strip()
    
    # Check for valid Mermaid diagram type declarations
    valid_starts = [
        "flowchart",
        "graph",
        "sequenceDiagram",
        "classDiagram",
        "stateDiagram",
        "erDiagram",
        "gantt",
        "pie",
        "journey",
        "mindmap",
        "timeline"
    ]
    
    for diagram_type in valid_starts:
        if mermaid_def.startswith(diagram_type):
            logger.info(f"✓ Valid Mermaid syntax detected: {diagram_type}")
            return True
    
    logger.warning(f"Invalid Mermaid syntax: does not start with recognized diagram type")
    return False


def generate_roadmap(document_id: str, document_filename: str) -> str:
    """
    Generate a Mermaid flowchart/roadmap from a document using Gemini.
    
    Args:
        document_id: UUID of the document.
        document_filename: Name of the document for context.
        
    Returns:
        Mermaid.js diagram definition string.
        
    Raises:
        RuntimeError: If generation fails or syntax is invalid.
    """
    logger.info(f"Generating roadmap for document: {document_filename}")
    
    # Get full document text
    full_text = _get_document_text_from_chromadb(document_id)
    
    # Construct prompt
    prompt = f"""You are an expert at creating visual learning roadmaps. Based on the following document content, create a Mermaid.js flowchart diagram that represents the document's structure, key concepts, and learning path.

Document: {document_filename}

Content:
{full_text[:15000]}

Instructions:
- Create a flowchart using Mermaid.js syntax (start with "flowchart TD" or "flowchart LR")
- Show the main topics, subtopics, and relationships between concepts
- Use clear, concise node labels (keep them short)
- Use arrows to show learning progression or concept relationships
- Include 8 to 15 nodes maximum (keep it focused and readable)
- Return ONLY the Mermaid diagram definition as a JSON object with a "diagram" key
- Do NOT include any explanation, only the Mermaid syntax

Example format:
{{"diagram": "flowchart TD\\n    A[Start] --> B[Topic 1]\\n    B --> C[Topic 2]\\n    C --> D[End]"}}

Generate the roadmap as a JSON object with a "diagram" field."""

    # Try generating with retries
    for attempt in range(2):
        try:
            result = _call_gemini_json(prompt, max_retries=1)
            
            # Extract diagram from JSON
            if isinstance(result, dict) and "diagram" in result:
                mermaid_def = result["diagram"]
            elif isinstance(result, str):
                mermaid_def = result
            else:
                raise RuntimeError("Gemini returned unexpected format")
            
            # Validate Mermaid syntax
            if _validate_mermaid_syntax(mermaid_def):
                logger.info(f"✓ Generated valid Mermaid roadmap ({len(mermaid_def)} chars)")
                return mermaid_def.strip()
            else:
                if attempt == 0:
                    logger.warning("Invalid Mermaid syntax, retrying with stricter prompt...")
                    prompt = prompt.replace(
                        "Generate the roadmap",
                        "CRITICAL: You MUST start with 'flowchart TD' or 'flowchart LR'. Generate the roadmap"
                    )
                else:
                    raise RuntimeError("Generated Mermaid syntax failed validation")
                    
        except Exception as e:
            if attempt == 1:
                raise RuntimeError(f"Failed to generate valid roadmap: {str(e)}")
            logger.warning(f"Roadmap generation attempt {attempt + 1} failed, retrying...")
    
    raise RuntimeError("Failed to generate roadmap after retries")
