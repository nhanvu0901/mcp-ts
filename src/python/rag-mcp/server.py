import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
from langchain_openai import AzureOpenAIEmbeddings
import logging
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, # Set desired logging level (e.g., DEBUG, INFO, WARNING)
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
qdrant_host = os.getenv("QDRANT_HOST")
mcp = FastMCP(
    "RAGService",
    instructions="RAG service that searches and retrieves relevant document chunks based on queries.",
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
async def retrieve(query: str, user_id: str, collection_id: str, limit: int = 5) -> str:
    """
    Query Qdrant vector database and return matching results from user documents.

    Args:
        query: Text query to search for
        user_id: User ID to filter documents
        collection_id: Collection ID (used as Qdrant collection name)
        limit: Maximum number of results to return

    Returns:
        Concatenated text content from retrieved documents
    """
    logger.info(f"${qdrant_client}")
    try:
        logger.debug(f"Generating embedding for query: '{query}'")
        query_embedding = embedding_model.embed_query(query)
        logger.debug("Query embedding generated successfully.")

        logger.debug(f"Searching Qdrant collection: '{collection_id}' with filter user_id: '{user_id}'")
        search_results = qdrant_client.search(
            collection_name=collection_id,
            query_vector=query_embedding,
            query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
            limit=limit
        )
        logger.info(f"Found {len(search_results)} results from Qdrant.")

        results = []
        for i, result in enumerate(search_results):
            text = result.payload.get('text', str(result.payload))
            results.append(text)
            logger.debug(f"Result {i+1}: {text[:100]}...") # Log first 100 characters of each result

        return "\n".join(results)

    except Exception as e:
        logger.error(f"Error during retrieval for query '{query}': {e}", exc_info=True)
        return f"Error during retrieval: {str(e)}"


if __name__ == "__main__":
    print("RAG Service MCP server running on port 8002...")
    logger.info("RAG Service MCP server starting up...")
    mcp.run(transport="sse")
    logger.info("RAG Service MCP server shut down.")