import os
import logging
import re
import requests
from openai import OpenAI
from django.conf import settings
from .cache import get_cached_embedding, cache_embedding, get_cached_response, cache_response
from documents.services import _embed_text, _get_gemini_api_key
from config.chroma import get_chroma_client

_get_chroma_client = get_chroma_client
logger = logging.getLogger(__name__)


def _clean_answer_text(text: str) -> str:
    """Strip markdown emphasis and decorative bullet symbols from model output."""
    if not text:
        return ""

    cleaned = text.strip()
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", cleaned)
    cleaned = re.sub(r"(?m)^\s*[-*+•\u2022\u25E6]\s*", "", cleaned)
    cleaned = re.sub(r"(?m)^\s*#+\s*", "", cleaned)
    cleaned = re.sub(r"[\u2605\u2606\u2730\u2731\u2022\u25CF\u25AA\u25E6]+", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()


def _generate_llm_response(prompt: str) -> str:
    """
    Generate an answer using Groq (primary) with automatic fallback to OpenRouter free models.
    
    Tries Groq first for fast inference. If Groq fails for any reason (API error, timeout, 
    model deprecated, connection error), automatically falls back to OpenRouter's free tier 
    models, rotating through the list until one succeeds.
    
    Args:
        prompt: The complete prompt including context and question.
        
    Returns:
        Generated answer text.
        
    Raises:
        RuntimeError: If all providers (Groq + all OpenRouter models) fail.
    """
    # Try Groq first (primary provider - fast inference hardware)
    if settings.GROQ_API_KEY:
        try:
            logger.info(f"Attempting Groq with model: {settings.GROQ_MODEL}")
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1024
                },
                timeout=15  # Reasonable timeout so hanging requests don't block fallback
            )
            
            if response.ok:
                answer = response.json()["choices"][0]["message"]["content"].strip()
                logger.info(f"✓ Response served by: Groq/{settings.GROQ_MODEL}")
                return answer
            else:
                logger.warning(f"Groq API error {response.status_code}: {response.text}")
        except requests.exceptions.Timeout:
            logger.warning("Groq request timed out after 15s, falling back to OpenRouter")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Groq connection error: {e}, falling back to OpenRouter")
        except Exception as e:
            logger.warning(f"Groq unexpected error ({type(e).__name__}): {e}, falling back to OpenRouter")
    else:
        logger.info("GROQ_API_KEY not configured, using OpenRouter directly")
    
    # Fallback to OpenRouter free models (rotate through list)
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError(
            "AI service is temporarily unavailable. Both Groq and OpenRouter are not configured."
        )
    
    openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    )
    
    for model_id in settings.OPENROUTER_FREE_MODELS:
        try:
            logger.info(f"Attempting OpenRouter fallback with model: {model_id}")
            completion = openrouter_client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024,
                timeout=15
            )
            answer = completion.choices[0].message.content.strip()
            logger.info(f"✓ Response served by: OpenRouter/{model_id}")
            return answer
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Handle rate limits - try next model immediately
            if "429" in error_msg or "rate limit" in error_msg or "capacity" in error_msg:
                logger.warning(f"OpenRouter model {model_id} rate limited, trying next model")
                continue
            
            # Handle model not found or no longer free - log clearly and skip
            elif "model not found" in error_msg or "payment" in error_msg or "billing" in error_msg:
                logger.warning(f"⚠ OPENROUTER_FREE_MODELS entry no longer free or valid: {model_id}")
                continue
            
            # Other errors - try next model rather than retrying same one
            else:
                logger.warning(f"OpenRouter model {model_id} error ({type(e).__name__}): {e}, trying next model")
                continue
    
    # All providers failed
    raise RuntimeError(
        "AI service is temporarily unavailable, please try again. "
        "All LLM providers (Groq and OpenRouter free models) are currently unavailable or rate limited."
    )


def retrieve_chunks(question: str, document_id: str = None, top_k: int = 5) -> tuple[list[str], list[dict], list[str], bool]:
    """
    Embed the question and retrieve the top-k most similar chunks from ChromaDB.

    Args:
        question: The user's natural language question.
        document_id: Optional UUID string to scope search to specific document.
        top_k: Number of chunks to retrieve.

    Returns:
        Tuple of (chunk_texts, chunk_metadata_list, chunk_ids, cache_hit).
        Returns empty lists and False if no results.
    """
    try:
        chroma_client = _get_chroma_client()
        collection = chroma_client.get_collection(name="all_documents")
    except Exception:
        return [], [], [], False

    try:
        collection_size = collection.count()
        if collection_size == 0:
            return [], [], [], False

        # Check cache for embedding using raw query text hash.
        cached_embedding = get_cached_embedding(question)
        embedding_cache_hit = cached_embedding is not None

        if cached_embedding:
            question_embedding = cached_embedding
        else:
            try:
                question_embedding = _embed_text(question, "RETRIEVAL_QUERY")
                cache_embedding(question, question_embedding)
            except Exception as e:
                raise RuntimeError(f"Failed to embed question: {e}") from e

        where_filter = {"doc_id": {"$eq": document_id}} if document_id else None

        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=min(top_k, collection_size),
            where=where_filter,
        )

        chunks = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        ids = results["ids"][0] if results["ids"] else []

        return chunks, metadatas, ids, embedding_cache_hit
    except Exception as e:
        raise RuntimeError(f"Failed to query ChromaDB: {e}") from e


def generate_answer(
    question: str,
    chunks: list[str],
    metadatas: list[dict],
    chunk_ids: list[str],
    conversation_history: str = "",
    cache_scope: str = "",
) -> tuple[str, list[str], list[dict], bool]:
    """
    Build a prompt from retrieved chunks and generate an answer via Gemini.

    Args:
        question: The user's natural language question.
        chunks: List of relevant text chunks to use as context.
        metadatas: List of metadata dicts corresponding to each chunk.
        chunk_ids: List of chunk IDs from ChromaDB.

    Returns:
        Tuple of (generated_answer, list_of_source_filenames, list_of_citations, cache_hit).
        Returns informational message, empty list, empty citations, and False if no chunks provided.
    """
    if not chunks:
        return (
            "No relevant information found in your documents. Please try rephrasing your question or upload relevant documents.",
            [],
            [],
            False,
        )

    # Check cache for response
    cached_response = get_cached_response(question, chunk_ids, cache_scope=cache_scope + conversation_history)
    if cached_response:
        answer, sources, citations = cached_response
        return answer, sources, citations, True

    context = "\n\n---\n\n".join(chunks)
    prompt = (
        "You are a careful assistant. Answer using only the provided context. "
        "Use the information in the context to answer the question directly. "
        "If the context is incomplete or does not support the answer, say that plainly instead of guessing. "
        "Do not invent facts, do not mention missing context as a workaround, and do not add unsupported claims. "
        "Do not use markdown formatting, bold text, bullets, stars, or special symbols. "
        "Write in plain, readable sentences.\n\n"
        f"{conversation_history}"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer in plain English without markdown or bullets:"
    )

    try:
        answer = _clean_answer_text(_generate_llm_response(prompt))

        sources = list(dict.fromkeys([meta.get("source", "Unknown") for meta in metadatas]))
        citations = [
            {
                "source": meta.get("source", "Unknown"),
                "doc_id": meta.get("doc_id"),
                "chunk_id": cid,
                "chunk_index": meta.get("chunk_index"),
            }
            for meta, cid in zip(metadatas, chunk_ids)
        ]

        cache_response(
            question,
            chunk_ids,
            answer,
            sources,
            citations,
            cache_scope=cache_scope + conversation_history,
        )

        return answer, sources, citations, False
    except Exception as e:
        raise RuntimeError(
            f"Failed to generate answer: {str(e)} Error type: {type(e).__name__}"
        ) from e
