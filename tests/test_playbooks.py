"""Lesson 8: offline checks for playbook retrieval and agent requirements."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from vigil.playbooks import get_investigation_playbook
from vigil.triage_agent import TriageAgent


def fake_reply(text=None, calls=None):
    """Mimic the small part of a cloud-model reply used by BaseAgent."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=text, tool_calls=calls
        ))]
    )


def fake_call(name, arguments, call_id):
    """Mimic one tool request made by an LLM."""
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class PlaybookTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.agent = TriageAgent(
            client=self.client, model="fake-test-model", use_playbook=True
        )
        self.playbook_call = fake_call(
            "get_investigation_playbook",
            '{"playbook_id":"ssh-bruteforce-v1"}',
            "call-playbook",
        )
        self.alert_call = fake_call(
            "get_demo_alert_by_id",
            '{"alert_id":"demo-ssh-001"}',
            "call-alert",
        )

    def test_known_playbook_has_five_steps(self):
        playbook = get_investigation_playbook("ssh-bruteforce-v1")
        self.assertTrue(playbook["found"])
        self.assertEqual(len(playbook["steps"]), 5)
        self.assertEqual(playbook["steps"][0]["step_id"], "SSH-01")

    def test_playbook_is_a_copy_not_the_original(self):
        playbook = get_investigation_playbook("ssh-bruteforce-v1")
        playbook["steps"][0]["name"] = "changed"
        fresh = get_investigation_playbook("ssh-bruteforce-v1")
        self.assertEqual(fresh["steps"][0]["name"], "Identify the alert")

    def test_unknown_playbook_returns_not_found(self):
        answer = get_investigation_playbook("web-bruteforce-v1")
        self.assertFalse(answer["found"])
        self.assertNotIn("steps", answer)

    def test_playbook_tool_is_registered_in_playbook_mode(self):
        names = [x["function"]["name"] for x in self.agent.tool_specs]
        self.assertIn("get_investigation_playbook", names)
        self.assertIn("get_demo_alert_by_id", names)

    def test_old_mode_still_has_only_original_tools(self):
        old_agent = TriageAgent(client=self.client, model="fake-test-model")
        names = [x["function"]["name"] for x in old_agent.tool_specs]
        self.assertEqual(names, ["get_demo_alert", "get_demo_alert_by_id"])
        self.assertEqual(old_agent.required_tool_names, set())

    def test_playbook_tool_returns_result(self):
        answer = self.agent._execute_tool(
            "get_investigation_playbook", '{"playbook_id":"ssh-bruteforce-v1"}'
        )
        self.assertTrue(answer["result"]["found"])

    def test_playbook_tool_rejects_missing_id(self):
        answer = self.agent._execute_tool("get_investigation_playbook", "{}")
        self.assertEqual(answer["error_code"], "INVALID_ARGUMENTS")

    def test_playbook_tool_rejects_extra_field(self):
        answer = self.agent._execute_tool(
            "get_investigation_playbook",
            '{"playbook_id":"ssh-bruteforce-v1","delete":true}',
        )
        self.assertEqual(answer["error_code"], "INVALID_ARGUMENTS")

    def test_playbook_tool_rejects_bad_id_type(self):
        answer = self.agent._execute_tool(
            "get_investigation_playbook", '{"playbook_id":123}'
        )
        self.assertEqual(answer["error_code"], "INVALID_ARGUMENTS")

    def test_report_rejected_if_playbook_not_retrieved(self):
        self.client.chat.completions.create.side_effect = [
            fake_reply(calls=[self.alert_call]),
            fake_reply(text="Attempted report"),
        ]
        with self.assertRaisesRegex(RuntimeError, "required tools not completed"):
            self.agent.run("Investigate using playbook")

    def test_report_rejected_if_alert_not_retrieved(self):
        self.client.chat.completions.create.side_effect = [
            fake_reply(calls=[self.playbook_call]),
            fake_reply(text="Attempted report"),
        ]
        with self.assertRaisesRegex(RuntimeError, "no evidence tool succeeded"):
            self.agent.run("Investigate using playbook")

    def test_report_rejected_if_playbook_not_found(self):
        unknown = fake_call(
            "get_investigation_playbook",
            '{"playbook_id":"web-bruteforce-v1"}',
            "call-unknown",
        )
        self.client.chat.completions.create.side_effect = [
            fake_reply(calls=[unknown, self.alert_call]),
            fake_reply(text="Attempted report"),
        ]
        with self.assertRaisesRegex(RuntimeError, "required tools not completed"):
            self.agent.run("Investigate using missing playbook")

    def test_report_rejected_if_playbook_arguments_invalid(self):
        bad = fake_call("get_investigation_playbook", "{}", "call-bad")
        self.client.chat.completions.create.side_effect = [
            fake_reply(calls=[bad, self.alert_call]),
            fake_reply(text="Attempted report"),
        ]
        with self.assertRaisesRegex(RuntimeError, "required tools not completed"):
            self.agent.run("Investigate using playbook")

    def test_both_tools_then_report_succeeds(self):
        self.client.chat.completions.create.side_effect = [
            fake_reply(calls=[self.playbook_call, self.alert_call]),
            fake_reply(text="Steps SSH-01 through SSH-05 reviewed."),
        ]
        answer = self.agent.run("Investigate using playbook")
        self.assertIn("SSH-01", answer)
        self.assertEqual(self.client.chat.completions.create.call_count, 2)
        messages = self.client.chat.completions.create.call_args_list[1].kwargs["messages"]
        tool_messages = [m for m in messages if m["role"] == "tool"]
        self.assertEqual(len(tool_messages), 2)
        self.assertTrue(json.loads(tool_messages[0]["content"])["result"]["found"])
        self.assertEqual(
            json.loads(tool_messages[1]["content"])["result"]["alert_id"],
            "demo-ssh-001",
        )

    def test_old_agent_can_still_report_with_only_alert(self):
        old_agent = TriageAgent(client=self.client, model="fake-test-model")
        self.client.chat.completions.create.side_effect = [
            fake_reply(calls=[self.alert_call]),
            fake_reply(text="Old investigation complete."),
        ]
        self.assertEqual(
            old_agent.run("Investigate normal alert"),
            "Old investigation complete.",
        )


if __name__ == "__main__":
    unittest.main()