import os
import logging
import requests
from django.conf import settings
from .cache import get_cached_embedding, cache_embedding, get_cached_response, cache_response
from documents.services import _embed_text, _get_gemini_api_key
from config.chroma import get_chroma_client

_get_chroma_client = get_chroma_client
logger = logging.getLogger(__name__)


def _generate_gemini_answer(prompt: str) -> str:
    """Generate an answer with Gemini using the same key as embeddings."""
    model = settings.GEMINI_CHAT_MODEL.removeprefix("models/")
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": _get_gemini_api_key()},
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
        },
        timeout=90,
    )
    if not response.ok:
        raise RuntimeError(f"Gemini chat API returned {response.status_code}: {response.text}")

    candidates = response.json().get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini chat API returned no answer candidates")
    return "".join(
        part.get("text", "")
        for part in candidates[0].get("content", {}).get("parts", [])
    ).strip()


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
        "You are a helpful assistant. Answer the question below using only the provided context.\n\n"
        f"{conversation_history}"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )

    try:
        answer = _generate_gemini_answer(prompt)

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
            f"Failed to generate answer with Gemini using model '{settings.GEMINI_CHAT_MODEL}': "
            f"{str(e)} Error type: {type(e).__name__}"
        ) from e
