"""Lesson 10: test persistent investigation history without using cloud APIs."""

import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from vigil.investigation_history import InvestigationHistory
from vigil.report_validation import ReportValidationError
from vigil.structured_triage_agent import StructuredTriageAgent


def example_report():
    """A known-valid SYNTHETIC report, not the output of a real LLM."""
    return {
        "schema_version": "1.0",
        "alert_id": "demo-ssh-001",
        "source": "synthetic_fixture",
        "source_ip": "192.0.2.10",
        "authorization_status": "unknown",
        "severity": "undetermined",
        "confidence": "low",
        "events": [
            {"event_id": "log-001", "event_type": "ssh_login_failed", "count": 15, "username": None},
            {"event_id": "log-002", "event_type": "ssh_login_success", "count": None, "username": "admin"},
        ],
        "assessment": "Possible credential guessing, but no compromise is confirmed.",
        "uncertainties": ["No timestamps", "Authorization is unknown"],
        "playbook_steps": [
            {"step_id": "SSH-01", "status": "CHECKED", "finding": "Found demo alert"},
            {"step_id": "SSH-02", "status": "CHECKED", "finding": "Reviewed two events"},
            {"step_id": "SSH-03", "status": "NOT CHECKED", "finding": "No timestamps"},
            {"step_id": "SSH-04", "status": "NOT CHECKED", "finding": "Authorization unknown"},
            {"step_id": "SSH-05", "status": "CHECKED", "finding": "Reported findings"},
        ],
        "recommended_actions": ["Check original authentication logs"],
        "actions_taken": [],
    }


def fake_reply(text=None, calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=calls))])


def fake_call(name, arguments, call_id):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


class InvestigationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database_path = Path(self.temp.name) / "nested" / "investigations.sqlite3"
        self.history = InvestigationHistory(self.database_path)

    def save_example(self):
        return self.history.save_report(
            example_report(), provider="nvidia", model="fake-model"
        )

    def test_database_file_is_created(self):
        self.assertTrue(self.database_path.exists())

    def test_empty_history_has_no_reports(self):
        self.assertEqual(self.history.list_reports(), [])

    def test_save_returns_uuid_like_id(self):
        investigation_id = self.save_example()
        self.assertTrue(re.fullmatch(r"[0-9a-f]{32}", investigation_id))

    def test_save_and_read_returns_original_report(self):
        investigation_id = self.save_example()
        record = self.history.get_report(investigation_id)
        self.assertEqual(record["report"], example_report())
        self.assertEqual(record["alert_id"], "demo-ssh-001")

    def test_metadata_is_saved(self):
        record = self.history.get_report(self.save_example())
        self.assertEqual(record["provider"], "nvidia")
        self.assertEqual(record["model"], "fake-model")
        self.assertIn("+00:00", record["created_at_utc"])

    def test_each_save_creates_a_different_record(self):
        first = self.save_example()
        second = self.save_example()
        self.assertNotEqual(first, second)
        self.assertEqual(len(self.history.list_reports()), 2)

    def test_history_survives_new_instance(self):
        investigation_id = self.save_example()
        reopened = InvestigationHistory(self.database_path)
        self.assertEqual(reopened.get_report(investigation_id)["alert_id"], "demo-ssh-001")

    def test_list_only_returns_metadata(self):
        self.save_example()
        record = self.history.list_reports()[0]
        self.assertNotIn("report_json", record)
        self.assertNotIn("report", record)

    def test_list_is_most_recent_first(self):
        first = self.save_example()
        second = self.save_example()
        self.assertEqual([item["investigation_id"] for item in self.history.list_reports()], [second, first])

    def test_list_respects_limit(self):
        self.save_example()
        self.save_example()
        self.assertEqual(len(self.history.list_reports(limit=1)), 1)

    def test_filter_by_known_alert_id(self):
        self.save_example()
        self.assertEqual(len(self.history.list_reports(alert_id="demo-ssh-001")), 1)

    def test_filter_unknown_alert_id(self):
        self.save_example()
        self.assertEqual(self.history.list_reports(alert_id="not-here"), [])

    def test_sql_like_input_is_treated_as_plain_text(self):
        self.save_example()
        self.assertEqual(self.history.list_reports(alert_id="' OR 1=1 --"), [])
        self.assertIsNone(self.history.get_report("' OR 1=1 --"))

    def test_missing_record_returns_none(self):
        self.assertIsNone(self.history.get_report("missing"))

    def test_invalid_limit_rejected(self):
        for value in (0, -1, 51, True, "10"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.history.list_reports(limit=value)

    def test_invalid_alert_id_rejected(self):
        for value in ("", 5):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.history.list_reports(alert_id=value)

    def test_invalid_investigation_id_rejected(self):
        with self.assertRaises(ValueError):
            self.history.get_report("")

    def test_missing_provider_rejected(self):
        with self.assertRaises(ValueError):
            self.history.save_report(example_report(), provider="", model="fake-model")

    def test_missing_model_rejected(self):
        with self.assertRaises(ValueError):
            self.history.save_report(example_report(), provider="nvidia", model="")

    def test_non_dictionary_report_rejected(self):
        with self.assertRaises(ValueError):
            self.history.save_report([], provider="nvidia", model="fake-model")

    def test_invented_event_count_not_saved(self):
        bad = example_report()
        bad["events"][0]["count"] = 500
        with self.assertRaises(ReportValidationError):
            self.history.save_report(bad, provider="nvidia", model="fake-model")
        self.assertEqual(self.history.list_reports(), [])

    def test_action_claim_not_saved(self):
        bad = example_report()
        bad["actions_taken"] = ["Blocked IP"]
        with self.assertRaises(ReportValidationError):
            self.history.save_report(bad, provider="nvidia", model="fake-model")
        self.assertEqual(self.history.list_reports(), [])

    def test_original_dictionary_is_not_modified(self):
        original = example_report()
        frozen = copy.deepcopy(original)
        self.history.save_report(original, provider="nvidia", model="fake-model")
        self.assertEqual(original, frozen)

    def test_fake_llm_run_can_be_saved_and_read_back(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            fake_reply(calls=[
                fake_call("get_investigation_playbook", '{"playbook_id":"ssh-bruteforce-v1"}', "pb"),
                fake_call("get_demo_alert_by_id", '{"alert_id":"demo-ssh-001"}', "alert"),
            ]),
            fake_reply(text=json.dumps(example_report())),
        ]
        agent = StructuredTriageAgent(client=client, model="fake-test-model")
        report = agent.run_structured("Investigate synthetic alert")
        investigation_id = self.history.save_report(report, provider="nvidia", model="fake-test-model")
        self.assertEqual(self.history.get_report(investigation_id)["report"], report)
        self.assertEqual(client.chat.completions.create.call_count, 2)


if __name__ == "__main__":
    unittest.main()