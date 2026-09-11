import os
from google import genai
from google.genai import types
import chromadb
from django.conf import settings
from .cache import get_cached_embedding, cache_embedding, get_cached_response, cache_response

_CHROMA_PATH = os.path.join(settings.BASE_DIR, "chroma_db")


def _get_chroma_client():
    return chromadb.PersistentClient(path=_CHROMA_PATH)


def _use_groq():
    """Check if Groq API should be used instead of Gemini."""
    return bool(settings.GROQ_API_KEY)


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
    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(api_version="v1beta"),
    )

    # Check cache for embedding
    cache_key = f"{question}_{document_id}" if document_id else question
    cached_embedding = get_cached_embedding(cache_key)
    embedding_cache_hit = cached_embedding is not None
    
    if cached_embedding:
        question_embedding = cached_embedding
    else:
        try:
            question_embedding = client.models.embed_content(
                model="gemini-embedding-001",
                contents=question,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
            ).embeddings[0].values
            # Cache the embedding
            cache_embedding(cache_key, question_embedding)
        except Exception as e:
            raise RuntimeError(f"Failed to embed question: {e}") from e

    try:
        chroma_client = _get_chroma_client()
        collection = chroma_client.get_collection(name="all_documents")
    except Exception:
        # Collection does not exist
        return [], [], [], False

    try:
        # Build where filter if document_id is specified
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


def generate_answer(question: str, chunks: list[str], metadatas: list[dict], chunk_ids: list[str]) -> tuple[str, list[str], bool]:
    """
    Build a prompt from retrieved chunks and generate an answer via Groq.

    Args:
        question: The user's natural language question.
        chunks: List of relevant text chunks to use as context.
        metadatas: List of metadata dicts corresponding to each chunk.
        chunk_ids: List of chunk IDs from ChromaDB.

    Returns:
        Tuple of (generated_answer, list_of_source_filenames, cache_hit).
        Returns informational message, empty list, and False if no chunks provided.
    """
    if not chunks:
        return (
            "No relevant information found in your documents. Please try rephrasing your question or upload relevant documents.",
            [],
            False
        )

    # Check cache for response
    cached_response = get_cached_response(question, chunk_ids)
    if cached_response:
        answer, sources = cached_response
        return answer, sources, True

    context = "\n\n---\n\n".join(chunks)
    prompt = (
        "You are a helpful assistant. Answer the question below using only the provided context.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )

    try:
        # Use Groq via direct HTTP request (more reliable)
        if _use_groq():
            import requests
            
            headers = {
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1024
            }
            
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                raise RuntimeError(f"Groq API error: {response.status_code} - {response.text}")
            
            answer = response.json()["choices"][0]["message"]["content"]
        else:
            raise RuntimeError("GROQ_API_KEY not configured. Please set it in environment variables.")
        
        # Extract unique source filenames
        sources = list(dict.fromkeys([meta.get("source", "Unknown") for meta in metadatas]))
        
        # Cache the response
        cache_response(question, chunk_ids, answer, sources)
        
        return answer, sources, False
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to generate answer with Groq: {str(e)}. Error type: {type(e).__name__}") from e
