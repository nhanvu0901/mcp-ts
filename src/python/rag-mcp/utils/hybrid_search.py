import asyncio
import logging
from typing import List, Any
from qdrant_client import QdrantClient
from langchain_openai import AzureOpenAIEmbeddings

from .config import config
from .tfidf_search import TfidfService
from .dense_search import DenseSearchService
from .fusion_score import FusionService, FusionMethod, NormalizationMethod

logger = logging.getLogger(__name__)


class HybridSearchService:
    """
    Handles hybrid search combining dense and sparse search results
    """

    def __init__(self,
                 qdrant_client: QdrantClient,
                 embedding_model: AzureOpenAIEmbeddings,
                 tfidf_service: TfidfService,
                 fusion_service: FusionService):
        self.qdrant_client = qdrant_client
        self.tfidf_service = tfidf_service
        self.dense_search_service = DenseSearchService(embedding_model, qdrant_client)
        self.fusion_service = fusion_service

    async def perform_hybrid_search(self,
                                    query: str,
                                    collection_ids: List[str],
                                    user_id: str,
                                    limit: int = 10,
                                    dense_weight: float = None,
                                    normalization: str = None,
                                    fusion_method: str = None) -> List[Any]:
        """
        Perform hybrid search combining dense and sparse results.

        Args:
            query: User query text
            collection_ids: List of collection IDs to search
            user_id: User ID for filtering
            limit: Maximum results to return
            dense_weight: Weight for dense scores
            normalization: Score normalization method
            fusion_method: Method for combining results

        Returns:
            Combined and ranked search results
        """
        if dense_weight is None:
            dense_weight = config.DEFAULT_DENSE_WEIGHT
        if normalization is None:
            normalization = config.DEFAULT_NORMALIZATION
        if fusion_method is None:
            fusion_method = config.DEFAULT_FUSION_METHOD

        logger.info(f"Hybrid search: query='{query}', collections={len(collection_ids)}, dense_weight={dense_weight}")

        # Generate dense embedding
        query_embedding = await self.dense_search_service.generate_query_embedding(query)

        all_results = []

        collection_results_list = await asyncio.gather(
            *[self._search_collection_parallel(collection_id, query, query_embedding, user_id, limit, dense_weight,
                                               normalization, fusion_method)
              for collection_id in collection_ids]
        )

        for collection_results in collection_results_list:
            all_results.extend(collection_results)

        all_results.sort(key=lambda x: getattr(x, 'score', 0), reverse=True)

        logger.info(f"Hybrid search completed: {len(all_results)} total results")
        return all_results[:limit]

    async def _search_collection_parallel(self,
                                          collection_id: str,
                                          query: str,
                                          query_embedding: List[float],
                                          user_id: str,
                                          limit: int,
                                          dense_weight: float,
                                          normalization: str,
                                          fusion_method: str) -> List[Any]:
        """Helper function to perform parallel dense and sparse search for a single collection."""
        logger.debug(f"Processing collection: {collection_id}")

        try:
            dense_results, sparse_results = await asyncio.gather(
                self._perform_dense_search(query_embedding, collection_id, user_id, limit),
                self._perform_sparse_search(query, collection_id, user_id, limit)
            )
            logger.info("Finished parallel dense and sparse search")

            if sparse_results:
                norm_method = NormalizationMethod(normalization)
                fuse_method = FusionMethod(fusion_method)

                collection_results = self.fusion_service.fuse_dense_sparse(
                    dense_results=dense_results,
                    sparse_results=sparse_results,
                    dense_weight=dense_weight,
                    method=fuse_method,
                    normalization=norm_method
                )
            else:
                collection_results = dense_results

            # Tag with collection ID
            for result in collection_results:
                result._collection_id = collection_id

            return collection_results
        except Exception as e:
            logger.error(f"Error in parallel search for collection {collection_id}: {e}")
            return []

    async def _perform_sparse_search(self, query: str, collection_id: str, user_id: str, limit: int) -> List[Any]:
        """Prepare sparse search coroutine"""
        sparse_results = []
        sparse_vector = self.tfidf_service.query_to_sparse_vector(query, collection_id)

        if sparse_vector and sparse_vector.indices:
            try:
                response = self.qdrant_client.query_points(
                    collection_name=collection_id,
                    query=sparse_vector,
                    using="text_sparse",
                    query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
                    limit=limit * 2
                )
                sparse_results = response.points if hasattr(response, 'points') else []
                logger.debug(f"Sparse search found {len(sparse_results)} results in {collection_id}")
            except Exception as e:
                logger.warning(f"Sparse search failed for {collection_id}: {e}")
                sparse_results = []
        else:
            logger.debug(f"No sparse vector available for {collection_id}")

        return sparse_results

    async def _perform_dense_search(self, query_embedding: List[float], collection_id: str, user_id: str, limit: int) -> \
    List[Any]:
        """Perform dense search"""
        return self.dense_search_service.search_collection(
            query_embedding=query_embedding,
            collection_id=collection_id,
            user_id=user_id,
            limit=limit * 2
        )