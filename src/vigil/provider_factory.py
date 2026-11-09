"""Create one API client for the LLM provider selected in the terminal."""

import os

from openai import OpenAI


PROVIDERS = {
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_variable": "NVIDIA_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "key_variable": "DEEPSEEK_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "key_variable": "OPENAI_API_KEY",
    },
}


def create_model_client() -> tuple[OpenAI, str, str]:
    """Return (client, model, provider) for one selected provider."""

    provider = (os.getenv("VIGIL_PROVIDER") or "nvidia").strip().lower()

    if provider not in PROVIDERS:
        choices = ", ".join(PROVIDERS)
        raise ValueError(
            f"Unknown VIGIL_PROVIDER: {provider}. Choose: {choices}."
        )

    model = (os.getenv("VIGIL_MODEL") or "").strip()
    if not model:
        raise ValueError("VIGIL_MODEL is not set in this terminal.")

    settings = PROVIDERS[provider]
    key_variable = settings["key_variable"]
    api_key = (os.getenv(key_variable) or "").strip()

    if not api_key:
        raise ValueError(f"{key_variable} is not set in this terminal.")

    client = OpenAI(
        base_url=settings["base_url"],
        api_key=api_key,
        timeout=60.0,
        max_retries=1,
    )

    return client, model, provider