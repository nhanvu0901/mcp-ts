# Developer Guide

## Prerequisites

Before starting, ensure you have the following installed:
- **Docker & Docker Compose** - For running infrastructure services
- **Node.js** (v18 or higher) - For JavaScript/TypeScript applications
- **Python** (v3.8 or higher) - For Python applications
- **Git** - For version control

## Install Tools and Dependencies

### Install `just` Task Runner

Choose the installation method for your operating system:

#### **Windows**
```powershell
# Option 1: Using Chocolatey
choco install just

# Option 2: Using Scoop
scoop install just

# Option 3: Using Cargo (if Rust is installed)
cargo install just

# Option 4: Download binary directly
# Visit https://github.com/casey/just/releases
# Download the Windows binary and add to PATH
```

#### **macOS**
```bash
# Using Homebrew
brew install just

# Using MacPorts
sudo port install just
```

#### **Linux**
```bash
# Ubuntu / Debian
sudo apt install just

# Arch Linux
sudo pacman -S just

# CentOS / RHEL / Fedora
sudo dnf install just

# Or using Cargo
cargo install just
```

### Install Project Dependencies

After installing `just`, install NX CLI, Node.js, and Python dependencies:

```bash
just install
```


## Development Workflow

### **Detailed Setup Steps**

1. **Install Dependencies**
   ```bash
   npm install
   ```

2. **Build the Project**
   ```bash
   just build
   ```

3. **Start Infrastructure with Docker Compose**
   ```bash
   just compose-up
   ```
   > This will run all services defined in `docker-compose.yml` in detached mode.

### **Available Commands**

To see all available just commands:
```bash
just --list
```

### **Start MCP Services**

To start all MCP applications at once:

```bash
just serve-mcp
```

This will start:
- `@mcp/rag-mcp`
- `@mcp/summarization-mcp`
- `@mcp/translation-mcp`

⚠️ **Note:** If you plan to run `serve-mcp` manually, make sure to **stop the MCP-related services in Docker Compose first**,
because they use the same ports and will cause conflicts.

### **Start the Gateway**

Once the MCP services are up and running, you can start the gateway:

```bash
just serve-gw
```

The gateway exposes the API that communicates with the MCP applications.

⚠️ **Note:** If you plan to run `serve-gw` manually, make sure to **stop the gateway service in Docker Compose first**
to avoid port conflicts.

### **Run All Applications in Development Mode**
```bash
just serve
```

### **Check Service Status**
```bash
# Check Docker services
docker ps

# Check specific ports (Windows)
netstat -an | findstr :3000

# Check specific ports (macOS/Linux)  
lsof -i :3000
```

## Stop Services

To stop the Docker Compose infrastructure:

```bash
just compose-down
```

## Environment Variables

### Azure OpenAI Configuration
- `AZURE_OPENAI_EMBEDDING_API_KEY` - API key for Azure OpenAI embedding services
- `AZURE_OPENAI_EMBEDDING_ENDPOINT` - Azure OpenAI endpoint URL for embeddings
- `LLM_EMBEDDING_MODEL` - Embedding model deployment name
- `AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION` - API version for embedding requests
- `AZURE_OPENAI_API_KEY` - API key for Azure OpenAI chat/completion services
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint URL for chat completions
- `LLM_CHAT_MODEL` - Chat model deployment name
- `AZURE_OPENAI_MODEL_API_VERSION` - API version for chat completion requests
- `LLM_RERANKER_MODEL` - Model used for result reranking

### LiteLLM Proxy Configuration
- `LITELLM_APP_KEY` - Application key for LiteLLM proxy authentication
- `LITELLM_MASTER_KEY` - Master key for LiteLLM proxy admin access
- `LITELLM_SALT_KEY` - Salt key for LiteLLM security
- `LITELLM_UI` - Enable LiteLLM web UI interface
- `LITELLM_LOG` - Logging level for LiteLLM
- `LITELLM_DEBUG` - Debug mode for LiteLLM
- `LITELLM_DEFAULT_MODEL` - Default model for LiteLLM requests
- `LITELLM_STORE_MODEL_IN_DB` - Store model configurations in database
- `LITELLM_DATABASE_URL` - PostgreSQL connection string for LiteLLM
- `LITELLM_PROXY_URL` - LiteLLM proxy server URL

### Database Configuration
- `MONGO_INITDB_ROOT_USERNAME` - MongoDB root username
- `MONGO_INITDB_ROOT_PASSWORD` - MongoDB root password
- `MONGODB_URI` - MongoDB connection string
- `MONGODB_DB` - Default MongoDB database name

### Vector Database Configuration
- `QDRANT_URL` - Qdrant vector database URL
- `QDRANT_HOST` - Qdrant service hostname
- `QDRANT_PORT` - Qdrant service port

### MCP Service Configuration

- `RAG_MCP_URL` - RAG MCP service endpoint URL
- `DOCDB_SUMMARIZATION_MCP_URL` - Document summarization MCP service endpoint
- `DOCUMENT_TRANSLATION_MCP_URL` - Document translation MCP service endpoint

### Application Settings
- `NODE_ENV` - Node.js environment mode
- `DEBUG` - Enable debug logging
- `TFIDF_MODELS_DIR` - Directory path for TF-IDF model storage
- `SWAGGER_HOST` - Host URL for Swagger documentation in production environments

### AI Features Configuration
- `ENABLE_QUERY_EXPANSION` - Enable automatic query expansion for better search results
- `ENABLE_LLM_RERANKING` - Enable LLM-based reranking of search results
