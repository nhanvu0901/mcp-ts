from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import tempfile
import uuid
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from langchain_openai import AzureOpenAIEmbeddings

load_dotenv()

from services.document_processor import DocumentProcessor
from services.mongo_service import MongoService
from services.config import MONGODB_URI
from datetime import datetime, timezone
app = FastAPI(title="Document Service API")

mongo_client = MongoClient(MONGODB_URI)
mongo_service = MongoService(mongo_client)
qdrant_host = os.getenv("QDRANT_HOST")

embedding_model = AzureOpenAIEmbeddings(
    azure_endpoint=os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION"),
    model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
)


class CollectionCreate(BaseModel):
    name: str
    user_id: str


class DocumentSearch(BaseModel):
    query: str
    user_id: str
    collection_id: Optional[str] = None
    search_type: Optional[str] = "hybrid"  # "hybrid", "dense", or "sparse"
    dense_weight: Optional[float] = 0.6
    limit: Optional[int] = 10


class DocumentQuery(BaseModel):
    query: str
    user_id: str
    collection_id: Optional[str] = None
    search_type: Optional[str] = "hybrid"  # "hybrid", "dense", "sparse", or "semantic"
    dense_weight: Optional[float] = 0.6
    limit: Optional[int] = 10
    filters: Optional[dict] = None  # Additional metadata filters
    include_metadata: Optional[bool] = True
    include_text: Optional[bool] = True
    min_score: Optional[float] = 0.0  # Minimum similarity score threshold

class DocumentOCRUpload(BaseModel):
    suggested_languages: Optional[List[str]] = ["eng"]
    use_llm: bool = True


@app.get("/documents/last-30-days")
async def get_document_references(user_id: str):
    """
        Get recent document metadata for a user.

        Returns document metadata (not full content) for documents uploaded
        in the last 30 days. Intended for syncing and recent activity displays.

        Args:
            user_id (str): User identifier to filter documents

        Returns:
            dict: Response containing:
                - documents: List of document metadata objects
                - total_count: Number of documents found
                - sync_timestamp: ISO timestamp of when data was retrieved
        """
    try:
        print(f"=== GET DOCUMENT REFERENCES (30 DAYS) ===")
        print(f"User ID: {user_id}")

        docs = mongo_service.list_user_documents_last_30_days(user_id)

        print(f"Found {len(docs)} documents from last 30 days")

        result = []
        for doc in docs:
            result.append({
                "document_id": doc["_id"],
                "document_name": doc.get("document_name"),
                "normalized_name": doc.get("normalized_name"),
                "collection_id": doc.get("collection_id"),
                "file_type": doc.get("file_type"),
                "upload_date": doc.get("upload_date")
            })

        return {
            "documents": result,
            "total_count": len(result),
            "sync_timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        print(f"Error getting document references: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/collections")
async def create_collection(collection: CollectionCreate):
    collection_id = str(uuid.uuid4())

    try:
        print(f"Creating hybrid collection: {collection.name} for user: {collection.user_id}")
        print(f"Generated collection_id: {collection_id}")

        try:
            from qdrant_client.models import (
                VectorParams, Distance, 
                SparseVectorParams, SparseIndexParams,
                BinaryQuantization, BinaryQuantizationConfig,
                OptimizersConfigDiff
            )
            
            qdrant_client = QdrantClient(host=qdrant_host, port=6333)

            if not qdrant_client.collection_exists(collection_id):
                # Create hybrid collection with both dense and sparse vectors
                qdrant_client.create_collection(
                    collection_name=collection_id,
                    vectors_config={
                        "text_dense": VectorParams(
                            size=3072,  # Azure OpenAI text-embedding-3-large
                            distance=Distance.COSINE,
                            on_disk=True
                        )
                    },
                    sparse_vectors_config={
                        "text_sparse": SparseVectorParams(
                            index=SparseIndexParams(on_disk=False)
                        )
                    },
                    # Performance optimizations
                    quantization_config=BinaryQuantization(
                        binary=BinaryQuantizationConfig(always_ram=True)
                    ),
                    optimizers_config=OptimizersConfigDiff(
                        max_segment_size=5_000_000
                    )
                )
                print(f"✅ Created hybrid Qdrant collection: {collection_id}")
            else:
                print(f"Qdrant collection already exists: {collection_id}")

        except Exception as qdrant_error:
            print(f"Qdrant error: {qdrant_error}")
            raise HTTPException(status_code=500, detail=f"Failed to create Qdrant collection: {str(qdrant_error)}")

        # Save to MongoDB with hybrid metadata
        success = mongo_service.save_collection(
            collection_id=collection_id,
            name=collection.name,
            user_id=collection.user_id,
            metadata={
                "created_at": uuid.uuid4().hex,
                "vector_config": "hybrid",
                "dense_size": 3072,
                "sparse_enabled": True,
                "embedding_model": "text-embedding-3-large"
            }
        )

        print(f"MongoDB save result: {success}")

        if success:
            return {
                "collection_id": collection_id,
                "name": collection.name,
                "status": "created",
                "type": "hybrid",
                "features": {
                    "dense_search": True,
                    "sparse_search": True,
                    "hybrid_ranking": True
                }
            }
        else:
            # Rollback: Delete Qdrant collection if MongoDB save failed
            try:
                qdrant_client.delete_collection(collection_id)
                print(f"Rollback: Deleted Qdrant collection {collection_id}")
            except:
                pass
            raise HTTPException(status_code=500, detail="Failed to create collection in MongoDB")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating hybrid collection: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create hybrid collection: {str(e)}")


@app.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str, user_id: str):
    try:
        collection_doc = mongo_service.get_collection(collection_id, user_id)

        if not collection_doc:
            raise HTTPException(status_code=404, detail="Collection not found")

        success = mongo_service.delete_collection(collection_id, user_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete collection from MongoDB")

        try:
            qdrant_client = QdrantClient(host=qdrant_host, port=6333)
            if qdrant_client.collection_exists(collection_id):
                qdrant_client.delete_collection(collection_id)
                print(f"Deleted Qdrant collection: {collection_id}")
        except Exception as e:
            print(f"Warning: Failed to delete Qdrant collection {collection_id}: {e}")

        return {"status": "deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/collections")
async def list_collections(user_id: str):
    try:
        collections = mongo_service.list_user_collections(user_id)

        result = []
        for col in collections:
            result.append({
                "collection_id": col.get("_id"),
                "name": col.get("name"),
                "user_id": col.get("user_id")
            })

        return {"collections": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents")
async def upload_document(
        file: UploadFile = File(...),
        user_id: str = Form(...),
        collection_id: Optional[str] = Form(None),
        embed: bool = Form(False)
):
    document_id = str(uuid.uuid4())
    temp_file_path = None

    try:
        print(f"=== UPLOAD DOCUMENT ===")
        print(f"File: {file.filename}")
        print(f"User ID: {user_id}")
        print(f"Collection ID: {collection_id}")
        print(f"Embed: {embed}")
        print(f"Document ID: {document_id}")

        normalized_filename = mongo_service.normalize_document_name(file.filename)

        if mongo_service.check_document_name_exists(user_id, collection_id, normalized_filename):
            raise HTTPException(
                status_code=409,
                detail=f"A document with the name '{file.filename}' already exists in this collection"
            )

        qdrant_collection_name = "default"

        if collection_id:
            collection_doc = mongo_service.get_collection(collection_id, user_id)

            print(f"Collection doc found: {collection_doc}")

            if collection_doc:
                qdrant_collection_name = collection_id
                print(f"Using Qdrant collection: {qdrant_collection_name}")
            else:
                raise HTTPException(status_code=403, detail="Collection not found or not authorized")

        file_extension = file.filename.split('.')[-1].lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as tmp_file:
            temp_file_path = tmp_file.name
            content = await file.read()
            tmp_file.write(content)

        print(f"Temp file created: {temp_file_path}")
        print(f"File size: {len(content)} bytes")

        if embed and not embedding_model:
            raise HTTPException(status_code=500, detail="Embedding model not configured")

        processor = DocumentProcessor(
            collection_name=qdrant_collection_name,
            embedding_model=embedding_model,
            mongo_client=mongo_client,
            enable_hybrid=True  # Enable hybrid search by default
        )

        print(f"Processing file with embed={embed}")

        success = processor.process_file(
            file_path=temp_file_path,
            document_id=document_id,
            user_id=user_id,
            document_name=file.filename,
            file_type=file_extension,
            embed=embed,
            metadata={
                "collection_id": collection_id
            }
        )

        print(f"Process file result: {success}")

        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        if success:
            print(f"Document uploaded successfully: {document_id}")
            return {
                "document_id": document_id,
                "document_name": file.filename,
                "normalized_name": normalized_filename,
                "file_type": file_extension,
                "collection_id": collection_id,
                "status": "uploaded"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to process document")

    except HTTPException:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise
    except Exception as e:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        print(f"Error uploading document: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents/ocr")
async def upload_document_ocr(
        file: UploadFile = File(...),
        user_id: str = Form(...),
        collection_id: Optional[str] = Form(None),
        embed: bool = Form(False),
        # ADD: OCR-specific parameters
        suggested_languages: Optional[str] = Form("eng"),  # Comma-separated string
        use_llm: bool = Form(True)
):
    """
    Upload and process document using OCR extraction.
    
    Args:
        file: The uploaded file
        user_id: User identifier
        collection_id: Optional collection identifier
        embed: Whether to create embeddings
        suggested_languages: Comma-separated OCR languages (e.g., "eng,vie")
        use_llm: Whether to use LLM for text correction and formatting
    """
    document_id = str(uuid.uuid4())
    temp_file_path = None

    try:
        print(f"=== UPLOAD DOCUMENT WITH OCR ===")
        print(f"File: {file.filename}")
        print(f"User ID: {user_id}")
        print(f"Collection ID: {collection_id}")
        print(f"Embed: {embed}")
        print(f"OCR Languages: {suggested_languages}")
        print(f"Use LLM: {use_llm}")
        print(f"Document ID: {document_id}")

        # ADD: Parse languages string to list
        language_list = [lang.strip() for lang in suggested_languages.split(",")] if suggested_languages else ["eng"]
        print(f"Parsed languages: {language_list}")

        normalized_filename = mongo_service.normalize_document_name(file.filename)

        if mongo_service.check_document_name_exists(user_id, collection_id, normalized_filename):
            raise HTTPException(
                status_code=409,
                detail=f"A document with the name '{file.filename}' already exists in this collection"
            )

        qdrant_collection_name = "default"

        if collection_id:
            collection_doc = mongo_service.get_collection(collection_id, user_id)
            print(f"Collection doc found: {collection_doc}")

            if collection_doc:
                qdrant_collection_name = collection_id
                print(f"Using Qdrant collection: {qdrant_collection_name}")
            else:
                raise HTTPException(status_code=403, detail="Collection not found or not authorized")

        file_extension = file.filename.split('.')[-1].lower()

        # ADD: Check if file type supports OCR
        if file_extension not in ['pdf']:
            raise HTTPException(
                status_code=400, 
                detail=f"OCR is currently only supported for PDF files. File type: {file_extension}"
            )

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as tmp_file:
            temp_file_path = tmp_file.name
            content = await file.read()
            tmp_file.write(content)

        print(f"Temp file created: {temp_file_path}")
        print(f"File size: {len(content)} bytes")

        if embed and not embedding_model:
            raise HTTPException(status_code=500, detail="Embedding model not configured")

        processor = DocumentProcessor(
            collection_name=qdrant_collection_name,
            embedding_model=embedding_model,
            mongo_client=mongo_client
        )

        print(f"Processing file with OCR - embed={embed}, languages={language_list}, use_llm={use_llm}")

        # ADD: Use the new OCR processing method
        success = processor.process_file_with_ocr(
            file_path=temp_file_path,
            document_id=document_id,
            user_id=user_id,
            document_name=file.filename,
            file_type=file_extension,
            embed=embed,
            metadata={
                "collection_id": collection_id
            },
            suggested_languages=language_list,
            use_llm=use_llm
        )

        print(f"OCR process file result: {success}")

        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        if success:
            print(f"Document uploaded with OCR successfully: {document_id}")
            return {
                "document_id": document_id,
                "document_name": file.filename,
                "normalized_name": normalized_filename,
                "file_type": file_extension,
                "collection_id": collection_id,
                "extraction_method": "ocr",
                "ocr_languages": language_list,
                "llm_enhanced": use_llm,
                "status": "uploaded"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to process document with OCR")

    except HTTPException:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise
    except Exception as e:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        print(f"Error uploading document with OCR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

@app.get("/documents/{document_id}")
async def get_document_info(document_id: str):
    try:
        db = mongo_client[mongo_service.db_name]
        collection = db[mongo_service.DOCUMENTS_COLLECTION]

        doc = collection.find_one({"_id": document_id})

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "document_id": document_id,
            "document_name": doc.get("document_name"),
            "normalized_name": doc.get("normalized_name"),
            "file_type": doc.get("file_type"),
            "user_id": doc.get("user_id"),
            "collection_id": doc.get("collection_id"),
            "upload_date": doc.get("upload_date")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents(user_id: str, collection_id: Optional[str] = None):
    try:
        print(f"=== LIST DOCUMENTS ===")
        print(f"User ID: {user_id}")
        print(f"Collection ID: {collection_id}")

        docs = mongo_service.list_user_documents(user_id, collection_id)

        print(f"Found {len(docs)} documents")
        for doc in docs:
            print(f"Doc: {doc.get('_id')} - {doc.get('document_name')}")

        result = []
        for doc in docs:
            result.append({
                "document_id": doc["_id"],
                "document_name": doc.get("document_name"),
                "normalized_name": doc.get("normalized_name"),
                "file_type": doc.get("file_type"),
                "collection_id": doc.get("collection_id"),
                "upload_date": doc.get("upload_date")
            })

        return {"documents": result}

    except Exception as e:
        print(f"Error listing documents: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/query")
async def query_documents(query: DocumentQuery):
    """
    Advanced document query endpoint with flexible search options and filtering
    """
    try:
        if not query.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        print(f"=== DOCUMENT QUERY ===")
        print(f"Query: {query.query}")
        print(f"User ID: {query.user_id}")
        print(f"Collection ID: {query.collection_id}")
        print(f"Search Type: {query.search_type}")
        print(f"Dense Weight: {query.dense_weight}")
        print(f"Limit: {query.limit}")
        print(f"Filters: {query.filters}")

        qdrant_collection_name = "default"

        if query.collection_id:
            collection_doc = mongo_service.get_collection(query.collection_id, query.user_id)

            if collection_doc:
                qdrant_collection_name = query.collection_id
            else:
                raise HTTPException(status_code=403, detail="Collection not found or not authorized")

        processor = DocumentProcessor(
            collection_name=qdrant_collection_name,
            embedding_model=embedding_model,
            mongo_client=mongo_client,
            enable_hybrid=True
        )

        # Determine search method based on search_type
        if query.search_type == "dense" or query.search_type == "semantic":
            search_results = processor.dense_search(
                query=query.query,
                user_id=query.user_id,
                collection_id=query.collection_id,
                limit=query.limit
            )
        elif query.search_type == "hybrid":
            search_results = processor.hybrid_search(
                query=query.query,
                user_id=query.user_id,
                collection_id=query.collection_id,
                limit=query.limit,
                dense_weight=query.dense_weight
            )
        else:
            # Default to hybrid search
            search_results = processor.search_documents(
                query=query.query,
                user_id=query.user_id,
                collection_id=query.collection_id,
                limit=query.limit,
                dense_weight=query.dense_weight
            )

        # Apply score threshold filtering
        if query.min_score > 0:
            search_results = [hit for hit in search_results if hit.score >= query.min_score]

        results = []
        for hit in search_results:
            document_name = hit.payload.get("document_name", "Unknown Document")
            page_number = hit.payload.get("page_number", 1)
            chunk_id = hit.payload.get("chunk_id")
            file_type = hit.payload.get("file_type", "").lower()

            # Use page number for PDF and DOC/DOCX files, chunk_id for others
            if file_type in ['pdf', 'doc', 'docx']:
                citation = f"\\cite{{{document_name}, page {page_number}}}"
                reference_type = "page"
            else:
                citation = f"\\cite{{{document_name}, chunk {chunk_id}}}"
                reference_type = "chunk"

            result_item = {
                "document_id": hit.payload.get("document_id"),
                "document_name": document_name,
                "page_number": page_number if file_type in ['pdf', 'doc', 'docx'] else None,
                "chunk_id": chunk_id,
                "score": hit.score,
                "citation": citation,
                "reference_type": reference_type
            }

            # Include text if requested
            if query.include_text:
                result_item["text"] = hit.payload.get("text")

            # Include metadata if requested
            if query.include_metadata:
                metadata = {k: v for k, v in hit.payload.items() 
                           if k not in ["text", "document_id", "document_name", "page_number", "chunk_id", "user_id"]}
                result_item["metadata"] = metadata

            # Apply additional filters if provided
            if query.filters:
                should_include = True
                for filter_key, filter_value in query.filters.items():
                    if filter_key in hit.payload:
                        if isinstance(filter_value, list):
                            if hit.payload[filter_key] not in filter_value:
                                should_include = False
                                break
                        else:
                            if hit.payload[filter_key] != filter_value:
                                should_include = False
                                break
                
                if should_include:
                    results.append(result_item)
            else:
                results.append(result_item)

        # Sort by score (highest first)
        results.sort(key=lambda x: x["score"], reverse=True)

        return {
            "results": results,
            "total_found": len(results),
            "query": query.query,
            "search_type": query.search_type,
            "dense_weight": query.dense_weight if query.search_type == "hybrid" else None,
            "filters_applied": query.filters,
            "min_score": query.min_score,
            "collection_id": query.collection_id
        }

    except Exception as e:
        print(f"Error in query_documents: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/search")
async def search_documents(search: DocumentSearch):
    try:
        if not search.query.strip():
            raise HTTPException(status_code=400, detail="Search query cannot be empty")

        qdrant_collection_name = "default"

        if search.collection_id:
            collection_doc = mongo_service.get_collection(search.collection_id, search.user_id)

            if collection_doc:
                qdrant_collection_name = search.collection_id
            else:
                raise HTTPException(status_code=403, detail="Collection not found or not authorized")

        processor = DocumentProcessor(
            collection_name=qdrant_collection_name,
            embedding_model=embedding_model,
            mongo_client=mongo_client,
            enable_hybrid=True  # Enable hybrid search by default
        )

        # Determine search method based on search_type
        if search.search_type == "dense":
            search_results = processor.dense_search(
                query=search.query,
                user_id=search.user_id,
                collection_id=search.collection_id,
                limit=search.limit
            )
        elif search.search_type == "hybrid":
            search_results = processor.hybrid_search(
                query=search.query,
                user_id=search.user_id,
                collection_id=search.collection_id,
                limit=search.limit,
                dense_weight=search.dense_weight
            )
        else:
            # Default to hybrid search
            search_results = processor.search_documents(
                query=search.query,
                user_id=search.user_id,
                collection_id=search.collection_id,
                limit=search.limit,
                dense_weight=search.dense_weight
            )

        results = []
        for hit in search_results:
            document_name = hit.payload.get("document_name", "Unknown Document")
            page_number = hit.payload.get("page_number", 1)
            chunk_id = hit.payload.get("chunk_id")
            file_type = hit.payload.get("file_type", "").lower()

            # Use page number for PDF and DOC/DOCX files, chunk_id for others
            if file_type in ['pdf', 'doc', 'docx']:
                citation = f"\\cite{{{document_name}, page {page_number}}}"
                reference_type = "page"
            else:
                citation = f"\\cite{{{document_name}, chunk {chunk_id}}}"
                reference_type = "chunk"

            result_item = {
                "document_id": hit.payload.get("document_id"),
                "document_name": document_name,
                "page_number": page_number if file_type in ['pdf', 'doc', 'docx'] else None,
                "chunk_id": chunk_id,
                "text": hit.payload.get("text"),
                "score": hit.score,
                "citation": citation,
                "reference_type": reference_type
            }
            results.append(result_item)

        return {
            "results": results,
            "total_found": len(results),
            "query": search.query,
            "search_type": search.search_type,
            "dense_weight": search.dense_weight if search.search_type == "hybrid" else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str, user_id: str):
    try:
        db = mongo_client[mongo_service.db_name]
        collection = db[mongo_service.DOCUMENTS_COLLECTION]

        doc = collection.find_one({"_id": document_id})

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if doc.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this document")

        qdrant_collection_name = "default"
        collection_id = doc.get("collection_id")

        if collection_id:
            qdrant_collection_name = collection_id

        processor = DocumentProcessor(
            collection_name=qdrant_collection_name,
            embedding_model=embedding_model,
            mongo_client=mongo_client,
            enable_hybrid=True  # Enable hybrid search by default
        )

        success = processor.delete_document(document_id, user_id)

        if success:
            return {"status": "deleted"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete document")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{document_id}/status")
async def get_document_status(document_id: str):
    try:
        db = mongo_client[mongo_service.db_name]
        collection = db[mongo_service.DOCUMENTS_COLLECTION]

        doc = collection.find_one({"_id": document_id})

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        status = "ready" if doc.get("text") else "processing"

        return {"document_id": document_id, "status": status}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    try:
        mongo_client.admin.command('ping')
        mongo_status = "connected"
    except Exception as e:
        mongo_status = f"error: {str(e)}"
    
    try:
        qdrant_client = QdrantClient(host=qdrant_host, port=6333)
        qdrant_client.get_collections()
        qdrant_status = "connected"
    except Exception as e:
        qdrant_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "mongodb": mongo_status,
        "mongodb_db": mongo_service.db_name,
        "qdrant": qdrant_status
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)