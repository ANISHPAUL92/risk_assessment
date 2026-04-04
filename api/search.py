"""
api/search.py — Company name search endpoint.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query

from collectors.companies_house import CompaniesHouseCollector, parse_company_matches
from config import SEARCH_TIMEOUT_SECS
from types_ import CompanyQuery

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search")
async def search_companies(
    q: str = Query(..., min_length=2, max_length=200),
    jurisdiction: str = Query("GB", min_length=2, max_length=10),
) -> dict:
    """
    Returns candidate company matches for a name query.
    """
    jurisdiction = "".join(c for c in jurisdiction.upper() if c.isalpha())[:2]

    collector = CompaniesHouseCollector()
    try:
        data = await asyncio.wait_for(
            collector.collect(CompanyQuery(company_name=q, jurisdiction=jurisdiction)),
            timeout=SEARCH_TIMEOUT_SECS,
        )
        raw = data.raw if isinstance(data.raw, dict) else {}
        matches = parse_company_matches({"search_results": raw.get("search_results", {})})
        return {"matches": [m.model_dump() for m in matches]}

    except asyncio.TimeoutError:
        logger.warning("[search] timed out after %ss for query '%s'", SEARCH_TIMEOUT_SECS, q)
        return {"matches": [], "error": "Search timed out — try again"}

    except Exception as e:
        logger.error("[search] unexpected error: %s", e)
        return {"matches": [], "error": "Search unavailable"}
