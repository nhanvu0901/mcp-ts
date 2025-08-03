import asyncio
import logging
from typing import List, Any, Optional
from langchain_openai import AzureOpenAIEmbeddings
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


class DenseSearchService:
    """
    Handles dense vector search using semantic embeddings.

    Manages embedding generation and semantic similarity search
    for conceptual document retrieval.
    """

    def __init__(self, embedding_model: AzureOpenAIEmbeddings, qdrant_client: QdrantClient):
        self.embedding_model = embedding_model
        self.qdrant_client = qdrant_client

    async def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate dense embedding for query text.

        Args:
            query: User query text

        Returns:
            Dense embedding vector
        """
        try:
            embedding = self.embedding_model.embed_query(query)
            logger.debug(f"Generated embedding for query: '{query[:50]}...'")
            return embedding
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            raise

    def search_collection(self,
                          query_embedding: List[float],
                          collection_id: str,
                          user_id: str,
                          limit: int = 10) -> List[Any]:
        """
        Perform dense vector search on a single collection.

        Args:
            query_embedding: Dense query vector
            collection_id: Collection to search
            user_id: User ID for filtering
            limit: Maximum results to return

        Returns:
            List of search results from Qdrant
        """
        try:
            results = self.qdrant_client.search(
                collection_name=collection_id,
                query_vector=("text_dense", query_embedding),
                query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
                limit=limit
            )

            logger.debug(f"Dense search found {len(results)} results in {collection_id}")
            return results

        except Exception as e:
            logger.error(f"Error in dense search for collection {collection_id}: {e}")
            return []

    async def search_parallel_multiple_collections(self,
                                                   query_embedding: List[float],
                                                   collection_ids: List[str],
                                                   user_id: str,
                                                   limit: int = 10) -> List[Any]:
        try:
            async def process_search_multiple_collections(
                                                            query_embedding: List[float],
                                                            collection_id: str,
                                                            user_id: str,
                                                            limit: int = 10):
                try:
                    results = self.search_collection(
                        query_embedding=query_embedding,
                        collection_id=collection_id,
                        user_id=user_id,
                        limit=limit
                    )
                    # Tag results with collection ID for tracking
                    for result in results:
                        result._collection_id = collection_id
                    return result
                except Exception as e:
                    logger.error(f"Error in process parrallel collection {e}")
                    return []


            collection_results_list = await asyncio.gather(
                *[process_search_multiple_collections(
                    query_embedding,
                    collection_id,
                    user_id,
                    limit
                ) for collection_id in collection_ids]
            )
            collection_results_list.sort(key=lambda x: getattr(x, 'score', 0), reverse=True)
            return collection_results_list
        except Exception as e:
            logger.error(f"Error in search parrallel collection {e}")
            return []



    async def search_multiple_collections(self,
                                          query: str,
                                          collection_ids: List[str],
                                          user_id: str,
                                          limit: int = 10) -> List[Any]:
        """
        Perform dense search across multiple collections.

        Args:
            query: User query text
            collection_ids: List of collections to search
            user_id: User ID for filtering
            limit: Maximum results per collection

        Returns:
            Combined and sorted results from all collections
        """
        # Generate embedding once for all collections
        query_embedding = await self.generate_query_embedding(query)

        all_results = []

        for collection_id in collection_ids:
            results = self.search_collection(
                query_embedding=query_embedding,
                collection_id=collection_id,
                user_id=user_id,
                limit=limit
            )

            # Tag results with collection ID for tracking
            for result in results:
                result._collection_id = collection_id

            all_results.extend(results)

        # Sort by score descending
        all_results.sort(key=lambda x: getattr(x, 'score', 0), reverse=True)

        logger.info(f"Dense search across {len(collection_ids)} collections: {len(all_results)} total results")
        return all_results
