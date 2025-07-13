from pymongo import MongoClient
from pymongo.errors import OperationFailure
from .config import MONGODB_DB


class MongoService:
    DOCUMENTS_COLLECTION = "documents"
    COLLECTIONS_COLLECTION = "collections"

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db_name = MONGODB_DB

    def check_mongo_database(self,type: str):
        if not self.mongo_client:
            print("[MongoDB] No client provided, skipping save.")
            return False
        data_name = self.COLLECTIONS_COLLECTION if type == 'collection' else self.DOCUMENTS_COLLECTION
        if not (self.db_name and data_name):
            print("[MongoDB] Missing database/collection info, skipping save.")
            return False

    def save_document(self, document_id: str, text: str, user_id: str, metadata: dict = None):
        self.check_mongo_database('document')

        try:
            db = self.mongo_client[self.db_name]
            collection = db[self.DOCUMENTS_COLLECTION]

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

    def save_collection(self, collection_id: str, name: str, user_id: str, metadata: dict = None):
        self.check_mongo_database('collection')

        try:
            db = self.mongo_client[self.db_name]
            collection = db[self.COLLECTIONS_COLLECTION]

            doc = {
                "_id": collection_id,
                "name": name,
                "user_id": user_id,
            }
            if metadata:
                doc.update(metadata)

            result = collection.replace_one({"_id": collection_id}, doc, upsert=True)

            if result.upserted_id or result.modified_count > 0:
                print(f"[MongoDB] Saved collection_id={collection_id}")
                return True
            else:
                print(f"[MongoDB] No changes made for collection_id={collection_id}")
                return True

        except OperationFailure as e:
            print(f"[MongoDB] Operation failed for collection_id={collection_id}: {e}")
            return False

    def get_document_text(self, document_id: str, user_id: str) -> str:
        if not self.mongo_client:
            raise ValueError("MongoDB client is required")

        if not (self.db_name and self.DOCUMENTS_COLLECTION):
            raise ValueError("Missing MongoDB database/collection info")

        db = self.mongo_client[self.db_name]
        collection = db[self.DOCUMENTS_COLLECTION]
        doc = collection.find_one({"_id": document_id, "user_id": user_id})

        if not doc or "text" not in doc:
            raise ValueError("Document not found or missing 'text' field")

        return doc["text"]

    def get_collection(self, collection_id: str, user_id: str):
        if not self.mongo_client:
            return None

        db = self.mongo_client[self.db_name]
        collection = db[self.COLLECTIONS_COLLECTION]
        return collection.find_one({"_id": collection_id, "user_id": user_id})

    def delete_document(self, document_id: str, user_id: str) -> bool:
        if not self.mongo_client:
            return False

        if not (self.db_name and self.DOCUMENTS_COLLECTION):
            return False

        try:
            db = self.mongo_client[self.db_name]
            collection = db[self.DOCUMENTS_COLLECTION]

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

    def delete_collection(self, collection_id: str, user_id: str) -> bool:
        if not self.mongo_client:
            return False

        try:
            db = self.mongo_client[self.db_name]

            collections_coll = db[self.COLLECTIONS_COLLECTION]
            documents_coll = db[self.DOCUMENTS_COLLECTION]

            collection_doc = collections_coll.find_one({"_id": collection_id})
            if not collection_doc:
                return False

            if collection_doc.get("user_id") != user_id:
                raise ValueError("Not authorized to delete this collection")

            collections_coll.delete_one({"_id": collection_id})
            documents_coll.delete_many({"collection_id": collection_id, "user_id": user_id})

            return True

        except Exception as e:
            print(f"[MongoDB] Delete collection failed for collection_id={collection_id}: {e}")
            return False

    def list_user_documents(self, user_id: str, collection_id: str = None) -> list:
        if not self.mongo_client:
            return []

        try:
            db = self.mongo_client[self.db_name]
            collection = db[self.DOCUMENTS_COLLECTION]

            query = {"user_id": user_id}
            if collection_id:
                query["collection_id"] = collection_id

            docs = list(collection.find(query))
            return docs

        except Exception as e:
            print(f"[MongoDB] List documents failed for user_id={user_id}: {e}")
            return []

    def list_user_collections(self, user_id: str) -> list:
        if not self.mongo_client:
            return []

        try:
            db = self.mongo_client[self.db_name]
            collection = db[self.COLLECTIONS_COLLECTION]

            collections = list(collection.find({"user_id": user_id}))
            return collections

        except Exception as e:
            print(f"[MongoDB] List collections failed for user_id={user_id}: {e}")
            return []