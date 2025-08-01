import os
import pickle
import logging
from typing import Optional, List
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import csr_matrix
from qdrant_client.models import SparseVector

logger = logging.getLogger(__name__)


class TfidfService:
    """
    Handles TF-IDF vectorization for sparse search functionality.

    Manages training, loading, saving, and query transformation for
    keyword-based document retrieval.
    """

    def __init__(self, models_dir: str = "/app/tfidf_models"):
        self.models_dir = models_dir
        self.vectorizer_cache = {}
        os.makedirs(models_dir, exist_ok=True)

    def get_vectorizer_path(self, collection_id: str) -> str:
        """Get file path for TF-IDF vectorizer"""
        return os.path.join(self.models_dir, f"{collection_id}_tfidf.pkl")

    def load_vectorizer(self, collection_id: str) -> Optional[TfidfVectorizer]:
        """
        Load TF-IDF vectorizer for a specific collection.

        Args:
            collection_id: Unique collection identifier

        Returns:
            TfidfVectorizer if found, None otherwise
        """
        if collection_id in self.vectorizer_cache:
            return self.vectorizer_cache[collection_id]

        vectorizer_path = self.get_vectorizer_path(collection_id)

        if os.path.exists(vectorizer_path):
            try:
                with open(vectorizer_path, 'rb') as f:
                    vectorizer = pickle.load(f)
                self.vectorizer_cache[collection_id] = vectorizer
                logger.info(f"Loaded TF-IDF vectorizer for {collection_id}")
                return vectorizer
            except Exception as e:
                logger.error(f"Error loading TF-IDF vectorizer for {collection_id}: {e}")
                return None

        logger.warning(f"No TF-IDF vectorizer found for collection {collection_id}")
        return None

    def save_vectorizer(self, collection_id: str, vectorizer: TfidfVectorizer) -> bool:
        """
        Save TF-IDF vectorizer to disk.

        Args:
            collection_id: Unique collection identifier
            vectorizer: Trained TF-IDF vectorizer

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            vectorizer_path = self.get_vectorizer_path(collection_id)
            with open(vectorizer_path, 'wb') as f:
                pickle.dump(vectorizer, f)

            # Update cache
            self.vectorizer_cache[collection_id] = vectorizer
            logger.info(f"Saved TF-IDF vectorizer for {collection_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving TF-IDF vectorizer for {collection_id}: {e}")
            return False

    def train_vectorizer(self, collection_id: str, texts: List[str]) -> Optional[TfidfVectorizer]:
        """
        Train new TF-IDF vectorizer on document corpus.

        Args:
            collection_id: Unique collection identifier
            texts: List of document texts for training

        Returns:
            Trained TfidfVectorizer or None if training failed
        """
        if not texts:
            logger.warning(f"No texts provided for training TF-IDF vectorizer for {collection_id}")
            return None

        try:
            vectorizer = TfidfVectorizer(
                stop_words='english',
                max_features=10000,
                min_df=1,
                max_df=0.95,
                ngram_range=(1, 2)  # Include bigrams for better keyword matching
            )

            vectorizer.fit(texts)

            # Save the trained vectorizer
            if self.save_vectorizer(collection_id, vectorizer):
                logger.info(f"Trained TF-IDF vectorizer on {len(texts)} documents for {collection_id}")
                return vectorizer
            else:
                logger.error(f"Failed to save trained vectorizer for {collection_id}")
                return None

        except Exception as e:
            logger.error(f"Error training TF-IDF vectorizer for {collection_id}: {e}")
            return None

    def query_to_sparse_vector(self, query: str, collection_id: str) -> Optional[SparseVector]:
        """
        Convert query text to sparse vector format.

        Args:
            query: User query text
            collection_id: Collection to get vectorizer for

        Returns:
            SparseVector for Qdrant or None if conversion failed
        """
        vectorizer = self.load_vectorizer(collection_id)
        if not vectorizer:
            logger.warning(f"No vectorizer available for collection {collection_id}")
            return None

        try:
            # Transform query using TF-IDF
            tfidf_vector = vectorizer.transform([query])
            csr_vector = csr_matrix(tfidf_vector)

            # Convert to Qdrant SparseVector format
            indices = []
            values = []
            for i, j in zip(*csr_vector.nonzero()):
                indices.append(j)
                values.append(float(csr_vector[i, j]))

            if not indices:
                logger.debug(f"Query '{query}' produced empty sparse vector for {collection_id}")
                return SparseVector(indices=[], values=[])

            return SparseVector(indices=indices, values=values)

        except Exception as e:
            logger.error(f"Error converting query to sparse vector for {collection_id}: {e}")
            return None

    def get_vocabulary_size(self, collection_id: str) -> int:
        """Get size of vocabulary for a collection"""
        vectorizer = self.load_vectorizer(collection_id)
        if vectorizer and hasattr(vectorizer, 'vocabulary_'):
            return len(vectorizer.vocabulary_)
        return 0

    def clear_cache(self):
        """Clear vectorizer cache"""
        self.vectorizer_cache.clear()
        logger.info("Cleared TF-IDF vectorizer cache")

    def get_cache_info(self) -> dict:
        """Get information about cached vectorizers"""
        return {
            "cached_collections": list(self.vectorizer_cache.keys()),
            "cache_size": len(self.vectorizer_cache),
            "models_directory": self.models_dir
        }