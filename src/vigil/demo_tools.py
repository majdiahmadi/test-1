"""Read-only demonstration tools; no connection to Wazuh yet."""


def get_demo_alert() -> dict:
    """Return a fixed, synthetic SSH security alert."""
    return {
        "source": "synthetic_fixture",
        "alert_id": "demo-ssh-001",
        "source_ip": "192.0.2.10",
        "authorization_status": "unknown",
        "events": [
            {
                "event_id": "log-001",
                "event_type": "ssh_login_failed",
                "count": 15,
            },
            {
                "event_id": "log-002",
                "event_type": "ssh_login_success",
                "username": "admin",
            },
        ],
    }


def get_demo_alert_by_id(alert_id: str) -> dict:
    """Look up an alert ID in our single in-memory demonstration fixture."""
    alert = get_demo_alert()

    if alert_id == alert["alert_id"]:
        return alert

    return {
        "source": "synthetic_fixture",
        "requested_alert_id": alert_id,
        "found": False,
    }