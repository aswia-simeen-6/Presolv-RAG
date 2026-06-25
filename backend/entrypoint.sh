#!/bin/sh
set -e

CHROMA_DIR="${CHROMA_DIR:-./chroma_db}"
PDF_DIR="${PDF_DIR:-./PDF}"

# Run ingestion if ChromaDB hasn't been populated yet
if [ ! -d "$CHROMA_DIR" ] || [ -z "$(ls -A $CHROMA_DIR 2>/dev/null)" ]; then
    echo "🔄 ChromaDB empty — running ingestion..."
    python ingest.py --pdf-dir "$PDF_DIR" --chroma-dir "$CHROMA_DIR"
    echo "✅ Ingestion complete"
else
    echo "✅ ChromaDB already populated, skipping ingestion"
fi

echo "🚀 Starting API server..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
