import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_COLLECTION_NAME = "mcp"
QDRANT_HOST = os.getenv("QDRANT_HOST")
DEFAULT_QDRANT_PORT = 6333
VECTOR_SIZE = 3072

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB")

class ChunkingMethod:
    RECURSIVE_CHARACTER = "recursive_character"
    CHARACTER = "character"
    TOKEN = "token"
    SPACY = "spacy"
    NLTK = "nltk"
    MARKDOWN_HEADER = "markdown_header"
    HTML_HEADER = "html_header"
    PYTHON_CODE = "python_code"
    LATEX = "latex"
    CUSTOM_TOKEN = "custom_token"