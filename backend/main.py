import io
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from rag import VectorStore, generate_answer

# ──────────────────────────────────────────────
#  App lifespan
# ──────────────────────────────────────────────
store = VectorStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Angel AI Backend – Gemini", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────
def extract_text(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    elif ext in (".docx",):
        import docx
        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        return content.decode("utf-8", errors="ignore")


# ──────────────────────────────────────────────
#  Routes
# ──────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "documents": len(store.chunks), "llm": "gemini-2.0-flash"}


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = extract_text(file.filename, content)
        added = store.add_document(text, file.filename)
        return {
            "success": True,
            "filename": file.filename,
            "chunks_added": added,
            "total_chunks": len(store.chunks),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/documents")
async def clear_documents():
    store.clear()
    return {"success": True, "message": "All documents cleared."}


class ChatRequest(BaseModel):
    query: str
    top_k: int = 5


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        results = store.search(req.query, req.top_k)
        context_chunks = [chunk for chunk, _, _ in results]
        sources = list({src for _, src, _ in results})
        answer = generate_answer(req.query, context_chunks)
        return {
            "answer": answer,
            "sources": sources,
            "context_used": len(context_chunks),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
