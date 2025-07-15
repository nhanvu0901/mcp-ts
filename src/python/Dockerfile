FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    gosu \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/uploads && \
    mkdir -p logs

RUN useradd --create-home --shell /bin/bash mcp && \
    chown -R mcp:mcp /app

# Create supervisor configuration
RUN mkdir -p /etc/supervisor/conf.d
COPY supervisord.conf /etc/supervisor/conf.d/

# Create startup script
RUN echo '#!/bin/bash\n\
# Fix permissions for the mounted volume\n\
chown -R mcp:mcp /app/data/uploads\n\
# Start supervisor as mcp user\n\
exec gosu mcp supervisord -c /etc/supervisor/conf.d/supervisord.conf' > /start-services.sh && \
    chmod +x /start-services.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

VOLUME ["/app/data/uploads"]

# Expose all service ports
EXPOSE 8000 8002 8003 8004

ENTRYPOINT ["/start-services.sh"]