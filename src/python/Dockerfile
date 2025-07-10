FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/uploads && \
    mkdir -p logs

RUN useradd --create-home --shell /bin/bash mcp && \
    chown -R mcp:mcp /app

# Create an entrypoint script to fix permissions
RUN echo '#!/bin/bash\n\
# Fix permissions for the mounted volume\n\
chown -R mcp:mcp /app/data/uploads\n\
# Execute the command as the mcp user\n\
exec gosu mcp "$@"' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MCP_PORT=8001

VOLUME ["/app/data/uploads"]

EXPOSE 8001

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "mcp_servers/mcp_server_document.py"]