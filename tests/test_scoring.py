"""Tests for scoring.py — pure functions, no I/O."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from scoring import calculate_completeness, completeness_label, _is_empty, _nested


class TestCalculateCompleteness:
    def test_empty_profile_returns_zero(self):
        assert calculate_completeness({}) == 0.0

    def test_fully_populated_profile_returns_high_score(self):
        profile = {
            "canonical_name": "Acme Ltd", "registration_number": "12345678",
            "incorporation_date": "2019-01-01", "company_status": "active",
            "registered_address": "123 London Rd", "company_type": "ltd",
            "directors": [{"name": "John Smith"}],
            "filing_history": {"total_filings": 12, "last_filed_date": "2024-01-01", "has_overdue_filings": False},
            "adverse_media": {"has_adverse_media": False, "summary": "No adverse media."},
            "overall_risk_level": "low", "risk_summary": "Low risk.",
            "risk_signals": [{"signal": "none", "severity": "low", "detail": "Clean"}],
        }
        assert calculate_completeness(profile) >= 0.90

    def test_partial_profile_is_between_bounds(self):
        profile = {"canonical_name": "Acme Ltd", "registration_number": "12345678", "company_status": "active"}
        score = calculate_completeness(profile)
        assert 0.0 < score < 1.0

    def test_empty_directors_list_counts_as_missing(self):
        base = {"canonical_name": "Acme Ltd"}
        score_empty = calculate_completeness({**base, "directors": []})
        score_filled = calculate_completeness({**base, "directors": [{"name": "John"}]})
        assert score_filled > score_empty

    def test_score_bounds(self):
        for profile in [{}, {"canonical_name": "X"}, {"directors": [{"name": "A"}]}]:
            assert 0.0 <= calculate_completeness(profile) <= 1.0

    def test_null_values_not_counted(self):
        assert calculate_completeness({"canonical_name": None, "registration_number": None}) == 0.0

    def test_rounded_to_two_dp(self):
        score = calculate_completeness({"canonical_name": "Acme"})
        assert score == round(score, 2)


class TestCompletenessLabel:
    @pytest.mark.parametrize("score,expected", [
        (1.0, "High confidence"), (0.85, "High confidence"),
        (0.84, "Moderate confidence"), (0.60, "Moderate confidence"),
        (0.59, "Low confidence"), (0.35, "Low confidence"),
        (0.34, "Very low confidence"), (0.0, "Very low confidence"),
    ])
    def test_bands(self, score, expected):
        assert completeness_label(score) == expected


class TestIsEmpty:
    def test_none(self): assert _is_empty(None)
    def test_empty_string(self): assert _is_empty("") and _is_empty("  ")
    def test_empty_list(self): assert _is_empty([])
    def test_empty_dict(self): assert _is_empty({})
    def test_zero_not_empty(self): assert not _is_empty(0)
    def test_false_not_empty(self): assert not _is_empty(False)
    def test_populated_not_empty(self):
        assert not _is_empty("hello")
        assert not _is_empty([1])
        assert not _is_empty(42)


class TestNested:
    def test_retrieves_value(self): assert _nested({"a": {"b": 42}}, "a", "b") == 42
    def test_missing_key(self): assert _nested({"a": {}}, "a", "b") is None
    def test_non_dict_intermediate(self): assert _nested({"a": "x"}, "a", "b") is None
    def test_single_key(self): assert _nested({"x": 1}, "x") == 1
