import os
import threading
import math
import time
import logging
from array import array
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
            return _extract_pdf_text(file_path, filename, status_callback)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from PDF '{filename}': {e}") from e

    else:
        raise ValueError(
            f"Unsupported file type '{ext}' for '{filename}'. Accepted formats: pdf, txt."
        )


# --- OCR for scanned PDFs -------------------------------------------------
# RapidOCR runs PaddleOCR's PP-OCR models on ONNX Runtime: pip-only (no system
# binaries like tesseract/poppler, which the web host cannot install) and CPU-friendly.
# It runs in a separate short-lived process (ocr_worker.py) so the model's memory
# is freed after every document instead of staying inside the web worker.
_MIN_PAGE_TEXT_CHARS = 20        # pages with less embedded text are treated as scanned
_OCR_TIMEOUT_SECONDS = 15 * 60
_OCR_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr_worker.py")
_ocr_lock = threading.Lock()     # one OCR process at a time per web worker bounds memory


def _ocr_pages(file_path: str, page_indexes: list[int]) -> dict[int, str]:
    """OCR the given PDF pages in a child process; returns {page_index: text}."""
    import json
    import subprocess
    import sys

    with _ocr_lock:
        try:
            completed = subprocess.run(
                [sys.executable, _OCR_WORKER, file_path, *map(str, page_indexes)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=_OCR_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("OCR took too long and was stopped.") from e
    if completed.returncode != 0:
        reason = (completed.stderr or "").strip().splitlines()
        if completed.returncode < 0 or completed.returncode == 137:
            raise RuntimeError("OCR ran out of memory on this document.")
        raise RuntimeError(f"OCR is unavailable: {reason[-1] if reason else 'unknown error'}")
    marker = "__OCR_RESULT__"
    lines = [line for line in (completed.stdout or "").splitlines() if line.startswith(marker)]
    if not lines:
        raise RuntimeError("OCR returned no result.")
    return {int(k): v for k, v in json.loads(lines[-1][len(marker):]).items()}


def _extract_pdf_text(file_path: str, filename: str, status_callback=None) -> str:
    """Embedded text per page; pages without it (scans) go through OCR, up to _OCR_MAX_PAGES."""
    with fitz.open(file_path) as doc:
        pages_text = [page.get_text() for page in doc]

    scanned = [i for i, text in enumerate(pages_text) if len(text.strip()) < _MIN_PAGE_TEXT_CHARS]
    scanned = scanned[:_OCR_MAX_PAGES]
    if scanned:
        logger.info("Running OCR on %s scanned page(s) of %s", len(scanned), filename)
        if status_callback:
            status_callback()
        for index, text in _ocr_pages(file_path, scanned).items():
            pages_text[index] = text

    full_text = "\n".join(pages_text)
    if len(full_text.strip()) < _MIN_PAGE_TEXT_CHARS:
        raise RuntimeError(
            f"No readable text could be extracted from PDF '{filename}'. "
            "The scan may be blank, too blurry, or handwritten."
        )
    return full_text


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

    # Database copy first: it survives restarts, ChromaDB on local disk does not
    save_chunks_to_db(document_id, chunks, embeddings, collection_name)

    try:
        _upsert_chroma(collection_name, document_id, chunks, embeddings, filename, upload_date)
        _indexed_documents.add(document_id)
    except Exception as e:
        raise RuntimeError(f"Failed to store embeddings in ChromaDB: {e}") from e


def _pack_embedding(vector: list[float]) -> bytes:
    return array("f", vector).tobytes()


def _unpack_embedding(data) -> list[float]:
    values = array("f")
    values.frombytes(bytes(data))
    return values.tolist()


def save_chunks_to_db(document_id: str, chunks: list[str], embeddings: list[list[float]], collection_name: str) -> None:
    from .models import DocumentChunk

    DocumentChunk.objects.filter(document_id=document_id).delete()
    DocumentChunk.objects.bulk_create([
        DocumentChunk(
            document_id=document_id,
            chunk_index=i,
            text=chunk,
            embedding=_pack_embedding(vector),
            collection=collection_name,
        )
        for i, (chunk, vector) in enumerate(zip(chunks, embeddings))
    ], batch_size=100)


def _upsert_chroma(collection_name, document_id, chunks, embeddings, filename, upload_date, indexes=None):
    indexes = list(indexes) if indexes is not None else list(range(len(chunks)))
    collection = get_chroma_client().get_or_create_collection(name=collection_name)
    collection.upsert(
        ids=[f"{document_id}_chunk_{i}" for i in indexes],
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{
            "source": filename,
            "doc_id": document_id,
            "upload_date": upload_date,
            "chunk_index": i,
        } for i in indexes],
    )


# Documents this process has confirmed are in ChromaDB (reset when the process restarts)
_indexed_documents: set[str] = set()
_index_lock = threading.Lock()


def _chroma_has_document(document_id: str) -> bool:
    chroma = get_chroma_client()
    for name in DOCUMENT_COLLECTIONS:
        try:
            collection = chroma.get_collection(name=name)
        except Exception:
            continue
        if collection.get(where={"doc_id": {"$eq": document_id}}, limit=1, include=[])["ids"]:
            return True
    return False


def _backfill_db_from_chroma(document_id: str) -> None:
    """Copy a document stored before chunks were kept in the database."""
    chroma = get_chroma_client()
    for name in DOCUMENT_COLLECTIONS:
        try:
            collection = chroma.get_collection(name=name)
        except Exception:
            continue
        results = collection.get(
            where={"doc_id": {"$eq": document_id}},
            include=["documents", "metadatas", "embeddings"],
        )
        if not results["ids"]:
            continue
        rows = sorted(
            zip(results["metadatas"], results["documents"], results["embeddings"]),
            key=lambda row: row[0].get("chunk_index", 0),
        )
        save_chunks_to_db(document_id, [r[1] for r in rows], [list(r[2]) for r in rows], name)
        return


def ensure_documents_indexed(documents) -> None:
    """
    Make sure each ready document's chunks are in ChromaDB, rebuilding them from
    the database after the host's disk was wiped. Cheap after the first call per process.
    """
    from .models import DocumentChunk

    for doc in documents:
        doc_id = str(doc.id)
        if doc.status != "ready" or doc_id in _indexed_documents:
            continue
        with _index_lock:
            if doc_id in _indexed_documents:
                continue
            try:
                stored = list(DocumentChunk.objects.filter(document_id=doc_id).order_by("chunk_index"))
                if _chroma_has_document(doc_id):
                    if not stored:
                        _backfill_db_from_chroma(doc_id)
                elif stored:
                    logger.info("Restoring %s chunks for document %s into ChromaDB", len(stored), doc_id)
                    by_collection: dict[str, list] = {}
                    for chunk in stored:
                        by_collection.setdefault(chunk.collection, []).append(chunk)
                    for name, rows in by_collection.items():
                        _upsert_chroma(
                            name,
                            doc_id,
                            [r.text for r in rows],
                            [_unpack_embedding(r.embedding) for r in rows],
                            doc.filename,
                            doc.created_at.isoformat(),
                            indexes=[r.chunk_index for r in rows],
                        )
                else:
                    logger.warning("Document %s has no stored chunks to restore", doc_id)
                    continue
                _indexed_documents.add(doc_id)
            except Exception:
                logger.exception("Could not restore document %s into ChromaDB", doc_id)


def get_document_text(document_id: str) -> str:
    """Full document text from the database copy; empty string if none is stored."""
    from .models import DocumentChunk

    texts = DocumentChunk.objects.filter(document_id=document_id).order_by("chunk_index").values_list("text", flat=True)
    return "\n\n".join(texts)


def delete_document_completely(doc) -> None:
    """Remove a document's vectors, file on disk and database rows (chunks, sessions, flashcards cascade)."""
    doc_id = str(doc.id)
    try:
        delete_document_from_chromadb(doc_id)
    except Exception:
        logger.exception("Failed to remove document %s from ChromaDB", doc_id)
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError:
            logger.warning("Could not remove file %s", doc.file_path)
    _indexed_documents.discard(doc_id)
    doc.delete()


_PURGE_INTERVAL_SECONDS = 10 * 60
_last_purge = 0.0


def purge_expired_documents(force: bool = False) -> int:
    """Delete documents past their retention window. Runs at most every 10 minutes unless forced."""
    global _last_purge
    from .models import Document

    now = time.monotonic()
    if not force and now - _last_purge < _PURGE_INTERVAL_SECONDS:
        return 0
    _last_purge = now

    count = 0
    for doc in Document.objects.expired():
        delete_document_completely(doc)
        count += 1
    if count:
        logger.info("Purged %s expired documents", count)
    return count


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
