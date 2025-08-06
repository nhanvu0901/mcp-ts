import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
import logging
import asyncio
from typing import List, Any
from utils.config import config
# Import new utility services
from utils.tfidf_search import TfidfService
from utils.dense_search import DenseSearchService
from utils.fusion_score import FusionService
from utils.query_expansion import QueryExpansionService
from utils.hybrid_search import HybridSearchService
load_dotenv()
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
ENABLE_QUERY_EXPANSION = os.getenv("ENABLE_QUERY_EXPANSION", "false").lower() == "true"
# Search Configuration
DEFAULT_DENSE_WEIGHT = config.DEFAULT_DENSE_WEIGHT
DEFAULT_SEARCH_TYPE = config.DEFAULT_SEARCH_TYPE

SIMILARITY_THRESHOLD = config.SIMILARITY_THRESHOLD
DEFAULT_NORMALIZATION = config.DEFAULT_NORMALIZATION
EXPANSION_FUSION_METHOD = config.EXPANSION_FUSION_METHOD
DEFAULT_FUSION_METHOD = config.DEFAULT_FUSION_METHOD
# TF-IDF Configuration
TFIDF_MODELS_DIR = config.TFIDF_MODELS_DIR

# Initialize MCP Server
mcp = FastMCP(
    config.SERVICE_NAME,
    host=config.SERVICE_HOST,
    port=config.SERVICE_PORT,
)

# Initialize clients and services
qdrant_client = QdrantClient(**config.get_qdrant_config())

embedding_model = AzureOpenAIEmbeddings(
    **config.get_embedding_config()
)

llm_client = AzureChatOpenAI(
    **config.get_llm_config()
)

# Initialize service classes
tfidf_service = TfidfService(models_dir=TFIDF_MODELS_DIR)
dense_search_service = DenseSearchService(embedding_model, qdrant_client)
fusion_service = FusionService(default_dense_weight=DEFAULT_DENSE_WEIGHT)
hybrid_search_service = HybridSearchService(
    qdrant_client,
    embedding_model,
    tfidf_service,
    fusion_service
)
query_expansion_service = QueryExpansionService(llm_client,hybrid_search_service,fusion_service)


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
        if file_type in ['pdf', 'doc', 'docx', 'pptx', 'ppt']:
            citation = f"SOURCE_CITATION: \\cite{{{document_name}, page {page_number}}}"
        else:
            citation = f"SOURCE_CITATION: \\cite{{{document_name}, chunk {chunk_id}}}"

        formatted_chunk = f"{text} {citation}"
        formatted_results.append(formatted_chunk)

        logger.debug(f"Result {i + 1}: {document_name}, Score: {score:.3f}")

    return "\n\n".join(formatted_results)


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

        if ENABLE_QUERY_EXPANSION:
            logger.info("Query expansion enabled - using expanded retrieval")
            return await query_expansion_service.perform_query_expansion_retrieval(
                query, user_id, collection_id, limit, dense_weight, normalization
            )

        if search_type == "hybrid":
            results = await hybrid_search_service.perform_hybrid_search(
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
    mcp.run(transport="sse")
    logger.info("RAG Service MCP server shut down.")
