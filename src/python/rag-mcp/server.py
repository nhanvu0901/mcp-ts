import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
from langchain_openai import AzureOpenAIEmbeddings

load_dotenv()

azure_embedding_endpoint = os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT")
azure_embedding_api_key = os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY")
azure_embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
azure_embedding_api_version = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION")

if not all([azure_embedding_endpoint, azure_embedding_api_key, azure_embedding_model, azure_embedding_api_version]):
    raise ValueError("Missing required Azure OpenAI environment variables")

qdrant_client = QdrantClient(host="localhost", port=6333)
embedding_model = AzureOpenAIEmbeddings(
    model=azure_embedding_model,
    azure_endpoint=azure_embedding_endpoint,
    api_key=azure_embedding_api_key,
    openai_api_version=azure_embedding_api_version
)

mcp = FastMCP(
    "RAGService",
    instructions="RAG service for searching and retrieving document chunks based on queries.",
    host="0.0.0.0",
    port=8002,
)


@mcp.tool()
async def retrieve(
    query: str, 
    qdrant_collection_name: str,
    limit: int = 5
) -> str:
    """
    Query Qdrant vector database and return matching results.
    
    Args:
        query: Text query to search for
        qdrant_collection_name: Actual Qdrant collection name (uuid_collectionname)
        limit: Maximum number of results to return
    
    Returns:
        Concatenated text content from retrieved documents
    """
    try:
        query_embedding = embedding_model.embed_query(query)
        
        search_results = qdrant_client.search(
            collection_name=qdrant_collection_name,
            query_vector=query_embedding,
            limit=limit
        )
        
        results = []
        for result in search_results:
            text = result.payload.get('text', str(result.payload))
            results.append(text)
        
        return "\n".join(results)
        
    except Exception as e:
        return f"Error during query: {str(e)}"

if __name__ == "__main__":
    print("RAG Service MCP server is running on port 8002...")
    mcp.run(transport="sse")