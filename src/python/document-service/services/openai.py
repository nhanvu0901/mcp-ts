import json
import os

from openai import AsyncAzureOpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential

_CLIENT = AsyncAzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_MODEL_API_VERSION"),  # Fixed: was AZURE_OPENAI_MODEL_VERSION
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
)
_MODEL_NAME = os.environ.get("AZURE_OPENAI_MODEL_NAME")

_MINI_CLIENT = AsyncAzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_MODEL_API_VERSION"),  # Fixed: was AZURE_OPENAI_MODEL_VERSION
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
)
_MINI_MODEL_NAME = os.environ.get("AZURE_OPENAI_MODEL_NAME")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(min=0.5, max=4),
)
async def _send_openai_request(
    system_prompt: str, user_message: str, fast: bool = True
) -> dict:
    """
    Sends a chat completion request to OpenAI and returns the response content.

    Args:
        system_prompt (str): The system-level instruction for the AI.
        user_message (str): The user's message to the AI.
        fast (bool, optional): If True, uses the mini model and client for faster responses. Defaults to False.

    Returns:
        dict: The parsed JSON content from the AI's response.
    """
    # Select model and client based on the 'fast' parameter
    if fast:
        model = _MINI_MODEL_NAME
        client = _MINI_CLIENT
    else:
        model = _MODEL_NAME
        client = _CLIENT

    # print(model)

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
        # Uncomment and adjust parameters as needed
        # "max_tokens": 4000,
        # "temperature": 0.2,
        # "top_p": 0.95,
        # "frequency_penalty": 0.2,
        # "presence_penalty": 0.2,
    }

    try:
        # Send the request to OpenAI
        completion = await client.chat.completions.create(**chat_params)

        # Parse the JSON content from the response
        content = json.loads(completion.choices[0].message.content)

        return content

    except Exception as e:
        # Log the exception and re-raise for retry
        print(f"Error during OpenAI request: {e}")
        raise e


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(min=0.5, max=4),
)
async def _send_streaming_request(
    system_prompt: str, user_message: str, fast: bool = True
) -> dict:
    """
    Sends a chat completion request to OpenAI and returns the response content.

    Args:
        system_prompt (str): The system-level instruction for the AI.
        user_message (str): The user's message to the AI.
        fast (bool, optional): If True, uses the mini model and client for faster responses. Defaults to False.

    Returns:
        dict: The parsed JSON content from the AI's response.
    """
    # Select model and client based on the 'fast' parameter
    if fast:
        model = _MINI_MODEL_NAME
        client = _MINI_CLIENT
    else:
        model = _MODEL_NAME
        client = _CLIENT

    # print(model)

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
        # Uncomment and adjust parameters as needed
        # "max_tokens": 4000,
        # "temperature": 0.2,
        # "top_p": 0.95,
        # "frequency_penalty": 0.2,
        # "presence_penalty": 0.2,
    }

    try:
        # Send the request to OpenAI
        completion = await client.chat.completions.stream(**chat_params)

        # Parse the JSON content from the response
        content = json.loads(completion.choices[0].message.content)

        return content

    except Exception as e:
        # Log the exception and re-raise for retry
        print(f"Error during OpenAI request: {e}")
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
    Sends a chat completion request to OpenAI and returns the response content.

    Args:
        system_prompt (str): The system-level instruction for the AI.
        user_message (str): The user's message to the AI.
        fast (bool, optional): If True, uses the mini model and client for faster responses. Defaults to False.

    Returns:
        dict: The parsed JSON content from the AI's response.
    """
    # Select model and client based on the 'fast' parameter
    if fast:
        model = _MINI_MODEL_NAME
        client = _MINI_CLIENT
    else:
        model = _MODEL_NAME
        client = _CLIENT

    # print(model)

    # Construct chat parameters
    chat_params = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]
        + messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        # Uncomment and adjust parameters as needed
        # "max_tokens": 4000,
        # "temperature": 0.2,
        # "top_p": 0.95,
        # "frequency_penalty": 0.2,
        # "presence_penalty": 0.2,
    }

    try:
        # Send the request to OpenAI
        completion = await client.chat.completions.create(**chat_params)
        async for chunk in completion:
            if chunk.choices and len(chunk.choices) > 0:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

        # async for chunk in completion:
        #     if not chunk.choices:
        #         usage_info = chunk.usage  # Extract the usage info
        #         break

        #     content = chunk.choices[0].delta.content
        #     if content:
        #         yield content
        # # async for chunk in completion:
        # #     current_content = chunk["choices"][0]["delta"].get("content", "")
        # #     yield current_content

        # if usage_info:
        #     yield {"usage": usage_info}

    except Exception as e:
        # Log the exception and re-raise for retry
        print(f"Error during OpenAI request: {e}")
        raise e
