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