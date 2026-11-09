
"""Save and read validated synthetic SOC investigation reports in SQLite."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from vigil.demo_tools import get_demo_alert
from vigil.playbooks import get_investigation_playbook
from vigil.report_validation import validate_json_report


class InvestigationHistory:
    """Store one row for each completed, validated investigation."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_table()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open SQLite, manage the transaction, and always close it."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row

        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _create_table(self) -> None:
        """Create the table on the first run; leave it alone on later runs."""
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS investigations (
                    investigation_id TEXT PRIMARY KEY,
                    alert_id TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    report_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_investigations_alert
                ON investigations (alert_id, created_at_utc)
                """
            )

    def save_report(
        self,
        report: dict[str, Any],
        *,
        provider: str,
        model: str,
    ) -> str:
        """Validate the demo report, save it, and return its unique ID."""
        if not isinstance(report, dict):
            raise ValueError("Report must be a Python dictionary.")

        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("Provider must be non-empty text.")

        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model must be non-empty text.")

        report_text = json.dumps(
            report,
            ensure_ascii=False,
            allow_nan=False,
        )

        validate_json_report(
            report_text,
            alert=get_demo_alert(),
            playbook=get_investigation_playbook("ssh-bruteforce-v1"),
        )

        investigation_id = uuid4().hex
        created_at_utc = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO investigations
                    (investigation_id, alert_id, created_at_utc,
                     provider, model, report_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    investigation_id,
                    report["alert_id"],
                    created_at_utc,
                    provider.strip(),
                    model.strip(),
                    report_text,
                ),
            )

        return investigation_id

    def list_reports(
        self,
        *,
        limit: int = 10,
        alert_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List recent investigation metadata without loading all reports."""
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 50
        ):
            raise ValueError(
                "Limit must be a whole number between 1 and 50."
            )

        if alert_id is not None and (
            not isinstance(alert_id, str) or not alert_id
        ):
            raise ValueError(
                "Alert ID must be non-empty text when provided."
            )

        query = (
            "SELECT investigation_id, alert_id, created_at_utc, provider, model "
            "FROM investigations"
        )

        parameters: tuple[Any, ...]

        if alert_id is None:
            parameters = (limit,)
        else:
            query += " WHERE alert_id = ?"
            parameters = (alert_id, limit)

        query += " ORDER BY created_at_utc DESC, rowid DESC LIMIT ?"

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [dict(row) for row in rows]

    def get_report(self, investigation_id: str) -> dict[str, Any] | None:
        """Return one complete saved investigation, or None if missing."""
        if (
            not isinstance(investigation_id, str)
            or not investigation_id.strip()
        ):
            raise ValueError(
                "Investigation ID must be non-empty text."
            )

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM investigations WHERE investigation_id = ?",
                (investigation_id,),
            ).fetchone()

        if row is None:
            return None

        record = dict(row)
        record["report"] = json.loads(record.pop("report_json"))

        return record
