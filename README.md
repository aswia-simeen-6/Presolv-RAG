# Presolv RAG — Annual Report Q&A Agent

A production-ready Retrieval-Augmented Generation (RAG) system for querying multiple annual report PDFs via natural language. Ask questions, get cited answers with page references — including data extracted from charts and graphs.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          INGESTION PIPELINE                         │
│                                                                     │
│  PDF Files                                                          │
│  (Annual Reports)                                                   │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐  │
│  │  pdfplumber │────▶│  Text Extraction │     │  PyMuPDF (fitz) │  │
│  │  (primary)  │     │  + Table rows    │     │  (fallback)     │  │
│  └─────────────┘     └────────┬─────────┘     └────────┬────────┘  │
│                               │                         │           │
│                               ▼                         │           │
│                    ┌──────────────────────┐             │           │
│                    │   Section Header     │             │           │
│                    │   Detection          │             │           │
│                    │  (annual report      │             │           │
│                    │   patterns)          │             │           │
│                    └──────────┬───────────┘             │           │
│                               │                         │           │
│                               ▼                         ▼           │
│                    ┌──────────────────────┐  ┌──────────────────┐  │
│                    │  Sentence-Aware      │  │  Image Detection │  │
│                    │  Chunking            │  │  (>10k px)       │  │
│                    │  800 chars / 150     │  └────────┬─────────┘  │
│                    │  overlap             │           │             │
│                    └──────────┬───────────┘           ▼             │
│                               │              ┌──────────────────┐  │
│                               │              │  Groq Vision     │  │
│                               │              │  llama-4-scout   │  │
│                               │              │  Chart/Graph     │  │
│                               │              │  Description     │  │
│                               │              └────────┬─────────┘  │
│                               │                       │             │
│                               ▼                       ▼             │
│                    ┌─────────────────────────────────────────────┐  │
│                    │   [Section: <title>]\n<chunk text>          │  │
│                    │   chunk_type: "text" | "image_description"  │  │
│                    └────────────────────┬────────────────────────┘  │
│                                         │                           │
│                                         ▼                           │
│                    ┌─────────────────────────────────────────────┐  │
│                    │   all-MiniLM-L6-v2  (local, 384-dim)        │  │
│                    │   Batch embedding — no API, no rate limits   │  │
│                    └────────────────────┬────────────────────────┘  │
│                                         │                           │
│                                         ▼                           │
│                    ┌─────────────────────────────────────────────┐  │
│                    │   ChromaDB  (persistent, cosine similarity)  │  │
│                    └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                          QUERY PIPELINE                             │
│                                                                     │
│   User Question                                                     │
│        │                                                            │
│        ▼                                                            │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │  Stage 1 — Bi-Encoder Retrieval                              │  │
│   │  all-MiniLM-L6-v2 encodes the question → cosine similarity   │  │
│   │  against ChromaDB → top 16 candidates (threshold 0.25)       │  │
│   └───────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│                               ▼                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │  Stage 2 — Cross-Encoder Reranking                           │  │
│   │  BAAI/bge-reranker-base scores each (question, chunk) pair   │  │
│   │  jointly → re-sorts → top 5 sent to LLM                      │  │
│   └───────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│                               ▼                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │  Groq — llama-3.1-8b-instant                                 │  │
│   │  Streamed generation with strict citation rules              │  │
│   │  Output: answer tokens + <CITATIONS> JSON block              │  │
│   └───────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│                               ▼                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │  FastAPI  (SSE streaming)  →  React + Vite + TailwindCSS     │  │
│   │  Tokens streamed live — source cards with section + page     │  │
│   └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack & Design Decisions

### Embeddings — `sentence-transformers/all-MiniLM-L6-v2` (local)

**Chosen because:** runs entirely on CPU, no API key, no rate limits, no cost. At ingestion time for 6 × 120-page annual reports this matters — cloud embedding APIs charge per token and throttle free tiers hard.

**What was tried first:** Google's `text-embedding-004` via the Gemini API. It failed with a 404 because the free SDK (`google-generativeai`) targets the `v1beta` endpoint but `text-embedding-004` requires the stable `v1`. Downgrading to `embedding-001` resolved the 404 but immediately hit **429 RESOURCE_EXHAUSTED** — the Gemini free tier caps embedding at 100 requests/minute, which isn't enough for a 122-page PDF producing ~240 chunks (would take 3+ minutes per document with sleep padding, and the entire 6-PDF corpus would take ~20 minutes just for embeddings).

Switching to local sentence-transformers eliminated all of that: 6 PDFs embed in under 2 minutes on CPU with zero API calls.

**Trade-off:** MiniLM is a smaller model (384 dimensions vs 768+ for larger models). The 256-token context window means chunks are sized to 800 characters (~200 tokens) to stay safely within the truncation limit.

---

### LLM Generation — Groq (`llama-3.1-8b-instant`)

**Chosen because:** Groq's free tier is generous for generation (not embedding), and `llama-3.1-8b-instant` is extremely fast — tokens arrive in ~100ms. Streaming via `AsyncGroq` works natively with FastAPI's `StreamingResponse`.

**Why not Gemini Flash 2.5:** Google's `gemini-2.5-flash` is a strong model but the free tier for generation also hits `429 RESOURCE_EXHAUSTED` under any sustained load. Since this project already uses Groq for vision (see below), keeping a single provider simplifies key management and avoids cross-provider rate-limit juggling.

---

### Reranking — `BAAI/bge-reranker-base` (local cross-encoder)

The retrieval pipeline is two-stage:

1. **Bi-encoder (MiniLM)** — fast, approximate. Embeds question and chunks independently and compares vectors. Retrieves 16 candidates.
2. **Cross-encoder (BGE reranker)** — slow but precise. Sees the question and each chunk *together*, so it understands whether the chunk actually *answers* the question. Scores all 16, returns top 5 to the LLM.

**Why BGE over `ms-marco-MiniLM`:** MS MARCO cross-encoders are trained on web search queries. Annual reports are formal financial documents — a different domain. BGE reranker is trained on diverse retrieval datasets and consistently outperforms MS MARCO models on document retrieval benchmarks outside the web search domain.

**Cost:** ~120ms overhead per query (15ms × 8 chunks), runs locally, no API.

---

### Vector Store — ChromaDB (local persistent)

Persistent on disk (`./chroma_db`), cosine similarity space, metadata filtering support. No server to run — just a Python package. On Render, the ChromaDB directory is mounted on a persistent disk so indexes survive deploys.

---

### Visual Content (Charts & Graphs)

Annual reports are dense with financial charts — bar graphs, pie charts, waterfall charts, trend lines. Standard text extraction (`pdfplumber`) produces empty or garbage text for image-only pages.

**How it's handled:**

1. **Detection:** PyMuPDF scans each page's embedded images. Any image larger than 100×100 pixels (10,000 px threshold) is considered a potential chart — small images like logos and icons are skipped.

2. **Description:** The page is rendered at 2× resolution and sent to `meta-llama/llama-4-scout-17b-16e-instruct` (Groq Vision) with an annual-report-specific prompt asking it to extract specific numbers, percentages, axis labels, legends, and trends. If no meaningful visual content is found the model replies `NO_VISUAL_CONTENT` and the page is skipped.

3. **Storage:** Descriptions are stored as regular chunks with `chunk_type: "image_description"` metadata and the same section prefix as surrounding text. They participate in retrieval and reranking identically to text chunks.

4. **UI:** Source cards show a `📊 chart` badge when a citation comes from a visual chunk, so users know the answer drew from a chart rather than body text.

This means a query like "what was the revenue growth trend shown in the charts?" can surface actual chart descriptions with page citations.

---

## Chunking Strategy

| Phase | What it does |
|---|---|
| **Phase 1** | Sentence-aware splitting (800 chars / 150 overlap). Abbreviation masking prevents splits on "Rs.", "e.g.", "U.S." etc. Stays within MiniLM's 256-token window. |
| **Phase 2** | Section header detection for annual report patterns (numbered headings, ALL-CAPS titles, keyword prefixes like "Financial Statements", "Note 12"). Header text is prepended to every chunk in that section so context survives chunking. |
| **Phase 3** | Skipped — all 6 documents are annual reports with no FAQ sections. |
| **Phase 4** | PyMuPDF + Groq Vision for chart/graph pages (see above). |

Each chunk is stored with `section_title`, `chunk_type`, `doc_name`, and `page_num` metadata for display in citations.

---

## Project Structure

```
Presolv-Rag/
├── PDF/                        # Source annual report PDFs (6 files)
├── backend/
│   ├── ingest.py               # PDF → chunks → embeddings → ChromaDB
│   ├── rag.py                  # Retrieve → rerank → stream answer
│   ├── main.py                 # FastAPI app (SSE, upload endpoint)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env                    # GROQ_API_KEY, CHROMA_DIR, PDF_DIR
├── frontend/
│   └── src/
│       ├── App.jsx
│       └── components/
│           ├── ChatArea.jsx
│           ├── InputBar.jsx
│           ├── Message.jsx
│           ├── Sidebar.jsx     # Document list + PDF upload
│           └── SourceCard.jsx  # Citation cards with section + chart badge
└── render.yaml                 # Render.com deployment config
```

---

## Setup

### 1. Environment

```bash
cp backend/.env.example backend/.env
# Add your GROQ_API_KEY from console.groq.com (free)
```

### 2. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Ingest PDFs

```bash
cd backend

# Full ingestion with chart/graph extraction (recommended)
python ingest.py

# Text only — faster, skips vision API calls
python ingest.py --no-vision

# Single file
python ingest.py --file ../PDF/PDF1.pdf
```

First run downloads `all-MiniLM-L6-v2` (~90 MB) and `BAAI/bge-reranker-base` (~278 MB) — cached locally after that.

### 4. Run

```bash
# Terminal 1 — backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install && npm run dev
```

Open `http://localhost:5173`

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Server status + indexed flag |
| `GET` | `/documents` | List indexed document names |
| `POST` | `/query/stream` | SSE streaming Q&A (`{"question": "..."}`) |
| `POST` | `/ingest` | Re-index all PDFs (`?vision=false` to skip vision) |
| `POST` | `/ingest/upload` | Upload + index a new PDF (`?vision=false` optional) |

---

## Deployment (Render)

```bash
git push origin main   # Render auto-deploys on push
```

Set `GROQ_API_KEY` in Render dashboard → Environment. ChromaDB data persists on a 1 GB attached disk at `/data/chroma_db`. Run ingestion once after first deploy via the `/ingest` endpoint or by shelling in.
