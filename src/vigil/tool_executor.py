"""Safely execute only approved tools and return predictable JSON-safe results."""

import json
from collections.abc import Callable
from typing import Any

from vigil.tool_validation import validate_tool_arguments


MAX_TOOL_RESULT_BYTES = 4096


class ToolExecutor:
    """Check a tool request, run it, and safely package its result."""

    def __init__(
        self,
        tool_specs: list[dict[str, Any]],
        tool_functions: dict[str, Callable[..., Any]],
        max_result_bytes: int = MAX_TOOL_RESULT_BYTES,
    ) -> None:
        if max_result_bytes < 1:
            raise ValueError("max_result_bytes must be greater than zero")

        self.tool_specs = tool_specs
        self.tool_functions = tool_functions
        self.max_result_bytes = max_result_bytes

    def execute(self, name: str, raw_arguments: str) -> dict[str, Any]:
        """Never run an unknown tool or a tool with invalid arguments."""

        function = self.tool_functions.get(name)
        if function is None:
            return {
                "error": "Requested tool is not allowed",
                "error_code": "TOOL_NOT_ALLOWED",
            }

        spec = next(
            (
                item
                for item in self.tool_specs
                if item.get("function", {}).get("name") == name
            ),
            None,
        )
        if spec is None:
            return {
                "error": "Approved tool has no registered input schema",
                "error_code": "SCHEMA_MISSING",
            }

        try:
            schema = spec["function"]["parameters"]
            arguments = validate_tool_arguments(raw_arguments, schema)
        except (KeyError, TypeError):
            return {
                "error": "Registered tool input schema is invalid",
                "error_code": "SCHEMA_INVALID",
            }
        except ValueError as error:
            return {
                "error": str(error),
                "error_code": "INVALID_ARGUMENTS",
            }

        try:
            tool_result = function(**arguments)
        except (TypeError, ValueError):
            return {
                "error": "Tool arguments are invalid",
                "error_code": "TOOL_EXECUTION_FAILED",
            }
        except Exception:
            return {
                "error": "Approved tool failed to execute",
                "error_code": "TOOL_EXECUTION_FAILED",
            }

        wrapped_result = {"result": tool_result}

        try:
            encoded_result = json.dumps(
                wrapped_result,
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            return {
                "error": "Tool returned data that cannot be encoded as JSON",
                "error_code": "RESULT_NOT_JSON",
            }

        if len(encoded_result) > self.max_result_bytes:
            return {
                "error": "Tool result is too large",
                "error_code": "RESULT_TOO_LARGE",
            }

        return wrapped_result