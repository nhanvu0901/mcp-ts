import litellm
import os
from langchain_openai import ChatOpenAI

class LLMClient:
    def __init__(self, model_name: str, api_key: str, num_retries: int = 3, **kwargs):
        self.default_args = {
            "model": model_name,
            "api_key": api_key,
            "num_retries": num_retries,
        }

        litellm_proxy_url = kwargs.get("litellm_proxy_url")
        if litellm_proxy_url:
            self.default_args["base_url"] = f"{litellm_proxy_url}/v1"

    def complete(self, messages, **kwargs):
        args = {**self.default_args, "messages": messages, **kwargs}
        return litellm.completion(**args)

    async def acomplete(self, messages, **kwargs):
        args = {**self.default_args, "messages": messages, **kwargs}
        return await litellm.acompletion(**args)

    def stream(self, messages, **kwargs):
        args = {**self.default_args, "messages": messages, **kwargs}
        return litellm.completion(**args, stream=True)

    async def astream(self, messages, **kwargs):
        args = {**self.default_args, "messages": messages, **kwargs}
        return await litellm.acompletion(**args, stream=True)


def get_llm_client() -> ChatOpenAI:
    litellm_proxy_url = os.getenv("LITELLM_PROXY_URL")
    litellm_app_key = os.getenv("LITELLM_APP_KEY")
    model_name = os.getenv("AZURE_OPENAI_MODEL_NAME")

    return ChatOpenAI(
        model=model_name,
        api_key=litellm_app_key,
        base_url=f"{litellm_proxy_url}/v1",
        temperature=0.1,
        max_tokens=4000,
        timeout=30.0,
        max_retries=3
    )