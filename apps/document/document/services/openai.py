import json
import os
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential


def get_litellm_client():
    """Get LiteLLM client configuration"""
    litellm_proxy_url = os.getenv("LITELLM_PROXY_URL")
    litellm_app_key = os.getenv("LITELLM_APP_KEY")

    if not litellm_app_key:
        raise ValueError("LITELLM_APP_KEY environment variable is required")

    return AsyncOpenAI(
        api_key=litellm_app_key,
        base_url=f"{litellm_proxy_url}/v1",
        timeout=60.0,
        max_retries=3
    )


def get_model_name():
    """Get model name from environment"""
    return os.getenv("AZURE_OPENAI_MODEL_NAME")


# Lazy initialization - clients created when needed, not at import time
_CLIENT = None
_MINI_CLIENT = None


def get_client():
    """Get or create the main client"""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = get_litellm_client()
    return _CLIENT


def get_mini_client():
    """Get or create the mini client (same as main for LiteLLM)"""
    global _MINI_CLIENT
    if _MINI_CLIENT is None:
        _MINI_CLIENT = get_litellm_client()
    return _MINI_CLIENT


_MODEL_NAME = get_model_name()
_MINI_MODEL_NAME = get_model_name()  # Same model for both


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(min=0.5, max=4),
)
async def _send_openai_request(
    system_prompt: str, user_message: str, fast: bool = True
) -> dict:
    """
    Sends a chat completion request via LiteLLM proxy and returns the response content.

    Args:
        system_prompt (str): The system-level instruction for the AI.
        user_message (str): The user's message to the AI.
        fast (bool, optional): If True, uses the mini model and client for faster responses. Defaults to True.

    Returns:
        dict: The parsed JSON content from the AI's response.
    """
    # Select model and client based on the 'fast' parameter
    if fast:
        model = _MINI_MODEL_NAME
        client = get_mini_client()
    else:
        model = _MODEL_NAME
        client = get_client()

    # Construct chat parameters
    chat_params = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 4000,
    }

    try:
        # Send the request via LiteLLM proxy
        completion = await client.chat.completions.create(**chat_params)

        # Parse the JSON content from the response
        content = json.loads(completion.choices[0].message.content)

        return content

    except Exception as e:
        # Log the exception and re-raise for retry
        print(f"Error during LiteLLM request: {e}")
        raise e


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(min=0.5, max=4),
)
async def _send_streaming_request(
    system_prompt: str, user_message: str, fast: bool = True
) -> dict:
    """
    Sends a streaming chat completion request via LiteLLM proxy.

    Args:
        system_prompt (str): The system-level instruction for the AI.
        user_message (str): The user's message to the AI.
        fast (bool, optional): If True, uses the mini model and client for faster responses. Defaults to True.

    Returns:
        dict: The parsed JSON content from the AI's response.
    """
    # Select model and client based on the 'fast' parameter
    if fast:
        model = _MINI_MODEL_NAME
        client = get_mini_client()
    else:
        model = _MODEL_NAME
        client = get_client()

    # Construct chat parameters
    chat_params = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 4000,
        "stream": True,
    }

    try:
        # Send the streaming request via LiteLLM proxy
        completion = await client.chat.completions.create(**chat_params)

        full_content = ""
        async for chunk in completion:
            if chunk.choices and len(chunk.choices) > 0:
                content = chunk.choices[0].delta.content
                if content:
                    full_content += content

        # Parse the complete JSON content
        content = json.loads(full_content)
        return content

    except Exception as e:
        # Log the exception and re-raise for retry
        print(f"Error during LiteLLM streaming request: {e}")
        raise e


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(min=0.5, max=4),
)
async def _send_streaming_openai_request(
    messages: list[dict],
    system_prompt: str = "You are ChatGPT, a helpful AI assistant.",
    fast: bool = True,
):
    """
    Sends a streaming chat completion request via LiteLLM proxy.

    Args:
        system_prompt (str): The system-level instruction for the AI.
        messages (list): List of messages for the conversation.
        fast (bool, optional): If True, uses the mini model and client for faster responses. Defaults to True.

    Yields:
        str: Content chunks from the AI's response.
    """
    # Select model and client based on the 'fast' parameter
    if fast:
        model = _MINI_MODEL_NAME
        client = get_mini_client()
    else:
        model = _MODEL_NAME
        client = get_client()

    # Construct chat parameters
    chat_params = {
        "model": model,
        "messages": [
                        {
                            "role": "system",
                            "content": system_prompt,
                        }
                    ] + messages,
        "stream": True,
        "temperature": 0.2,
        "max_tokens": 4000,
    }

    try:
        # Send the request via LiteLLM proxy
        completion = await client.chat.completions.create(**chat_params)
        async for chunk in completion:
            if chunk.choices and len(chunk.choices) > 0:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

    except Exception as e:
        # Log the exception and re-raise for retry
        print(f"Error during LiteLLM streaming request: {e}")
        raise e
