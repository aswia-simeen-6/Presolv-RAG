#!/bin/bash
# start.sh — boot backend + frontend for local development
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  RAG Document Assistant — Local Dev"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Check .env ────────────────────────────────────────────────────────────────
if [ ! -f "$ROOT_DIR/backend/.env" ]; then
  echo ""
  echo "⚠️  backend/.env not found."
  echo "   Copy backend/.env.example → backend/.env and fill in your API keys."
  echo ""
  exit 1
fi

# ── Install Python deps ───────────────────────────────────────────────────────
echo ""
echo "📦 Installing Python dependencies..."
cd "$ROOT_DIR/backend"
pip install -r requirements.txt -q

# ── Ingest PDFs (if not already done) ────────────────────────────────────────
if [ ! -d "$ROOT_DIR/backend/chroma_db" ] || [ -z "$(ls -A $ROOT_DIR/backend/chroma_db 2>/dev/null)" ]; then
  echo ""
  echo "🔄 Indexing PDFs (first run — this may take a few minutes)..."
  python ingest.py
else
  echo "✅ ChromaDB already populated, skipping ingestion"
fi

# ── Install Node deps ─────────────────────────────────────────────────────────
echo ""
echo "📦 Installing frontend dependencies..."
cd "$ROOT_DIR/frontend"
npm install --silent

# ── Start both servers ────────────────────────────────────────────────────────
echo ""
echo "🚀 Starting servers..."
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both."
echo ""

# Run backend in background, frontend in foreground
cd "$ROOT_DIR/backend"
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

cd "$ROOT_DIR/frontend"
npm run dev

# Kill backend when frontend exits
kill $BACKEND_PID 2>/dev/null || true
