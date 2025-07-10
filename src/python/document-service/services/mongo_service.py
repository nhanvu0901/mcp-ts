from pymongo import MongoClient
from pymongo.errors import OperationFailure
from .config import MONGODB_DB, MONGODB_COLLECTION

class MongoService:
    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db_name = MONGODB_DB
        self.collection_name = MONGODB_COLLECTION
    
    def save_document(self, document_id: str, text: str, user_id: str, metadata: dict = None):
        if not self.mongo_client:
            print("[MongoDB] No client provided, skipping save.")
            return False
        
        if not (self.db_name and self.collection_name):
            print("[MongoDB] Missing database/collection info, skipping save.")
            return False
        
        try:
            db = self.mongo_client[self.db_name]
            collection = db[self.collection_name]
            
            doc = {
                "_id": document_id,
                "text": text,
                "user_id": user_id,
            }
            if metadata:
                doc.update(metadata)
            
            result = collection.replace_one({"_id": document_id}, doc, upsert=True)
            
            if result.upserted_id or result.modified_count > 0:
                print(f"[MongoDB] Saved document_id={document_id}")
                return True
            else:
                print(f"[MongoDB] No changes made for document_id={document_id}")
                return True
                
        except OperationFailure as e:
            print(f"[MongoDB] Operation failed for document_id={document_id}: {e}")
            return False
    
    def get_document_text(self, document_id: str, user_id: str) -> str:
        if not self.mongo_client:
            raise ValueError("MongoDB client is required")
        
        if not (self.db_name and self.collection_name):
            raise ValueError("Missing MongoDB database/collection info")
        
        db = self.mongo_client[self.db_name]
        collection = db[self.collection_name]
        doc = collection.find_one({"_id": document_id, "user_id": user_id})
        
        if not doc or "text" not in doc:
            raise ValueError("Document not found or missing 'text' field")
        
        return doc["text"]
    
    def delete_document(self, document_id: str, user_id: str) -> bool:
        if not self.mongo_client:
            return False
            
        if not (self.db_name and self.collection_name):
            return False
        
        try:
            db = self.mongo_client[self.db_name]
            collection = db[self.collection_name]
            
            doc = collection.find_one({"_id": document_id})
            if not doc:
                return False
                
            if doc.get("user_id") != user_id:
                raise ValueError("Not authorized to delete this document")
            
            result = collection.delete_one({"_id": document_id})
            return result.deleted_count > 0
            
        except Exception as e:
            print(f"[MongoDB] Delete failed for document_id={document_id}: {e}")
            return False
    
    def list_user_documents(self, user_id: str, collection_id: str = None) -> list:
        if not self.mongo_client:
            return []
            
        try:
            db = self.mongo_client[self.db_name]
            collection = db[self.collection_name]
            
            query = {"user_id": user_id, "type": {"$ne": "collection"}}
            if collection_id:
                query["collection_id"] = collection_id
            
            docs = list(collection.find(query))
            return docs
            
        except Exception as e:
            print(f"[MongoDB] List documents failed for user_id={user_id}: {e}")
            return []