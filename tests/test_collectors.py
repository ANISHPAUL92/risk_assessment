"""Tests for collector parsing and registry — no network calls."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from collectors.companies_house import parse_company_matches
from collectors import get_collectors_for_jurisdiction, ALL_COLLECTORS


class TestParseCompanyMatches:
    def _raw(self, items):
        return {"search_results": {"items": items}}

    def test_empty(self):
        assert parse_company_matches(self._raw([])) == []

    def test_single_match(self):
        raw = self._raw([{
            "title": "Acme Ltd", "company_number": "12345678",
            "company_status": "active", "date_of_creation": "2019-03-15",
            "registered_office_address": {"address_line_1": "123 Rd", "locality": "London", "postal_code": "EC1A 1BB"},
        }])
        matches = parse_company_matches(raw)
        assert len(matches) == 1
        assert matches[0].company_name == "Acme Ltd"
        assert matches[0].registration_number == "12345678"
        assert "London" in matches[0].address

    def test_multiple_matches(self):
        raw = self._raw([
            {"title": "Acme Ltd", "company_number": "11111111", "company_status": "active"},
            {"title": "Acme Holdings", "company_number": "22222222", "company_status": "dissolved"},
        ])
        assert len(parse_company_matches(raw)) == 2

    def test_missing_address_is_none(self):
        raw = self._raw([{"title": "Acme", "company_number": "111", "company_status": "active"}])
        assert parse_company_matches(raw)[0].address is None

    def test_malformed_raw(self):
        assert parse_company_matches({}) == []
        assert parse_company_matches({"search_results": {}}) == []


class TestCollectorRegistry:
    def test_gb_has_companies_house(self):
        assert "companies_house" in [c.name for c in get_collectors_for_jurisdiction("GB")]

    def test_gb_has_adverse_media(self):
        assert "adverse_media" in [c.name for c in get_collectors_for_jurisdiction("GB")]

    def test_us_has_adverse_media_not_companies_house(self):
        names = [c.name for c in get_collectors_for_jurisdiction("US")]
        assert "adverse_media" in names
        assert "companies_house" not in names

    def test_all_collectors_have_name_and_jurisdictions(self):
        for c in ALL_COLLECTORS:
            assert isinstance(c.name, str) and c.name
            assert isinstance(c.supported_jurisdictions, list) and c.supported_jurisdictions
