import threading
import fitz  # PyMuPDF
from google import genai
from google.genai import types
import chromadb
from django.conf import settings


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


def embed_and_store(document_id: str, chunks: list[str], filename: str) -> None:
    """
    Generate embeddings for each chunk via Gemini text-embedding-004 and store
    them in a ChromaDB collection named doc_{document_id}.

    Args:
        document_id: UUID string of the Document record.
        chunks: List of text chunk strings.
        filename: Original filename stored as metadata.

    Raises:
        RuntimeError: If embedding or storage fails.
    """
    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(api_version="v1beta"),
    )

    try:
        embeddings = [
            client.models.embed_content(
                model="gemini-embedding-001",
                contents=chunk,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            ).embeddings[0].values
            for chunk in chunks
        ]
    except Exception as e:
        raise RuntimeError(f"Failed to generate embeddings: {e}") from e

    try:
        client = chromadb.Client()
        collection = client.get_or_create_collection(name=f"doc_{document_id}")
        collection.upsert(
            ids=[f"chunk_{i}" for i in range(len(chunks))],
            documents=chunks,
            embeddings=embeddings,
            metadatas=[{"source": filename, "chunk_index": i} for i in range(len(chunks))],
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
        embed_and_store(str(doc.id), chunks, doc.filename)
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
