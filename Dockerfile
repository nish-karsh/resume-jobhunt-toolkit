# Cloud image for the Resume Job-Hunt Toolkit (Streamlit, private).
# Defaults suit Hugging Face Spaces (Docker SDK), which expects port 7860.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHERUSAGESTATS=false \
    MODE=cloud \
    SETTINGS__MODE=cloud \
    DATA_DIR=/data \
    PORT=7860

# System libraries for WeasyPrint (Pango/Cairo/GDK-Pixbuf) + fonts.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
        libcairo2 libffi8 shared-mime-info \
        fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt requirements-cloud.txt ./
RUN pip install -r requirements-cloud.txt

COPY . .

# Writable, persistable data dir (mount a volume here to keep the job DB + tracker).
RUN mkdir -p /data && chmod 777 /data

EXPOSE 7860

# HF Spaces / most PaaS set $PORT; default to 7860.
CMD ["sh", "-c", "streamlit run app.py --server.port ${PORT:-7860} --server.address 0.0.0.0"]
