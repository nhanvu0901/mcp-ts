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