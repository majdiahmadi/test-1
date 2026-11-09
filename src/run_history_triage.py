"""Run structured demo triage and save its report in investigation history."""

import json
import sqlite3
from pathlib import Path

from vigil.investigation_history import InvestigationHistory
from vigil.provider_factory import create_model_client
from vigil.report_validation import ReportValidationError
from vigil.structured_triage_agent import StructuredTriageAgent


def main() -> None:
    try:
        client, model, provider = create_model_client()
    except ValueError as error:
        raise SystemExit(str(error)) from None

    print(f"Selected provider: {provider}")
    print(f"Selected model: {model}")

    agent = StructuredTriageAgent(client=client, model=model)
    task = (
        "Investigate synthetic alert demo-ssh-001 using playbook "
        "ssh-bruteforce-v1. Retrieve the evidence and playbook with tools. "
        "Return only the required JSON investigation report."
    )

    try:
        report = agent.run_structured(task)
        database_path = (
            Path(__file__).resolve().parents[1] / "data" / "investigations.sqlite3"
        )
        history = InvestigationHistory(database_path)
        investigation_id = history.save_report(
            report, provider=provider, model=model
        )
    except (ReportValidationError, ValueError, sqlite3.Error, RuntimeError) as error:
        raise SystemExit(f"History triage stopped: {error}") from None
    except Exception as error:
        raise SystemExit(
            f"History triage stopped ({type(error).__name__}). "
            "Check your provider and model settings."
        ) from None

    print("\nValidated report saved in the local investigation history.")
    print(f"Investigation ID: {investigation_id}")
    print(f"Database: {database_path}")
    print("\nReport:\n")
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()