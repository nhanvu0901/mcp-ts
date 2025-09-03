<a id="readme-top"></a>

<div align="center">

![Guide](https://img.shields.io/badge/Guide-Developer-green?style=for-the-badge&logo=code&logoColor=white)

<br />
<h3 align="center">Developer Guide</h3>

<p align="center">
Setup, development, and environment documentation for contributors to the AI Gateway platform.<br />
<a href="https://gitlab/ai/AI_HUB/ai-gateway/ai-gateway"><strong>Repository »</strong></a>
</p>
</div>

<details>
   <summary>Table of Contents</summary>
   <ol>
      <li><a href="#prerequisites">Prerequisites</a></li>
      <li><a href="#install-tools-and-dependencies">Install Tools and Dependencies</a></li>
      <li><a href="#development-workflow">Development Workflow</a></li>
      <li><a href="#stop-services">Stop Services</a></li>
      <li><a href="#environment-variables">Environment Variables</a></li>
   </ol>
</details>

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
- `LLM_TRANSLATION_MODEL` - Chat model for the translation service
- `LLM_SUMERIZATION_MODEL` - Chat model for sumerization service
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
### Authorization

- `PUBLIC_KEY` - Public key for JWT token verification (used by Gateway and MCP services)
- `ISSUER` - JWT issuer URL (used for validating tokens)
- `API_KEY` - API key for internal service **authentication**

These variables should be set in your `.env` file. See `.env.example` for reference.

### How to Obtain a JWT Token for Testing

To test Gateway or MCP services, you need a valid JWT token. You can obtain one from Keycloak using the following request:

**Request:**

```http
POST https://keycloak.ai-itp-k8s.assecosk.local/realms/assistant/protocol/openid-connect/token
Content-Type: application/x-www-form-urlencoded

client_id=service-be&client_secret=nKYqSiWB2Juk2etpc8bLWN4JzqJwrf0B&grant_type=client_credentials
```

**Example using curl:**

```bash
curl -X POST \
  https://keycloak.ai-itp-k8s.assecosk.local/realms/assistant/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=service-be" \
  -d "client_secret=nKYqSiWB2Juk2etpc8bLWN4JzqJwrf0B" \
  -d "grant_type=client_credentials"
```

The response will contain an `access_token` field. Use this token in the `Authorization` header for requests to Gateway and MCP services:

```http
Authorization: Bearer <access_token>
```

**Note:**
- The token must be signed by the public key configured in your service (`PUBLIC_KEY`).
- The issuer must match the value in `ISSUER`.
- If the token is invalid or missing, you will receive a 401 Unauthorized error.

### How to Obtain Issuer and Public Key

You can retrieve the issuer URL and public key for JWT validation from the Keycloak well-known endpoint:

```
https://keycloak.ai-itp-k8s.assecosk.local/realms/assistant/.well-known/oauth-authorization-server
```

- The `issuer` field in the response provides the correct value for your `ISSUER` environment variable.
- The `jwks_uri` field provides the URL to fetch the public key (JWKS) for token verification. You can use this URL directly or extract the key as needed for your `PUBLIC_KEY` variable.

**Example response fields:**
```json
{
  "issuer": "https://keycloak.ai-itp-k8s.assecosk.local/realms/assistant",
  "jwks_uri": "https://keycloak.ai-itp-k8s.assecosk.local/realms/assistant/protocol/openid-connect/certs",
  ...
}
```

### Example Service Account Token

You can use the following example token for local development and testing as a service account:

```env
API_KEY="eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJXZ3E0V1dSS250cTBPSDF5SlpsVF9ST1NxUnBLRnR2VlpJNVM3VWtRaFBvIn0.eyJleHAiOjE3ODcyMjQ5MjEsImlhdCI6MTc1NTY4ODkyMSwianRpIjoiODg5MjdjOTMtZTgxYi00ODljLWE0MDItMTgxMmJhNzIyNTk5IiwiaXNzIjoiaHR0cHM6Ly9rZXljbG9hay5haS1pdHAtazhzLmFzc2Vjb3NrLmxvY2FsL3JlYWxtcy9hc3Npc3RhbnQiLCJhdWQiOiJhY2NvdW50Iiwic3ViIjoiYjZmZmNlOGEtMjYxMC00MzBmLTk3OGUtZmI4ZmRjYWJmMzZjIiwidHlwIjoiQmVhcmVyIiwiYXpwIjoic2VydmljZS1iZSIsImFjciI6IjEiLCJhbGxvd2VkLW9yaWdpbnMiOlsiKiJdLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsib2ZmbGluZV9hY2Nlc3MiLCJkZWZhdWx0LXJvbGVzLWFzc2lzdGFudCIsInVtYV9hdXRob3JizemF0aW9uIl19LCJyZXNvdXJjZV9hY2Nlc3MiOnsiYWNjb3VudCI6eyJyb2xlcyI6WyJtYW5hZ2UtYWNjb3VudCIsIm1hbmFnZS1hY2NvdW50LWxpbmtzIiwidmlldy1wcm9maWxlIl19fSwic2NvcGUiOiJwcm9maWxlIGVtYWlsIiwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJjbGllbnRIb3N0IjoiMTAuMjMzLjc3LjExMSIsInByZWZlcnJlZF91c2VybmFtZSI6InNlcnZpY2UtYWNjb3VudC1zZXJ2aWNlLWJlIiwiY2xpZW50QWRkcmVzcyI6IjEwLjIzMy43Ny4xMTEiLCJjbGllbnRfaWQiOiJzZXJ2aWNlLWJlIn0.1_Ylol43HWjiJoTwV46d51NdenCjzFq2Hk28LDVfSNUf50Jnobp8WPT9JP51BRxy2455eUhU0QQuTilQULQNfNJO178lnwdDb41kATfoF9mSrANNgVnMb_ylEAKv_2Sg0GKCwFIcF82y5nvLP2bK63OJesnCe_xC6ZzOs1U74YkOMIT6YDRYQxzBr3HuD703Fq7yxSHCWFd9O5e06yTZj9yj3AjMl_kU_mivbhKNc2RiLoKB792Vnl_bnGUvV5eQQj0TeqL_OrDaQrsv262j9BONxylGi6hMRsz2U9GosiG7bHXaTQ9jV_4crRe2mRyUH1BvKnbiSAVhl-RDMSkrWw"
```

**Description:**
- This is a JWT token for a service account (client_id: `service-be`).
- Use it for local/test/dev environments to authenticate requests to Gateway and MCP services.
- For production, always obtain a fresh token from Keycloak as described above.
