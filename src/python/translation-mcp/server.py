import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from motor.motor_asyncio import AsyncIOMotorClient
from langchain_openai import AzureChatOpenAI

from services.translation import DocumentTranslator

load_dotenv()

azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_model = os.getenv("AZURE_OPENAI_MODEL_NAME")
azure_api_version = os.getenv("AZURE_OPENAI_MODEL_API_VERSION")
mongo_uri = os.getenv("MONGODB_URI")

if not all([azure_api_key, azure_endpoint, azure_model, azure_api_version, mongo_uri]):
    raise ValueError("Missing required environment variables")

mongo_client = AsyncIOMotorClient(mongo_uri)
llm_client = AzureChatOpenAI(
    azure_endpoint=azure_endpoint,
    api_key=azure_api_key,
    azure_deployment=azure_model,
    api_version=azure_api_version,
    temperature=0
)

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
    mcp.run(transport="sse")