"""Reusable agent loop with tool limits and an evidence requirement."""

import json
from collections.abc import Callable
from typing import Any

from openai import OpenAI

from vigil.model_manager import ModelManager
from vigil.tool_executor import ToolExecutor


class BaseAgent:
    """Manage model rounds and execute only approved, validated tools."""

    def __init__(
        self,
        name: str,
        instructions: str,
        model: str,
        client: OpenAI,
        tool_specs: list[dict[str, Any]],
        tool_functions: dict[str, Callable[..., Any]],
        max_rounds: int = 4,
        max_tool_calls: int = 6,
        require_evidence: bool = False,
        evidence_tool_names: set[str] | None = None,
        required_tool_names: set[str] | None = None,
    ) -> None:
        if max_rounds < 2:
            raise ValueError("max_rounds must be at least 2")
        if max_tool_calls < 1:
            raise ValueError("max_tool_calls must be greater than zero")

        self.name = name
        self.instructions = instructions
        self.model_manager = ModelManager(client=client, model=model)
        self.tool_specs = tool_specs
        self.tool_functions = tool_functions
        self.tool_executor = ToolExecutor(tool_specs, tool_functions)
        self.max_rounds = max_rounds
        self.max_tool_calls = max_tool_calls
        self.require_evidence = require_evidence
        self.evidence_tool_names = set(evidence_tool_names or set())
        self.required_tool_names = set(required_tool_names or set())

    def _execute_tool(self, name: str, raw_arguments: str) -> dict[str, Any]:
        """Keep the old Lesson 6 method name for compatibility with tests."""
        return self.tool_executor.execute(name, raw_arguments)

    def run(self, task: str) -> str:
        """Investigate until a supported report is returned or limits are hit."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": task},
        ]
        tool_calls_used = 0
        used_evidence_tool = False
        completed_required_tools: set[str] = set()

        for round_number in range(1, self.max_rounds + 1):
            print(f"\n{self.name} agent round {round_number}")

            completion = self.model_manager.create_completion(
                messages=messages,
                tools=self.tool_specs,
            )

            assistant_message = completion.choices[0].message
            tool_calls = assistant_message.tool_calls or []

            if not tool_calls:
                if self.require_evidence and not used_evidence_tool:
                    raise RuntimeError(
                        "Investigation incomplete: no evidence tool succeeded"
                    )
                missing = self.required_tool_names - completed_required_tools
                if missing:
                    raise RuntimeError(
                        "Investigation incomplete: required tools not completed: "
                        + ", ".join(sorted(missing))
                    )
                if assistant_message.content:
                    return assistant_message.content
                raise RuntimeError("The model returned neither text nor a tool call")

            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )

            for call in tool_calls:
                tool_name = call.function.name
                print(f"Tool requested: {tool_name}")

                if tool_calls_used >= self.max_tool_calls:
                    result = {
                        "error": "Tool-call limit reached",
                        "error_code": "TOOL_LIMIT_REACHED",
                    }
                else:
                    tool_calls_used += 1
                    result = self._execute_tool(tool_name, call.function.arguments)

                if tool_name in self.evidence_tool_names and "result" in result:
                    used_evidence_tool = True

                if tool_name in self.required_tool_names and "result" in result:
                    tool_data = result["result"]
                    if not (isinstance(tool_data, dict) and tool_data.get("found") is False):
                        completed_required_tools.add(tool_name)

                if "error_code" in result:
                    print(f"Tool status: {result['error_code']}")
                else:
                    print("Tool status: success")

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False, allow_nan=False),
                    }
                )

        raise RuntimeError("Agent reached the round limit without a final report")