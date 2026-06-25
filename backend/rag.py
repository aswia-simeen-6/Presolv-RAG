"""
RAG pipeline: question -> retrieve -> rerank -> generate (streaming) -> citations
Embeddings:  sentence-transformers/all-MiniLM-L6-v2  (local)
Reranking:   BAAI/bge-reranker-base                  (local cross-encoder)
Generation:  Groq / llama-3.1-8b-instant             (streaming)
"""
import os, json, re
from typing import AsyncGenerator
import chromadb
from groq import AsyncGroq
from sentence_transformers import SentenceTransformer, CrossEncoder

COLLECTION_NAME  = "documents"
TOP_K_RETRIEVE   = 16    # wider first-pass; reranker cuts this down
TOP_K_RERANK     = 5     # final chunks sent to the LLM after reranking
SIM_THRESHOLD    = 0.25  # slightly looser: reranker handles final precision
EMBED_MODEL      = "all-MiniLM-L6-v2"
RERANK_MODEL     = "BAAI/bge-reranker-base"
GENERATION_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are a precise document assistant. Answer questions ONLY using the provided source documents.

RULES:
1. Base every answer solely on the [Source N] passages. Never use outside knowledge.
2. Cite every claim inline: [Source 1] or [Source 2, Source 3].
3. If context is insufficient, output exactly: INSUFFICIENT_CONTEXT
4. Be concise and direct.
5. At the very end, append:

<CITATIONS>
[{"doc": "<name>", "page": <num>, "excerpt": "<1-2 sentence quote>"}]
</CITATIONS>"""

_embedder          = None
_reranker          = None
_groq_client       = None
_chroma_collection = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def _get_reranker():
    global _reranker
    if _reranker is None:
        print("Loading reranker model (first run ~278 MB download)...")
        _reranker = CrossEncoder(RERANK_MODEL)
    return _reranker


def _get_groq():
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
    return _groq_client


def _get_collection(chroma_dir):
    global _chroma_collection
    if _chroma_collection is None:
        client = chromadb.PersistentClient(path=chroma_dir)
        _chroma_collection = client.get_collection(COLLECTION_NAME)
    return _chroma_collection


def retrieve(question, chroma_dir):
    """
    Two-stage retrieval:
      Stage 1 — bi-encoder (MiniLM) pulls TOP_K_RETRIEVE candidates by cosine similarity.
      Stage 2 — cross-encoder (BGE) scores each candidate against the question
                 and returns the top TOP_K_RERANK, re-indexed 1..N.
    """
    q_vec = _get_embedder().encode([question], show_progress_bar=False)[0].tolist()

    col = _get_collection(chroma_dir)
    res = col.query(
        query_embeddings=[q_vec],
        n_results=min(TOP_K_RETRIEVE, col.count()),
        include=["documents", "metadatas", "distances"],
    )

    candidates = [
        {
            "doc_name":      m["doc_name"],
            "page_num":      m["page_num"],
            "section_title": m.get("section_title", ""),
            "chunk_type":    m.get("chunk_type", "text"),
            "text":          doc,
            "similarity":    round(1 - dist, 4),
        }
        for doc, m, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        )
        if (1 - dist) >= SIM_THRESHOLD
    ]

    max_sim = max((c["similarity"] for c in candidates), default=0)

    if not candidates:
        return {"sources": [], "relevant": [], "max_similarity": max_sim}

    # Stage 2: cross-encoder reranking
    pairs  = [(question, c["text"]) for c in candidates]
    scores = _get_reranker().predict(pairs, show_progress_bar=False)

    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    top    = ranked[:TOP_K_RERANK]

    relevant = [
        {**c, "index": i + 1, "rerank_score": round(float(score), 4)}
        for i, (score, c) in enumerate(top)
    ]

    return {"sources": candidates, "relevant": relevant, "max_similarity": max_sim}


def build_prompt(question, sources):
    ctx = "\n\n---\n\n".join(
        f"[Source {s['index']}: {s['doc_name']}, Page {s['page_num']}]\n{s['text']}"
        for s in sources
    )
    return f"Context documents:\n\n{ctx}\n\n---\n\nQuestion: {question}"


def parse_citations(text):
    m = re.search(r"<CITATIONS>(.*?)</CITATIONS>", text, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(1).strip())
    except Exception:
        return []


async def stream_answer(question, chroma_dir) -> AsyncGenerator[dict, None]:
    try:
        retrieval = retrieve(question, chroma_dir)

        if not retrieval["relevant"]:
            yield {
                "type":           "refused",
                "message":        "I don't have enough information in the provided documents to answer this question.",
                "max_similarity": retrieval["max_similarity"],
            }
            return

        yield {"type": "sources", "sources": retrieval["relevant"]}

        prompt     = build_prompt(question, retrieval["relevant"])
        full_text  = ""
        sent_up_to = 0
        TAIL       = 20

        stream = await _get_groq().chat.completions.create(
            model=GENERATION_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            stream=True,
            max_tokens=2048,
            temperature=0.1,
        )

        hit_citations = False
        async for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if not token:
                continue

            full_text += token

            if "INSUFFICIENT_CONTEXT" in full_text:
                yield {
                    "type":           "refused",
                    "message":        "I don't have enough information in the provided documents to answer this question.",
                    "max_similarity": retrieval["max_similarity"],
                }
                return

            pos = full_text.find("<CITATIONS>")
            if pos != -1:
                unsent = full_text[sent_up_to:pos]
                if unsent:
                    yield {"type": "token", "content": unsent}
                hit_citations = True
                break
            else:
                safe = max(sent_up_to, len(full_text) - TAIL)
                if safe > sent_up_to:
                    yield {"type": "token", "content": full_text[sent_up_to:safe]}
                    sent_up_to = safe

        if not hit_citations and sent_up_to < len(full_text):
            yield {"type": "token", "content": full_text[sent_up_to:]}

        yield {"type": "citations", "citations": parse_citations(full_text)}
        yield {"type": "done"}

    except Exception as exc:
        yield {"type": "error", "message": str(exc)}
