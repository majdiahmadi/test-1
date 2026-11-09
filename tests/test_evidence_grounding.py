"""Lesson 11: reject unsupported narrative claims from a fake LLM."""

import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from vigil.demo_tools import get_demo_alert
from vigil.evidence_grounding import EvidenceGroundingError, check_evidence_grounding
from vigil.playbooks import get_investigation_playbook
from vigil.report_validation import ReportValidationError, validate_json_report
from vigil.structured_triage_agent import StructuredTriageAgent


# We reuse the valid example prepared in Lesson 9.
from test_json_reports import sample_report


class EvidenceGroundingTests(unittest.TestCase):
    def setUp(self):
        self.alert = get_demo_alert()
        self.playbook = get_investigation_playbook("ssh-bruteforce-v1")
        self.report = sample_report()

    def check(self, report):
        return validate_json_report(json.dumps(report), self.alert, self.playbook)

    def test_valid_cautious_report_passes(self):
        self.assertEqual(self.check(self.report)["alert_id"], "demo-ssh-001")

    def test_direct_grounding_helper_raises_specific_error(self):
        self.report["assessment"] = "The admin account was compromised."
        with self.assertRaises(EvidenceGroundingError):
            check_evidence_grounding(self.report, self.alert)

    def test_report_from_earlier_real_run_is_rejected(self):
        self.report["assessment"] = (
            "The alert shows 15 failed login attempts followed by "
            "a successful admin login. Event order cannot be confirmed."
        )
        with self.assertRaisesRegex(ReportValidationError, "event-order"):
            self.check(self.report)

    def test_success_after_failures_is_rejected(self):
        self.report["assessment"] = "The successful login occurred after the failed attempts."
        with self.assertRaises(ReportValidationError):
            self.check(self.report)

    def test_failures_before_success_is_rejected(self):
        self.report["assessment"] = "The failed attempts happened before the successful login."
        with self.assertRaises(ReportValidationError):
            self.check(self.report)

    def test_then_success_is_rejected(self):
        self.report["assessment"] = "Failed logins occurred, then a successful login."
        with self.assertRaises(ReportValidationError):
            self.check(self.report)

    def test_uncertain_order_is_allowed(self):
        self.report["assessment"] = (
            "It is unknown whether failed logins were followed by a successful login."
        )
        self.check(self.report)

    def test_compromised_account_is_rejected(self):
        self.report["assessment"] = "The admin account was compromised."
        with self.assertRaisesRegex(ReportValidationError, "compromise"):
            self.check(self.report)

    def test_confirmed_unauthorized_access_is_rejected(self):
        self.report["assessment"] = "This is confirmed unauthorized access."
        with self.assertRaises(ReportValidationError):
            self.check(self.report)

    def test_suspected_activity_is_allowed(self):
        self.report["assessment"] = (
            "The events could indicate credential guessing. A successful login "
            "does not prove compromise."
        )
        self.check(self.report)

    def test_rejects_bad_playbook_finding(self):
        self.report["playbook_steps"][1]["finding"] = (
            "The failed logins were followed by one successful SSH login."
        )
        with self.assertRaises(ReportValidationError):
            self.check(self.report)

    def test_missing_timestamp_uncertainty_rejected(self):
        self.report["uncertainties"] = ["Authorization is unknown."]
        with self.assertRaisesRegex(ReportValidationError, "timestamps"):
            self.check(self.report)

    def test_missing_authorization_uncertainty_rejected(self):
        self.report["uncertainties"] = ["Event timestamps are missing."]
        with self.assertRaisesRegex(ReportValidationError, "authorization"):
            self.check(self.report)

    def test_recommendations_remain_conditional(self):
        self.report["recommended_actions"] = [
            "If the login proves unauthorized, begin incident response."
        ]
        self.check(self.report)

    def test_old_schema_still_rejects_changed_count(self):
        self.report["events"][0]["count"] = 16
        with self.assertRaises(ValueError):
            self.check(self.report)

    def test_fake_llm_bad_narrative_is_rejected(self):
        self.report["assessment"] = (
            "15 failed attempts followed by a successful admin login."
        )
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=None, tool_calls=[
                    SimpleNamespace(id="pb", function=SimpleNamespace(
                        name="get_investigation_playbook",
                        arguments='{"playbook_id":"ssh-bruteforce-v1"}')),
                    SimpleNamespace(id="al", function=SimpleNamespace(
                        name="get_demo_alert_by_id",
                        arguments='{"alert_id":"demo-ssh-001"}')),
                ]
            ))]),
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps(self.report), tool_calls=None
            ))]),
        ]
        agent = StructuredTriageAgent(client=client, model="offline-test-model")
        with self.assertRaises(ReportValidationError):
            agent.run_structured("Investigate synthetic alert")
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_fake_llm_good_narrative_is_accepted(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=None, tool_calls=[
                    SimpleNamespace(id="pb", function=SimpleNamespace(
                        name="get_investigation_playbook",
                        arguments='{"playbook_id":"ssh-bruteforce-v1"}')),
                    SimpleNamespace(id="al", function=SimpleNamespace(
                        name="get_demo_alert_by_id",
                        arguments='{"alert_id":"demo-ssh-001"}')),
                ]
            ))]),
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps(self.report), tool_calls=None
            ))]),
        ]
        agent = StructuredTriageAgent(client=client, model="offline-test-model")
        self.assertEqual(agent.run_structured("Investigate synthetic alert")["alert_id"], "demo-ssh-001")


if __name__ == "__main__":
    unittest.main()