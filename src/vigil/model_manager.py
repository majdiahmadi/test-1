"""Keep one LLM model and its API client in one reusable place."""

from typing import Any

from openai import OpenAI

class ModelManager:
    """Send LLM requests using one configured model and client."""

    def __init__(self, client: OpenAI, model: str) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model name must not be empty.")

        self.client = client
        self.model = model.strip()

    def create_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        request: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        if tools is not None:
            request["tools"] = tools
            request["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**request)
        return response