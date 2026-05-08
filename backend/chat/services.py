from google import genai
from google.genai import types
import chromadb
from django.conf import settings


def retrieve_chunks(document_id: str, question: str, top_k: int = 5) -> list[str]:
    """
    Embed the question and retrieve the top-k most similar chunks from ChromaDB.

    Args:
        document_id: UUID string of the Document record.
        question: The user's natural language question.
        top_k: Number of chunks to retrieve.

    Returns:
        List of chunk text strings. Returns empty list if collection does not exist.
    """
    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(api_version="v1beta"),
    )

    try:
        question_embedding = client.models.embed_content(
            model="gemini-embedding-001",
            contents=question,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        ).embeddings[0].values
    except Exception as e:
        raise RuntimeError(f"Failed to embed question: {e}") from e

    try:
        chroma_client = chromadb.Client()
        collection = chroma_client.get_collection(name=f"doc_{document_id}")
    except Exception:
        # Collection does not exist
        return []

    try:
        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=min(top_k, collection.count()),
        )
        return results["documents"][0] if results["documents"] else []
    except Exception as e:
        raise RuntimeError(f"Failed to query ChromaDB: {e}") from e


def generate_answer(question: str, chunks: list[str]) -> str:
    """
    Build a prompt from retrieved chunks and generate an answer via Gemini.

    Args:
        question: The user's natural language question.
        chunks: List of relevant text chunks to use as context.

    Returns:
        Generated answer string, or an informational message if no chunks provided.
    """
    if not chunks:
        return (
            "The document does not appear to contain information relevant to your question."
        )

    genai_client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(api_version="v1beta"),
    )

    context = "\n\n---\n\n".join(chunks)
    prompt = (
        "You are a helpful assistant. Answer the question below using only the provided context.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )

    try:
        response = genai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        raise RuntimeError(f"Failed to generate answer: {e}") from e
