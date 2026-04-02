"""Tests for LLM structurer helper functions — no API calls."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from llm.structurer import _try_parse_json, _build_fallback_profile, PROMPT_VERSION
from types_ import CompanyQuery, RawCollectorData, RiskLevel


class TestTryParseJson:
    def test_clean_json(self):
        assert _try_parse_json('{"key": "value"}') == {"key": "value"}

    def test_strips_json_fence(self):
        assert _try_parse_json('```json\n{"k": 1}\n```') == {"k": 1}

    def test_strips_plain_fence(self):
        assert _try_parse_json('```\n{"k": 1}\n```') == {"k": 1}

    def test_invalid_returns_none(self):
        assert _try_parse_json("not json") is None
        assert _try_parse_json("") is None

    def test_array_returns_none(self):
        assert _try_parse_json("[1, 2, 3]") is None

    def test_handles_whitespace(self):
        assert _try_parse_json('  {"x": 1}  ') == {"x": 1}


class TestBuildFallbackProfile:
    def test_returns_unknown_risk(self):
        q = CompanyQuery(company_name="Acme", jurisdiction="GB")
        p = _build_fallback_profile(q, [])
        assert p.overall_risk_level == RiskLevel.UNKNOWN
        assert p.completeness_score == 0.0

    def test_includes_data_sources(self):
        q = CompanyQuery(company_name="Acme", jurisdiction="GB")
        data = [RawCollectorData(source="companies_house", raw={}), RawCollectorData(source="adverse_media", raw={})]
        p = _build_fallback_profile(q, data)
        assert "companies_house" in p.data_sources_used
        assert "adverse_media" in p.data_sources_used

    def test_has_assessment_failed_signal(self):
        q = CompanyQuery(company_name="Acme", jurisdiction="GB")
        p = _build_fallback_profile(q, [])
        assert any(s.signal == "assessment_failed" for s in p.risk_signals)

    def test_prompt_version_set(self):
        q = CompanyQuery(company_name="Acme", jurisdiction="GB")
        assert _build_fallback_profile(q, []).prompt_version == PROMPT_VERSION


class TestCompanyQuery:
    def test_raises_with_no_identifier(self):
        with pytest.raises(Exception):
            CompanyQuery(jurisdiction="GB")

    def test_name_only_ok(self):
        q = CompanyQuery(company_name="Acme", jurisdiction="GB")
        assert q.company_name == "Acme"

    def test_reg_only_ok(self):
        q = CompanyQuery(registration_number="12345678", jurisdiction="GB")
        assert q.registration_number == "12345678"

    def test_default_jurisdiction(self):
        assert CompanyQuery(company_name="Acme").jurisdiction == "GB"
