# Použitie oficiálneho Python obrazu s verziou 3.11
FROM docker.asseco-ce.com/ai_dev/docker/python_node:python3.13-nodejs24

# Nastavenie pracovného adresára
WORKDIR /app

# Kopírovanie požiadaviek
COPY requirements.txt requirements.txt

# Aktualizácia pip
RUN pip install --upgrade pip

# Inštalácia závislostí
RUN pip install --no-cache-dir -r requirements.txt

# Kopírovanie zdrojového kódu
COPY mcps/translation-mcp/translation-mcp/ .

# Nastavenie premenných prostredia (voliteľné)
ENV PYTHONUNBUFFERED=1
ENV QDRANT_HOST=localhost

EXPOSE 8004

CMD ["python", "server.py"]