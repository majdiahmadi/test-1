"""JSON Schema for our Lesson 9 synthetic SSH investigation reports."""

from typing import Any


REPORT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "schema_version": {"const": "1.0"},
        "alert_id": {"type": "string", "minLength": 1},
        "source": {"const": "synthetic_fixture"},
        "source_ip": {"type": "string", "minLength": 1},
        "authorization_status": {"type": "string", "minLength": 1},
        "severity": {
            "type": "string",
            "enum": ["undetermined", "low", "medium", "high", "critical"],
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "events": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "minLength": 1},
                    "event_type": {"type": "string", "minLength": 1},
                    "count": {"type": ["integer", "null"], "minimum": 0},
                    "username": {"type": ["string", "null"]},
                },
                "required": ["event_id", "event_type", "count", "username"],
                "additionalProperties": False,
            },
        },
        "assessment": {"type": "string", "minLength": 1},
        "uncertainties": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "playbook_steps": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "step_id": {"type": "string", "minLength": 1},
                    "status": {"enum": ["CHECKED", "NOT CHECKED"]},
                    "finding": {"type": "string", "minLength": 1},
                },
                "required": ["step_id", "status", "finding"],
                "additionalProperties": False,
            },
        },
        "recommended_actions": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "actions_taken": {
            "type": "array",
            "maxItems": 0,
        },
    },
    "required": [
        "schema_version",
        "alert_id",
        "source",
        "source_ip",
        "authorization_status",
        "severity",
        "confidence",
        "events",
        "assessment",
        "uncertainties",
        "playbook_steps",
        "recommended_actions",
        "actions_taken",
    ],
    "additionalProperties": False,
}