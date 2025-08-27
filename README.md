# AI Gateway

An intelligent document processing and AI-powered query platform built with a microservices architecture. The system enables document upload, processing, semantic search, summarization, translation, and AI-powered question answering through a unified gateway API.

## Architecture

**Applications:**
- **Gateway** (Port 3000) - Main API gateway with AI agent capabilities
- **Document Service** (Port 8000) - Document management and hybrid search

**MCP Services:**
- **RAG MCP** (Port 8002) - Retrieval-augmented generation
- **Summarization MCP** (Port 8003) - Document summarization
- **Translation MCP** (Port 8004) - Document translation

**Infrastructure:**
- **MongoDB** - Document and metadata storage
- **Qdrant** - Vector database for semantic search
- **LiteLLM** - AI model proxy and management
- **PostgreSQL** - LiteLLM configuration storage


## Documentation

- **[Developer Guide](docs/developer.md)** - Setup, installation, and development workflow
- **[Customer Guide](docs/customer.md)** - API documentation and service descriptions
