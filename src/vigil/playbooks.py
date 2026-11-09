"""Read-only investigation playbooks; they are guidance, not automatic actions."""

from copy import deepcopy


PLAYBOOKS = {
    "ssh-bruteforce-v1": {
        "found": True,
        "source": "local_learning_playbook",
        "playbook_id": "ssh-bruteforce-v1",
        "title": "Investigate possible SSH credential guessing",
        "goal": "Review SSH evidence carefully without assuming compromise.",
        "steps": [
            {
                "step_id": "SSH-01",
                "name": "Identify the alert",
                "check": "Record the alert ID and whether its data is synthetic.",
            },
            {
                "step_id": "SSH-02",
                "name": "Review authentication evidence",
                "check": "List event IDs, failed-login counts, and successful logins.",
            },
            {
                "step_id": "SSH-03",
                "name": "Check the event timeline",
                "check": "Use timestamps to confirm event order; if missing, say unknown.",
            },
            {
                "step_id": "SSH-04",
                "name": "Check authorization and activity",
                "check": "Check if the login was approved and any post-login activity; mark missing evidence.",
            },
            {
                "step_id": "SSH-05",
                "name": "Summarize and recommend",
                "check": "Separate observed facts, possible interpretations, missing data, and next steps.",
            },
        ],
        "restrictions": [
            "Do not infer compromise from a successful login alone.",
            "Do not invent timestamps or event order.",
            "Do not block IPs or change systems.",
        ],
    }
}


def get_investigation_playbook(playbook_id: str) -> dict:
    """Return a copy of one known playbook, or a clear not-found result."""
    playbook = PLAYBOOKS.get(playbook_id)
    if playbook is None:
        return {
            "found": False,
            "source": "local_learning_playbook",
            "requested_playbook_id": playbook_id,
        }
    return deepcopy(playbook)