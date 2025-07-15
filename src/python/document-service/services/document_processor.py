from langchain_openai import AzureOpenAIEmbeddings
from pymongo import MongoClient
from .mongo_service import MongoService
from .qdrant_service import QdrantService
from .text_splitter import TextSplitter
from .config import ChunkingMethod, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP
from .utils import extract_text
from .config import DEFAULT_QDRANT_HOST

class DocumentProcessor:
    def __init__(self,
                 collection_name: str,
                 embedding_model: AzureOpenAIEmbeddings,
                 mongo_client: MongoClient = None,
                 qdrant_host: str = DEFAULT_QDRANT_HOST,
                 qdrant_port: int = 6333,
                 vector_size: int = 3072):
        
        if not embedding_model:
            raise ValueError("embedding_model must be provided")
        
        self.embedding_model = embedding_model
        self.mongo_service = MongoService(mongo_client) if mongo_client else None
        self.qdrant_service = QdrantService(collection_name, qdrant_host, qdrant_port, vector_size)
        self.text_splitter = TextSplitter()
        
        print("DocumentProcessor initialized successfully!")
    
    def extract_and_save_to_mongo(self, file_path: str, document_id: str, user_id: str,
                                  document_name: str = None, file_type: str = None, 
                                  metadata: dict = None):
        
        if not self.mongo_service:
            raise ValueError("MongoDB service not initialized")
        
        text = extract_text(file_path)
        
        meta = metadata or {}
        meta.update({
            "document_name": document_name,
            "file_type": file_type
        })
        
        success = self.mongo_service.save_document(document_id, text, user_id, meta)
        
        if success:
            print(f"[MongoDB] Saved extracted text for document_id={document_id}")
        
        return text
    
    def process_and_embed(self, 
                         text: str,
                         document_id: str,
                         user_id: str,
                         document_name: str = None,
                         file_type: str = None,
                         method: str = ChunkingMethod.RECURSIVE_CHARACTER,
                         chunk_size: int = DEFAULT_CHUNK_SIZE,
                         overlap: int = DEFAULT_CHUNK_OVERLAP,
                         metadata: dict = None,
                         **kwargs):
        
        if method == "auto":
            method = self.text_splitter.auto_select_method(file_type)
        
        chunks = self.text_splitter.split_text(text, method, chunk_size, overlap, **kwargs)
        
        if not chunks:
            print(f"No chunks created for document_id={document_id}")
            return False
        
        try:
            embeddings = self.embedding_model.embed_documents(chunks)
        except Exception as e:
            print(f"Error embedding chunks for document_id={document_id}: {e}")
            return False
        
        metadata_list = []
        for i in range(len(chunks)):
            metadata_list.append({
                "document_name": document_name,
                "chunk_method": method,
                "file_type": file_type,
                "document_id": document_id
            })
        
        success = self.qdrant_service.upsert_chunks(chunks, embeddings, metadata_list, user_id)
        
        if success and self.mongo_service:
            # Prepare MongoDB metadata
            mongo_metadata = {
                "document_name": document_name,
                "file_type": file_type
            }
            
            # Add any additional metadata passed from the caller
            if metadata:
                mongo_metadata.update(metadata)
            
            print(f"[DocumentProcessor] Saving to MongoDB with metadata: {mongo_metadata}")
            
            self.mongo_service.save_document(document_id, text, user_id, mongo_metadata)
        
        return success
    
    def process_file(self, file_path: str, document_id: str, user_id: str,
                    document_name: str = None, file_type: str = None,
                    embed: bool = False, metadata: dict = None, **kwargs):
        
        text = extract_text(file_path)
        
        if embed:
            return self.process_and_embed(
                text=text,
                document_id=document_id,
                user_id=user_id,
                document_name=document_name,
                file_type=file_type,
                metadata=metadata,
                **kwargs
            )
        else:
            if not self.mongo_service:
                raise ValueError("MongoDB service not initialized")
            
            meta = metadata or {}
            meta.update({
                "document_name": document_name,
                "file_type": file_type
            })
            
            print(f"[DocumentProcessor] Saving to MongoDB only with metadata: {meta}")
            
            return self.mongo_service.save_document(document_id, text, user_id, meta)
    
    def delete_document(self, document_id: str, user_id: str) -> bool:
        mongo_success = True
        qdrant_success = True
        
        if self.mongo_service:
            mongo_success = self.mongo_service.delete_document(document_id, user_id)
        
        qdrant_success = self.qdrant_service.delete_document_chunks(document_id, user_id)
        
        return mongo_success and qdrant_success
    
    def search_documents(self, query: str, user_id: str, collection_id: str = None, limit: int = 10):
        try:
            query_embedding = self.embedding_model.embed_query(query)
            return self.qdrant_service.search_documents(query_embedding, user_id, collection_id, limit)
        except Exception as e:
            print(f"Error in search_documents: {e}")
            return []