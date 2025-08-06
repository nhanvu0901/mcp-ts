import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class RAGConfig:
    """Centralized configuration for RAG Service"""

    # Service Configuration
    SERVICE_NAME: str = "RAGService"
    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = 8002

    # Qdrant Configuration
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))

    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_MODEL_NAME: str = os.getenv("AZURE_OPENAI_MODEL_NAME", "")
    AZURE_OPENAI_MODEL_API_VERSION: str = os.getenv("AZURE_OPENAI_MODEL_API_VERSION", "")

    # Embedding Configuration
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "")
    AZURE_OPENAI_EMBEDDING_ENDPOINT: str = os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT", "")
    AZURE_OPENAI_EMBEDDING_API_KEY: str = os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY", "")
    AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION: str = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION", "")
    AZURE_OPENAI_TEMPERATURE: str = 0.3
    # Search Configuration
    DEFAULT_DENSE_WEIGHT: float = float(os.getenv("DENSE_WEIGHT", "0.6"))
    DEFAULT_SEARCH_TYPE: str = "hybrid"
    DEFAULT_FUSION_METHOD: str = "weighted"
    DEFAULT_NORMALIZATION: str = "min_max"
    SIMILARITY_THRESHOLD: float = 0.0

    # TF-IDF Configuration
    TFIDF_MODELS_DIR: str = os.getenv("TFIDF_MODELS_DIR", "/app/tfidf_models")

    # Query Expansion Configuration
    ENABLE_QUERY_EXPANSION: bool = os.getenv("ENABLE_QUERY_EXPANSION", "false").lower() == "true"
    MAX_QUERY_VARIANTS: int = int(os.getenv("MAX_QUERY_VARIANTS", "3"))
    EXPANSION_FUSION_METHOD: str = os.getenv("EXPANSION_FUSION_METHOD", "rrf")

    # Performance Configuration
    MAX_CONCURRENT_SEARCHES: int = 5
    SEARCH_TIMEOUT: int = 30

    @classmethod
    def validate_config(cls) -> List[str]:
        """Validate required configuration and return list of missing variables"""
        required_vars = [
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_MODEL_NAME",
            "AZURE_OPENAI_MODEL_API_VERSION",
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
            "AZURE_OPENAI_EMBEDDING_ENDPOINT",
            "AZURE_OPENAI_EMBEDDING_API_KEY",
            "AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION"
        ]

        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)

        return missing_vars

    @classmethod
    def get_embedding_config(cls) -> dict:
        """Get embedding model configuration"""
        return {
            "model": cls.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            "azure_endpoint": cls.AZURE_OPENAI_EMBEDDING_ENDPOINT,
            "api_key": cls.AZURE_OPENAI_EMBEDDING_API_KEY,
            "openai_api_version": cls.AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION
        }

    @classmethod
    def get_llm_config(cls) -> dict:
        """Get LLM client configuration"""
        return {
            "azure_endpoint": cls.AZURE_OPENAI_ENDPOINT,
            "api_key": cls.AZURE_OPENAI_API_KEY,
            "azure_deployment": cls.AZURE_OPENAI_MODEL_NAME,
            "api_version": cls.AZURE_OPENAI_MODEL_API_VERSION,
            "temperature": cls.AZURE_OPENAI_TEMPERATURE
        }

    @classmethod
    def get_qdrant_config(cls) -> dict:
        return {
            "host": cls.QDRANT_HOST,
            "port": cls.QDRANT_PORT
        }

config = RAGConfig()