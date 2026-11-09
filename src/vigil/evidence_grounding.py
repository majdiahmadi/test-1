"""Small, deterministic claim checks for our synthetic SSH lesson.

This is NOT a general factuality detector. It catches a few unsupported
statements before an AI-written investigation can be accepted or saved.
"""

import re
from typing import Any


class EvidenceGroundingError(ValueError):
    """The text claims more than the synthetic evidence can support."""


# Check BOTH directions: "failures followed by success" and
# "success happened after failures" can mean the same thing.
_ORDER_PATTERNS = (
    re.compile(r"\bfail(?:ed|ures?)\b.{0,140}\bfollowed by\b.{0,140}\bsuccess", re.I),
    re.compile(r"\bfail(?:ed|ures?)\b.{0,140}\b(?:then|before|later)\b.{0,140}\bsuccess", re.I),
    re.compile(r"\bsuccess(?:ful)?\b.{0,140}\bafter\b.{0,140}\bfail", re.I),
)

# These words explain that a possible sequence has NOT been established.
_UNCERTAIN_ORDER = re.compile(
    r"\b(?:whether|unknown|unclear|cannot|can't|could not|not confirmed|"
    r"not established|not verified|no evidence|unverified)\b",
    re.I,
)

# These examples are especially serious when the authorization is unknown.
_COMPROMISE_PATTERNS = (
    re.compile(r"\b(?:confirmed|proven|definite)\s+(?:unauthorized access|compromise|breach)\b", re.I),
    re.compile(r"\b(?:account|system|host|admin)\s+(?:was|is|has been)\s+compromised\b", re.I),
    re.compile(r"\b(?:attacker|adversary)\s+(?:gained|obtained)\s+(?:access|control)\b", re.I),
    re.compile(r"\b(?:password|credentials?)\s+(?:was|were)\s+(?:successfully\s+)?(?:guessed|cracked|stolen)\b", re.I),
    re.compile(r"\b(?:login|access)\s+(?:was|is)\s+unauthorized\b", re.I),
)

_UNCERTAIN_COMPROMISE = re.compile(
    r"\b(?:no evidence|not confirmed|not proven|cannot confirm|can't confirm|"
    r"unknown whether|unclear whether|whether|if|possible|possibly|"
    r"may have|might have|could have)\b",
    re.I,
)


def _sentences(text: str) -> list[str]:
    """Split readable text into short parts for our simple phrase checks."""
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]


def check_evidence_grounding(report: dict[str, Any], alert: dict[str, Any]) -> None:
    """Reject a few unsupported text claims in this demo's final report.

    Call only AFTER JSON/schema validation. This function does not repair
    mistakes or prove that every remaining sentence is true.
    """
    if not isinstance(report, dict) or not isinstance(alert, dict):
        raise EvidenceGroundingError("Report and evidence must be dictionaries.")

    uncertainties = " ".join(report["uncertainties"]).lower()
    if "timestamp" not in uncertainties and "event time" not in uncertainties:
        raise EvidenceGroundingError("Uncertainties must mention the missing event timestamps.")
    if "authoriz" not in uncertainties and "authoris" not in uncertainties:
        raise EvidenceGroundingError("Uncertainties must mention the unknown authorization.")

    missing_timestamps = any(not event.get("timestamp") for event in alert["events"])
    authorization_unknown = alert.get("authorization_status") == "unknown"

    fields = [("assessment", report["assessment"])]
    fields.extend(
        (f"playbook_steps[{step['step_id']}].finding", step["finding"])
        for step in report["playbook_steps"]
    )

    for field, text in fields:
        for sentence in _sentences(text):
            if missing_timestamps and any(p.search(sentence) for p in _ORDER_PATTERNS):
                if not _UNCERTAIN_ORDER.search(sentence):
                    raise EvidenceGroundingError(
                        f"Unsupported event-order claim in {field}: timestamps are missing."
                    )
            if authorization_unknown and any(p.search(sentence) for p in _COMPROMISE_PATTERNS):
                if not _UNCERTAIN_COMPROMISE.search(sentence):
                    raise EvidenceGroundingError(
                        f"Unsupported compromise claim in {field}: authorization is unknown."
                    )