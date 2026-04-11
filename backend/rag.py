import os
import numpy as np
import google.generativeai as genai
from typing import List, Tuple

EMBED_MODEL = "models/text-embedding-004"
LLM_MODEL   = "models/gemini-2.0-flash"

CHUNK_SIZE    = 500
CHUNK_OVERLAP = 80


def configure_genai():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set in environment.")
    genai.configure(api_key=api_key)


# ──────────────────────────────────────────────
#  In-memory vector store (per-session)
# ──────────────────────────────────────────────
class VectorStore:
    def __init__(self):
        self.chunks: List[str] = []
        self.embeddings: np.ndarray = np.empty((0,), dtype=np.float32)
        self.source_names: List[str] = []

    def clear(self):
        self.chunks = []
        self.embeddings = np.empty((0,), dtype=np.float32)
        self.source_names = []

    def add_document(self, text: str, source: str) -> int:
        configure_genai()
        new_chunks = chunk_text(text)
        if not new_chunks:
            return 0
        vecs = embed_texts(new_chunks)
        self.chunks.extend(new_chunks)
        self.source_names.extend([source] * len(new_chunks))
        if self.embeddings.size == 0:
            self.embeddings = np.array(vecs, dtype=np.float32)
        else:
            self.embeddings = np.vstack([self.embeddings, np.array(vecs, dtype=np.float32)])
        return len(new_chunks)

    def search(self, query: str, top_k: int) -> List[Tuple[str, str, float]]:
        if not self.chunks:
            return []
        configure_genai()
        q_vec = np.array(embed_query(query), dtype=np.float32)
        norms = np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(q_vec)
        norms = np.where(norms == 0, 1e-10, norms)
        sims = (self.embeddings @ q_vec) / norms
        top_indices = np.argsort(sims)[::-1][:top_k]
        return [(self.chunks[i], self.source_names[i], float(sims[i])) for i in top_indices]


# ──────────────────────────────────────────────
#  Text chunking
# ──────────────────────────────────────────────
def chunk_text(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# ──────────────────────────────────────────────
#  Gemini Embeddings
# ──────────────────────────────────────────────
def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of passage texts (for indexing)."""
    all_embeddings = []
    batch_size = 32
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        result = genai.embed_content(
            model=EMBED_MODEL,
            content=batch,
            task_type="retrieval_document",
        )
        all_embeddings.extend(result["embedding"])
    return all_embeddings


def embed_query(query: str) -> List[float]:
    """Embed a single query string."""
    result = genai.embed_content(
        model=EMBED_MODEL,
        content=query,
        task_type="retrieval_query",
    )
    return result["embedding"]


# ──────────────────────────────────────────────
#  Gemini LLM Generation
# ──────────────────────────────────────────────
def generate_answer(query: str, context_chunks: List[str]) -> str:
    configure_genai()
    model = genai.GenerativeModel(
        model_name=LLM_MODEL,
        system_instruction=(
            "You are Angel AI, a helpful and intelligent assistant powered by Google Gemini. "
            "Use the provided context to answer the user's question accurately and concisely. "
            "If the context doesn't contain the answer, say so honestly and answer from your general knowledge."
        ),
    )

    if context_chunks:
        context = "\n\n---\n\n".join(context_chunks)
        prompt = f"Context:\n{context}\n\nQuestion: {query}"
    else:
        prompt = (
            f"No documents have been uploaded yet. Answer from general knowledge.\n\nQuestion: {query}"
        )

    response = model.generate_content(prompt)
    return response.text
