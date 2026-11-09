"""Lesson 9: schema checks, evidence checks, and a fake LLM run."""

import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from jsonschema import Draft202012Validator

from vigil.demo_tools import get_demo_alert
from vigil.playbooks import get_investigation_playbook
from vigil.report_schema import REPORT_SCHEMA
from vigil.report_validation import ReportValidationError, validate_json_report
from vigil.structured_triage_agent import StructuredTriageAgent
from vigil.triage_agent import TriageAgent


def sample_report():
    """A valid demo report for offline tests; not written by a real model."""
    return {
        "schema_version": "1.0",
        "alert_id": "demo-ssh-001",
        "source": "synthetic_fixture",
        "source_ip": "192.0.2.10",
        "authorization_status": "unknown",
        "severity": "undetermined",
        "confidence": "low",
        "events": [
            {
                "event_id": "log-001",
                "event_type": "ssh_login_failed",
                "count": 15,
                "username": None,
            },
            {
                "event_id": "log-002",
                "event_type": "ssh_login_success",
                "count": None,
                "username": "admin",
            },
        ],
        "assessment": "Possible credential guessing; no compromise confirmed.",
        "uncertainties": ["No timestamps", "Authorization is unknown"],
        "playbook_steps": [
            {"step_id": "SSH-01", "status": "CHECKED", "finding": "Demo alert identified"},
            {"step_id": "SSH-02", "status": "CHECKED", "finding": "Two SSH event records reviewed"},
            {"step_id": "SSH-03", "status": "NOT CHECKED", "finding": "Timestamps are unavailable"},
            {"step_id": "SSH-04", "status": "NOT CHECKED", "finding": "Authorization and activity are unknown"},
            {"step_id": "SSH-05", "status": "CHECKED", "finding": "Findings and next steps recorded"},
        ],
        "recommended_actions": ["Verify authorization using real log records"],
        "actions_taken": [],
    }


def fake_reply(text=None, calls=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=calls))]
    )


def fake_call(name, arguments, call_id):
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=name, arguments=arguments)
    )


class JsonReportTests(unittest.TestCase):
    def setUp(self):
        self.alert = get_demo_alert()
        self.playbook = get_investigation_playbook("ssh-bruteforce-v1")

    def validate(self, report):
        return validate_json_report(json.dumps(report), self.alert, self.playbook)

    def test_schema_itself_is_valid(self):
        Draft202012Validator.check_schema(REPORT_SCHEMA)

    def test_valid_report_is_accepted(self):
        self.assertEqual(self.validate(sample_report())["alert_id"], "demo-ssh-001")

    def test_bad_json_rejected(self):
        with self.assertRaisesRegex(ReportValidationError, "not valid JSON"):
            validate_json_report("not json", self.alert, self.playbook)

    def test_markdown_code_fence_rejected(self):
        with self.assertRaises(ReportValidationError):
            validate_json_report("```json\n{}\n```", self.alert, self.playbook)

    def test_missing_field_rejected(self):
        data = sample_report()
        del data["actions_taken"]
        with self.assertRaises(ReportValidationError):
            self.validate(data)

    def test_extra_field_rejected(self):
        data = sample_report()
        data["invented_field"] = "hello"
        with self.assertRaises(ReportValidationError):
            self.validate(data)

    def test_wrong_event_count_rejected(self):
        data = sample_report()
        data["events"][0]["count"] = 999
        with self.assertRaisesRegex(ReportValidationError, "events do not match"):
            self.validate(data)

    def test_missing_event_rejected(self):
        data = sample_report()
        data["events"].pop()
        with self.assertRaises(ReportValidationError):
            self.validate(data)

    def test_duplicate_event_rejected(self):
        data = sample_report()
        data["events"].append(copy.deepcopy(data["events"][0]))
        with self.assertRaises(ReportValidationError):
            self.validate(data)

    def test_wrong_source_ip_rejected(self):
        data = sample_report()
        data["source_ip"] = "203.0.113.123"
        with self.assertRaisesRegex(ReportValidationError, "source_ip"):
            self.validate(data)

    def test_high_severity_rejected_for_this_fixture(self):
        data = sample_report()
        data["severity"] = "high"
        with self.assertRaises(ReportValidationError):
            self.validate(data)

    def test_missing_playbook_step_rejected(self):
        data = sample_report()
        data["playbook_steps"].pop()
        with self.assertRaises(ReportValidationError):
            self.validate(data)

    def test_duplicate_playbook_step_rejected(self):
        data = sample_report()
        data["playbook_steps"].append(copy.deepcopy(data["playbook_steps"][0]))
        with self.assertRaises(ReportValidationError):
            self.validate(data)

    def test_unknown_timeline_cannot_be_checked(self):
        data = sample_report()
        data["playbook_steps"][2]["status"] = "CHECKED"
        with self.assertRaisesRegex(ReportValidationError, "SSH-03"):
            self.validate(data)

    def test_unknown_authorization_cannot_be_checked(self):
        data = sample_report()
        data["playbook_steps"][3]["status"] = "CHECKED"
        with self.assertRaisesRegex(ReportValidationError, "SSH-04"):
            self.validate(data)

    def test_actions_taken_must_be_empty(self):
        data = sample_report()
        data["actions_taken"] = ["Blocked IP"]
        with self.assertRaises(ReportValidationError):
            self.validate(data)

    def test_structured_agent_uses_playbook_and_validates(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            fake_reply(calls=[
                fake_call("get_investigation_playbook", '{"playbook_id":"ssh-bruteforce-v1"}', "pb"),
                fake_call("get_demo_alert_by_id", '{"alert_id":"demo-ssh-001"}', "evidence"),
            ]),
            fake_reply(text=json.dumps(sample_report())),
        ]
        agent = StructuredTriageAgent(client=client, model="fake-test-model")
        result = agent.run_structured("Investigate the SSH alert")
        self.assertEqual(result["alert_id"], "demo-ssh-001")
        self.assertEqual(client.chat.completions.create.call_count, 2)
        self.assertIn("FINAL answer", agent.instructions)

    def test_structured_agent_rejects_hallucinated_event(self):
        bad_report = sample_report()
        bad_report["events"][0]["count"] = 900
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            fake_reply(calls=[
                fake_call("get_investigation_playbook", '{"playbook_id":"ssh-bruteforce-v1"}', "pb"),
                fake_call("get_demo_alert_by_id", '{"alert_id":"demo-ssh-001"}', "evidence"),
            ]),
            fake_reply(text=json.dumps(bad_report)),
        ]
        agent = StructuredTriageAgent(client=client, model="fake-test-model")
        with self.assertRaisesRegex(ReportValidationError, "events do not match"):
            agent.run_structured("Investigate the SSH alert")

    def test_old_triage_agent_still_works(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            fake_reply(calls=[fake_call("get_demo_alert", "{}", "alert")]),
            fake_reply(text="Normal text report still works"),
        ]
        agent = TriageAgent(client=client, model="fake-test-model")
        self.assertEqual(agent.run("Review synthetic alert"), "Normal text report still works")


if __name__ == "__main__":
    unittest.main()