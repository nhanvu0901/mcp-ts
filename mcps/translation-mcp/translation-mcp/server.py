import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from motor.motor_asyncio import AsyncIOMotorClient
from services.translation import DocumentTranslator
from services.utils import get_llm_client

load_dotenv()

mongo_uri = os.getenv("MONGODB_URI")
if not mongo_uri:
    raise ValueError("Missing required environment variable: MONGODB_URI")

mongo_client = AsyncIOMotorClient(mongo_uri)

llm_client = get_llm_client()

translator = DocumentTranslator(mongo_client, llm_client)

mcp = FastMCP(
    "DocumentTranslationService",
    instructions="Translate documents by user_id and document_id from MongoDB.",
    host="0.0.0.0",
    port=8004,
)

@mcp.tool()
async def translate_document(
    user_id: str,
    document_id: str,
    target_lang: str
) -> str:
    """
    Translate document to target language.

    Args:
        user_id: User ID for document access
        document_id: Document ID to translate
        target_lang: Target language for translation

    Returns:
        Translated document text with word count
    """
    try:
        translated_text, word_count = await translator.translate_document(
            user_id=user_id,
            document_id=document_id,
            target_lang=target_lang
        )
        return f"Translation ({word_count} words):\n\n{translated_text}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def translate_text(
    text: str,
    target_lang: str
) -> str:
    """
    Translate raw text to target language.

    Args:
        text: Text to translate
        target_lang: Target language for translation

    Returns:
        Translated text
    """
    try:
        translated_text = await translator.translate_text(text, target_lang)
        return translated_text
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    print("Translation MCP server is running on port 8004...")
    mcp.run(transport="streamable-http")
