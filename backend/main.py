"""
FastAPI application — RAG Agent API
"""

import os
import json
import asyncio
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

import rag
import ingest as ingest_module

load_dotenv()

# ── config ────────────────────────────────────────────────────────────────────
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
PDF_DIR    = os.getenv("PDF_DIR",    "../PDF")

# ── app ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="RAG Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── models ────────────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str


# ── helpers ───────────────────────────────────────────────────────────────────
def _is_indexed() -> bool:
    """Return True if ChromaDB has been populated."""
    import chromadb
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        col = client.get_collection("documents")
        return col.count() > 0
    except Exception:
        return False


def _format_sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    indexed = _is_indexed()
    return {"status": "ok", "indexed": indexed}


@app.get("/documents")
def list_documents():
    """Return names of all indexed documents."""
    import chromadb
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        col = client.get_collection("documents")
        # Get distinct doc names from metadata
        result = col.get(include=["metadatas"])
        names = sorted({m["doc_name"] for m in result["metadatas"]})
        return {"documents": names}
    except Exception:
        # Fall back to PDF filenames if not yet indexed
        pdf_path = Path(PDF_DIR)
        if pdf_path.exists():
            names = sorted(p.stem for p in pdf_path.glob("*.pdf"))
            return {"documents": names, "indexed": False}
        return {"documents": [], "indexed": False}


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """Stream answer as Server-Sent Events."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if not _is_indexed():
        async def not_indexed():
            yield _format_sse({
                "type": "error",
                "message": "Documents not yet indexed. Run the ingestion script first: python ingest.py",
            })
        return StreamingResponse(not_indexed(), media_type="text/event-stream")

    async def event_stream():
        async for event in rag.stream_answer(request.question, CHROMA_DIR):
            yield _format_sse(event)
            await asyncio.sleep(0)   # yield control to event loop

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )


@app.post("/ingest")
def trigger_ingest(vision: bool = True):
    """Trigger ingestion of all PDFs in PDF_DIR. Pass ?vision=false to skip vision."""
    try:
        ingest_module.ingest(PDF_DIR, CHROMA_DIR, use_vision=vision)
        return {"status": "ok", "message": "Ingestion complete"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/upload")
async def ingest_upload(file: UploadFile = File(...), vision: bool = True):
    """Upload a PDF and immediately embed it into the vector store.

    Pass ?vision=false to skip Groq Vision (faster, text-only).
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Save to PDF_DIR so it persists alongside existing documents
    upload_dir = Path(PDF_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename

    try:
        with dest.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    finally:
        await file.close()

    try:
        chunks = await asyncio.to_thread(
            ingest_module.ingest_file, dest, CHROMA_DIR, vision
        )
    except Exception as e:
        dest.unlink(missing_ok=True)   # clean up saved file on failure
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok", "doc_name": dest.stem, "chunks": chunks}
