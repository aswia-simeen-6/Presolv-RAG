"""
Ingestion script: PDF -> chunks -> embeddings -> ChromaDB
Phase 1: sentence-aware chunking (800/150 chars, within MiniLM window)
Phase 2: section-aware chunking with header injection (annual reports)
Phase 4: graph/image description via Groq Vision
Run: python ingest.py              (all PDFs in PDF_DIR)
     python ingest.py --file x.pdf (single file)
     python ingest.py --no-vision  (skip vision processing)
"""
import os, sys, hashlib, argparse, re, base64, time
from pathlib import Path
import pdfplumber, fitz, chromadb
from sentence_transformers import SentenceTransformer
from groq import Groq as GroqSync
from dotenv import load_dotenv

load_dotenv()

CHUNK_CHARS     = 800
OVERLAP_CHARS   = 150
EMBED_BATCH     = 64
MIN_CHUNK_CHARS = 40
COLLECTION_NAME = "documents"
EMBED_MODEL     = "all-MiniLM-L6-v2"
VISION_MODEL    = "meta-llama/llama-4-scout-17b-16e-instruct"
VISION_SLEEP    = 2.0        # seconds between vision API calls
MIN_IMG_PIXELS  = 10_000     # ignore images smaller than ~100×100 px

_embedder   = None
_groq_sync  = None

def get_embedder():
    global _embedder
    if _embedder is None:
        print("  Loading embedding model...")
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder

def get_groq():
    global _groq_sync
    if _groq_sync is None:
        _groq_sync = GroqSync(api_key=os.environ["GROQ_API_KEY"])
    return _groq_sync


# ── PDF extraction ─────────────────────────────────────────────────────────────

def extract_pages(pdf_path):
    """Extract text per page using pdfplumber (fitz fallback)."""
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                for table in (page.extract_tables() or []):
                    for row in table:
                        if row:
                            text += "\n" + " | ".join(str(c).strip() if c else "" for c in row)
                pages.append({"page_num": i + 1, "text": text.strip()})
    except Exception as e:
        print(f"  pdfplumber failed ({e}), falling back to PyMuPDF")
        doc = fitz.open(str(pdf_path))
        for i, page in enumerate(doc):
            pages.append({"page_num": i + 1, "text": page.get_text("text").strip()})
        doc.close()
    return pages


# ── Phase 2: Section header detection (annual reports) ────────────────────────

_HEADER_PATTERNS = [
    re.compile(r'^(\d{1,2}\.?(\d{1,2}\.?)*)\s+[A-Z][A-Za-z\s\-&,()]{2,60}$'),
    re.compile(r'^(Note|Notes|Schedule|Annexure|Appendix|Exhibit)\s+\d+[\s:\-]', re.IGNORECASE),
    re.compile(r'^[A-Z][A-Z\s\-&/,()\']{4,60}$'),
    re.compile(
        r'^(Chairman|Managing Director|CEO|CFO|Board|Directors|Auditor|'
        r'Financial|Management|Corporate|Risk|Governance|Sustainability|'
        r'Overview|Highlights|Performance|Strategy|Outlook|Report|'
        r'Statement|Balance Sheet|Profit|Loss|Cash Flow|Equity)',
        re.IGNORECASE
    ),
]

_NOISE_PATTERNS = [
    re.compile(r'\.\.\.\s*\d+$'),
    re.compile(r'\s{3,}\d+$'),
    re.compile(r'^\d+$'),
    re.compile(r'^(Page|Pg\.?)\s+\d+', re.IGNORECASE),
    re.compile(r'-$'),
    re.compile(r'^[a-z]'),
    re.compile(r',\s'),
    re.compile(r'\.\s+[a-z]'),
    re.compile(r'^([A-Z]\s){2,}'),
]

def is_section_header(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 80 or len(line) < 4:
        return False
    for noise in _NOISE_PATTERNS:
        if noise.search(line):
            return False
    if re.search(r'\.\s', line):
        return False
    for pattern in _HEADER_PATTERNS:
        if pattern.match(line):
            return True
    return False

def detect_section(lines: list) -> str | None:
    for line in lines:
        if is_section_header(line):
            return line.strip()
    return None


# ── Phase 1: Sentence-aware chunking ──────────────────────────────────────────

def split_sentences(text):
    abbrevs = (r'\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e|U\.S|U\.K|'
               r'approx|dept|est|govt|max|min|no|pp|vol|Rs|INR|USD|EUR|Fig|Sec|Art)\.')
    text = re.sub(abbrevs, lambda m: m.group(0).replace('.', '<DOT>'), text, flags=re.IGNORECASE)
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z\"\'])', text)
    return [p.replace('<DOT>', '.').strip() for p in parts if p.strip()]

def chunk_text(text, chunk_size=CHUNK_CHARS, overlap=OVERLAP_CHARS):
    sentences = split_sentences(text)
    if not sentences:
        return []
    chunks, current_sents, current_len = [], [], 0
    for sent in sentences:
        sent_len = len(sent)
        if current_sents and current_len + sent_len + 1 > chunk_size:
            chunks.append(" ".join(current_sents))
            overlap_sents, overlap_len = [], 0
            for s in reversed(current_sents):
                if overlap_len + len(s) + 1 <= overlap:
                    overlap_sents.insert(0, s)
                    overlap_len += len(s) + 1
                else:
                    break
            current_sents, current_len = overlap_sents, overlap_len
        if sent_len > chunk_size:
            if current_sents:
                chunks.append(" ".join(current_sents))
                current_sents, current_len = [], 0
            start = 0
            while start < sent_len:
                chunks.append(sent[start:min(start + chunk_size, sent_len)])
                start += chunk_size - overlap
        else:
            current_sents.append(sent)
            current_len += sent_len + 1
    if current_sents:
        chunks.append(" ".join(current_sents))
    return [c.strip() for c in chunks if len(c.strip()) >= MIN_CHUNK_CHARS]


# ── Phase 4: Vision processing ────────────────────────────────────────────────

def page_has_meaningful_images(fitz_page) -> bool:
    """Return True if the page has at least one image large enough to be a chart/graph."""
    for img in fitz_page.get_images(full=True):
        try:
            pix = fitz.Pixmap(fitz_page.parent, img[0])
            if pix.width * pix.height > MIN_IMG_PIXELS:
                return True
        except Exception:
            pass
    return False

def describe_page_visually(fitz_doc, page_idx: int) -> str | None:
    """Render a page as PNG and ask Groq Vision to describe charts/figures."""
    try:
        pix    = fitz_doc[page_idx].get_pixmap(matrix=fitz.Matrix(2, 2))
        b64    = base64.b64encode(pix.tobytes("png")).decode()

        resp = get_groq().chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text",
                     "text": (
                         "This is a page from an annual report. "
                         "Describe all charts, graphs, tables and figures visible. "
                         "Include specific numbers, percentages, trends, axis labels and legends. "
                         "If there are no charts or graphs, reply with exactly: NO_VISUAL_CONTENT"
                     )},
                ]
            }],
            max_tokens=600,
        )
        description = resp.choices[0].message.content.strip()
        if "NO_VISUAL_CONTENT" in description:
            return None
        return description
    except Exception as e:
        print(f"     Vision error: {e}")
        return None


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_texts(texts):
    return get_embedder().encode(texts, batch_size=EMBED_BATCH, show_progress_bar=False).tolist()


# ── Core ingestion ────────────────────────────────────────────────────────────

def ingest_file(pdf_path, chroma_dir, use_vision=True):
    pdf_path = Path(pdf_path)
    doc_name = pdf_path.stem

    chroma     = chromadb.PersistentClient(path=chroma_dir)
    collection = chroma.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    print(f"  {doc_name} ({pdf_path.stat().st_size // 1024} KB)")
    pages = extract_pages(pdf_path)
    print(f"   {len(pages)} pages")

    fitz_doc        = fitz.open(str(pdf_path))
    all_chunks      = []
    chunk_idx       = 0
    current_section = "General"
    vision_count    = 0

    for page in pages:
        page_idx = page["page_num"] - 1
        if not page["text"] and not use_vision:
            continue

        # Phase 2: section detection
        if page["text"]:
            new_section = detect_section(page["text"].splitlines()[:8])
            if new_section:
                current_section = new_section

        # Phase 1+2: text chunks with section prefix
        for ct in chunk_text(page["text"] or ""):
            prefixed = f"[Section: {current_section}]\n{ct}"
            cid = hashlib.md5(
                f"{doc_name}|{page['page_num']}|{chunk_idx}|{ct[:80]}".encode()
            ).hexdigest()
            all_chunks.append({
                "id": cid, "text": prefixed,
                "doc_name": doc_name, "page_num": page["page_num"],
                "section_title": current_section, "chunk_type": "text",
            })
            chunk_idx += 1

        # Phase 4: vision chunk for image-heavy pages
        if use_vision and page_idx < len(fitz_doc):
            fitz_page = fitz_doc[page_idx]
            if page_has_meaningful_images(fitz_page):
                cid_vision = hashlib.md5(
                    f"{doc_name}|vision|{page['page_num']}".encode()
                ).hexdigest()
                # Skip if already indexed
                if collection.get(ids=[cid_vision])["ids"]:
                    continue
                print(f"     Page {page['page_num']}: describing visuals...", end=" ", flush=True)
                description = describe_page_visually(fitz_doc, page_idx)
                if description:
                    vis_text = (f"[Section: {current_section}]\n"
                                f"[Visual content on page {page['page_num']}]\n"
                                f"{description}")
                    all_chunks.append({
                        "id": cid_vision, "text": vis_text,
                        "doc_name": doc_name, "page_num": page["page_num"],
                        "section_title": current_section, "chunk_type": "image_description",
                    })
                    vision_count += 1
                    print("done")
                else:
                    print("no visuals")
                time.sleep(VISION_SLEEP)

    fitz_doc.close()

    if not all_chunks:
        print("   No content extracted, skipping")
        return 0

    existing   = set(collection.get(ids=[c["id"] for c in all_chunks])["ids"])
    new_chunks = [c for c in all_chunks if c["id"] not in existing]

    if not new_chunks:
        print(f"   Already indexed ({len(all_chunks)} chunks), skipping")
        return 0

    print(f"   Embedding {len(new_chunks)} chunks ({vision_count} vision)...")
    embeddings = embed_texts([c["text"] for c in new_chunks])
    collection.add(
        ids        = [c["id"]   for c in new_chunks],
        embeddings = embeddings,
        documents  = [c["text"] for c in new_chunks],
        metadatas  = [{
            "doc_name":      c["doc_name"],
            "page_num":      c["page_num"],
            "section_title": c["section_title"],
            "chunk_type":    c["chunk_type"],
        } for c in new_chunks],
    )
    print(f"   Indexed {len(new_chunks)} chunks")

    sections = {}
    for c in new_chunks:
        sections[c["section_title"]] = sections.get(c["section_title"], 0) + 1
    print("   Sections detected:")
    for sec, cnt in list(sections.items())[:10]:
        print(f"     {sec[:60]:<60} {cnt:>3} chunks")
    if len(sections) > 10:
        print(f"     ... and {len(sections) - 10} more")
    return len(new_chunks)


def ingest(pdf_dir, chroma_dir, use_vision=True):
    pdf_dir   = Path(pdf_dir)
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found in {pdf_dir}")
        sys.exit(1)
    print(f"Found {len(pdf_paths)} PDFs")
    for pdf_path in pdf_paths:
        print(f"\nProcessing: {pdf_path.name}")
        ingest_file(pdf_path, chroma_dir, use_vision=use_vision)
    col = chromadb.PersistentClient(path=chroma_dir).get_collection(COLLECTION_NAME)
    print(f"\nDone -- {col.count()} total chunks in {chroma_dir!r}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir",    default=os.getenv("PDF_DIR",    "../PDF"))
    parser.add_argument("--chroma-dir", default=os.getenv("CHROMA_DIR", "./chroma_db"))
    parser.add_argument("--file",       default=None)
    parser.add_argument("--no-vision",  action="store_true", help="Skip vision processing")
    args = parser.parse_args()

    if args.file:
        ingest_file(args.file, args.chroma_dir, use_vision=not args.no_vision)
    else:
        ingest(args.pdf_dir, args.chroma_dir, use_vision=not args.no_vision)
