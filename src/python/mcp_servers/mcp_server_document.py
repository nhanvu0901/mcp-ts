import os
import sys
from typing import Dict, Any
from pathlib import Path
#Docker
# sys.path.append('/app')
#local
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
from langchain_openai import AzureOpenAIEmbeddings
from services.document_processor import DocumentProcessor
from pymongo import MongoClient

project_root = Path(__file__).parent.parent
os.chdir(project_root)

mcp = FastMCP(
    "DocumentService",
    instructions="Document processing service that can upload, process, and manage documents with vector embeddings.",
    host="0.0.0.0",
    port=8001,
)
#Local
UPLOAD_DIR = Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
print(f"Upload directory created/verified at: {UPLOAD_DIR.resolve()}")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
VECTOR_SIZE = 3072
QDRANT_HOST = os.getenv("QDRANT_HOST") or 'localhost'

mongo_uri = os.getenv("MONGODB_URI")
mongo_client = MongoClient(mongo_uri) if mongo_uri else None

qdrant_client = QdrantClient(host=QDRANT_HOST, port=6333)

azure_embedding_endpoint = os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT")
azure_embedding_api_key = os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY")
azure_embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
azure_embedding_api_version = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION")

embedding_model = AzureOpenAIEmbeddings(
    model=azure_embedding_model,
    azure_endpoint=azure_embedding_endpoint,
    api_key=azure_embedding_api_key,
    openai_api_version=azure_embedding_api_version
)


@mcp.tool()
async def process_document(
        file_path: str,
        filename: str,
        document_id: str,
        user_id: str,
) -> Dict[str, Any]:
    try:
        if not os.path.exists(file_path):
            return {
                "status": "error",
                "error": f"File not found: {file_path}",
                "document_id": document_id
            }

        collection_name = f"user_{user_id}_docs"

        document_processor = DocumentProcessor(
            collection_name=collection_name,
            qdrant_host=QDRANT_HOST,
            qdrant_port=6333,
            embedding_model=embedding_model,
            vector_size=VECTOR_SIZE,
            mongo_client=mongo_client
        )

        file_type = filename.split('.')[-1].lower()

        text_content = document_processor.extract_text(file_path)

        document_processor.process_and_add_chunks_to_qdrant(
            text=text_content,
            method="auto",
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
            file_type=file_type,
            document_name=filename,
            document_id=document_id
        )

        return {
            "status": "success",
            "document_id": document_id,
            "filename": filename,
            "file_path": file_path,
            "collection_id": collection_name
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "document_id": document_id
        }


@mcp.tool()
async def upload_and_save_to_mongo(
        file_path: str,
        filename: str,
        document_id: str,
) -> Dict[str, Any]:
    try:
        if not os.path.exists(file_path):
            return {
                "status": "error",
                "error": f"File not found: {file_path}",
                "document_id": document_id
            }

        document_processor = DocumentProcessor(
            collection_name="default",
            qdrant_host=QDRANT_HOST,
            qdrant_port=6333,
            embedding_model=embedding_model,
            vector_size=VECTOR_SIZE,
            mongo_client=mongo_client
        )

        file_type = filename.split('.')[-1].lower()

        text = document_processor.extract_and_save_to_mongo(
            file_path=file_path,
            document_id=document_id,
            document_name=filename,
            file_type=file_type
        )
        return {
            "status": "success",
            "document_id": document_id,
            "filename": filename,
            "file_path": file_path,
            "mongo_saved": True
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "document_id": document_id
        }


if __name__ == "__main__":
    print("Document Service MCP server is running on port 8001...")
    mcp.run(transport="sse")