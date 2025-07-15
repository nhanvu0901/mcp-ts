# Fastify MCP RAG Application

A TypeScript/Fastify application with LangGraph and MCP integration for document processing and RAG (Retrieval-Augmented Generation).

## Prerequisites

- Node.js LTS (version >=18)
- Docker and Docker Compose
- Python 3.11+

## Installation & Setup

### 1. Clone Repository and Install Dependencies

```bash
git clone <your-repo-url>
cd ai-assistant
npm install
```

### 2. Environment Configuration

Create `.env` file from example:
```bash
cp .env.example .env
```



### 3. Start Docker Services

Start MongoDB and Qdrant services:
```bash
docker-compose up -d
```

### 4. Setup FastAPI Document Service

Navigate to the document service directory:
```bash
cd src/python/document-service
```

Create and activate Python virtual environment:
```bash
python -m venv .venv

# Windows
.venv/Scripts/Activate.ps1

# Linux/Mac
source .venv/bin/activate
```

Install Python dependencies:
```bash
pip3 install -r requirements.txt
```

Start the FastAPI server:
```bash
uvicorn main:app --reload
```

### 5. Start TypeScript MCP RAG Server

In a new terminal, navigate to the MCP server directory:
```bash
cd src/mcpserver
npm install
npm run dev:rag
```

### 6. Start Main Application

In another terminal, start the main Fastify application:
```bash
npm run dev
```

## API Documentation

Access the API documentation at:
- Main API: http://localhost:3000/docs
- Document Service: http://localhost:8000/docs
- RAG Service: http://localhost:8002

## Services Overview

- **Main Application** (Port 3000): Fastify server with document upload and agent endpoints
- **Document Service** (Port 8000): FastAPI service for document processing and MongoDB storage
- **RAG Service** (Port 8002): MCP server for vector search and retrieval
- **MongoDB** (Port 27017): Document storage
- **Qdrant** (Port 6333): Vector database

## Development Workflow

1. Start Docker services: `docker-compose up -d mongodb qdrant`
2. Start FastAPI document service: `cd src/python/document-service && uvicorn main:app --reload`
3. Start RAG MCP server: `cd src/mcpserver && npm run dev:rag`
4. Start main application: `npm run dev`
5. Access Swagger documentation for API testing

## Quick Start Commands

```bash
# Start all services in order
docker-compose up -d mongodb qdrant

# Terminal 1: Document Service
cd src/python/document-service
.venv/Scripts/Activate.ps1  # or source .venv/bin/activate
uvicorn main:app --reload

# Terminal 2: RAG Service
cd src/mcpserver
npm run dev:rag

# Terminal 3: Main Application
npm run dev
```