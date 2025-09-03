import os
import sys
from dotenv import load_dotenv
from fastmcp import FastMCP
from motor.motor_asyncio import AsyncIOMotorClient

from fastmcp.server.auth.providers.jwt import JWTVerifier

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.summarization import DocumentSummarizer

load_dotenv()

mongo_uri = os.getenv("MONGODB_URI")
if not mongo_uri:
    raise ValueError("MONGODB_URI environment variable is required")

mongo_client = AsyncIOMotorClient(mongo_uri)
summarizer = DocumentSummarizer(mongo_client)

# auth (https://gofastmcp.com/servers/auth/token-verification#jwks-endpoint-integration)
public_key = os.getenv("PUBLIC_KEY")
issuer = os.getenv("ISSUER")

if public_key and public_key.startswith("-----BEGIN CERTIFICATE-----"):
    verifier = JWTVerifier(
        public_key=public_key,
        issuer=issuer,
    )
elif public_key:
    verifier = JWTVerifier(
        jwks_uri=public_key,
        issuer=issuer,
    )
else:
    raise ValueError("PUBLIC_KEY environment variable is not set or invalid.")


mcp = FastMCP(
    "DocDBSummarizerService",
    instructions="Summarize documents by user_id and document_id from MongoDB.",
    host="0.0.0.0",
    port=8003,
    auth=verifier
)

@mcp.tool()
async def summarize_by_detail_level(
    user_id: str,
    document_id: str,
    summarization_level: str = "medium",
    additional_instructions: str = None
) -> str:
    """
    Summarize document with detail level control.

    Args:
        user_id: User ID for document access
        document_id: Document ID to summarize
        summarization_level: Detail level (concise, medium, detailed)
        additional_instructions: Additional instructions for customizing the summary

    Returns:
        Document summary with word count
    """
    try:
        summary, word_count = await summarizer.summarize_document(
            user_id=user_id,
            document_id=document_id,
            level=summarization_level,
            further_instruction=additional_instructions
        )
        return f"Summary ({word_count} words):\n\n{summary}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def summarize_by_word_count(
    user_id: str,
    document_id: str,
    num_words: int = 100,
    additional_instructions: str = None
) -> str:
    """
    Summarize document to target word count.

    Args:
        user_id: User ID for document access
        document_id: Document ID to summarize
        num_words: Target word count
        additional_instructions: Additional instructions for customizing the summary

    Returns:
        Document summary with actual word count
    """
    try:
        summary, actual_word_count = await summarizer.summarize_document_with_word_count(
            user_id=user_id,
            document_id=document_id,
            num_words=num_words,
            further_instruction=additional_instructions
        )
        return f"Summary (Target: {num_words} words, Actual: {actual_word_count} words):\n\n{summary}"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    print("DocDB Summarizer MCP server streamable-http is running on port 8003...")
    mcp.run(transport="streamable-http")
