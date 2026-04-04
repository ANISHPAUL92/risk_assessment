"""
scoring.py — Pure functions for result quality evaluation.
"""
from __future__ import annotations

from typing import Any


def calculate_completeness(profile: dict[str, Any]) -> float:
    """
    Proportion of key risk fields that are non-null/non-empty.
    """
    checks: list[tuple[Any, int]] = [
        (profile.get("canonical_name"), 2),
        (profile.get("registration_number"), 2),
        (profile.get("incorporation_date"), 2),
        (profile.get("company_status"), 2),
        (profile.get("registered_address"), 1),
        (profile.get("company_type"), 1),
        (profile.get("directors") or None, 2),
        (_nested(profile, "filing_history", "total_filings"), 1),
        (_nested(profile, "filing_history", "last_filed_date"), 1),
        (_nested(profile, "filing_history", "has_overdue_filings"), 1),
        (_nested(profile, "adverse_media", "has_adverse_media"), 2),
        (_nested(profile, "adverse_media", "summary"), 1),
        (profile.get("overall_risk_level"), 2),
        (profile.get("risk_summary"), 1),
        (profile.get("risk_signals") or None, 1),
    ]
    total = sum(w for _, w in checks)
    filled = sum(w for v, w in checks if not _is_empty(v))
    return round(filled / total, 2) if total else 0.0


def completeness_label(score: float) -> str:
    if score >= 0.85:
        return "High confidence"
    if score >= 0.60:
        return "Moderate confidence"
    if score >= 0.35:
        return "Low confidence"
    return "Very low confidence"


def risk_level_colour(level: str) -> str:
    return {
        "low": "#22c55e",
        "medium": "#f59e0b",
        "high": "#ef4444",
        "unknown": "#6b7280",
    }.get(level, "#6b7280")


# Internal helpers #

def _nested(d: dict, *keys: str) -> Any:
    current = d
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and not value:
        return True
    return False
