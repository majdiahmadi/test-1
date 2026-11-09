"""Read completed investigations from VIGIL's local SQLite database."""

import argparse
import json
import sqlite3
from pathlib import Path

from vigil.investigation_history import InvestigationHistory


def main() -> None:
    parser = argparse.ArgumentParser(description="View saved VIGIL investigations.")
    commands = parser.add_subparsers(dest="command", required=True)

    list_command = commands.add_parser("list", help="List recent investigations")
    list_command.add_argument("--limit", type=int, default=10)
    list_command.add_argument("--alert-id", default=None)

    show_command = commands.add_parser("show", help="Show one investigation")
    show_command.add_argument("investigation_id")

    args = parser.parse_args()
    database_path = (
        Path(__file__).resolve().parents[1] / "data" / "investigations.sqlite3"
    )

    try:
        history = InvestigationHistory(database_path)
        if args.command == "list":
            records = history.list_reports(
                limit=args.limit, alert_id=args.alert_id
            )
            if not records:
                print("No saved investigations found.")
                return
            for record in records:
                print(
                    f"{record['created_at_utc']} | "
                    f"ID: {record['investigation_id']} | "
                    f"Alert: {record['alert_id']} | "
                    f"Provider: {record['provider']} | "
                    f"Model: {record['model']}"
                )
        else:
            record = history.get_report(args.investigation_id)
            if record is None:
                raise SystemExit("No investigation found with that ID.")
            print(json.dumps(record, indent=2, ensure_ascii=False))
    except (ValueError, sqlite3.Error) as error:
        raise SystemExit(f"Could not read investigation history: {error}") from None


if __name__ == "__main__":
    main()