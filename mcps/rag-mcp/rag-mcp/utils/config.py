import os
from typing import List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

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

    LLM_CHAT_MODEL: str = os.getenv("LLM_CHAT_MODEL")
    LLM_EMBEDDING_MODEL: str = os.getenv("LLM_EMBEDDING_MODEL")
    AZURE_OPENAI_TEMPERATURE: float = 0.3

    # Search Configuration
    DEFAULT_DENSE_WEIGHT: float = 0.6
    DEFAULT_SEARCH_TYPE: str = "hybrid"
    DEFAULT_FUSION_METHOD: str = "weighted"
    DEFAULT_NORMALIZATION: str = "min_max"
    SIMILARITY_THRESHOLD: float = 0.0

    # LiteLLM Configuration
    LITELLM_PROXY_URL: str = os.getenv("LITELLM_PROXY_URL", "http://localhost:4000")
    LITELLM_APP_KEY: str = os.getenv("LITELLM_APP_KEY", "")

    # TF-IDF Configuration
    TFIDF_MODELS_DIR: str = os.getenv("TFIDF_MODELS_DIR", "/app/tfidf_models")

    # Query Expansion Configuration
    ENABLE_QUERY_EXPANSION: bool = os.getenv("ENABLE_QUERY_EXPANSION", "false").lower() == "true"
    MAX_QUERY_VARIANTS: int = 3
    EXPANSION_FUSION_METHOD: str = "rrf"

    # LLM Reranker Configuration
    ENABLE_LLM_RERANKING: bool = os.getenv("ENABLE_LLM_RERANKING", "false").lower() == "true"
    LLM_RERANKER_MODEL: str = os.getenv("LLM_RERANKER_MODEL", "")
    RERANKER_TOP_K: int = 20
    RERANKER_TOP_N: int = 10
    RERANKER_BATCH_SIZE: int = 5
    RERANKER_TEMPERATURE: float = 0.1
    RERANKER_MAX_TOKENS: int = 10
    RERANKER_TIMEOUT: int = 30

    MAX_CONCURRENT_SEARCHES: int = 5
    SEARCH_TIMEOUT: int = 30

    @classmethod
    def get_litellm_config(cls) -> ChatOpenAI:
        """Get LiteLLM proxy configuration for LLM calls"""
        return ChatOpenAI(
            model=cls.LLM_CHAT_MODEL,
            api_key=cls.LITELLM_APP_KEY ,
            base_url=f"{cls.LITELLM_PROXY_URL}/v1",
            temperature=0.1,
            max_tokens=4000,
            timeout=30.0,
            max_retries=3
        )

    @classmethod
    def get_llm_config(cls) -> ChatOpenAI:
        """Get LLM client configuration - now using LiteLLM"""
        return cls.get_litellm_config()

    @classmethod
    def get_embedding_model(cls) -> OpenAIEmbeddings:
        """Get configured embedding model using LiteLLM proxy"""
        return OpenAIEmbeddings(
            model=cls.LLM_EMBEDDING_MODEL,
            openai_api_base=f"{cls.LITELLM_PROXY_URL}/v1",
            openai_api_key=cls.LITELLM_APP_KEY,
            timeout=30.0,
            max_retries=3
        )

    @classmethod
    def get_reranker_config(cls) -> ChatOpenAI:
        """Get reranker-specific LLM configuration - now using LiteLLM"""
        return ChatOpenAI(
            model=cls.LLM_RERANKER_MODEL,
            api_key=cls.LITELLM_APP_KEY or None,
            base_url=f"{cls.LITELLM_PROXY_URL}/v1",
            temperature=cls.RERANKER_TEMPERATURE,
            max_tokens=cls.RERANKER_MAX_TOKENS,
            timeout=cls.RERANKER_TIMEOUT,
            max_retries=3
        )

    @classmethod
    def get_qdrant_config(cls) -> dict:
        return {
            "host": cls.QDRANT_HOST,
            "port": cls.QDRANT_PORT
        }

    @classmethod
    def validate_config(cls) -> List[str]:
        """Validate required configuration and return list of missing variables"""
        required_vars = [
            "LITELLM_PROXY_URL",
            "LLM_CHAT_MODEL",
        ]

        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        return missing_vars


config = RAGConfig()
