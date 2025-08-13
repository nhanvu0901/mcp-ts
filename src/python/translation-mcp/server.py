import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from motor.motor_asyncio import AsyncIOMotorClient
from langchain_openai import ChatOpenAI

from services.translation import DocumentTranslator

load_dotenv()

mongo_uri = os.getenv("MONGODB_URI")
if not mongo_uri:
    raise ValueError("Missing required environment variable: MONGODB_URI")

mongo_client = AsyncIOMotorClient(mongo_uri)

litellm_proxy_url = os.getenv("LITELLM_PROXY_URL")
litellm_app_key = os.getenv("LITELLM_APP_KEY")
azure_model = os.getenv("AZURE_OPENAI_MODEL_NAME")

# Validate required environment variables
if not litellm_proxy_url:
    raise ValueError("Missing required environment variable: LITELLM_PROXY_URL")
if not litellm_app_key:
    raise ValueError("Missing required environment variable: LITELLM_APP_KEY")
if not azure_model:
    raise ValueError("Missing required environment variable: LITELLM_DEFAULT_MODEL")

llm_client = ChatOpenAI(
    model=azure_model,
    api_key=litellm_app_key,
    base_url=f"{litellm_proxy_url}/v1",
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
    try:
        translated_text = await translator.translate_text(text, target_lang)
        return translated_text
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    print("Translation MCP server is running on port 8004...")
    mcp.run(transport="sse")