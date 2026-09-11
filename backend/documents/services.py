import os
import threading
import math
import chromadb
import fitz  # PyMuPDF
import cohere
from django.conf import settings

# Persistent ChromaDB stored on disk so data survives across requests
_CHROMA_PATH = os.path.join(settings.BASE_DIR, "chroma_db")
_CHUNK_SIZE_CHARS = 500 * 4
_OVERLAP_CHARS = 50 * 4
_COHERE_EMBED_BATCH = 50


def _get_chroma_client():
    return chromadb.PersistentClient(path=_CHROMA_PATH)


def _get_cohere_client():
    return cohere.Client(settings.COHERE_API_KEY)


def extract_text(file_path: str, filename: str) -> str:
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
            doc.close()
            text = "\n".join(pages)
            if not text.strip():
                raise RuntimeError(
                    f"No readable text could be extracted from PDF '{filename}'. "
                    "The file may be scanned or image-based."
                )
            return text
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
    Generate embeddings for each chunk via Cohere and store them in a shared
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
        co = _get_cohere_client()
        embeddings: list[list[float]] = []
        for i in range(0, len(chunks), _COHERE_EMBED_BATCH):
            batch = chunks[i:i + _COHERE_EMBED_BATCH]
            response = co.embed(
                texts=batch,
                model="embed-english-v3.0",
                input_type="search_document",
            )
            embeddings.extend(response.embeddings)
    except Exception as e:
        raise RuntimeError(f"Failed to generate embeddings: {e}") from e

    try:
        chroma = _get_chroma_client()
        collection = chroma.get_or_create_collection(name="all_documents")
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

    try:
        doc = Document.objects.get(id=document_id)
        text = extract_text(doc.file_path, doc.filename)
        chunks = chunk_text(text)
        embed_and_store(str(doc.id), chunks, doc.filename, doc.created_at.isoformat())
        doc.status = "ready"
        doc.error_message = ""
        doc.save()
    except Exception as e:
        try:
            doc = Document.objects.get(id=document_id)
            doc.status = "error"
            doc.error_message = str(e)
            doc.save()
        except Exception:
            pass


def delete_document_from_chromadb(document_id: str) -> None:
    """
    Delete all chunks for a specific document from ChromaDB using metadata filtering.

    Args:
        document_id: UUID string of the Document record.

    Raises:
        RuntimeError: If deletion fails.
    """
    try:
        chroma = _get_chroma_client()
        collection = chroma.get_collection(name="all_documents")
        
        # Get all chunk IDs for this document
        results = collection.get(
            where={"doc_id": document_id}
        )
        
        if results["ids"]:
            collection.delete(ids=results["ids"])
    except Exception as e:
        raise RuntimeError(f"Failed to delete document from ChromaDB: {e}") from e
