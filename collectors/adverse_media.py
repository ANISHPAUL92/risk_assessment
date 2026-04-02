"""collectors/adverse_media.py — Web search for adverse media. Mock fallback if no key."""
from __future__ import annotations

import logging
import os

import httpx

from collectors.base import DataCollector
from types_ import CompanyQuery, RawCollectorData

logger = logging.getLogger(__name__)
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


class AdverseMediaCollector(DataCollector):
    name = "adverse_media"
    supported_jurisdictions = ["*"]

    def __init__(self) -> None:
        self._api_key = os.getenv("BRAVE_SEARCH_API_KEY") or None
        if not self._api_key:
            logger.warning("[AdverseMedia] No Brave API key — using mock data")

    async def collect(self, query: CompanyQuery) -> RawCollectorData:
        company_ref = query.company_name or f"company {query.registration_number}"
        if not self._api_key:
            return self._mock_data(company_ref)

        queries = [
            f'"{company_ref}" scam fraud',
            f'"{company_ref}" regulatory fine penalty',
            f'"{company_ref}" {query.jurisdiction} adverse news',
        ]

        import asyncio
        async with httpx.AsyncClient(timeout=6.0) as client:
            results = await asyncio.gather(
                *[self._search(client, q) for q in queries],
                return_exceptions=True,
            )

        all_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning("[AdverseMedia] query %d failed: %s", i, r)
            else:
                all_results.extend(r)

        return RawCollectorData(
            source=self.name,
            raw={"queries": queries, "results": all_results},
        )

    async def _search(self, client: httpx.AsyncClient, query: str) -> list[dict]:
        res = await client.get(
            BRAVE_URL,
            params={"q": query, "count": 5},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self._api_key or "",
            },
        )
        res.raise_for_status()
        return res.json().get("web", {}).get("results", [])

    def _mock_data(self, company_name: str) -> RawCollectorData:
        return RawCollectorData(
            source=self.name,
            raw={
                "queries": [f'"{company_name}" scam fraud'],
                "results": [{
                    "title": "No significant adverse media found",
                    "url": "https://example.com",
                    "description": f"{company_name} appears in standard business directories with no notable negative coverage.",
                }],
            },
        )
