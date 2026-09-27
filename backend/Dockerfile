# Image de l'API Flask (port 8002) — FS Market Intelligence
FROM python:3.12-slim

WORKDIR /app

# libglib2.0-0 : libs systeme pour le rendu PDF (pdfplumber)
# tesseract-ocr : binaire requis par pytesseract (extraction/arabic_ocr_extractor.py,
#   pages scannees AL_AMANAH_TAKAFUL, + bilan_kpi_extractor._ocr_words) - le
#   modele Arabe est fourni par extraction/tessdata_ara/ (commite au repo,
#   copie plus bas), pas besoin du paquet tesseract-ocr-ara
# ghostscript : requis par camelot-py flavor='stream' (extraction/full_table_extractor.py)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    tesseract-ocr \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY api/ ./api/
COPY database/ ./database/
COPY extraction/ ./extraction/
COPY config/ ./config/
COPY scraping/ ./scraping/

EXPOSE 8002

CMD ["gunicorn", "--bind", "0.0.0.0:8002", "--workers", "2", "--timeout", "120", "api.app:app"]
