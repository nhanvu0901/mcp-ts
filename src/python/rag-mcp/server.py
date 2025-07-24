import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
from langchain_openai import AzureOpenAIEmbeddings
import logging
import collections.abc

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

#qdrant_host = 'localhost
qdrant_host = os.getenv("QDRANT_HOST")
mcp = FastMCP(
    "RAGService",
    instructions="RAG service that searches and retrieves relevant document chunks with inline source references.",
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


@mcp.tool()
async def retrieve(query: str, user_id: str, collection_id: list[str], limit: int = 5) -> str:
    """
    Query Qdrant vector database and return matching results with inline citations.
    Args:
        query: Text query to search for
        user_id: User ID to filter documents
        collection_id: List of collection IDs (Qdrant collection names, always UUIDs)
        limit: Maximum number of results to return
    Returns:
        Formatted text with inline citations at the end of each text chunk
    """
    try:
        if not isinstance(collection_id, list) or not all(isinstance(cid, str) for cid in collection_id):
            return f"Invalid collection_id type: expected list of strings, got {type(collection_id)}: {collection_id!r}"
        logger.debug(f"Collection ID(s): '{collection_id}'")
        logger.debug(f"Generating embedding for query: '{query}'")
        query_embedding = embedding_model.embed_query(query)
        logger.debug("Query embedding generated successfully.")

        all_results = []
        for cid in collection_id:
            logger.debug(f"Searching Qdrant collection: '{cid}' with filter user_id: '{user_id}'")
            search_response = qdrant_client.query_points(
                collection_name=cid,
                query=query_embedding,
                query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
                limit=limit
            )
            results = getattr(search_response, 'points', [])
            for r in results:
                # Attach collection id for citation if needed
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
            # Optionally include collection id in citation if needed
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


if __name__ == "__main__":
    print("RAG Service MCP server running on port 8002...")
    logger.info("RAG Service MCP server starting up...")
    mcp.run(transport="sse")
    logger.info("RAG Service MCP server shut down.")