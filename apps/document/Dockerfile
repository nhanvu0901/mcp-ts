# Použitie oficiálneho Python obrazu s verziou 3.11
FROM docker.asseco-ce.com/ai_dev/docker/python_node:python3.13-nodejs24

# Nastavenie pracovného adresára
WORKDIR /app

# Install system dependencies for document processing and OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gosu \
    supervisor \
    libreoffice \
    libmagic1 \
    catdoc \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-slk \
    tesseract-ocr-ces \
    poppler-utils \
    # OpenCV/OpenGL support
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /app/tfidf_models && \
    mkdir -p logs

# Create user and set permissions
RUN useradd --create-home --shell /bin/bash mcp && \
    chown -R mcp:mcp /app

# Kopírovanie požiadaviek
COPY requirements.txt requirements.txt

# Aktualizácia pip
RUN pip install --upgrade pip

# Inštalácia závislostí
RUN pip install --no-cache-dir -r requirements.txt

# Kopírovanie zdrojového kódu
COPY apps/document/document/ .

# Nastavenie premenných prostredia (voliteľné)
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Define volumes for persistent data
VOLUME ["/app/tfidf_models"]

EXPOSE 8000
# Spustenie aplikácie
CMD ["python", "main.py"]