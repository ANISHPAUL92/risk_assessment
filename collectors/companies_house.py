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

# The demo company that always returns rich mock data in development
_DEMO_NAME = "cartoon network ltd"


class CompaniesHouseCollector(DataCollector):
    name = "companies_house"
    supported_jurisdictions = ["GB"]

    def __init__(self) -> None:
        raw_key = os.getenv("COMPANIES_HOUSE_API_KEY", "").strip()
        self._api_key = raw_key if raw_key else None
        if not self._api_key:
            logger.warning("[CompaniesHouse] No API key — using mock data")

    async def collect(self, query: CompanyQuery) -> RawCollectorData:
        # Always check for demo company first — regardless of API key presence
        if query.company_name and query.company_name.strip().lower() == _DEMO_NAME:
            return self._demo_data(query)

        # No real API key — return null for everything else
        if not self._api_key:
            return self._no_data(query)

        # Real API key present — fetch live data
        async with httpx.AsyncClient(
            base_url=BASE_URL,
            headers=self._auth_headers(),
            timeout=8.0,
        ) as client:
            if query.registration_number:
                return await self._fetch_by_number(client, query.registration_number)
            return await self._fetch_by_name(client, query.company_name or "")

    # ── Real API helpers ───────────────────────────────────────────────────────

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

    def _demo_data(self, query: CompanyQuery) -> RawCollectorData:
        """Rich demo profile for Cartoon Network Ltd — used in development."""
        logger.info("[CompaniesHouse] Returning demo profile for '%s'.", query.company_name)
        return RawCollectorData(
            source=self.name,
            raw={
                "mock_notice": "Demo data for development — not a real Companies House record.",
                "profile": {
                    "company_name": query.company_name,
                    "company_number": query.registration_number or "00000001",
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

    def _no_data(self, query: CompanyQuery) -> RawCollectorData:
        """Returned for any company we cannot look up without a real API key."""
        logger.info(
            "[CompaniesHouse] No API key — returning null data for '%s' / '%s'.",
            query.company_name, query.registration_number,
        )
        return RawCollectorData(
            source=self.name,
            raw={
                "no_key": True,
                "mock_notice": (
                    "No Companies House API key configured. "
                    "No address, filing, or director data is available."
                ),
                "queried_name": query.company_name,
                "queried_registration_number": query.registration_number,
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