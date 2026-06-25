FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PyMuPDF and pdfplumber
RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Copy PDFs (context must be project root: docker build -f backend/Dockerfile .)
COPY PDF/ ./PDF/

EXPOSE 8000

# entrypoint: ingest on first start if chroma_db is empty, then serve
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
