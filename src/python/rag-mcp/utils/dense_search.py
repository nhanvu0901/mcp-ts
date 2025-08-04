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
                                                   query: str,
                                                   collection_ids: List[str],
                                                   user_id: str,
                                                   limit: int = 10) -> List[Any]:
        try:

            MAX_CONCURRENT_SEARCHES = 5
            SEARCH_TIMEOUT = 30

            async def process_search_multiple_collections(
                    query_embedding: List[float],
                    collection_id: str,
                    user_id: str,
                    limit: int = 10):
                try:
                    results = await asyncio.wait_for(
                        self.search_collection(
                            query_embedding=query_embedding,
                            collection_id=collection_id,
                            user_id=user_id,
                            limit=limit
                        ),
                        timeout=SEARCH_TIMEOUT
                    )
                    for result in results:
                        result._collection_id = collection_id
                    return results
                except asyncio.TimeoutError:
                    logger.warning(f"Search timeout for collection {collection_id}")
                    return []
                except Exception as e:
                    logger.error(f"Error in process parallel collection {collection_id}: {e}")
                    return []

            query_embedding = await self.generate_query_embedding(query)

            semaphore = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)

            async def controlled_search(collection_id):
                async with semaphore:
                    return await process_search_multiple_collections(
                        query_embedding,
                        collection_id,
                        user_id,
                        limit
                    )

            collection_results_list = await asyncio.gather(
                *[controlled_search(collection_id) for collection_id in collection_ids],
                return_exceptions=True  # Don't fail entire operation if one collection fails
            )

            all_results = []
            for collection_results in collection_results_list:
                if isinstance(collection_results, Exception):
                    logger.error(f"Collection search failed: {collection_results}")
                    continue
                if collection_results:
                    all_results.extend(collection_results)

            if not all_results:
                logger.warning(f"No results found for query: {query}")
                return []

            all_results.sort(key=lambda x: getattr(x, 'score', 0), reverse=True)
            return all_results[:limit] if limit else all_results

        except Exception as e:
            logger.error(f"Error in search parallel collection: {e}")
            return []