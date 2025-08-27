<a id="readme-top"></a>

<div align="center">

![Docker](https://img.shields.io/badge/Docker-ready-blue?style=for-the-badge&logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-supported-blue?style=for-the-badge&logo=kubernetes&logoColor=white)

<br />
<h3 align="center">AI GATEWAY</h3>

<p align="center">
description
<br />
<a href="https://git.asseco-ce.com/ai_dev/AI_HUB/stt/server"><strong>Repository »</strong></a>
</p>
</div>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#environment-variables">Environment Variables</a></li>
    <li><a href="#docker-compose">Docker Compose</a></li>
    <li><a href="#mounting-file-volume">Mounting File Volume</a></li>
    <li><a href="#kubernetes-deployment">Kubernetes Deployment</a></li>
  </ol>
</details>

## Architecture Overview
The AI Gateway platform consists of several main components:

- **Gateway**: Node.js/TypeScript API server, main entrypoint for client requests. Handles routing, authentication, and orchestration.
- **Document, RAG MCP, Summarization MCP, Translation MCP**: Python microservices for document processing, retrieval-augmented generation, summarization, and translation. Communicate via REST endpoints (typically `/mcp`).
- **LiteLLM**: Proxy for LLM API calls, handles authentication, logging, and model selection. Connects to Azure OpenAI and other LLM providers.
- **MongoDB**: Stores documents, metadata, and user/session data.
- **Qdrant**: Vector database for semantic search and retrieval.
- **Postgres**: Used by LiteLLM for model and log storage.

**Data Flow:**
- Client → Gateway → (Document/RAG/Summarization/Translation MCP) → LiteLLM → LLM Provider
- Gateway and MCP services use MongoDB and Qdrant for persistence and search.
- LiteLLM uses Postgres for its own data.

**Deployment:**
- All components are containerized and orchestrated via Docker Compose or Kubernetes.

See diagrams and more details in the integration documentation or internal wiki if available.
## Environment Variables

Below is a full list of environment variables with example values and descriptions:

| Variable                                   | Description                         | Example Value                                                         |
| ------------------------------------------ | ----------------------------------- | --------------------------------------------------------------------- |
| `ALLOWED_ORIGIN`                           | Allowed origin for CORS             | `*`                                                                   |
| `AZURE_OPENAI_EMBEDDING_API_KEY`           | API key for Azure OpenAI embedding  | `your-embedding-api-key-here`                                         |
| `AZURE_OPENAI_EMBEDDING_ENDPOINT`          | Endpoint for Azure OpenAI embedding | `https://your-resource.openai.azure.com`                              |
| `LLM_EMBEDDING_MODEL`                      | Embedding model name                | `ace-text-embedding-3-large`                                          |
| `AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION` | API version for embedding model     | `2023-05-15`                                                          |
| `AZURE_OPENAI_API_KEY`                     | API key for Azure OpenAI chat       | `your-chat-api-key-here`                                              |
| `AZURE_OPENAI_ENDPOINT`                    | Endpoint for Azure OpenAI chat      | `https://your-resource.openai.azure.com`                              |
| `LLM_CHAT_MODEL`                           | Chat model name                     | `gpt-4o`                                                              |
| `AZURE_OPENAI_MODEL_API_VERSION`           | API version for chat model          | `2024-02-15-preview`                                                  |
| `LLM_RERANKER_MODEL`                       | Reranker model name                 | `gpt-4o-mini`                                                         |
| `LITELLM_APP_KEY`                          | LiteLLM application key             | `sk-1234`                                                             |
| `LITELLM_MASTER_KEY`                       | LiteLLM master key                  | `sk-1234`                                                             |
| `LITELLM_SALT_KEY`                         | LiteLLM salt key                    | `sk-salt-1234`                                                        |
| `LITELLM_UI`                               | Enable LiteLLM UI                   | `True`                                                                |
| `LITELLM_LOG`                              | Logging level                       | `INFO`                                                                |
| `LITELLM_DEBUG`                            | Enable debug mode                   | `False`                                                               |
| `LITELLM_DEFAULT_MODEL`                    | Default LiteLLM model               | `gpt-4o`                                                              |
| `LITELLM_STORE_MODEL_IN_DB`                | Store model in database             | `True`                                                                |
| `LITELLM_DATABASE_URL`                     | Database URL for LiteLLM            | `postgresql://litellm_user:litellm_password@localhost:5432/litellm`   |
| `LITELLM_PROXY_URL`                        | Proxy URL for LiteLLM               | `http://localhost:4000`                                               |
| `MONGO_INITDB_ROOT_USERNAME`               | MongoDB root username               | `root`                                                                |
| `MONGO_INITDB_ROOT_PASSWORD`               | MongoDB root password               | `rootPass`                                                            |
| `MONGODB_URI`                              | MongoDB connection URI              | `mongodb://root:rootPass@mongodb:27017/ai_assistant?authSource=admin` |
| `MONGODB_DB`                               | MongoDB database name               | `ai_assistant`                                                        |
| `QDRANT_URL`                               | Qdrant service URL                  | `http://qdrant:6333`                                                  |
| `QDRANT_HOST`                              | Qdrant host                         | `qdrant`                                                              |
| `QDRANT_PORT`                              | Qdrant port                         | `6333`                                                                |
| `MCP_SERVER_PORT`                          | MCP server port                     | `8001`                                                                |
| `RAG_MCP_URL`                              | URL for RAG MCP                     | `http://localhost:8002/mcp`                                           |
| `DOCDB_SUMMARIZATION_MCP_URL`              | URL for document summarization MCP  | `http://localhost:8003/mcp`                                           |
| `DOCUMENT_TRANSLATION_MCP_URL`             | URL for document translation MCP    | `http://localhost:8004/mcp`                                           |
| `SWAGGER_HOST`                             | Host pre Swagger dokumentáciu       | `http://localhost:3000`                                               |
| `NODE_ENV`                                 | Node.js environment                 | `development`                                                         |
| `DEBUG`                                    | Enable debugging                    | `true`                                                                |
| `TFIDF_MODELS_DIR`                         | Directory for TF-IDF models         | `/app/tfidf_models`                                                   |
| `ENABLE_QUERY_EXPANSION`                   | Enable query expansion              | `true`                                                                |
| `ENABLE_LLM_RERANKING`                     | Enable LLM reranking                | `true`                                                                |

> **Tip:** All these variables can be set directly in the `environment:` section of your `compose.yml` or as `env` in your Kubernetes manifests.

## Docker Compose

A sample `docker-compose.yml` might look like:

```yaml
services:
    gateway:
        image: docker.asseco-ce.com/ai_dev/ai_hub/ai-gateway/gateway:0.0.1
        container_name: gateway
        restart: unless-stopped
        ports:
            - "3000:3000"
        env_file:
            - .env
        environment:
            - MONGODB_URI=mongodb://root:rootPass@mongodb:27017/ai_assistant?authSource=admin
            - ALLOWED_ORIGINS=${ALLOWED_ORIGIN}
            - NODE_ENV=development
            - RAG_MCP_URL=http://rag-mcp:8002/mcp
            - DOCDB_SUMMARIZATION_MCP_URL=http://summarization-mcp:8003/mcp
            - DOCUMENT_TRANSLATION_MCP_URL=http://translation-mcp:8004/mcp
            - LITELLM_PROXY_URL=http://litellm:4000
            - LITELLM_APP_KEY=${LITELLM_APP_KEY}
            - AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
            - AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
            - LLM_CHAT_MODEL=${LLM_CHAT_MODEL}
            - AZURE_OPENAI_MODEL_API_VERSION=${AZURE_OPENAI_MODEL_API_VERSION}
        depends_on:
            - mongodb
            - qdrant
            - rag-mcp
            - summarization-mcp
            - translation-mcp

    document:
        image: docker.asseco-ce.com/ai_dev/ai_hub/ai-gateway/document:0.0.1
        container_name: document
        restart: unless-stopped
        ports:
            - "8000:8000"
        env_file:
            - .env
        environment:
            - MONGODB_URI=mongodb://root:rootPass@mongodb:27017/ai_assistant?authSource=admin
            - MONGODB_DB=${MONGODB_DB}
            - QDRANT_HOST=${QDRANT_HOST}
            - QDRANT_PORT=${QDRANT_PORT}
            - LITELLM_PROXY_URL=http://litellm:4000
            - LITELLM_APP_KEY=${LITELLM_APP_KEY}
            - LLM_CHAT_MODEL=${LLM_CHAT_MODEL}
            - LLM_EMBEDDING_MODEL=${LLM_EMBEDDING_MODEL}
            - LLM_RERANKER_MODEL=${LLM_RERANKER_MODEL}
        volumes:
            - ./tmp:/app/tfidf_models:rw
        depends_on:
            - qdrant
            - mongodb
            - litellm

    rag-mcp:
        image: docker.asseco-ce.com/ai_dev/ai_hub/ai-gateway/rag-mcp:0.0.1
        container_name: rag-mcp
        restart: unless-stopped
        ports:
            - "8002:8002"
        env_file:
            - .env
        environment:
            - MONGODB_URI=mongodb://root:rootPass@mongodb:27017/ai_assistant?authSource=admin
            - MONGODB_DB=${MONGODB_DB}
            - QDRANT_HOST=${QDRANT_HOST}
            - QDRANT_PORT=${QDRANT_PORT}
            - LITELLM_PROXY_URL=http://litellm:4000
            - LITELLM_APP_KEY=${LITELLM_APP_KEY}
            - LLM_CHAT_MODEL=${LLM_CHAT_MODEL}
            - LLM_EMBEDDING_MODEL=${LLM_EMBEDDING_MODEL}
            - LLM_RERANKER_MODEL=${LLM_RERANKER_MODEL}
            - ENABLE_QUERY_EXPANSION=${ENABLE_QUERY_EXPANSION}
            - ENABLE_LLM_RERANKING=${ENABLE_LLM_RERANKING}
        volumes:
            - ./tmp:/app/tfidf_models:rw
        depends_on:
            - mongodb
            - qdrant
            - litellm

    summarization-mcp:
        image: docker.asseco-ce.com/ai_dev/ai_hub/ai-gateway/summarization-mcp:0.0.1
        container_name: summarization-mcp
        restart: unless-stopped
        ports:
            - "8003:8003"
        env_file:
            - .env
        environment:
            - MONGODB_URI=mongodb://root:rootPass@mongodb:27017/ai_assistant?authSource=admin
            - MONGODB_DB=${MONGODB_DB}
            - QDRANT_HOST=${QDRANT_HOST}
            - QDRANT_PORT=${QDRANT_PORT}
            - LITELLM_PROXY_URL=http://litellm:4000
            - LITELLM_APP_KEY=${LITELLM_APP_KEY}
            - LLM_CHAT_MODEL=${LLM_CHAT_MODEL}
            - LLM_RERANKER_MODEL=${LLM_RERANKER_MODEL}
        depends_on:
            - mongodb
            - qdrant
            - litellm

    translation-mcp:
        image: docker.asseco-ce.com/ai_dev/ai_hub/ai-gateway/translation-mcp:0.0.1
        container_name: translation-mcp
        restart: unless-stopped
        ports:
            - "8004:8004"
        env_file:
            - .env
        environment:
            - MONGODB_URI=mongodb://root:rootPass@mongodb:27017/ai_assistant?authSource=admin
            - MONGODB_DB=${MONGODB_DB}
            - QDRANT_HOST=${QDRANT_HOST}
            - QDRANT_PORT=${QDRANT_PORT}
            - LITELLM_PROXY_URL=http://litellm:4000
            - LITELLM_APP_KEY=${LITELLM_APP_KEY}
            - LLM_CHAT_MODEL=${LLM_CHAT_MODEL}
            - LLM_RERANKER_MODEL=${LLM_RERANKER_MODEL}
        depends_on:
            - mongodb
            - qdrant
            - litellm

    postgres:
        image: postgres:15-alpine
        container_name: postgres
        restart: unless-stopped
        ports:
            - "5432:5432"
        environment:
            POSTGRES_DB: litellm
            POSTGRES_USER: litellm_user
            POSTGRES_PASSWORD: litellm_password
            POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=C"
        volumes:
            - postgres_data:/var/lib/postgresql/data

    litellm:
        image: ghcr.io/berriai/litellm:main-latest
        container_name: litellm
        restart: unless-stopped
        ports:
            - "4000:4000"
        environment:
            DATABASE_URL: "postgresql://litellm_user:litellm_password@postgres:5432/litellm"
            STORE_MODEL_IN_DB: "True"
            DISABLE_DATABASE: "False"
            LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY}
            LITELLM_SALT_KEY: ${LITELLM_SALT_KEY}
            LITELLM_APP_KEY: ${LITELLM_APP_KEY}
            LITELLM_LOG: ${LITELLM_LOG}
            AZURE_OPENAI_API_KEY: ${AZURE_OPENAI_API_KEY}
            AZURE_OPENAI_ENDPOINT: ${AZURE_OPENAI_ENDPOINT}
            AZURE_OPENAI_MODEL_API_VERSION: ${AZURE_OPENAI_MODEL_API_VERSION}
            AZURE_OPENAI_EMBEDDING_API_KEY: ${AZURE_OPENAI_EMBEDDING_API_KEY}
            AZURE_OPENAI_EMBEDDING_ENDPOINT: ${AZURE_OPENAI_EMBEDDING_ENDPOINT}
            AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION: ${AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION}
            LITELLM_UI: ${LITELLM_UI}
            LITELLM_DEBUG: ${LITELLM_DEBUG}
        volumes:
            - ./litellm.yaml:/app/config.yaml:ro
        depends_on:
            - postgres
        command: [ "--config", "/app/config.yaml", "--port", "4000", "--num_workers", "1" ]

    mongodb:
        image: mongo:8.0.11
        container_name: mongodb
        restart: unless-stopped
        ports:
            - "27017:27017"
        environment:
            MONGO_INITDB_ROOT_USERNAME: ${MONGO_INITDB_ROOT_USERNAME}
            MONGO_INITDB_ROOT_PASSWORD: ${MONGO_INITDB_ROOT_PASSWORD}
            MONGO_INITDB_DATABASE: ai_assistant
        volumes:
            - mongodb_data:/data/db
            - ./mongo.js:/docker-entrypoint-initdb.d/mongo-init.js:ro

    qdrant:
        image: qdrant/qdrant:latest
        container_name: qdrant
        restart: unless-stopped
        ports:
            - "6333:6333"
        volumes:
            - qdrant_data:/qdrant/storage

volumes:
    mongodb_data:
    qdrant_data:
    postgres_data:

```

Start everything with:

```sh
docker-compose up -d
```

## Mounting File Volume

Some services (e.g., document processing, RAG MCP) persist TF‑IDF models or cache files. In Docker Compose this is already mapped:

- Host: `./tmp`
- Container: `/app/tfidf_models`

Notes:
- Ensure the directory exists and is writable by Docker: `mkdir -p ./tmp && chmod -R 775 ./tmp`.
- In Kubernetes, use a PersistentVolumeClaim and mount it at `/app/tfidf_models`.
- Optionally set `TFIDF_MODELS_DIR=/app/tfidf_models` to make the path explicit.


## Kubernetes Deployment

### Gateway

A minimal Kubernetes deployment example:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gateway
spec:
  replicas: 1
  selector:
    matchLabels:
      app: gateway
  template:
    metadata:
      labels:
        app: gateway
    spec:
      containers:
        - name: gateway
          envFrom:
            - configMapRef:
                name: ai-gateway-env
          image: docker.asseco-ce.com/ai_dev/ai_hub/ai-gateway/gateway:0.0.1
          ports:
            - containerPort: 3000
          volumeMounts: null
      volumes: null
---
apiVersion: v1
kind: Service
metadata:
  name: gateway
spec:
  type: ClusterIP
  ports:
    - port: 3000
      targetPort: 3000
  selector:
    app: gateway
```

### Document

A minimal Kubernetes deployment example:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: document
spec:
  replicas: 1
  selector:
    matchLabels:
      app: document
  template:
    metadata:
      labels:
        app: document
    spec:
      containers:
        - name: document
          envFrom:
            - configMapRef:
                name: ai-gateway-env
          image: docker.asseco-ce.com/ai_dev/ai_hub/ai-gateway/document:0.0.1
          ports:
            - containerPort: 8000
---
apiVersion: v1
kind: Service
metadata:
  name: document
spec:
  type: ClusterIP
  ports:
    - port: 8000
      targetPort: 8000
  selector:
    app: document
```

### RAG MCP

A minimal Kubernetes deployment example:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-mcp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: rag-mcp
  template:
    metadata:
      labels:
        app: rag-mcp
    spec:
      containers:
        - name: rag-mcp
          envFrom:
            - configMapRef:
                name: ai-gateway-env
          image: docker.asseco-ce.com/ai_dev/ai_hub/ai-gateway/rag-mcp:0.0.1
          ports:
            - containerPort: 8002
---
apiVersion: v1
kind: Service
metadata:
  name: rag-mcp
spec:
  type: ClusterIP
  ports:
    - port: 8002
      targetPort: 8002
  selector:
    app: rag-mcp
```

### Summarization MCP

A minimal Kubernetes deployment example:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: summarization-mcp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: summarization-mcp
  template:
    metadata:
      labels:
        app: summarization-mcp
    spec:
      containers:
        - name: summarization-mcp
          envFrom:
            - configMapRef:
                name: ai-gateway-env
          image: docker.asseco-ce.com/ai_dev/ai_hub/ai-gateway/summarization-mcp:0.0.1
          ports:
            - containerPort: 8003
---
apiVersion: v1
kind: Service
metadata:
  name: summarization-mcp
spec:
  type: ClusterIP
  ports:
    - port: 8003
      targetPort: 8003
  selector:
    app: summarization-mcp
```

### Translation MCP

A minimal Kubernetes deployment example:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: translation-mcp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: translation-mcp
  template:
    metadata:
      labels:
        app: translation-mcp
    spec:
      containers:
        - name: translation-mcp
          envFrom:
            - configMapRef:
                name: ai-gateway-env
          image: docker.asseco-ce.com/ai_dev/ai_hub/ai-gateway/translation-mcp:0.0.1
          ports:
            - containerPort: 8004
---
apiVersion: v1
kind: Service
metadata:
  name: translation-mcp
spec:
  type: ClusterIP
  ports:
    - port: 8004
      targetPort: 8004
  selector:
    app: translation-mcp
```

### LiteLLM

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: litellm-config-file
data:
  config.yaml: |
      model_list: 
        - model_name: gpt-4o
          litellm_params:
            model: azure/gpt-4o-ca
            api_base: https://my-endpoint-canada-berri992.openai.azure.com/
            api_key: os.environ/CA_AZURE_OPENAI_API_KEY
---
apiVersion: v1
kind: Secret
type: Opaque
metadata:
  name: litellm-secrets
data:
  CA_AZURE_OPENAI_API_KEY: bWVvd19pbV9hX2NhdA== # your api key in base64
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm-deployment
  labels:
    app: litellm
spec:
  selector:
    matchLabels:
      app: litellm
  template:
    metadata:
      labels:
        app: litellm
    spec:
      containers:
      - name: litellm
        image: ghcr.io/berriai/litellm:main-stable
        env:
            - name: AZURE_API_KEY
              value: "d6******"
            - name: AZURE_API_BASE
              value: "https://ope******"
            - name: LITELLM_MASTER_KEY
              value: "sk-1234"
            - name: DATABASE_URL
              value: "po**********"
        args:
          - "--config"
          - "/app/proxy_server_config.yaml"
        ports:
        - containerPort: 4000
        volumeMounts:
        - name: config-volume
          mountPath: /app/proxy_server_config.yaml
          subPath: config.yaml
        envFrom:
        - secretRef:
            name: litellm-secrets
      volumes:
        - name: config-volume
          configMap:
            name: litellm-config-file
---
apiVersion: v1
kind: Service
metadata:
  name: litellm
spec:
  type: ClusterIP
  ports:
    - port: 4000
      targetPort: 4000
  selector:
    app: litellm
```

### Mongo

- Credentials: configured via `MONGO_INITDB_ROOT_USERNAME` and `MONGO_INITDB_ROOT_PASSWORD`.
- Initialization: `mongo.js` is mounted to `/docker-entrypoint-initdb.d/` to seed databases or create indexes at startup.
- Volumes: use `mongodb_data` in Docker, or a PVC in Kubernetes for persistence.
- Backup/restore (examples):
  - Backup: `docker exec mongodb mongodump --out=/backup && docker cp mongodb:/backup ./mongo-backup`.
  - Restore: `docker cp ./mongo-backup mongodb:/restore && docker exec mongodb mongorestore /restore`.
- Health: consider readiness/liveness probes on `mongodb` when running on Kubernetes.

### Qdrant

- Persistence: `qdrant_data` volume in Docker; use a PVC in Kubernetes.
- Basic checks:
  - List collections: `curl http://localhost:6333/collections`.
  - Health: `curl http://localhost:6333/healthz`.
- Backups: schedule persistent volume snapshots or use Qdrant snapshot APIs. Keep snapshots and DB backups consistent.

