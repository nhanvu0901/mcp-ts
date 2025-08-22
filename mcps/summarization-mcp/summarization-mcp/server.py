import os
import sys
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.summarization import DocumentSummarizer

load_dotenv()

mongo_uri = os.getenv("MONGODB_URI")
if not mongo_uri:
    raise ValueError("MONGODB_URI environment variable is required")

mongo_client = AsyncIOMotorClient(mongo_uri)
summarizer = DocumentSummarizer(mongo_client)

mcp = FastMCP(
    "DocDBSummarizerService",
    instructions="Summarize documents by user_id and document_id from MongoDB.",
    host="0.0.0.0",
    port=8003,
)

@mcp.tool()
async def summarize_by_detail_level(
    user_id: str,
    document_id: str,
    summarization_level: str = "medium",
    further_instruction: str = None
) -> str:
    """
    Summarize document with detail level control.

    Args:
        user_id: User ID for document access
        document_id: Document ID to summarize
        summarization_level: Detail level (concise, medium, detailed)
        further_instruction: Additional instructions

    Returns:
        Document summary with word count
    """
    try:
        summary, word_count = await summarizer.summarize_document(
            user_id=user_id,
            document_id=document_id,
            level=summarization_level,
            further_instruction=further_instruction
        )
        return f"Summary ({word_count} words):\n\n{summary}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def summarize_by_word_count(
    user_id: str,
    document_id: str,
    num_words: int = 100
) -> str:
    """
    Summarize document to target word count.

    Args:
        user_id: User ID for document access
        document_id: Document ID to summarize
        num_words: Target word count

    Returns:
        Document summary with actual word count
    """
    try:
        summary, actual_word_count = await summarizer.summarize_document_with_word_count(
            user_id=user_id,
            document_id=document_id,
            num_words=num_words
        )
        return f"Summary (Target: {num_words} words, Actual: {actual_word_count} words):\n\n{summary}"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    print("DocDB Summarizer MCP server streamable-http is running on port 8003...")
    mcp.run(transport="streamable-http")
