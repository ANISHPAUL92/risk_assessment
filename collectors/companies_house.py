"""collectors/companies_house.py — Companies House API (GB) with mock fallback."""
from __future__ import annotations

import base64
import logging
import os
from typing import Any

import httpx

from collectors.base import DataCollector
from types_ import CompanyMatch, CompanyQuery, RawCollectorData

logger = logging.getLogger(__name__)
BASE_URL = "https://api.company-information.service.gov.uk"


class CompaniesHouseCollector(DataCollector):
    name = "companies_house"
    supported_jurisdictions = ["GB"]

    def __init__(self) -> None:
        self._api_key = os.getenv("COMPANIES_HOUSE_API_KEY") or None
        if not self._api_key:
            logger.warning("[CompaniesHouse] No API key — using mock data")

    async def collect(self, query: CompanyQuery) -> RawCollectorData:
        if not self._api_key:
            return self._mock_data(query)

        async with httpx.AsyncClient(
            base_url=BASE_URL,
            headers=self._auth_headers(),
            timeout=8.0,
        ) as client:
            if query.registration_number:
                return await self._fetch_by_number(client, query.registration_number)
            return await self._fetch_by_name(client, query.company_name or "")

    async def _fetch_by_number(self, client: httpx.AsyncClient, number: str) -> RawCollectorData:
        import asyncio
        results = await asyncio.gather(
            client.get(f"/company/{number}"),
            client.get(f"/company/{number}/officers"),
            client.get(f"/company/{number}/filing-history", params={"items_per_page": 10}),
            return_exceptions=True,
        )

        def safe_json(res: Any) -> Any:
            if isinstance(res, Exception):
                return {}
            if res.status_code != 200:
                return {}
            return res.json()

        profile_data = safe_json(results[0])
        if not profile_data:
            raise RuntimeError(f"Company not found: {number}")

        return RawCollectorData(
            source=self.name,
            raw={
                "profile": profile_data,
                "officers": safe_json(results[1]),
                "filings": safe_json(results[2]),
            },
        )

    async def _fetch_by_name(self, client: httpx.AsyncClient, name: str) -> RawCollectorData:
        res = await client.get("/search/companies", params={"q": name, "items_per_page": 5})
        res.raise_for_status()
        return RawCollectorData(source=self.name, raw={"search_results": res.json()})

    def _auth_headers(self) -> dict[str, str]:
        encoded = base64.b64encode(f"{self._api_key}:".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    def _mock_data(self, query: CompanyQuery) -> RawCollectorData:
        # Registration number only — we cannot fabricate a real company from a number
        # we've never seen. Return empty data so the LLM reports no info found.
        if query.registration_number and not query.company_name:
            logger.info(
                "[CompaniesHouse] Mock mode: cannot look up %s without a real API key.",
                query.registration_number,
            )
            return RawCollectorData(
                source=self.name,
                raw={
                    "mock_notice": (
                        "No Companies House API key configured. "
                        "Cannot look up company by registration number without a live API call. "
                        "No company data is available for this query."
                    ),
                    "queried_registration_number": query.registration_number,
                    "profile": None,
                    "officers": None,
                    "filings": None,
                },
            )

        # Name search — only return rich mock data for the designated demo company.
        # For everything else return null so the LLM does not treat fake data as real.
        DEMO_NAME = "cartoon network ltd"
        if query.company_name and query.company_name.strip().lower() == DEMO_NAME:
            logger.info("[CompaniesHouse] Mock mode: returning demo profile for '%s'.", query.company_name)
            return RawCollectorData(
                source=self.name,
                raw={
                    "mock_notice": "Demo data for development — not a real Companies House record.",
                    "profile": {
                        "company_name": query.company_name,
                        "company_number": "00000001",
                        "company_status": "active",
                        "type": "ltd",
                        "date_of_creation": "2015-06-01",
                        "registered_office_address": {
                            "address_line_1": "1 Media House",
                            "locality": "London",
                            "postal_code": "W1T 3JH",
                            "country": "England",
                        },
                        "sic_codes": ["59113"],
                        "accounts": {
                            "next_due": "2025-12-31",
                            "last_accounts": {"made_up_to": "2023-12-31"},
                        },
                        "confirmation_statement": {
                            "next_due": "2025-06-01",
                            "last_made_up_to": "2024-06-01",
                            "overdue": False,
                        },
                    },
                    "officers": {
                        "items": [],
                        "mock_notice": "Director information not available in demo mode.",
                    },
                    "filings": {
                        "total_count": 18,
                        "items": [
                            {"date": "2024-06-01", "description": "Confirmation statement", "category": "confirmation-statement"},
                            {"date": "2024-02-10", "description": "Total exemption full accounts", "category": "accounts"},
                            {"date": "2023-06-01", "description": "Confirmation statement", "category": "confirmation-statement"},
                        ],
                    },
                },
            )

        # Any other name without an API key — return null so the LLM is honest
        # that it has no verified company data to work with.
        logger.info(
            "[CompaniesHouse] Mock mode: no real data available for '%s' without an API key.",
            query.company_name,
        )
        return RawCollectorData(
            source=self.name,
            raw={
                "mock_notice": (
                    "No Companies House API key configured. "
                    "Cannot look up company details without a live API call. "
                    "No address, filing, or director data is available."
                ),
                "queried_company_name": query.company_name,
                "profile": None,
                "officers": None,
                "filings": None,
            },
        )


def parse_company_matches(raw: dict[str, Any]) -> list[CompanyMatch]:
    """Convert Companies House search response to CompanyMatch list. Pure function."""
    items = raw.get("search_results", {}).get("items", [])
    matches = []
    for item in items:
        addr = item.get("registered_office_address", {})
        addr_parts = [
            addr.get(k) for k in ("address_line_1", "address_line_2", "locality", "postal_code")
            if addr.get(k)
        ]
        matches.append(CompanyMatch(
            company_name=item.get("title", ""),
            registration_number=item.get("company_number", ""),
            company_status=item.get("company_status", "unknown"),
            incorporation_date=item.get("date_of_creation"),
            address=", ".join(addr_parts) or None,
        ))
    return matches
