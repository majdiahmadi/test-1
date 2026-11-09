"""Lesson 7: offline tests for execution errors, limits and evidence checks."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from vigil.tool_executor import ToolExecutor
from vigil.triage_agent import TriageAgent


def fake_response(text=None, calls=None):
    """Build a minimal model response without a real API request."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text, tool_calls=calls)
            )
        ]
    )


def fake_tool_call(name, arguments, call_id="call-1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class ToolExecutionTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.agent = TriageAgent(client=self.client, model="fake-test-model")

    def test_valid_tool_keeps_old_result_format(self):
        output = self.agent._execute_tool(
            "get_demo_alert_by_id", '{"alert_id":"demo-ssh-001"}'
        )
        self.assertEqual(output["result"]["alert_id"], "demo-ssh-001")
        self.assertNotIn("error", output)

    def test_invalid_tool_has_machine_readable_error_code(self):
        output = self.agent._execute_tool("delete_everything", "{}")
        self.assertEqual(output["error"], "Requested tool is not allowed")
        self.assertEqual(output["error_code"], "TOOL_NOT_ALLOWED")

    def test_invalid_arguments_have_error_code(self):
        output = self.agent._execute_tool("get_demo_alert_by_id", "{}")
        self.assertEqual(output["error_code"], "INVALID_ARGUMENTS")
        self.assertIn("required", output["error"])

    def test_missing_schema_rejected(self):
        executor = ToolExecutor([], {"other": lambda: {"ok": True}})
        output = executor.execute("other", "{}")
        self.assertEqual(output["error_code"], "SCHEMA_MISSING")

    def test_bad_schema_structure_rejected(self):
        specs = [{"function": {"name": "other", "parameters": None}}]
        executor = ToolExecutor(specs, {"other": lambda: 123})
        output = executor.execute("other", "{}")
        self.assertEqual(output["error_code"], "INVALID_ARGUMENTS")

    def test_python_tool_exception_hides_internal_details(self):
        self.agent.tool_executor.tool_functions["get_demo_alert"] = (
            lambda: (_ for _ in ()).throw(RuntimeError("SECRET_INTERNAL_DETAILS"))
        )
        output = self.agent._execute_tool("get_demo_alert", "{}")
        self.assertEqual(output["error_code"], "TOOL_EXECUTION_FAILED")
        self.assertNotIn("SECRET", str(output))

    def test_python_tool_value_error_is_safe(self):
        def raise_value_error():
            raise ValueError("internal record id=1234")

        self.agent.tool_executor.tool_functions["get_demo_alert"] = raise_value_error
        output = self.agent._execute_tool("get_demo_alert", "{}")
        self.assertEqual(output["error_code"], "TOOL_EXECUTION_FAILED")
        self.assertNotIn("1234", str(output))

    def test_non_json_result_rejected(self):
        self.agent.tool_executor.tool_functions["get_demo_alert"] = lambda: {1, 2}
        output = self.agent._execute_tool("get_demo_alert", "{}")
        self.assertEqual(output["error_code"], "RESULT_NOT_JSON")

    def test_too_large_result_rejected(self):
        self.agent.tool_executor.tool_functions["get_demo_alert"] = (
            lambda: "x" * 10000
        )
        output = self.agent._execute_tool("get_demo_alert", "{}")
        self.assertEqual(output["error_code"], "RESULT_TOO_LARGE")
        self.assertNotIn("result", output)

    def test_oversized_result_does_not_count_as_evidence(self):
        self.agent.tool_executor.tool_functions["get_demo_alert"] = (
            lambda: "x" * 10000
        )
        self.client.chat.completions.create.side_effect = [
            fake_response(calls=[fake_tool_call("get_demo_alert", "{}")]),
            fake_response(text="Unsupported final report"),
        ]
        with self.assertRaisesRegex(RuntimeError, "no evidence tool succeeded"):
            self.agent.run("Test synthetic alert")

    def test_no_tool_call_does_not_allow_report(self):
        self.client.chat.completions.create.return_value = fake_response(
            text="I guessed a report without any evidence"
        )
        with self.assertRaisesRegex(RuntimeError, "no evidence tool succeeded"):
            self.agent.run("Investigate demo-ssh-001")

    def test_invalid_tool_does_not_count_as_evidence(self):
        self.client.chat.completions.create.side_effect = [
            fake_response(calls=[fake_tool_call("get_demo_alert_by_id", "{}")]),
            fake_response(text="Unsupported final report"),
        ]
        with self.assertRaisesRegex(RuntimeError, "no evidence tool succeeded"):
            self.agent.run("Investigate demo-ssh-001")

    def test_successful_evidence_tool_allows_report(self):
        self.client.chat.completions.create.side_effect = [
            fake_response(calls=[fake_tool_call("get_demo_alert", "{}")]),
            fake_response(text="Evidence-based demo report"),
        ]
        self.assertEqual(
            self.agent.run("Investigate demo-ssh-001"), "Evidence-based demo report"
        )

    def test_lookup_not_found_still_allows_not_found_report(self):
        self.client.chat.completions.create.side_effect = [
            fake_response(
                calls=[fake_tool_call(
                    "get_demo_alert_by_id", '{"alert_id":"demo-ssh-999"}'
                )]
            ),
            fake_response(text="No matching demo alert found"),
        ]
        self.assertEqual(
            self.agent.run("Investigate demo-ssh-999"), "No matching demo alert found"
        )
        sent = self.client.chat.completions.create.call_args_list[1].kwargs["messages"]
        self.assertFalse(json.loads(sent[-1]["content"])["result"]["found"])

    def test_tool_call_limit_refuses_seventh_request(self):
        self.agent.max_tool_calls = 1
        second_call = fake_tool_call("get_demo_alert", "{}", "call-2")
        first_call = fake_tool_call("get_demo_alert", "{}", "call-1")
        self.client.chat.completions.create.side_effect = [
            fake_response(calls=[first_call, second_call]),
            fake_response(text="Report after one evidence request"),
        ]
        self.assertEqual(
            self.agent.run("Investigate demo-ssh-001"),
            "Report after one evidence request",
        )
        sent = self.client.chat.completions.create.call_args_list[1].kwargs["messages"]
        self.assertEqual(json.loads(sent[-1]["content"])["error_code"], "TOOL_LIMIT_REACHED")
        self.assertEqual(json.loads(sent[-2]["content"])["result"]["alert_id"], "demo-ssh-001")

    def test_tool_can_retry_after_validation_error(self):
        self.client.chat.completions.create.side_effect = [
            fake_response(calls=[fake_tool_call("get_demo_alert_by_id", "{}", "bad")]),
            fake_response(calls=[fake_tool_call("get_demo_alert_by_id", '{"alert_id":"demo-ssh-001"}', "good")]),
            fake_response(text="Report after correcting input"),
        ]
        self.assertEqual(
            self.agent.run("Investigate demo-ssh-001"),
            "Report after correcting input",
        )
        self.assertEqual(self.client.chat.completions.create.call_count, 3)


if __name__ == "__main__":
    unittest.main()