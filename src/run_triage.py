"""Start the VIGIL Triage Agent with one selected LLM provider."""

from vigil.provider_factory import create_model_client
from vigil.triage_agent import TriageAgent


def main() -> None:
    try:
        client, model, provider = create_model_client()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    print(f"Selected provider: {provider}")
    print(f"Selected model: {model}")

    agent = TriageAgent(client=client, model=model)
    task = "Investigate synthetic SSH alert demo-ssh-001 using get_demo_alert_by_id."

    try:
        report = agent.run(task)
    except Exception as exc:
        raise SystemExit(
            f"Triage stopped ({type(exc).__name__}). "
            "Check your API settings, model tool support, and network."
        ) from None

    print("\nTriage report:\n")
    print(report)


if __name__ == "__main__":
    main()