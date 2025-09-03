import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from motor.motor_asyncio import AsyncIOMotorClient
from services.translation import DocumentTranslator
from services.utils import get_llm_client
from fastmcp.server.auth.providers.jwt import JWTVerifier

load_dotenv()

mongo_uri = os.getenv("MONGODB_URI")
if not mongo_uri:
    raise ValueError("Missing required environment variable: MONGODB_URI")

mongo_client = AsyncIOMotorClient(mongo_uri)

llm_client = get_llm_client()

translator = DocumentTranslator(mongo_client, llm_client)

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
    "DocumentTranslationService",
    instructions="Translate documents by user_id and document_id from MongoDB.",
    host="0.0.0.0",
    port=8004,
    auth=verifier
)

@mcp.tool()
async def translate_document(
    user_id: str,
    document_id: str,
    target_lang: str,
    additional_instructions: str = None
) -> str:
    """
    Translate document to target language.

    Args:
        user_id: User ID for document access
        document_id: Document ID to translate
        target_lang: Target language for translation
        additional_instructions: Additional instructions for customizing the translation

    Returns:
        Translated document text with word count
    """
    try:
        translated_text, word_count = await translator.translate_document(
            user_id=user_id,
            document_id=document_id,
            target_lang=target_lang,
            additional_instructions=additional_instructions
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
    print("Translation MCP server streamable-http is running on port 8004...")
    mcp.run(transport="streamable-http")
