import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector, NamedSparseVector
from langchain_openai import AzureOpenAIEmbeddings
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import csr_matrix
import numpy as np
import pickle
import logging
import asyncio
from typing import List, Dict, Any

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

qdrant_host = os.getenv("QDRANT_HOST", "localhost")
mcp = FastMCP(
    "RAGService",
    instructions="RAG service that searches and retrieves relevant document chunks with inline source references using hybrid search (dense + sparse vectors).",
    host="0.0.0.0",
    port=8002,
)

qdrant_client = QdrantClient(host=qdrant_host, port=6333)

embedding_model = AzureOpenAIEmbeddings(
    model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
    azure_endpoint=os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY"),
    openai_api_version=os.getenv("AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION")
)

# Global TF-IDF vectorizer cache
tfidf_cache: Dict[str, TfidfVectorizer] = {}


def load_tfidf_vectorizer(collection_id: str) -> TfidfVectorizer:
    """Load TF-IDF vectorizer for a specific collection"""
    if collection_id in tfidf_cache:
        return tfidf_cache[collection_id]

    # Use shared TF-IDF models directory in Docker container
    vectorizer_path = f"/app/tfidf_models/{collection_id}_tfidf.pkl"

    if os.path.exists(vectorizer_path):
        try:
            with open(vectorizer_path, 'rb') as f:
                vectorizer = pickle.load(f)
            tfidf_cache[collection_id] = vectorizer
            logger.info(f"✅ Loaded TF-IDF vectorizer for {collection_id}")
            return vectorizer
        except Exception as e:
            logger.error(f"Error loading TF-IDF vectorizer: {e}")
            return None
    return None


def get_sparse_query_vector(query: str, vectorizer: TfidfVectorizer) -> SparseVector:
    """Convert query to sparse vector format"""
    if not vectorizer:
        return None

    try:
        tfidf_vector = vectorizer.transform([query])
        csr_vector = csr_matrix(tfidf_vector)

        indices = []
        values = []
        for i, j in zip(*csr_vector.nonzero()):
            indices.append(j)
            values.append(float(csr_vector[i, j]))

        return SparseVector(indices=indices, values=values)
    except Exception as e:
        logger.error(f"Error generating sparse query vector: {e}")
        return None


def normalize_scores(scores: List[float], method: str = "min_max") -> List[float]:
    """Normalize scores using specified method"""
    if not scores:
        return []

    scores = np.array(scores)

    if method == "min_max":
        if scores.max() == scores.min():
            return [1.0] * len(scores)
        return ((scores - scores.min()) / (scores.max() - scores.min())).tolist()

    elif method == "reciprocal_rank":
        # Convert scores to ranks, then apply reciprocal rank
        ranks = np.argsort(np.argsort(-scores)) + 1  # 1-based ranking
        return (1.0 / ranks).tolist()

    elif method == "z_score":
        if scores.std() == 0:
            return [1.0] * len(scores)
        return ((scores - scores.mean()) / scores.std()).tolist()

    else:
        return scores.tolist()


def combine_search_results(dense_results: List[Any], sparse_results: List[Any],
                          dense_weight: float = 0.6, normalization: str = "min_max") -> List[Any]:
    """Combine dense and sparse search results with weighted fusion"""
    if not dense_results and not sparse_results:
        return []

    sparse_weight = 1 - dense_weight

    # Normalize scores
    dense_scores = normalize_scores([r.score for r in dense_results], normalization)
    sparse_scores = normalize_scores([r.score for r in sparse_results], normalization)

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

        # Weighted fusion
        final_score = dense_weight * dense_score + sparse_weight * sparse_score

        # Create combined result object
        result_obj.score = final_score
        combined.append(result_obj)

    # Sort by combined score
    combined.sort(key=lambda x: x.score, reverse=True)
    return combined


async def perform_hybrid_search(query: str, query_embedding: List[float], query_sparse: SparseVector,
                               collection_id: str, user_id: str, limit: int,
                               dense_weight: float = 0.6, normalization: str = "min_max") -> List[Any]:
    """Perform hybrid search combining dense and sparse results"""
    search_limit = min(limit * 2, 50)  # Get more for reranking
    query_filter = {"must": [{"key": "user_id", "match": {"value": user_id}}]}

    # Perform dense and sparse search in parallel
    async def dense_search():
        try:
            return qdrant_client.search(
                collection_name=collection_id,
                query_vector=("text_dense", query_embedding),
                query_filter=query_filter,
                limit=search_limit
            )
        except Exception as e:
            logger.error(f"Dense search failed: {e}")
            return []

    async def sparse_search():
        if not query_sparse:
            return []
        try:
            return qdrant_client.search(
                collection_name=collection_id,
                query_vector=NamedSparseVector(name="text_sparse", vector=query_sparse),
                query_filter=query_filter,
                limit=search_limit
            )
        except Exception as e:
            logger.error(f"Sparse search failed: {e}")
            return []

    # Execute searches in parallel
    dense_results, sparse_results = await asyncio.gather(
        dense_search(), sparse_search(), return_exceptions=True
    )

    # Handle exceptions
    if isinstance(dense_results, Exception):
        logger.error(f"Dense search exception: {dense_results}")
        dense_results = []
    if isinstance(sparse_results, Exception):
        logger.error(f"Sparse search exception: {sparse_results}")
        sparse_results = []

    # Combine results
    if sparse_results:
        combined_results = combine_search_results(dense_results, sparse_results, dense_weight, normalization)
        logger.info(f"Hybrid search: {len(dense_results)} dense + {len(sparse_results)} sparse results")
    else:
        combined_results = dense_results
        logger.info(f"Fallback to dense search: {len(dense_results)} results")

    return combined_results[:limit]


@mcp.tool()
async def retrieve(query: str, user_id: str, collection_id: List[str],
                   limit: int = 5, search_type: str = "hybrid",
                   dense_weight: float = 0.6, normalization: str = "min_max") -> str:
    """
    Query Qdrant vector database using hybrid search and return matching results with inline citations.

    Args:
        query: Text query to search for
        user_id: User ID to filter documents
        collection_id: List of collection IDs (Qdrant collection names, always UUIDs)
        limit: Maximum number of results to return
        search_type: Search type - "hybrid", "dense", or "sparse"
        dense_weight: Weight for dense search in hybrid mode (0.0-1.0)
        normalization: Score normalization method - "min_max", "reciprocal_rank", or "z_score"

    Returns:
        Formatted text with inline citations at the end of each text chunk
    """
    try:
        if not isinstance(collection_id, list) or not all(isinstance(cid, str) for cid in collection_id):
            return f"Invalid collection_id type: expected list of strings, got {type(collection_id)}: {collection_id!r}"

        logger.info(f"Starting {search_type} search for query: '{query}' in collections: {collection_id}")

        # Generate dense embedding
        logger.debug(f"Generating embedding for query: '{query}'")
        query_embedding = embedding_model.embed_query(query)
        logger.debug("Query embedding generated successfully.")

        all_results = []

        for cid in collection_id:
            logger.debug(f"Processing collection: '{cid}'")

            # Load TF-IDF vectorizer for hybrid/sparse search
            query_sparse = None
            if search_type in ["hybrid", "sparse"]:
                vectorizer = load_tfidf_vectorizer(cid)
                if vectorizer:
                    query_sparse = get_sparse_query_vector(query, vectorizer)
                    if query_sparse:
                        logger.debug("Sparse query vector generated successfully")
                    else:
                        logger.warning("Failed to generate sparse query vector")
                else:
                    logger.warning(f"No TF-IDF vectorizer found for collection {cid}")

            # Perform search based on type
            if search_type == "hybrid" and query_sparse:
                # Hybrid search
                results = await perform_hybrid_search(
                    query, query_embedding, query_sparse, cid, user_id,
                    limit, dense_weight, normalization
                )

            elif search_type == "dense":
                # Dense-only search
                logger.debug("Performing dense search...")
                results = qdrant_client.search(
                    collection_name=cid,
                    query_vector=("text_dense", query_embedding),
                    query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
                    limit=limit
                )

            elif search_type == "sparse" and query_sparse:
                # Sparse-only search
                logger.debug("Performing sparse search...")
                results = qdrant_client.search(
                    collection_name=cid,
                    query_vector=NamedSparseVector(name="text_sparse", vector=query_sparse),
                    query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
                    limit=limit
                )

            else:
                # Fallback to dense search
                logger.warning(f"Invalid search_type '{search_type}' or missing sparse vector, falling back to dense search")
                results = qdrant_client.search(
                    collection_name=cid,
                    query_vector=("text_dense", query_embedding),
                    query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
                    limit=limit
                )

            # Attach collection id to results
            for r in results:
                r._collection_id = cid
            all_results.extend(results)

        logger.info(f"Found {len(all_results)} results from Qdrant across {len(collection_id)} collections.")

        # Sort all results by score descending and take top N
        all_results.sort(key=lambda x: getattr(x, 'score', 0), reverse=True)
        top_results = all_results[:limit]

        if not top_results:
            return f"No relevant documents found for query: '{query}'"

        formatted_results = []
        for i, result in enumerate(top_results):
            text = result.payload.get('text', str(result.payload))
            document_name = result.payload.get('document_name', 'Unknown Document')
            page_number = result.payload.get('page_number', 1)
            chunk_id = result.payload.get('chunk_id', i)
            file_type = result.payload.get('file_type', '').lower()
            score = result.score or 0.0

            if file_type in ['pdf', 'doc', 'docx']:
                citation = f"SOURCE_CITATION: \\cite{{{document_name}, page {page_number}}}"
            else:
                citation = f"SOURCE_CITATION: \\cite{{{document_name}, chunk {chunk_id}}}"

            formatted_chunk = f"{text} {citation}"
            formatted_results.append(formatted_chunk)

            logger.debug(f"Result {i + 1}: {document_name}, Page {page_number}, Score: {score:.3f}")

        return "\n\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Error during retrieval for query '{query}': {e}", exc_info=True)
        return f"Error during retrieval: {str(e)}"


@mcp.tool()
async def retrieve_dense(query: str, user_id: str, collection_id: List[str], limit: int = 5) -> str:
    """
    Query Qdrant using dense search only (semantic similarity).

    Args:
        query: Text query to search for
        user_id: User ID to filter documents
        collection_id: List of collection IDs
        limit: Maximum number of results to return

    Returns:
        Formatted text with inline citations
    """
    return await retrieve(query, user_id, collection_id, limit, "dense")


@mcp.tool()
async def retrieve_hybrid(query: str, user_id: str, collection_id: List[str],
                         limit: int = 5, dense_weight: float = 0.6,
                         normalization: str = "min_max") -> str:
    """
    Query Qdrant using hybrid search (dense + sparse vectors).

    Args:
        query: Text query to search for
        user_id: User ID to filter documents
        collection_id: List of collection IDs
        limit: Maximum number of results to return
        dense_weight: Weight for dense search (0.0-1.0)
        normalization: Score normalization method

    Returns:
        Formatted text with inline citations
    """
    return await retrieve(query, user_id, collection_id, limit, "hybrid", dense_weight, normalization)


if __name__ == "__main__":
    print("RAG Service MCP server running on port 8002...")
    logger.info("RAG Service MCP server starting up...")
    mcp.run(transport="sse")
    logger.info("RAG Service MCP server shut down.")