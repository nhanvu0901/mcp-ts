import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
import logging
from typing import List, Any
from utils.config import config
import time

from utils import (
    HybridSearchService,
    QueryExpansionService,
    TfidfService,
    DenseSearchService,
    FusionService,
    LLMRerankerService,
    create_reranking_metadata
)

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
ENABLE_LLM_RERANKING = config.ENABLE_LLM_RERANKING
# Initialize MCP Server
mcp = FastMCP(
    config.SERVICE_NAME,
    host=config.SERVICE_HOST,
    port=config.SERVICE_PORT,
)

# Initialize clients and services
qdrant_client = QdrantClient(**config.get_qdrant_config())

# Use the new embedding model configuration through LiteLLM proxy
embedding_model = config.get_embedding_model()

llm_client = config.get_llm_config()

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

query_expansion_service = QueryExpansionService(llm_client, hybrid_search_service,
                                                fusion_service) if ENABLE_QUERY_EXPANSION else None
reranker_service = LLMRerankerService(config.get_reranker_config()) if ENABLE_LLM_RERANKING else None


def format_results_response(results: List[Any], reranking_metadata: dict = None) -> str:
    """
    Format search results with inline citations and optional reranking metadata.

    Args:
        results: List of search results from Qdrant
        reranking_metadata: Optional metadata about reranking process

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

        # Log with reranking info if available
        if hasattr(result, 'reranker_score'):
            logger.debug(f"Result {i + 1}: {document_name}, Hybrid: {score:.3f}, "
                         f"Reranker: {result.reranker_score}, Final Rank: {result.final_rank}")
        else:
            logger.debug(f"Result {i + 1}: {document_name}, Score: {score:.3f}")

    response_text = "\n\n".join(formatted_results)

    # Append reranking metadata if available (for debugging/transparency)
    if reranking_metadata and reranking_metadata.get('enabled'):
        metadata_note = (f"\n\n[Reranking: {reranking_metadata['candidates_processed']} → "
                         f"{reranking_metadata['final_results']} results, "
                         f"{reranking_metadata['processing_time_ms']:.0f}ms]")
        response_text += metadata_note

    return response_text


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

        # Adjust search limit for reranking (get more candidates for reranking)
        search_limit = config.RERANKER_TOP_K if ENABLE_LLM_RERANKING else limit
        final_limit = min(config.RERANKER_TOP_N, limit) if ENABLE_LLM_RERANKING else limit

        # Perform initial search with query expansion if enabled
        if ENABLE_QUERY_EXPANSION:
            logger.info("Query expansion enabled - using expanded retrieval")
            initial_results = await query_expansion_service.perform_query_expansion_retrieval(
                query, user_id, collection_id, search_limit, dense_weight, normalization
            )
        else:
            # Standard search without query expansion
            if search_type == "hybrid":
                initial_results = await hybrid_search_service.perform_hybrid_search(
                    query=query,
                    collection_ids=collection_id,
                    user_id=user_id,
                    limit=search_limit,
                    dense_weight=dense_weight,
                    normalization=normalization,
                    fusion_method=fusion_method
                )
            else:
                initial_results = await perform_dense_only_search(
                    query=query,
                    collection_ids=collection_id,
                    user_id=user_id,
                    limit=search_limit
                )

        if SIMILARITY_THRESHOLD > 0.0:
            initial_results = [r for r in initial_results if getattr(r, 'score', 0) >= SIMILARITY_THRESHOLD]
            logger.info(f"Applied similarity threshold {SIMILARITY_THRESHOLD}: {len(initial_results)} results remain")

        # Initialize reranking metadata
        reranking_metadata = create_reranking_metadata(
            enabled=False,
            candidates_processed=len(initial_results),
            final_results=len(initial_results),
            processing_time_ms=0
        )

        # Apply LLM reranking if enabled and results available
        if ENABLE_LLM_RERANKING and initial_results:
            try:
                start_time = time.time()
                logger.info(f"Starting LLM reranking on {len(initial_results)} candidates")

                reranked_results = await reranker_service.rerank_results(
                    query=query,
                    candidates=initial_results,
                    limit=final_limit
                )

                processing_time = (time.time() - start_time) * 1000
                final_results = reranked_results

                # Update reranking metadata
                reranking_metadata = create_reranking_metadata(
                    enabled=True,
                    candidates_processed=len(initial_results),
                    final_results=len(final_results),
                    processing_time_ms=processing_time
                )

                logger.info(f"LLM reranking completed: {len(initial_results)} → {len(final_results)} results")

            except Exception as e:
                logger.error(f"LLM reranking failed, using original results: {e}")
                final_results = initial_results[:final_limit]
        else:
            # No reranking - just take top N from initial results
            final_results = initial_results[:limit]

        return format_results_response(final_results, reranking_metadata)

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


if __name__ == "__main__":
    logger.info("RAG Service MCP server starting up...")
    logger.info(f"Using LiteLLM proxy at: {config.LITELLM_PROXY_URL}")
    logger.info(f"Embedding model via LiteLLM: {config.LLM_EMBEDDING_MODEL}")
    logger.info(f"Query expansion: {'ENABLED' if ENABLE_QUERY_EXPANSION else 'DISABLED'}")
    logger.info(f"LLM reranking: {'ENABLED' if ENABLE_LLM_RERANKING else 'DISABLED'}")
    mcp.run(transport="sse")
    logger.info("RAG Service MCP server shut down.")
