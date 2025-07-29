import uuid
import time
import os
import pickle
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    SparseVectorParams, SparseIndexParams,
    BinaryQuantization, BinaryQuantizationConfig,
    OptimizersConfigDiff, SparseVector, NamedSparseVector
)
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import csr_matrix
from .config import DEFAULT_QDRANT_HOST, DEFAULT_QDRANT_PORT, VECTOR_SIZE

class QdrantService:
    def __init__(self, collection_name: str,
                 qdrant_host: str = DEFAULT_QDRANT_HOST,
                 qdrant_port: int = DEFAULT_QDRANT_PORT,
                 vector_size: int = VECTOR_SIZE,
                 enable_hybrid: bool = True):
        
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.enable_hybrid = enable_hybrid
        self.client = self._connect_with_retry(qdrant_host, qdrant_port)
        self.tfidf_vectorizer = None
        self._ensure_collection_exists()
        self._load_tfidf_vectorizer()
    
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
                
                if self.enable_hybrid:
                    # Create hybrid collection
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config={
                            "text_dense": VectorParams(
                                size=self.vector_size,
                                distance=Distance.COSINE,
                                on_disk=True
                            )
                        },
                        sparse_vectors_config={
                            "text_sparse": SparseVectorParams(
                                index=SparseIndexParams(on_disk=False)
                            )
                        },
                        quantization_config=BinaryQuantization(
                            binary=BinaryQuantizationConfig(always_ram=True)
                        ),
                        optimizers_config=OptimizersConfigDiff(max_segment_size=5_000_000)
                    )
                    print(f"✅ Created hybrid collection: {self.collection_name}")
                else:
                    # Legacy single vector collection
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                    )
                    print(f"✅ Created legacy collection: {self.collection_name}")
            else:
                print(f"Collection '{self.collection_name}' already exists.")
        except Exception as e:
            print(f"Error checking/creating collection: {e}")
            raise
    
    def _load_tfidf_vectorizer(self):
        """Load existing TF-IDF vectorizer if available"""
        if not self.enable_hybrid:
            return
            
        # Use shared TF-IDF models directory in Docker container
        vectorizer_path = f"/app/tfidf_models/{self.collection_name}_tfidf.pkl"
        
        if os.path.exists(vectorizer_path):
            try:
                with open(vectorizer_path, 'rb') as f:
                    self.tfidf_vectorizer = pickle.load(f)
                print(f"✅ Loaded TF-IDF vectorizer for {self.collection_name}")
            except Exception as e:
                print(f"Error loading TF-IDF vectorizer: {e}")
                self.tfidf_vectorizer = None
    
    def _save_tfidf_vectorizer(self):
        """Save TF-IDF vectorizer for future use"""
        if not self.enable_hybrid or not self.tfidf_vectorizer:
            return
            
        # Use shared TF-IDF models directory in Docker container
        os.makedirs("/app/tfidf_models", exist_ok=True)
        vectorizer_path = f"/app/tfidf_models/{self.collection_name}_tfidf.pkl"
        
        try:
            with open(vectorizer_path, 'wb') as f:
                pickle.dump(self.tfidf_vectorizer, f)
            print(f"✅ Saved TF-IDF vectorizer for {self.collection_name}")
        except Exception as e:
            print(f"Error saving TF-IDF vectorizer: {e}")
    
    def _get_sparse_vector(self, text: str):
        """Convert text to sparse vector format"""
        if not self.enable_hybrid or not self.tfidf_vectorizer:
            return SparseVector(indices=[], values=[])
        
        if not hasattr(self.tfidf_vectorizer, 'vocabulary_'):
            return SparseVector(indices=[], values=[])
        
        tfidf_vector = self.tfidf_vectorizer.transform([text])
        csr_vector = csr_matrix(tfidf_vector)
        
        indices = []
        values = []
        for i, j in zip(*csr_vector.nonzero()):
            indices.append(j)
            values.append(float(csr_vector[i, j]))
            
        return SparseVector(indices=indices, values=values)
    
    def train_tfidf_vectorizer(self, texts: list):
        """Train TF-IDF vectorizer on document texts"""
        if not self.enable_hybrid:
            return
            
        self.tfidf_vectorizer = TfidfVectorizer(stop_words='english', max_features=10000)
        self.tfidf_vectorizer.fit(texts)
        self._save_tfidf_vectorizer()
        print(f"✅ Trained TF-IDF vectorizer on {len(texts)} documents")
    
    def upsert_chunks(self, chunks: list, dense_embeddings: list, metadata_list: list, user_id: str):
        """Upsert chunks with both dense and sparse vectors"""
        # Train TF-IDF if not available and hybrid is enabled
        if self.enable_hybrid and self.tfidf_vectorizer is None:
            print("Training TF-IDF vectorizer...")
            self.train_tfidf_vectorizer(chunks)
        
        points_to_upsert = []
        
        for i, (chunk, dense_embedding, metadata) in enumerate(zip(chunks, dense_embeddings, metadata_list)):
            if self.enable_hybrid:
                # Generate sparse vector
                sparse_embedding = self._get_sparse_vector(chunk)
                
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector={
                        "text_dense": dense_embedding,
                        "text_sparse": sparse_embedding
                    },
                    payload={**metadata, "text": chunk, "chunk_id": i, "user_id": user_id}
                )
            else:
                # Legacy single vector
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=dense_embedding,
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
    
    def _normalize_scores(self, scores):
        """Min-max normalization"""
        scores = np.array(scores)
        if len(scores) == 0 or scores.max() == scores.min():
            return [1.0] * len(scores)
        return ((scores - scores.min()) / (scores.max() - scores.min())).tolist()
    
    def _combine_search_results(self, dense_results, sparse_results, dense_weight=0.6):
        """Combine dense and sparse search results"""
        if not dense_results and not sparse_results:
            return []
        
        sparse_weight = 1 - dense_weight
        
        # Normalize scores
        dense_scores = self._normalize_scores([r.score for r in dense_results])
        sparse_scores = self._normalize_scores([r.score for r in sparse_results])
        
        # Create score mapping by point ID
        dense_map = {r.id: (score, r) for r, score in zip(dense_results, dense_scores)}
        sparse_map = {r.id: (score, r) for r, score in zip(sparse_results, sparse_scores)}
        
        # Combine scores
        combined = []
        all_ids = set(dense_map.keys()) | set(sparse_map.keys())
        
        for point_id in all_ids:
            dense_score, dense_result = dense_map.get(point_id, (0, None))
            sparse_score, sparse_result = sparse_map.get(point_id, (0, None))
            
            # Use result object from whichever search found it
            result_obj = dense_result or sparse_result
            
            final_score = dense_weight * dense_score + sparse_weight * sparse_score
            
            # Create combined result object
            result_obj.score = final_score
            combined.append(result_obj)
        
        # Sort by combined score
        combined.sort(key=lambda x: x.score, reverse=True)
        return combined
    
    def search_documents(self, query_vector: list, user_id: str, collection_id: str = None, limit: int = 10, dense_weight: float = 0.6):
        """Legacy method for backward compatibility - dense search only"""
        try:
            search_results = self.client.search(
                collection_name=collection_id or self.collection_name,
                query_vector=query_vector if not self.enable_hybrid else ("text_dense", query_vector),
                query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
                limit=limit
            )
            return search_results
        except Exception as e:
            print(f"Error searching documents: {e}")
            return []
    
    def hybrid_search(self, query_dense: list, user_id: str, query_sparse=None, collection_id: str = None, limit: int = 10, dense_weight: float = 0.6):
        """Hybrid search combining dense and sparse results"""
        if not self.enable_hybrid:
            return self.search_documents(query_dense, user_id, collection_id, limit)
        
        try:
            search_limit = min(limit * 2, 50)  # Get more for reranking
            query_filter = {"must": [{"key": "user_id", "match": {"value": user_id}}]}
            collection_name = collection_id or self.collection_name
            
            # Dense search
            dense_results = self.client.search(
                collection_name=collection_name,
                query_vector=("text_dense", query_dense),
                query_filter=query_filter,
                limit=search_limit
            )
            
            # Sparse search
            sparse_results = []
            if query_sparse and hasattr(query_sparse, 'indices'):
                try:
                    sparse_results = self.client.search(
                        collection_name=collection_name,
                        query_vector=NamedSparseVector(name="text_sparse", vector=query_sparse),
                        query_filter=query_filter,
                        limit=search_limit
                    )
                except Exception as e:
                    print(f"Sparse search failed: {e}, using dense only")
            
            # Combine results
            if sparse_results:
                combined_results = self._combine_search_results(dense_results, sparse_results, dense_weight)
            else:
                combined_results = dense_results
            
            return combined_results[:limit]
            
        except Exception as e:
            print(f"Error in hybrid search: {e}")
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