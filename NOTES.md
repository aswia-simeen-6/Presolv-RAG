# Notes

## Approach

Built a RAG pipeline from raw SDKs — no LangChain or LlamaIndex. The core loop is: extract → chunk → embed → store → retrieve → rerank → generate → stream. Each step is explicit and debuggable.

The two decisions that mattered most: local embeddings (sentence-transformers) instead of a cloud API, and a two-stage retrieval pipeline (bi-encoder for recall, cross-encoder for precision). Local embeddings eliminated rate limits entirely — Gemini's free tier hit 429s on the second PDF. The BGE reranker costs ~120ms per query but meaningfully improves which chunks reach the LLM.

Chunking is domain-aware: section headers in annual reports are detected and prepended to every chunk in that section, so the embedding carries context the chunk text alone wouldn't have. Vision chunks (Groq + llama-4-scout) handle chart-heavy pages that pdfplumber extracts as blank.

## What I'd Do Differently in Production

- **Token-aware chunking** — current 800-char limit is approximate. MiniLM truncates at 256 tokens; financial tables hit that limit faster than prose. Should use the model's own tokenizer to hard-cap at 220 tokens.
- **Table isolation** — pdfplumber tables get fed into the sentence splitter and shredded mid-row. Tables should be kept atomic and serialized with headers repeated per chunk.
- **Persistent ChromaDB on a proper disk** — the Render config mounts a 1 GB disk, which works for 6 PDFs but not at scale. Would move to a managed vector DB (Pinecone or Qdrant Cloud) for multi-tenant or larger corpora.
- **Auth and rate limiting** — the API is fully open. In production, add API key auth on the FastAPI layer and per-user request throttling.

## Tradeoffs Made for the 2-Hour Budget

- **No tests** — the retrieval and chunking logic has enough edge cases to warrant unit tests (section header detection especially). Skipped deliberately.
- **No hybrid search** — BM25 alongside dense retrieval would improve recall for exact reference queries ("Note 32", specific line items). Deferred because the reranker compensates for most of that gap and adding BM25 would require maintaining a second index and RRF merging logic.
- **Vision is sequential** — chart descriptions are extracted one page at a time with a 2s sleep. A production system would parallelise this with a worker queue.
