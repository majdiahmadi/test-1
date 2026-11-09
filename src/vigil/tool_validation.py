"""Check LLM tool arguments before an approved function receives them."""

import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError


MAX_ARGUMENT_CHARACTERS = 2048


def validate_tool_arguments(
    raw_arguments: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Return validated arguments, or raise ValueError with a safe message."""

    if not isinstance(raw_arguments, str):
        raise ValueError("Tool arguments must be JSON text.")

    if len(raw_arguments) > MAX_ARGUMENT_CHARACTERS:
        raise ValueError("Tool arguments are too long.")

    try:
        arguments = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        raise ValueError("Tool arguments must be valid JSON.") from None

    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object.")

    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError:
        raise ValueError("The registered tool schema is invalid.") from None

    try:
        Draft202012Validator(schema).validate(arguments)
    except ValidationError as error:
        raise ValueError(
            f"Tool arguments failed validation ({error.validator})."
        ) from None

    return arguments