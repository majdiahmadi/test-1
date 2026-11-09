"""Keep LLM tool descriptions and approved Python functions together."""

from collections.abc import Callable
from copy import deepcopy
from typing import Any


class ToolRegistry:
    """Register tools once and prepare the two lists BaseAgent needs."""

    def __init__(self) -> None:
        self._specs: dict[str, dict[str, Any]] = {}
        self._functions: dict[str, Callable[..., Any]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        function: Callable[..., Any],
        parameters: dict[str, Any],
    ) -> None:
        """Add one approved tool to the registry."""

        if not isinstance(name, str) or not name.strip():
            raise ValueError("Tool name must not be empty.")

        name = name.strip()

        if name in self._functions:
            raise ValueError(f"Tool '{name}' is already registered.")

        if not isinstance(description, str) or not description.strip():
            raise ValueError("Tool description must not be empty.")

        if not callable(function):
            raise TypeError("Tool function must be callable.")

        if not isinstance(parameters, dict) or parameters.get("type") != "object":
            raise ValueError("Tool parameters must describe a JSON object.")

        self._specs[name] = {
            "type": "function",
            "function": {
                "name": name,
                "description": description.strip(),
                "parameters": deepcopy(parameters),
            },
        }
        self._functions[name] = function

    def get_specs(self) -> list[dict[str, Any]]:
        """Return tool descriptions to show to the LLM."""
        return deepcopy(list(self._specs.values()))

    def get_functions(self) -> dict[str, Callable[..., Any]]:
        """Return the approved function map for Python execution."""
        return self._functions.copy()