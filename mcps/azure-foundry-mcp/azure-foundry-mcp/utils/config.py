import os
from dotenv import load_dotenv

load_dotenv()


class AzureFoundryConfig:
    SERVICE_NAME: str = "AzureFoundryService"
    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = 8005

    AZURE_PROJECT_ENDPOINT: str = os.getenv(
        "AZURE_PROJECT_ENDPOINT",
        "https://web-test2-resource.services.ai.azure.com/api/projects/web-test2"
    )

    AZURE_AGENT_ID: str = os.getenv(
        "AZURE_AGENT_ID",
        "asst_alhh7CfHPuPwMEIZFe2l66Ig"
    )

    REQUEST_TIMEOUT: int = 60
    MAX_RETRIES: int = 3
