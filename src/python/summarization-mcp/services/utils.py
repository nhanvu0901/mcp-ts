import litellm
import os
class LLMClient:
    """LLM Client for OpenAI/Azure integration"""
    
    def __init__(self, model_name: str, api_key: str, num_retries: int = 3, **kwargs):
        # Prepares the arguments for API calls
        self.default_args = {
            "model": model_name,
            "api_key": api_key,
            "num_retries": num_retries,
            **kwargs,
        }

        # Add Azure-specific arguments if needed
        if model_name.startswith("azure/"):
            api_base = kwargs.get("api_base", None)
            api_version = kwargs.get("api_version", None)
            if api_base and api_version:
                self.default_args["api_base"] = api_base
                self.default_args["api_version"] = api_version
            else:
                raise ValueError(
                    "Both `api_base` and `api_version` must be provided for Azure models."
                )

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


def get_llm_client() -> LLMClient:
    """Get LLM client based on environment configuration"""
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if azure_api_key:
        return LLMClient(
            f"azure/{os.getenv('AZURE_OPENAI_MODEL_NAME')}",
            api_key=azure_api_key,
            api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_MODEL_API_VERSION"),
        )
    elif openai_api_key:
        return LLMClient(
            f"openai/{os.getenv('OPENAI_MODEL_NAME', 'gpt-4o-mini')}",
            api_key=openai_api_key,
        )
    else:
        raise EnvironmentError(
            "No API key found. Set either AZURE_OPENAI_API_KEY or OPENAI_API_KEY in environment."
        )
