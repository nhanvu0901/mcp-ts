# Python Services

This directory contains a FastAPI document processing service and multiple MCP (Model Context Protocol) servers for document management, RAG retrieval, summarization, and translation.

## Services Overview

### Document Service (FastAPI)
- **Location**: `document-service/`
- **Port**: 8000
- **Purpose**: Document upload, processing, and management with vector embeddings
- **Features**: 
  - Document upload and storage
  - Text extraction and chunking
  - Vector embedding with Qdrant
  - Collection management
  - Document search and retrieval

### MCP Servers

#### RAG MCP Server
- **Location**: `rag-mcp/`
- **Port**: 8002
- **Purpose**: Vector search and document retrieval
- **Tools**: `retrieve()` - Query Qdrant for semantic document search

#### Summarization MCP Server
- **Location**: `summarization-mcp/`
- **Port**: 8003
- **Purpose**: Document summarization with configurable detail levels
- **Tools**: 
  - `summarize_by_detail_level()` - Summarize with level control (concise/medium/detailed)
  - `summarize_by_word_count()` - Summarize to target word count

#### Translation MCP Server
- **Location**: `translation-mcp/`
- **Port**: 8004
- **Purpose**: Document and text translation
- **Tools**:
  - `translate_document()` - Translate documents from MongoDB
  - `translate_text()` - Translate raw text

## Dependencies

### External Services
- **MongoDB**: Document metadata and text storage
- **Qdrant**: Vector database for embeddings (port 6333)
- **Azure OpenAI**: Embeddings and LLM services

### Required Environment Variables
```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_MODEL_NAME=your_model
AZURE_OPENAI_MODEL_API_VERSION=your_version
AZURE_OPENAI_EMBEDDING_ENDPOINT=your_embedding_endpoint
AZURE_OPENAI_EMBEDDING_API_KEY=your_embedding_key
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=your_embedding_model
AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION=your_embedding_version

# Database
MONGODB_URI=mongodb://localhost:27017
```

## Running the Services

### Option 1: Docker (Recommended)
```bash
# Build and run all services
docker build -t python-services .
docker run -p 8000:8000 -p 8002:8002 -p 8003:8003 -p 8004:8004 python-services
```

### Option 2: Individual Services
```bash
# Install dependencies
pip install -r requirements.txt

# Run document service
cd document-service
python main.py

# Run MCP servers (in separate terminals)
python rag-mcp/server.py
python summarization-mcp/server.py
python translation-mcp/server.py
```

### Option 3: Supervisor (Development)
```bash
pip install supervisor
supervisord -c supervisord.conf
```

## API Endpoints

### Document Service (http://localhost:8000)
- `POST /collections` - Create document collection
- `GET /collections` - List user collections
- `DELETE /collections/{id}` - Delete collection
- `POST /documents` - Upload document
- `GET /documents` - List documents
- `POST /documents/search` - Search documents
- `DELETE /documents/{id}` - Delete document
- `GET /health` - Health check

### MCP Servers
MCP servers use Server-Sent Events (SSE) transport and are designed to be consumed by MCP clients rather than direct HTTP calls.

## File Structure
```
src/python/
├── document-service/          # FastAPI document service
│   ├── main.py               # FastAPI application
│   └── services/             # Business logic modules
├── rag-mcp/                  # RAG retrieval MCP server
├── summarization-mcp/        # Document summarization MCP server
├── translation-mcp/          # Translation MCP server
├── requirements.txt          # Python dependencies
├── Dockerfile               # Multi-service container
└── supervisord.conf         # Process management config
```