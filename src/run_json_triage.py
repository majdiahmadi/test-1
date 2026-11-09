"""Run playbook-based triage and save a validated JSON report."""

import json
from pathlib import Path

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
    except (ReportValidationError, RuntimeError) as error:
        raise SystemExit(f"JSON triage stopped: {error}") from None
    except Exception as error:
        raise SystemExit(
            f"JSON triage stopped ({type(error).__name__}). "
            "Check your model/API settings."
        ) from None

    output_path = Path(__file__).resolve().parents[1] / "reports" / "demo-ssh-001.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    print("\nValidated JSON investigation report:\n")
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()