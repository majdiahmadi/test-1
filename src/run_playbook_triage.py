"""Run one synthetic SSH investigation using a local playbook."""

from vigil.provider_factory import create_model_client
from vigil.triage_agent import TriageAgent


def main() -> None:
    try:
        client, model, provider = create_model_client()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    print(f"Selected provider: {provider}")
    print(f"Selected model: {model}")

    agent = TriageAgent(client=client, model=model, use_playbook=True)
    task = (
        "Investigate the synthetic SSH alert demo-ssh-001 using "
        "playbook ssh-bruteforce-v1. Retrieve both the playbook and alert "
        "with tools. Present each playbook step by its step ID. "
        "Say NOT CHECKED for missing evidence. Do not claim event order, "
        "confirmed compromise, or response actions."
    )

    try:
        report = agent.run(task)
    except Exception as exc:
        raise SystemExit(
            f"Playbook triage stopped ({type(exc).__name__}): {exc}"
        ) from None

    print("\nPlaybook triage report:\n")
    print(report)


if __name__ == "__main__":
    main()