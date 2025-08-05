import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
import logging
import asyncio
from typing import List, Any

# Import new utility services
from utils.tfidf_search import TfidfService
from utils.dense_search import DenseSearchService
from utils.fusion_score import FusionService, FusionMethod, NormalizationMethod
from utils.query_expansion import (
    QueryExpansionService,
    ENABLE_QUERY_EXPANSION,
)

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment Configuration
QDRANT_HOST = "localhost"
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Search Configuration
DEFAULT_DENSE_WEIGHT = float(os.getenv("DENSE_WEIGHT", "0.6"))
DEFAULT_SEARCH_TYPE = "hybrid"

DEFAULT_FUSION_METHOD = "weighted"
SIMILARITY_THRESHOLD = "0.0"

DEFAULT_NORMALIZATION = "min_max"
EXPANSION_FUSION_METHOD = os.getenv("EXPANSION_FUSION_METHOD")
# TF-IDF Configuration
TFIDF_MODELS_DIR = os.getenv("TFIDF_MODELS_DIR", "/app/tfidf_models")

# Initialize MCP Server
mcp = FastMCP(
    "RAGService",
    instructions="RAG service that searches and retrieves relevant document chunks with inline source references using hybrid search (dense + sparse vectors).",
    host="0.0.0.0",
    port=8002,
)

# Initialize clients and services
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

embedding_model = AzureOpenAIEmbeddings(
    model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
    azure_endpoint=os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY"),
    openai_api_version=os.getenv("AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION")
)

llm_client = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_deployment=os.getenv("AZURE_OPENAI_MODEL_NAME"),
    api_version=os.getenv("AZURE_OPENAI_MODEL_API_VERSION"),
    temperature=0.3
)

# Initialize service classes
tfidf_service = TfidfService(models_dir=TFIDF_MODELS_DIR)
dense_search_service = DenseSearchService(embedding_model, qdrant_client)
fusion_service = FusionService(default_dense_weight=DEFAULT_DENSE_WEIGHT)
query_expansion_service = QueryExpansionService(llm_client)


def format_results_response(results: List[Any]) -> str:
    """
    Format search results with inline citations.

    Args:
        results: List of search results from Qdrant

    Returns:
        Formatted text with SOURCE_CITATION markers
    """
    if not results:
        return "No relevant documents found."

    formatted_results = []
    for i, result in enumerate(results):
        text = result.payload.get('text', str(result.payload))
        document_name = result.payload.get('document_name', 'Unknown Document')
        page_number = result.payload.get('page_number', 1)
        chunk_id = result.payload.get('chunk_id', i)
        file_type = result.payload.get('file_type', '').lower()
        score = getattr(result, 'score', 0.0)

        # Generate appropriate citation format
        if file_type in ['pdf', 'doc', 'docx']:
            citation = f"SOURCE_CITATION: \\cite{{{document_name}, page {page_number}}}"
        else:
            citation = f"SOURCE_CITATION: \\cite{{{document_name}, chunk {chunk_id}}}"

        formatted_chunk = f"{text} {citation}"
        formatted_results.append(formatted_chunk)

        logger.debug(f"Result {i + 1}: {document_name}, Score: {score:.3f}")

    return "\n\n".join(formatted_results)


async def perform_hybrid_search(query: str,
                                collection_ids: List[str],
                                user_id: str,
                                limit: int = 10,
                                dense_weight: float = None,
                                normalization: str = "min_max",
                                fusion_method: str = "weighted") -> List[Any]:
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
        dense_weight = DEFAULT_DENSE_WEIGHT

    logger.info(f"Hybrid search: query='{query}', collections={len(collection_ids)}, dense_weight={dense_weight}")

    # Generate dense embedding
    query_embedding = await dense_search_service.generate_query_embedding(query)

    all_results = []

    async def search_collection_parallel(collection_id: str):
        """Helper function to perform parallel dense and sparse search for a single collection."""
        logger.debug(f"Processing collection: {collection_id}")

        # Prepare sparse search coroutine
        async def perform_sparse_search():
            sparse_results = []
            sparse_vector = tfidf_service.query_to_sparse_vector(query, collection_id)

            if sparse_vector and sparse_vector.indices:
                try:
                    from qdrant_client.models import NamedSparseVector
                    sparse_results = qdrant_client.search(
                        collection_name=collection_id,
                        query_vector=NamedSparseVector(name="text_sparse", vector=sparse_vector),
                        query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
                        limit=limit * 2
                    )
                    logger.debug(f"Sparse search found {len(sparse_results)} results in {collection_id}")
                except Exception as e:
                    logger.warning(f"Sparse search failed for {collection_id}: {e}")
                    sparse_results = []
            else:
                logger.debug(f"No sparse vector available for {collection_id}")

            return sparse_results


        async def perform_dense_search():
            return dense_search_service.search_collection(
                query_embedding=query_embedding,
                collection_id=collection_id,
                user_id=user_id,
                limit=limit * 2
            )

        try:
            dense_results, sparse_results = await asyncio.gather(
                perform_dense_search(),
                perform_sparse_search()
            )
            logger.info("Finished parallel dense and sparse search")
            if sparse_results:
                norm_method = NormalizationMethod(normalization)
                fuse_method = FusionMethod(fusion_method)

                collection_results = fusion_service.fuse_dense_sparse(
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
            logger.info(f"Error parallel {e}")
            return []

    collection_results_list = await asyncio.gather(
        *[search_collection_parallel(collection_id) for collection_id in collection_ids]
    )

    for collection_results in collection_results_list:
        all_results.extend(collection_results)

    all_results.sort(key=lambda x: getattr(x, 'score', 0), reverse=True)

    logger.info(f"Hybrid search completed: {len(all_results)} total results")
    return all_results[:limit]


async def perform_dense_only_search(query: str,
                                    collection_ids: List[str],
                                    user_id: str,
                                    limit: int = 10) -> List[Any]:
    """
    Perform dense-only semantic search.

    Args:
        query: User query text
        collection_ids: Collections to search
        user_id: User ID for filtering
        limit: Maximum results

    Returns:
        Dense search results
    """
    logger.info(f"Dense-only search: query='{query}', collections={len(collection_ids)}")

    results = await dense_search_service.search_parallel_multiple_collections(
        query=query,
        collection_ids=collection_ids,
        user_id=user_id,
        limit=limit
    )

    return results


async def perform_query_expansion_retrieval(query: str,
                                            user_id: str,
                                            collection_ids: List[str],
                                            limit: int,
                                            dense_weight: float,
                                            normalization: str) -> str:
    """
    Perform retrieval with query expansion.

    Args:
        query: Original user query
        user_id: User ID for filtering
        collection_ids: Collections to search
        limit: Maximum results
        dense_weight: Weight for dense scores
        normalization: Score normalization method

    Returns:
        Formatted results string
    """
    logger.info(f"Starting query expansion retrieval for: '{query}'")

    # Generate query variants
    query_variants = await query_expansion_service.generate_query_variants(query)
    all_queries = [query] + query_variants

    # Perform retrieval for each query variant
    results_by_query = []

    for query_text in all_queries:
        query_results = await perform_hybrid_search(
            query=query_text,
            collection_ids=collection_ids,
            user_id=user_id,
            limit=limit,
            dense_weight=dense_weight,
            normalization=normalization
        )
        results_by_query.append(query_results)

    fused_results = fusion_service.fuse_query_variants(results_by_query, method=EXPANSION_FUSION_METHOD)

    # Take top results and convert back to expected format
    top_results = [result for result, score in fused_results[:limit]]

    logger.info(f"Query expansion completed: {len(top_results)} final results")
    return format_results_response(top_results)


@mcp.tool()
async def retrieve(query: str,
                   user_id: str,
                   collection_id: List[str],
                   limit: int = 5,
                   search_type: str = DEFAULT_SEARCH_TYPE,
                   dense_weight: float = DEFAULT_DENSE_WEIGHT,
                   normalization: str = DEFAULT_NORMALIZATION,
                   fusion_method: str = DEFAULT_FUSION_METHOD) -> str:
    """
    Search and retrieve relevant document chunks with configurable search methods.

    Args:
        query: Text query to search for
        user_id: User ID to filter documents
        collection_id: List of collection IDs to search
        limit: Maximum number of results to return
        search_type: Search method ("hybrid", "dense", "sparse")
        dense_weight: Weight for dense search (0.0-1.0)
        normalization: Score normalization method
        fusion_method: Method for combining results

    Returns:
        Formatted text with inline citations
    """
    try:
        # Validate inputs
        if not isinstance(collection_id, list) or not all(isinstance(cid, str) for cid in collection_id):
            return f"Invalid collection_id type: expected list of strings, got {type(collection_id)}: {collection_id!r}"
        logger.info(f"Starting {search_type} search for query: '{query}' in {len(collection_id)} collections")

        # Check if query expansion is enabled
        if ENABLE_QUERY_EXPANSION:
            logger.info("Query expansion enabled - using expanded retrieval")
            return await perform_query_expansion_retrieval(
                query, user_id, collection_id, limit, dense_weight, normalization
            )

        # Perform search based on type
        if search_type == "hybrid":
            results = await perform_hybrid_search(
                query=query,
                collection_ids=collection_id,
                user_id=user_id,
                limit=limit,
                dense_weight=dense_weight,
                normalization=normalization,
                fusion_method=fusion_method
            )
        else:
            results = await perform_dense_only_search(
                query=query,
                collection_ids=collection_id,
                user_id=user_id,
                limit=limit
            )

        # Apply similarity threshold if configured
        if SIMILARITY_THRESHOLD > 0.0:
            results = [r for r in results if getattr(r, 'score', 0) >= SIMILARITY_THRESHOLD]
            logger.info(f"Applied similarity threshold {SIMILARITY_THRESHOLD}: {len(results)} results remain")

        return format_results_response(results)

    except Exception as e:
        logger.error(f"Error during retrieval for query '{query}': {e}", exc_info=True)
        return f"Error during retrieval: {str(e)}"


@mcp.tool()
async def retrieve_dense(query: str, user_id: str, collection_id: List[str], limit: int = 5) -> str:
    """
    Query using dense search only (semantic similarity).

    Args:
        query: Text query to search for
        user_id: User ID to filter documents
        collection_id: List of collection IDs
        limit: Maximum number of results to return
    """
    return await retrieve(query, user_id, collection_id, limit, "dense")


# @mcp.tool()
# async def retrieve_hybrid(query: str,
#                           user_id: str,
#                           collection_id: List[str],
#                           limit: int = 5,
#                           dense_weight: float = None,
#                           normalization: str = None,
#                           fusion_method: str = None) -> str:
#     """
#     Query using hybrid search (dense + sparse vectors).
#
#     Args:
#         query: Text query to search for
#         user_id: User ID to filter documents
#         collection_id: List of collection IDs
#         limit: Maximum number of results to return
#         dense_weight: Weight for dense search (0.0-1.0)
#         normalization: Score normalization method
#
#     Returns:
#         Formatted text with inline citations
#     """
#     return await retrieve(query, user_id, collection_id, limit, "hybrid", dense_weight, normalization)


if __name__ == "__main__":
    logger.info("RAG Service MCP server starting up...")

    asyncio.run(perform_hybrid_search(
            query="What is ai agent",
            collection_ids=['79433835-c64d-4ac0-b143-6fdb018cdea5','aba7e48a-53a0-4d25-bab7-213b5ef75d1c','caa82a06-02c2-4dbd-8307-39e1acd8348a'],
            user_id='nhan',
            limit=10,
            dense_weight=0.6,
            normalization='min_max',
            fusion_method='weighted'
        ))

    mcp.run(transport="sse")
    logger.info("RAG Service MCP server shut down.")
