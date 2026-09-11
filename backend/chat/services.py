import os
import chromadb
import google.generativeai as genai
from groq import Groq
from django.conf import settings
from .cache import get_cached_embedding, cache_embedding, get_cached_response, cache_response

_CHROMA_PATH = os.path.join(settings.BASE_DIR, "chroma_db")


def _get_chroma_client():
    return chromadb.PersistentClient(path=_CHROMA_PATH)


def _get_gemini_client():
    """Gemini client for embeddings only."""
    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key == "AIza-your-gemini-api-key-here":
        raise ValueError(
            "Gemini API key is not configured for embeddings. Please set GEMINI_API_KEY in your .env file "
            "or environment variables. Get a free API key at https://makersuite.google.com/app/apikey"
        )
    genai.configure(api_key=api_key)
    return genai


def _get_groq_client():
    """Groq client for LLM chat."""
    api_key = settings.GROQ_API_KEY
    if not api_key or api_key == "gsk-your-groq-api-key-here":
        raise ValueError(
            "Groq API key is not configured. Please set GROQ_API_KEY in your .env file "
            "or environment variables. Get a free API key at https://console.groq.com/"
        )
    return Groq(api_key=api_key)


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
    # Check cache for embedding using raw query text hash
    cached_embedding = get_cached_embedding(question)
    embedding_cache_hit = cached_embedding is not None

    if cached_embedding:
        question_embedding = cached_embedding
    else:
        try:
            genai = _get_gemini_client()
            model = genai.GenerativeModel('models/embedding-001')
            result = genai.embed_content(
                model=model,
                content=question,
                task_type="retrieval_query"
            )
            question_embedding = result['embedding']
            cache_embedding(question, question_embedding)
        except Exception as e:
            raise RuntimeError(f"Failed to embed question: {e}") from e

    try:
        chroma_client = _get_chroma_client()
        collection = chroma_client.get_collection(name="all_documents")
    except Exception:
        return [], [], [], False

    try:
        where_filter = {"doc_id": document_id} if document_id else None

        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=min(top_k, collection.count()),
            where=where_filter,
        )

        chunks = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        ids = results["ids"][0] if results["ids"] else []

        return chunks, metadatas, ids, embedding_cache_hit
    except Exception as e:
        raise RuntimeError(f"Failed to query ChromaDB: {e}") from e


def generate_answer(question: str, chunks: list[str], metadatas: list[dict], chunk_ids: list[str]) -> tuple[str, list[str], list[dict], bool]:
    """
    Build a prompt from retrieved chunks and generate an answer via Groq.

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
    cached_response = get_cached_response(question, chunk_ids)
    if cached_response:
        answer, sources, citations = cached_response
        return answer, sources, citations, True

    context = "\n\n---\n\n".join(chunks)
    prompt = (
        "You are a helpful assistant. Answer the question below using only the provided context.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Answer questions using only the provided context."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        answer = response.choices[0].message.content

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

        cache_response(question, chunk_ids, answer, sources, citations)

        return answer, sources, citations, False
    except Exception as e:
        raise RuntimeError(f"Failed to generate answer with Groq: {str(e)}. Error type: {type(e).__name__}") from e
