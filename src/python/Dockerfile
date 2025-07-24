FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    gosu \
    supervisor \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/uploads && \
    mkdir -p logs

RUN useradd --create-home --shell /bin/bash mcp && \
    chown -R mcp:mcp /app

RUN mkdir -p /etc/supervisor/conf.d
COPY supervisord.conf /etc/supervisor/conf.d/

RUN echo '#!/bin/bash\n\
chown -R mcp:mcp /app/data/uploads\n\
exec gosu mcp supervisord -c /etc/supervisor/conf.d/supervisord.conf' > /start-services.sh && \
    chmod +x /start-services.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

VOLUME ["/app/data/uploads"]

EXPOSE 8000 8002 8003 8004

ENTRYPOINT ["/start-services.sh"]