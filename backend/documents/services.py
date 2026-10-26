import os
import threading
import math
import time
import logging
import fitz  # PyMuPDF
import requests
from django.conf import settings
from django.db import close_old_connections
from config.chroma import get_chroma_client

# Persistent ChromaDB stored on disk so data survives across requests
_CHUNK_SIZE_CHARS = 500 * 4
_OVERLAP_CHARS = 50 * 4
_EMBED_BATCH_SIZE = 50
_OCR_MAX_PAGES = 30
logger = logging.getLogger(__name__)


def _get_gemini_api_key():
    """Return the Gemini API key used for embeddings."""
    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key == "AIza-your-gemini-api-key-here":
        raise ValueError(
            "Gemini API key is not configured for embeddings. Please set GEMINI_API_KEY in your .env file "
            "or environment variables. Get a free API key at https://makersuite.google.com/app/apikey "
            "(Gemini is used for embeddings only, Groq is used for chat)"
        )
    return api_key


def _post_with_retry(url: str, retries: int = 3, **kwargs) -> requests.Response:
    """POST with exponential backoff on rate limits / transient server errors."""
    response = None
    for attempt in range(retries):
        try:
            response = requests.post(url, **kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt == retries - 1:
                raise
            logger.warning(f"Gemini request failed ({type(e).__name__}), retrying...")
        else:
            if response.status_code not in (429, 500, 502, 503, 504):
                return response
            logger.warning(f"Gemini returned {response.status_code}, retry {attempt + 1}/{retries}")
        if attempt < retries - 1:
            time.sleep(2 ** (attempt + 1))  # 2s, 4s
    return response


def _embed_text(text: str, task_type: str) -> list[float]:
    model = settings.GEMINI_EMBEDDING_MODEL.removeprefix("models/")
    response = _post_with_retry(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent",
        params={"key": _get_gemini_api_key()},
        json={
            "content": {"parts": [{"text": text}]},
            "taskType": task_type,
        },
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"Gemini embedding API returned {response.status_code}: {response.text}")
    return response.json()["embedding"]["values"]


def _embed_texts(texts: list[str], task_type: str) -> list[list[float]]:
    model = settings.GEMINI_EMBEDDING_MODEL.removeprefix("models/")
    response = _post_with_retry(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents",
        params={"key": _get_gemini_api_key()},
        json={
            "requests": [
                {
                    "model": f"models/{model}",
                    "content": {"parts": [{"text": text}]},
                    "taskType": task_type,
                }
                for text in texts
            ]
        },
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"Gemini batch embedding API returned {response.status_code}: {response.text}")
    embeddings = response.json().get("embeddings", [])
    if len(embeddings) != len(texts):
        raise RuntimeError("Gemini batch embedding API returned an unexpected number of embeddings")
    return [embedding["values"] for embedding in embeddings]


# Chroma collections must hold vectors of a single dimension, so Gemini (3072-d)
# and the local fallback model (384-d) are stored in separate collections.
GEMINI_COLLECTION = "all_documents"
LOCAL_COLLECTION = "all_documents_local"
DOCUMENT_COLLECTIONS = (GEMINI_COLLECTION, LOCAL_COLLECTION)

_local_embedder = None

_HF_EMBED_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"
)


def _hf_embed(texts: list[str]) -> list[list[float]]:
    """
    Hosted all-MiniLM-L6-v2 (free HF token). Same model as the local fallback,
    so vectors share the 384-d space and live in LOCAL_COLLECTION.
    """
    token = (settings.HF_API_TOKEN or "").strip()
    if not token or token.lower().startswith("your"):
        raise RuntimeError("HF_API_TOKEN not configured")
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i:i + _EMBED_BATCH_SIZE]
        response = _post_with_retry(
            _HF_EMBED_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"inputs": batch, "options": {"wait_for_model": True}},
            timeout=60,
        )
        if not response.ok:
            raise RuntimeError(f"Hugging Face embedding API returned {response.status_code}: {response.text[:200]}")
        vectors = response.json()
        if not isinstance(vectors, list) or len(vectors) != len(batch):
            raise RuntimeError("Hugging Face returned an unexpected number of embeddings")
        embeddings.extend([list(map(float, v)) for v in vectors])
    return embeddings


def _onnx_embed(texts: list[str]) -> list[list[float]]:
    """Free, keyless last resort: all-MiniLM-L6-v2 via ONNX, bundled with chromadb."""
    global _local_embedder
    if _local_embedder is None:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        _local_embedder = DefaultEmbeddingFunction()
    return [list(map(float, v)) for v in _local_embedder(texts)]


def _local_embed(texts: list[str]) -> list[list[float]]:
    """384-d MiniLM embeddings: Hugging Face API first, local ONNX model if that fails."""
    try:
        return _hf_embed(texts)
    except Exception as e:
        logger.warning(f"Hugging Face embeddings unavailable ({e}); using local ONNX model")
    return _onnx_embed(texts)


def embed_chunks(chunks: list[str]) -> tuple[str, list[list[float]]]:
    """
    Embed chunks with Gemini, falling back to the local model if Gemini fails.

    Returns:
        (collection_name, embeddings) so callers store vectors with matching dimensions.
    """
    try:
        embeddings: list[list[float]] = []
        for i in range(0, len(chunks), _EMBED_BATCH_SIZE):
            embeddings.extend(_embed_texts(chunks[i:i + _EMBED_BATCH_SIZE], "RETRIEVAL_DOCUMENT"))
        return GEMINI_COLLECTION, embeddings
    except Exception as e:
        logger.warning(f"Gemini embeddings failed ({e}); using local embedding fallback")
    return LOCAL_COLLECTION, _local_embed(chunks)


def extract_text(file_path: str, filename: str, status_callback=None) -> str:
    """
    Extract text from a PDF or TXT file.

    Args:
        file_path: Absolute path to the file on disk.
        filename: Original filename, used to determine file type.

    Returns:
        Extracted text as a single string.

    Raises:
        ValueError: If the file extension is not supported.
        RuntimeError: If text extraction fails.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "txt":
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError as e:
            raise RuntimeError(f"Failed to read text file '{filename}': {e}") from e

    elif ext == "pdf":
        try:
            doc = fitz.open(file_path)
            pages = [page.get_text() for page in doc]
            page_count = len(doc)
            doc.close()
            text = "\n".join(pages)
            if len(text.strip()) >= 20:
                return text

            logger.info("Falling back to OCR for %s", filename)
            if status_callback:
                status_callback()

            from pdf2image import convert_from_path
            import pytesseract

            images = convert_from_path(
                file_path,
                first_page=1,
                last_page=min(page_count, _OCR_MAX_PAGES),
            )
            ocr_text = "\n".join(pytesseract.image_to_string(image) for image in images)
            if not ocr_text.strip():
                raise RuntimeError(
                    f"No readable text could be extracted from PDF '{filename}'. "
                    "The file may be scanned or image-based."
                )
            return ocr_text
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from PDF '{filename}': {e}") from e

    else:
        raise ValueError(
            f"Unsupported file type '{ext}' for '{filename}'. Accepted formats: pdf, txt."
        )


# 1 token ≈ 4 characters
_CHUNK_SIZE_CHARS = 500 * 4   # 2000 chars
_OVERLAP_CHARS = 50 * 4       # 200 chars


def chunk_text(text: str) -> list[str]:
    """
    Split text into chunks of ~500 tokens (2000 chars) with ~50-token (200-char) overlap.

    Returns:
        List of chunk strings. Returns an empty list if text is empty.
    """
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE_CHARS
        chunks.append(text[start:end])
        start += _CHUNK_SIZE_CHARS - _OVERLAP_CHARS

    return chunks


def embed_and_store(document_id: str, chunks: list[str], filename: str, upload_date: str) -> None:
    """
    Generate embeddings for each chunk via Gemini and store them in a shared
    ChromaDB collection 'all_documents' with metadata tagging.

    Args:
        document_id: UUID string of the Document record.
        chunks: List of text chunk strings.
        filename: Original filename stored as metadata.
        upload_date: ISO format upload timestamp.

    Raises:
        RuntimeError: If embedding or storage fails.
    """
    if not chunks:
        return

    try:
        collection_name, embeddings = embed_chunks(chunks)
    except Exception as e:
        raise RuntimeError(f"Failed to generate embeddings: {e}") from e

    try:
        chroma = get_chroma_client()
        collection = chroma.get_or_create_collection(name=collection_name)
        collection.upsert(
            ids=[f"{document_id}_chunk_{i}" for i in range(len(chunks))],
            documents=chunks,
            embeddings=embeddings,
            metadatas=[{
                "source": filename,
                "doc_id": document_id,
                "upload_date": upload_date,
                "chunk_index": i,
            } for i in range(len(chunks))],
        )
    except Exception as e:
        raise RuntimeError(f"Failed to store embeddings in ChromaDB: {e}") from e


def process_document(document_id: str) -> None:
    """
    Background task: extract text → chunk → embed and store.
    Updates Document.status to 'ready' on success or 'error' on failure.
    """
    # Import here to avoid circular imports
    from .models import Document

    close_old_connections()
    try:
        doc = Document.objects.get(id=document_id)

        def mark_ocr_processing():
            doc.status = "processing_ocr"
            doc.save(update_fields=["status"])

        text = extract_text(doc.file_path, doc.filename, status_callback=mark_ocr_processing)
        chunks = chunk_text(text)
        embed_and_store(str(doc.id), chunks, doc.filename, doc.created_at.isoformat())
        doc.status = "ready"
        doc.error_message = ""
        doc.save()
    except Exception as e:
        logger.exception("Document processing failed for %s", document_id)
        try:
            doc = Document.objects.get(id=document_id)
            doc.status = "error"
            doc.error_message = str(e)
            doc.save()
        except Exception:
            pass
    finally:
        close_old_connections()


def delete_document_from_chromadb(document_id: str) -> None:
    """
    Delete all chunks for a specific document from ChromaDB using metadata filtering.

    Args:
        document_id: UUID string of the Document record.

    Raises:
        RuntimeError: If deletion fails.
    """
    try:
        chroma = get_chroma_client()
        for name in DOCUMENT_COLLECTIONS:
            try:
                collection = chroma.get_collection(name=name)
            except Exception:
                continue
            # Get all chunk IDs for this document
            results = collection.get(where={"doc_id": {"$eq": document_id}})
            if results["ids"]:
                collection.delete(ids=results["ids"])
    except Exception as e:
        raise RuntimeError(f"Failed to delete document from ChromaDB: {e}") from e
