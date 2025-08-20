import os
from langchain_openai import ChatOpenAI

def get_llm_client() -> ChatOpenAI:
    litellm_proxy_url = os.getenv("LITELLM_PROXY_URL")
    litellm_app_key = os.getenv("LITELLM_APP_KEY")
    model_name = os.getenv("LLM_CHAT_MODEL")

    return ChatOpenAI(
        model=model_name,
        api_key=litellm_app_key,
        base_url=f"{litellm_proxy_url}/v1",
        temperature=0.1,
        max_tokens=4000,
        timeout=30.0,
        max_retries=3
    )
