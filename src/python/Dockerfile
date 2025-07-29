FROM python:3.11-slim

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

# Install Python dependencies with robust error handling
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 --retries 3 -r requirements.txt || \
    (echo "First attempt failed, trying with --force-reinstall" && \
     pip install --no-cache-dir --force-reinstall --default-timeout=100 -r requirements.txt)

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data/uploads && \
    mkdir -p /app/tfidf_models && \
    mkdir -p logs

# Create user and set permissions
RUN useradd --create-home --shell /bin/bash mcp && \
    chown -R mcp:mcp /app

# Setup supervisor configuration
RUN mkdir -p /etc/supervisor/conf.d
COPY supervisord.conf /etc/supervisor/conf.d/

# Create startup script with proper permission handling
RUN echo '#!/bin/bash\n\
# Fix permissions for the mounted volumes\n\
chown -R mcp:mcp /app/data/uploads\n\
chown -R mcp:mcp /app/tfidf_models\n\
# Start supervisor as mcp user\n\
exec gosu mcp supervisord -c /etc/supervisor/conf.d/supervisord.conf' > /start-services.sh && \
    chmod +x /start-services.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Define volumes for persistent data
VOLUME ["/app/data/uploads", "/app/tfidf_models"]

# Expose all service ports
EXPOSE 8000 8002 8003 8004

# Set entrypoint
ENTRYPOINT ["/start-services.sh"]