"""Offline tests for the VIGIL Tool Registry and Triage integration."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from vigil.demo_tools import get_demo_alert
from vigil.tool_registry import ToolRegistry
from vigil.triage_agent import TriageAgent


class ToolRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()

    def register_demo_tool(self):
        self.registry.register_tool(
            name="get_demo_alert",
            description="Read one synthetic SSH security alert.",
            function=get_demo_alert,
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        )

    def test_new_registry_is_empty(self):
        self.assertEqual(self.registry.get_specs(), [])
        self.assertEqual(self.registry.get_functions(), {})

    def test_register_creates_tool_description(self):
        self.register_demo_tool()
        specs = self.registry.get_specs()

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["function"]["name"], "get_demo_alert")
        self.assertEqual(specs[0]["type"], "function")

    def test_register_stores_real_function(self):
        self.register_demo_tool()
        functions = self.registry.get_functions()

        self.assertIs(functions["get_demo_alert"], get_demo_alert)
        self.assertEqual(functions["get_demo_alert"]()["alert_id"], "demo-ssh-001")

    def test_duplicate_name_is_rejected(self):
        self.register_demo_tool()

        with self.assertRaisesRegex(ValueError, "already registered"):
            self.register_demo_tool()

    def test_non_callable_is_rejected(self):
        with self.assertRaisesRegex(TypeError, "callable"):
            self.registry.register_tool(
                name="bad_tool",
                description="Invalid example",
                function="this is not a function",
                parameters={"type": "object"},
            )

    def test_blank_name_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Tool name"):
            self.registry.register_tool(
                name="   ",
                description="Invalid example",
                function=get_demo_alert,
                parameters={"type": "object"},
            )

    def test_invalid_schema_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            self.registry.register_tool(
                name="bad_schema",
                description="Invalid example",
                function=get_demo_alert,
                parameters={"type": "array"},
            )

    def test_specs_are_returned_as_copies(self):
        self.register_demo_tool()
        specs = self.registry.get_specs()
        specs[0]["function"]["parameters"]["properties"]["extra"] = {
            "type": "string"
        }

        original_specs = self.registry.get_specs()
        self.assertEqual(
            original_specs[0]["function"]["parameters"]["properties"],
            {},
        )

    def test_triage_uses_registry_with_fake_llm(self):
        requested_tool = SimpleNamespace(
            id="call-demo-1",
            function=SimpleNamespace(name="get_demo_alert", arguments="{}"),
        )

        first_reply = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=None, tool_calls=[requested_tool])
                )
            ]
        )
        second_reply = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Synthetic investigation complete.",
                        tool_calls=None,
                    )
                )
            ]
        )

        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = [first_reply, second_reply]

        agent = TriageAgent(client=fake_client, model="fake-test-model")
        report = agent.run("Test the synthetic alert")

        self.assertEqual(report, "Synthetic investigation complete.")
        self.assertEqual(fake_client.chat.completions.create.call_count, 2)

        api_calls = fake_client.chat.completions.create.call_args_list
        first_request = api_calls[0].kwargs
        second_request = api_calls[1].kwargs

        self.assertEqual(first_request["model"], "fake-test-model")
        self.assertEqual(
            first_request["tools"][0]["function"]["name"],
            "get_demo_alert",
        )

        tool_result = json.loads(second_request["messages"][-1]["content"])
        self.assertEqual(tool_result["result"]["alert_id"], "demo-ssh-001")


if __name__ == "__main__":
    unittest.main()