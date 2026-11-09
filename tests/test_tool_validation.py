"""Offline tests for Lesson 6: approved tools and input validation."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from vigil.demo_tools import get_demo_alert_by_id
from vigil.tool_validation import validate_tool_arguments
from vigil.triage_agent import TriageAgent


class ToolValidationTests(unittest.TestCase):
    def setUp(self):
        self.fake_client = MagicMock()
        self.agent = TriageAgent(client=self.fake_client, model="fake-test-model")
        self.schema = next(
            spec["function"]["parameters"]
            for spec in self.agent.tool_specs
            if spec["function"]["name"] == "get_demo_alert_by_id"
        )

    def test_correct_arguments_are_accepted(self):
        result = validate_tool_arguments('{"alert_id":"demo-ssh-001"}', self.schema)
        self.assertEqual(result, {"alert_id": "demo-ssh-001"})

    def test_missing_required_id_is_rejected(self):
        result = self.agent._execute_tool("get_demo_alert_by_id", "{}")
        self.assertIn("required", result["error"])

    def test_wrong_type_is_rejected(self):
        result = self.agent._execute_tool("get_demo_alert_by_id", '{"alert_id":123}')
        self.assertIn("type", result["error"])

    def test_unexpected_extra_field_is_rejected(self):
        result = self.agent._execute_tool(
            "get_demo_alert_by_id", '{"alert_id":"demo-ssh-001","delete":true}'
        )
        self.assertIn("additionalProperties", result["error"])

    def test_bad_id_pattern_is_rejected(self):
        result = self.agent._execute_tool(
            "get_demo_alert_by_id", '{"alert_id":"prod-ssh-001"}'
        )
        self.assertIn("pattern", result["error"])

    def test_invalid_json_is_rejected(self):
        result = self.agent._execute_tool("get_demo_alert_by_id", '{"alert_id":')
        self.assertIn("valid JSON", result["error"])

    def test_json_list_is_rejected(self):
        result = self.agent._execute_tool("get_demo_alert_by_id", "[]")
        self.assertIn("JSON object", result["error"])

    def test_long_input_is_rejected(self):
        result = self.agent._execute_tool("get_demo_alert_by_id", "a" * 2049)
        self.assertIn("too long", result["error"])

    def test_unknown_tool_is_rejected(self):
        result = self.agent._execute_tool("delete_everything", "{}")
        self.assertEqual(result["error"], "Requested tool is not allowed")

    def test_valid_alert_id_returns_evidence(self):
        result = self.agent._execute_tool(
            "get_demo_alert_by_id", '{"alert_id":"demo-ssh-001"}'
        )
        self.assertEqual(result["result"]["alert_id"], "demo-ssh-001")
        self.assertEqual(result["result"]["events"][0]["event_id"], "log-001")

    def test_valid_nonexistent_id_is_not_found(self):
        result = self.agent._execute_tool(
            "get_demo_alert_by_id", '{"alert_id":"demo-ssh-999"}'
        )
        self.assertIs(result["result"]["found"], False)
        self.assertNotIn("events", result["result"])

    def test_original_no_argument_tool_still_works(self):
        result = self.agent._execute_tool("get_demo_alert", "{}")
        self.assertEqual(result["result"]["alert_id"], "demo-ssh-001")

    def test_original_tool_rejects_extra_arguments(self):
        result = self.agent._execute_tool("get_demo_alert", '{"x":1}')
        self.assertIn("additionalProperties", result["error"])

    def test_invalid_arguments_do_not_call_python_function(self):
        mock_function = MagicMock()
        self.agent.tool_functions["get_demo_alert_by_id"] = mock_function
        self.agent._execute_tool("get_demo_alert_by_id", '{"alert_id":false}')
        mock_function.assert_not_called()

    def test_full_fake_llm_investigation(self):
        tool_call = SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(
                name="get_demo_alert_by_id",
                arguments=json.dumps({"alert_id": "demo-ssh-001"}),
            ),
        )
        first_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tool_call]))]
        )
        final_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Demo report.", tool_calls=None))]
        )
        self.fake_client.chat.completions.create.side_effect = [first_response, final_response]
        report = self.agent.run("Investigate demo-ssh-001")
        self.assertEqual(report, "Demo report.")
        self.assertEqual(self.fake_client.chat.completions.create.call_count, 2)
        sent_messages = self.fake_client.chat.completions.create.call_args_list[1].kwargs["messages"]
        response = json.loads(sent_messages[-1]["content"])
        self.assertEqual(response["result"]["alert_id"], "demo-ssh-001")


if __name__ == "__main__":
    unittest.main()