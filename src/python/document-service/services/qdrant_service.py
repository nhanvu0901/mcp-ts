import uuid
import time
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from .config import DEFAULT_QDRANT_HOST, DEFAULT_QDRANT_PORT, VECTOR_SIZE

class QdrantService:
    def __init__(self, collection_name: str,
                 qdrant_host: str = DEFAULT_QDRANT_HOST,
                 qdrant_port: int = DEFAULT_QDRANT_PORT,
                 vector_size: int = VECTOR_SIZE):
        
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.client = self._connect_with_retry(qdrant_host, qdrant_port)
        self._ensure_collection_exists()
    
    def _connect_with_retry(self, host: str, port: int, max_attempts: int = 30, delay: int = 2):
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"Attempting to connect to Qdrant at {host}:{port} (attempt {attempt}/{max_attempts})")
                client = QdrantClient(host=host, port=port)
                client.get_collections()
                print("Successfully connected to Qdrant!")
                return client
            except Exception as e:
                print(f"Connection attempt {attempt} failed: {e}")
                if attempt < max_attempts:
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print(f"Failed to connect to Qdrant after {max_attempts} attempts")
                    raise
    
    def _ensure_collection_exists(self):
        try:
            if not self.client.collection_exists(self.collection_name):
                print(f"Collection '{self.collection_name}' does not exist. Creating it.")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
                )
            else:
                print(f"Collection '{self.collection_name}' already exists.")
        except Exception as e:
            print(f"Error checking/creating collection: {e}")
            raise
    
    def upsert_chunks(self, chunks: list, embeddings: list, metadata_list: list, user_id: str):
        points_to_upsert = []
        
        for i, (chunk, embedding, metadata) in enumerate(zip(chunks, embeddings, metadata_list)):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={**metadata, "text": chunk, "chunk_id": i, "user_id": user_id}
            )
            points_to_upsert.append(point)
        
        if points_to_upsert:
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    wait=True,
                    points=points_to_upsert
                )
                print(f"Successfully upserted {len(points_to_upsert)} chunks to Qdrant")
                return True
            except Exception as e:
                print(f"Error upserting points to Qdrant: {e}")
                return False
        else:
            print("No chunks to upsert")
            return False
    
    def search_documents(self, query_vector: list, user_id: str, collection_id: str = None, limit: int = 10):
        try:
            search_results = self.client.search(
                collection_name=collection_id,
                query_vector=query_vector,
                query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
                limit=limit
            )
            
            return search_results
            
        except Exception as e:
            print(f"Error searching documents: {e}")
            return []
    
    def delete_document_chunks(self, document_id: str, user_id: str) -> bool:
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector={
                    "filter": {
                        "must": [
                            {"key": "document_id", "match": {"value": document_id}},
                            {"key": "user_id", "match": {"value": user_id}}
                        ]
                    }
                }
            )
            print(f"Deleted chunks for document_id={document_id}")
            return True
        except Exception as e:
            print(f"Error deleting chunks for document_id={document_id}: {e}")
            return False