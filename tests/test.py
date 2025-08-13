import os
import asyncio
import aiohttp
from langchain_openai import ChatOpenAI


async def test_litellm_connection():
    """Test if LiteLLM proxy is accessible and properly configured"""

    litellm_proxy_url = os.getenv("LITELLM_PROXY_URL", "http://localhost:4000")
    litellm_app_key = 'sk-1234567890abcdef'

    print(f"Testing LiteLLM proxy at: {litellm_proxy_url}")
    print(f"Using API key: {litellm_app_key[:10]}..." if litellm_app_key else "No API key set")

    # Test 1: Check if LiteLLM proxy is running
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{litellm_proxy_url}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    print("✅ LiteLLM proxy is running")
                    print(f"Health check response: {health_data}")
                else:
                    print(f"❌ LiteLLM proxy health check failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Cannot connect to LiteLLM proxy: {e}")
        return False

    # Test 2: Check available models
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {litellm_app_key}"} if litellm_app_key else {}
            async with session.get(f"{litellm_proxy_url}/v1/models", headers=headers) as response:
                if response.status == 200:
                    models_data = await response.json()
                    print("✅ Available models:")
                    for model in models_data.get("data", [])[:5]:  # Show first 5 models
                        print(f"  - {model.get('id', 'Unknown')}")
                else:
                    print(f"❌ Cannot fetch models: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
    except Exception as e:
        print(f"❌ Error fetching models: {e}")

    # Test 3: Test chat completions endpoint
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {litellm_app_key}",
                "Content-Type": "application/json"
            } if litellm_app_key else {"Content-Type": "application/json"}

            test_payload = {
                "model": os.getenv("AZURE_OPENAI_MODEL_NAME", "ace-gpt-4o"),
                "messages": [{"role": "user", "content": "Hello, this is a test"}],
                "max_tokens": 10
            }

            async with session.post(
                    f"{litellm_proxy_url}/v1/chat/completions",
                    headers=headers,
                    json=test_payload
            ) as response:
                if response.status == 200:
                    print("✅ Chat completions endpoint is working")
                    completion_data = await response.json()
                    message = completion_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    print(f"Test response: {message}")
                    return True
                else:
                    print(f"❌ Chat completions failed: {response.status}")
                    text = await response.text()
                    print(f"Error response: {text}")
                    return False
    except Exception as e:
        print(f"❌ Error testing chat completions: {e}")
        return False


def get_llm_client() -> ChatOpenAI:
    """
    Get LLM client configured for LiteLLM proxy with enhanced error handling
    """
    model_name = 'ace-gpt-4o'

    litellm_proxy_url = os.getenv("LITELLM_PROXY_URL", "http://localhost:4000")
    litellm_app_key = 'sk-1234567890abcdef'

    if not litellm_proxy_url:
        raise ValueError("Missing required environment variable: LITELLM_PROXY_URL")
    if not litellm_app_key:
        raise ValueError("Missing required environment variable: LITELLM_APP_KEY")
    if not model_name:
        raise ValueError("Missing required environment variable: AZURE_OPENAI_MODEL_NAME")

    # Clean environment variables (remove quotes if present)
    litellm_proxy_url = litellm_proxy_url.replace('"', '').replace("'", '').strip()
    litellm_app_key = litellm_app_key.replace('"', '').replace("'", '').strip()
    model_name = model_name.replace('"', '').replace("'", '').strip()

    # Ensure proxy URL doesn't end with slash
    if litellm_proxy_url.endswith('/'):
        litellm_proxy_url = litellm_proxy_url[:-1]

    print(f"Configuring ChatOpenAI with:")
    print(f"  Model: {model_name}")
    print(f"  Base URL: {litellm_proxy_url}/v1")
    print(f"  API Key: {litellm_app_key[:10]}...")

    return ChatOpenAI(
        model=model_name,
        api_key=litellm_app_key,
        base_url=f"{litellm_proxy_url}/v1",
        temperature=0.1,
        max_tokens=4000,
        timeout=60.0,  # Increased timeout
        max_retries=2,  # Reduced retries
        verbose=True  # Enable verbose logging
    )


# Test function to run diagnostics
async def run_diagnostics():
    """Run full diagnostics on LiteLLM setup"""
    print("=== LiteLLM Connection Diagnostics ===\n")

    # Check environment variables
    required_vars = ["LITELLM_PROXY_URL", "LITELLM_APP_KEY", "AZURE_OPENAI_MODEL_NAME"]
    print("Environment Variables:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            display_value = f"{value[:10]}..." if len(value) > 10 else value
            print(f"  ✅ {var}: {display_value}")
        else:
            print(f"  ❌ {var}: Not set")
    print()

    # Test connection
    success = await test_litellm_connection()

    if success:
        print("\n=== Testing ChatOpenAI Integration ===")
        try:
            client = get_llm_client()
            response = await client.ainvoke([{"role": "user", "content": "Say hello"}])
            print(f"✅ ChatOpenAI integration working: {response.content}")
        except Exception as e:
            print(f"❌ ChatOpenAI integration failed: {e}")

    return success


if __name__ == "__main__":
    asyncio.run(run_diagnostics())