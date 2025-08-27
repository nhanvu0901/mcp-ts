# Customer Guide

## API Documentation

### Gateway Service (Port 3000)

Base URL: `http://localhost:3000/docs`

#### AI Agent Endpoint

**POST /ask**

Process queries through AI agent with two distinct operational modes: query-based and intent-based.

#### Processing Overview

**Rules**:

- Either `query` or `intent` required (intent takes priority if both provided)
- `user_id` always required for authentication
- `session_id` auto-generated if not provided

**Modes**:

- **Query-based**: AI interprets natural language and selects tools automatically
- **Intent-based**: Direct execution of specified actions (summarise/translate/search)

#### Request Body

```json
{
  "query": "string (required if no intent, max 2000 chars)",
  "user_id": "string (required)",
  "session_id": "string (optional, auto-generated if not provided)",
  "collection_id": "string or array (optional)",
  "doc_id": "string (optional)",
  "intent": {
    "intent": "summarise | translate | search",
    "level": "concise | medium | detailed",
    "word_count": "number (10-2000)",
    "target_language": "string"
  }
}
```

**Field Descriptions:**

- **query**: The natural language question or search term to process through the AI agent. Required when intent is not provided. Maximum 2000 characters. Used for asking questions about documents, searching content, or requesting analysis.
- **user_id**: Unique identifier for the user making the request. Required for all requests. Used for authentication, document access control, and maintaining user-specific context.
- **session_id**: Identifier for conversation history. If not provided, the system auto-generates one using user_id and collection_id. Maintains chat history and context across multiple requests in the same conversation. **Frontend** should use the auto-generated ID from the response for subsequent requests to maintain conversation history.
- **collection_id**: Identifier(s) for document collection(s) to search within. Can be a single string or array of strings for multi-collection search. When provided, limits the search scope to specified collections. When not provided for general queries, the system searches external web sources instead of user documents. Required for search intent.
- **doc_id**: Specific document identifier for document-specific operations. Required for summarise and translate intents, which work directly with individual documents. For query operations, doc_id provides context to the AI agent but does not restrict RAG searches to that document - the RAG service will still search across all specified collections. If using doc_id with queries, collection_id should also be specified to define the search scope.

#### Intent-Specific Requirements

**Summarise Intent**

- Requires: `doc_id`
- Options: Either `level` OR `word_count` (not both)
- Validation: Fails if doc_id missing

**Translate Intent**

- Requires: `doc_id` and `target_language`
- Validation: Fails if either missing

**Search Intent**

- Optional: `collection_id` (single or array)
- Uses query parameter if provided for search terms
- Searches within user document collections, not external sources

#### Processing Flow

```
Request received
    ↓
Check if intent provided?
    ├─ YES → Validate intent requirements
    │         ├─ Valid → Process via IntentUtils
    │         └─ Invalid → Return error 400
    └─ NO → Check if query provided?
             ├─ YES → Process via AI Agent
             └─ NO → Return error 400
```

#### Response Structure

```json
{
  "success": true,
  "response": "string (AI or intent response)",
  "user_id": "string",
  "session_id": "string",
  "collection_id": "string or array",
  "timestamp": "ISO 8601 datetime",
  "query_type": "general | document_specific | intent_based",
  "intent_type": "summarise | translate | search (if intent used)",
  "source_references": [
    {
      "document_name": "string",
      "page_number": "number",
      "chunk_id": "number",
      "source_reference": "string",
      "reference_type": "page | chunk",
      "text_content": "string"
    }
  ],
  "sources_count": "number"
}
```

#### Error Responses

```json
{
  "success": false,
  "error": "string (error message)"
}
```

Status Codes:

- 400: Missing required fields or invalid intent configuration
- 500: Processing failure or service unavailable

#### API Documentation

**GET /docs**

- Swagger UI documentation interface

### Document Service (Port 8000)

Base URL: `http://localhost:8000/docs`

#### Collections

**POST /collections**

Creates a new document collection for organizing and grouping related files.

- Request Body:

    ```json
    {
      "name": "string",
      "user_id": "string"
    }
    ```

    - `name`: string (required) - Display name for the collection (e.g., "Q4 Reports", "Meeting Notes")
    - `user_id`: string (required) - Owner's unique identifier for access control and filtering

**GET /collections**

Retrieves all document collections belonging to a specific user.

- Query Parameters:
    - `user_id`: string (required) - Owner's identifier to filter collections (required for security)
- Response:

    ```json
    {
      "collections": [
        {
          "collection_id": "53bcca74-9d72-4558-bf03-e40cdc0be23d",
          "name": "ai",
          "user_id": "nhan"
        },
        {
          "collection_id": "fbab2daa-a245-48f3-a985-71a68ee3862f",
          "name": "pptx",
          "user_id": "nhan"
        }
      ]
    }
    ```

**DELETE /collections/{collection_id}**

Deletes a document collection and all associated documents.

- Path Parameters:
    - `collection_id`: string (required) - UUID of the collection to delete
- Query Parameters:
    - `user_id`: string (required) - Owner's identifier for authorization
- Response:

    ```json
    {
      "status": "deleted"
    }
    ```

- Note: Deletes the collection from both MongoDB and Qdrant vector store. All documents within the collection are permanently removed.

#### Documents

**POST /documents**

Uploads and processes a document file, with optional text embedding for search capabilities.

- Form Data:
    - `file`: File (required) - Document file to upload (PDF, DOC, TXT, etc.)
    - `user_id`: string (required) - Owner's identifier for access control and organization
    - `collection_id`: string (optional) - Target collection UUID for organizing the document. When left blank, the document is saved to a shared "default" collection where all users' documents without collection_id are stored together. This shared collection may have privacy implications as documents from different users exist in the same vector space.
    - `embed`: boolean (optional, default: true) - Generate text embeddings for semantic search functionality
- Response:

    ```json
    {
      "document_id": "string",
      "document_name": "string",
      "normalized_name": "string",
      "file_type": "string",
      "collection_id": "string",
      "status": "uploaded"
    }
    ```

**GET /documents**

Lists all documents for a specific user, optionally filtered by collection.

- Query Parameters:
    - `user_id`: string (required) - Owner's identifier to filter documents
    - `collection_id`: string (optional) - Filter documents by specific collection
- Response:

    ```json
    {
      "documents": [
        {
          "document_id": "string",
          "document_name": "string",
          "normalized_name": "string",
          "file_type": "string",
          "collection_id": "string",
          "upload_date": "datetime"
        }
      ]
    }
    ```

**DELETE /documents/{document_id}**

Deletes a specific document and all its associated chunks from both MongoDB and Qdrant.

- Path Parameters:
    - `document_id`: string (required) - UUID of the document to delete
- Query Parameters:
    - `user_id`: string (required) - Owner's identifier for authorization
- Response:

    ```json
    {
      "status": "deleted"
    }
    ```

- Note: Verifies ownership before deletion. Removes document from MongoDB and all associated chunks from Qdrant vector store.

**GET /documents/{document_id}**

Retrieves metadata and information about a specific document.

- Path Parameters:
    - `document_id`: string (required) - UUID of the document to retrieve
- Response:

    ```json
    {
      "document_id": "string",
      "document_name": "string",
      "normalized_name": "string",
      "file_type": "string",
      "user_id": "string",
      "collection_id": "string",
      "upload_date": "datetime"
    }
    ```

- Note: Returns document metadata only, not the actual document content. No user_id verification is performed, so any user can view metadata of any document if they know the document_id.

**GET /documents/{document_id}/status**

Checks the processing status of a specific document.

- Path Parameters:
    - `document_id`: string (required) - UUID of the document to check
- Response:

    ```json
    {
      "document_id": "string",
      "status": "ready | processing"
    }
    ```

- Note: Status is "ready" if document text has been extracted and stored, "processing" otherwise. No user authentication required.

**POST /documents/ocr**

Uploads a document with Optical Character Recognition (OCR) to extract text from images and scanned documents.

- Form Data:
    - `file`: File (required) - Image or scanned document file (PDF, JPG, PNG, etc.)
    - `user_id`: string (required) - Owner's identifier for access control and organization
    - `collection_id`: string (optional) - Target collection UUID for organizing the document (defaults to user's default collection)
    - `embed`: boolean (optional, default: false) - Generate text embeddings after OCR text extraction
    - `suggested_languages`: JSON array (optional, default: ["eng"]) - Language codes for OCR optimization (e.g., ["eng"] for English)
    - `use_llm`: boolean (optional, default: true) - Enable AI-powered text improvement and correction post-OCR
- Response:

    ```json
    {
      "document_id": "string",
      "message": "string",
      "chunks_created": "number (if embed=true)"
    }
    ```

**GET /documents/last-30-days**

Retrieves metadata for recently uploaded documents within the last 30 days for quick access and management.

- Query Parameters:
    - `user_id`: string (required) - Owner's identifier to filter documents (required for security and personalization)
- Response:

    ```json
    {
      "documents": [
        {
          "document_id": "string",
          "document_name": "string",
          "upload_date": "datetime",
          "file_type": "string"
        }
      ],
      "total_count": "number",
      "sync_timestamp": "ISO timestamp"
    }
    ```

**POST /documents/search**

Search documents with hybrid search.

- Request Body:

    ```json
    {
      "query": "string",
      "user_id": "string",
      "collection_id": "string (optional)",
      "search_type": "hybrid | dense | sparse (default: hybrid)",
      "dense_weight": "float (default: 0.6)",
      "limit": "integer (default: 10)"
    }
    ```

- Response:

    ```json
    {
      "results": [
        {
          "document_id": "string",
          "document_name": "string",
          "page_number": "number (for PDF/DOC files)",
          "chunk_id": "number",
          "text": "string",
          "score": "float",
          "citation": "string",
          "reference_type": "page | chunk"
        }
      ],
      "total_found": "number",
      "query": "string",
      "search_type": "string",
      "dense_weight": "float (if hybrid)"
    }
    ```

- Note: When `collection_id` is not provided, searches within the shared "default" collection containing all users' documents without specific collections.

**POST /documents/query**

Advanced document query with filters.

- Request Body:

    ```json
    {
      "query": "string",
      "user_id": "string",
      "collection_id": "string (optional)",
      "search_type": "hybrid | dense | sparse | semantic (default: hybrid)",
      "dense_weight": "float (default: 0.6)",
      "limit": "integer (default: 10)",
      "filters": "object (optional)",
      "include_metadata": "boolean (default: true)",
      "include_text": "boolean (default: true)",
      "min_score": "float (default: 0.0)"
    }
    ```

- Response:

    ```json
    {
      "results": [
        {
          "document_id": "string",
          "document_name": "string",
          "page_number": "number (optional)",
          "chunk_id": "number",
          "score": "float",
          "citation": "string",
          "reference_type": "page | chunk",
          "text": "string (if include_text=true)",
          "metadata": "object (if include_metadata=true)"
        }
      ],
      "total_found": "number",
      "query": "string",
      "search_type": "string",
      "dense_weight": "float (if hybrid)",
      "filters_applied": "object",
      "min_score": "float",
      "collection_id": "string"
    }
    ```

- Note: When `collection_id` is not provided, searches within the shared "default" collection containing all users' documents without specific collections.

## MCP Services Integration

The gateway integrates with three MCP (Model Context Protocol) services:

### RAG MCP Service

- URL: `http://localhost:8002/mcp`
- Handles retrieval-augmented generation
- Used for document search and contextual responses

### Document Summarization MCP

- URL: `http://localhost:8003/mcp`
- Provides document summarization
- Supports:
    - Detail levels: concise, medium, detailed
    - Word count-based summarization (10-2000 words)

### Document Translation MCP

- URL: `http://localhost:8004/mcp`
- Handles document translation
- Supports multiple target languages
