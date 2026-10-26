"""
AI-powered services for generating flashcards and roadmaps.

Provider chain: Groq (primary) -> Gemini -> OpenRouter free models.
"""
import json
import logging
import re
import requests
from django.conf import settings
from openai import OpenAI
from config.chroma import get_chroma_client
from .services import DOCUMENT_COLLECTIONS

logger = logging.getLogger(__name__)

_MAX_OUTPUT_TOKENS = 4096


class DocumentTextMissing(RuntimeError):
    """Raised when a document has no stored chunks (e.g. ChromaDB was wiped)."""


def _parse_json(text: str):
    """Parse model output as JSON, tolerating ```json fences and surrounding prose."""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fall back to the outermost {...} or [...] block
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(1))


def _key(value: str) -> str:
    """Treat empty or template placeholder keys (e.g. 'your-groq-key') as not configured."""
    value = (value or "").strip()
    return "" if not value or value.lower().startswith("your") else value


def _groq_json(prompt: str, model: str) -> str:
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": _MAX_OUTPUT_TOKENS,
            "response_format": {"type": "json_object"},  # top-level must be an object
        },
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"Groq {response.status_code}: {response.text[:300]}")
    return response.json()["choices"][0]["message"]["content"]


def _gemini_json(prompt: str) -> str:
    model = settings.GEMINI_CHAT_MODEL.removeprefix("models/")
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": settings.GEMINI_API_KEY},
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": _MAX_OUTPUT_TOKENS,
                "responseMimeType": "application/json",
                # 2.5 models spend output tokens on "thinking", which truncated the JSON
                "thinkingConfig": {"thinkingBudget": 0},
            },
        },
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"Gemini {response.status_code}: {response.text[:300]}")
    candidates = response.json().get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    return "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []))


def _openrouter_json(prompt: str, model_id: str) -> str:
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=settings.OPENROUTER_API_KEY)
    completion = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=_MAX_OUTPUT_TOKENS,
        timeout=60,
    )
    return completion.choices[0].message.content or ""


def _call_llm_json(prompt: str):
    """
    Generate structured JSON, falling through providers until one returns valid JSON.

    Raises:
        RuntimeError: If every configured provider fails.
    """
    # Order: Groq primary -> Groq fallback models -> Gemini -> OpenRouter free models
    providers = []
    if _key(settings.GROQ_API_KEY):
        for model in [settings.GROQ_MODEL, *settings.GROQ_FALLBACK_MODELS]:
            providers.append((f"Groq/{model}", lambda m=model: _groq_json(prompt, m)))
    if _key(settings.GEMINI_API_KEY):
        providers.append((f"Gemini/{settings.GEMINI_CHAT_MODEL}", lambda: _gemini_json(prompt)))
    if _key(settings.OPENROUTER_API_KEY):
        for model_id in settings.OPENROUTER_FREE_MODELS:
            providers.append((f"OpenRouter/{model_id}", lambda m=model_id: _openrouter_json(prompt, m)))

    if not providers:
        raise RuntimeError(
            "No AI provider configured. Set a real GROQ_API_KEY, GEMINI_API_KEY or OPENROUTER_API_KEY."
        )

    errors = []
    for name, call in providers:
        try:
            parsed = _parse_json(call())
            logger.info(f"✓ JSON generation served by {name}")
            return parsed
        except Exception as e:
            logger.warning(f"{name} failed ({type(e).__name__}): {e}")
            # Short reason (e.g. "Groq 401: Invalid API Key") so the client error is diagnosable
            errors.append(f"{name}: {str(e)[:120]}")

    raise RuntimeError("All AI providers failed: " + "; ".join(errors))


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

        # A document lives in the Gemini or the local-fallback collection
        chunks_with_index = []
        for name in DOCUMENT_COLLECTIONS:
            try:
                collection = chroma_client.get_collection(name=name)
            except Exception:
                continue
            results = collection.get(
                where={"doc_id": {"$eq": document_id}},
                include=["documents", "metadatas"]
            )
            for doc, meta in zip(results["documents"], results["metadatas"]):
                chunks_with_index.append((meta.get("chunk_index", 0), doc))

        if not chunks_with_index:
            raise DocumentTextMissing(f"No text chunks found for document {document_id}")
        
        chunks_with_index.sort(key=lambda x: x[0])
        full_text = "\n\n".join(chunk for _, chunk in chunks_with_index)
        
        logger.info(f"Retrieved {len(chunks_with_index)} chunks for document {document_id}")
        return full_text

    except DocumentTextMissing:
        raise
    except Exception as e:
        # Missing collection means ChromaDB storage was reset (e.g. redeploy on ephemeral disk)
        raise DocumentTextMissing(f"Failed to retrieve document text: {e}") from e


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
- Return ONLY a JSON object in this exact format, no additional text:
{{"flashcards": [
  {{"question": "What is...", "answer": "..."}},
  {{"question": "How does...", "answer": "..."}}
]}}

Generate between 10 and 15 flashcards."""

    result = _call_llm_json(prompt)

    # Accept {"flashcards": [...]} or a bare list
    if isinstance(result, dict):
        result = result.get("flashcards", [])
    if not isinstance(result, list):
        raise RuntimeError("AI did not return a list of flashcards")
    
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
            result = _call_llm_json(prompt)

            if isinstance(result, dict) and "diagram" in result:
                mermaid_def = result["diagram"]
            elif isinstance(result, str):
                mermaid_def = result
            else:
                raise RuntimeError("AI returned unexpected format")
            
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
