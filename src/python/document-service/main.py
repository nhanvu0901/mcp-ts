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

app = FastAPI(title="Document Service API")

mongo_client = MongoClient(MONGODB_URI)
mongo_service = MongoService(mongo_client)

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


@app.post("/collections")
async def create_collection(collection: CollectionCreate):
    collection_id = str(uuid.uuid4())

    try:
        print(f"Creating collection: {collection.name} for user: {collection.user_id}")
        print(f"Generated collection_id: {collection_id}")

        try:
            qdrant_client = QdrantClient(host="localhost", port=6333)

            if not qdrant_client.collection_exists(collection_id):
                qdrant_client.create_collection(
                    collection_name=collection_id,
                    vectors_config={
                        "size": 3072,
                        "distance": "Cosine"
                    }
                )
                print(f"Created Qdrant collection: {collection_id}")
            else:
                print(f"Qdrant collection already exists: {collection_id}")

        except Exception as qdrant_error:
            print(f"Qdrant error: {qdrant_error}")
            raise HTTPException(status_code=500, detail=f"Failed to create Qdrant collection: {str(qdrant_error)}")

        success = mongo_service.save_collection(
            collection_id=collection_id,
            name=collection.name,
            user_id=collection.user_id,
            metadata={"created_at": uuid.uuid4().hex}
        )

        print(f"MongoDB save result: {success}")

        if success:
            return {
                "collection_id": collection_id,
                "name": collection.name,
                "status": "created"
            }
        else:
            try:
                qdrant_client.delete_collection(collection_id)
                print(f"Rollback: Deleted Qdrant collection {collection_id}")
            except:
                pass
            raise HTTPException(status_code=500, detail="Failed to create collection in MongoDB")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating collection: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")


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
            qdrant_client = QdrantClient(host="localhost", port=6333)
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
            mongo_client=mongo_client
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
            return {"document_id": document_id, "status": "uploaded"}
        else:
            raise HTTPException(status_code=500, detail="Failed to process document")

    except Exception as e:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        print(f"Error uploading document: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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
            "name": doc.get("document_name"),
            "file_type": doc.get("file_type"),
            "user_id": doc.get("user_id"),
            "collection_id": doc.get("collection_id"),
            "upload_date": doc.get("_id").generation_time if hasattr(doc.get("_id"), "generation_time") else None
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
                "name": doc.get("document_name"),
                "file_type": doc.get("file_type"),
                "collection_id": doc.get("collection_id"),
                "upload_date": doc.get("_id").generation_time if hasattr(doc.get("_id"), "generation_time") else None
            })

        return {"documents": result}

    except Exception as e:
        print(f"Error listing documents: {str(e)}")
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
            mongo_client=mongo_client
        )

        search_results = processor.search_documents(
            query=search.query,
            user_id=search.user_id,
            collection_id=search.collection_id
        )

        results = []
        for hit in search_results:
            results.append({
                "document_id": hit.payload.get("document_id"),
                "document_name": hit.payload.get("document_name"),
                "text": hit.payload.get("text"),
                "score": hit.score,
                "chunk_id": hit.payload.get("chunk_id")
            })

        return {"results": results}

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
            mongo_client=mongo_client
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
        qdrant_client = QdrantClient(host="localhost", port=6333)
        qdrant_client.get_collections()
        qdrant_status = "connected"
    except Exception as e:
        qdrant_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "mongodb": mongo_status,
        "mongodb_db": mongo_service.db_name,
        "mongodb_collection": mongo_service.collection_name,
        "qdrant": qdrant_status
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)