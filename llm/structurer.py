"""
llm/structurer.py

Uses Claude (via OpenRouter) to transform raw collector data into a
validated CompanyRiskProfile.

Guardrails:
  1. Token budget cap    (LLM_MAX_TOKENS, default 1500)
  2. temperature=0       for reproducibility
  3. Pydantic validation on every response
  4. Corrective prompting retry — tells the model exactly what was wrong
  5. Typed fallback profile if all retries exhausted
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone

import anthropic
from pydantic import ValidationError

from scoring import calculate_completeness
from types_ import (
    AdverseMedia,
    CompanyQuery,
    CompanyRiskProfile,
    FilingHistory,
    RawCollectorData,
    RiskLevel,
    RiskSignal,
    Severity,
)

logger = logging.getLogger(__name__)

# ── Config — bump PROMPT_VERSION whenever the prompt text changes ──────────────
PROMPT_VERSION = "v1.2"
from config import ANTHROPIC_API_KEY, LLM_MODEL, LLM_MAX_TOKENS, LLM_MAX_RETRIES

MODEL = LLM_MODEL
MAX_TOKENS = LLM_MAX_TOKENS
MAX_RETRIES = LLM_MAX_RETRIES

_client = anthropic.Anthropic(
    api_key=ANTHROPIC_API_KEY,
    base_url="https://openrouter.ai/api",
    max_retries=0,
)


async def structure_with_llm(
    query: CompanyQuery,
    collected_data: list[RawCollectorData],
) -> CompanyRiskProfile:
    """Structure raw collector data into a validated CompanyRiskProfile."""
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(query, collected_data)
    last_error: str | None = None

    for attempt in range(MAX_RETRIES + 1):
        messages = _build_messages(user_prompt, last_error, attempt)
        try:
            response = _client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=0,
                top_p=1,
                system=system_prompt,
                messages=messages,
            )
        except anthropic.APIError as e:
            logger.error("[LLM] API error attempt %d: %s", attempt + 1, e)
            last_error = f"API error: {e}"
            continue

        raw_text = _extract_text(response)
        parsed = _try_parse_json(raw_text)

        if parsed is None:
            last_error = "Response was not valid JSON"
            logger.warning("[LLM] attempt %d: %s", attempt + 1, last_error)
            continue

        # Inject metadata — LLM must not set these
        parsed["assessed_at"] = datetime.now(timezone.utc).isoformat()
        parsed["prompt_version"] = PROMPT_VERSION
        parsed["data_sources_used"] = [d.source for d in collected_data]
        parsed["completeness_score"] = calculate_completeness(parsed)

        try:
            profile = CompanyRiskProfile.model_validate(parsed)
            logger.info("[LLM] success attempt %d completeness=%.2f", attempt + 1, profile.completeness_score)
            return profile
        except ValidationError as e:
            last_error = f"Schema error: {e.errors()[0]['msg']}"
            logger.warning("[LLM] attempt %d: %s", attempt + 1, last_error)

    logger.error("[LLM] all retries exhausted — returning fallback")
    return _build_fallback_profile(query, collected_data)


# ── Prompt helpers ─────────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    return """\
You are a financial compliance analyst. Extract and structure company risk \
information from raw data into a precise JSON schema.

RULES:
- Respond ONLY with a single valid JSON object. No markdown, no prose, no backticks.
- Never fabricate data. Use null for unknown fields.
- overall_risk_level must be one of: "low", "medium", "high", "unknown"
- severity values must be one of: "low", "medium", "high"
- Be conservative: when risk is ambiguous, prefer "medium" over "low".
- risk_signals must reflect actual evidence from the provided data.
- Do NOT include: assessed_at, prompt_version, data_sources_used, completeness_score.

OUTPUT SCHEMA:
{
  "canonical_name": string | null,
  "registration_number": string | null,
  "jurisdiction": string,
  "incorporation_date": string | null,
  "company_status": string | null,
  "company_type": string | null,
  "registered_address": string | null,
  "sic_codes": string[],
  "directors": [{"name": string, "appointed_on": string|null, "resigned_on": string|null, "other_directorships_count": number|null, "country_of_residence": string|null}],
  "filing_history": {"total_filings": number|null, "last_filed_date": string|null, "has_overdue_filings": boolean|null, "years_of_history": number|null},
  "adverse_media": {"has_adverse_media": boolean|null, "scam_mentions": number|null, "regulatory_actions": number|null, "summary": string|null, "sources": string[]},
  "risk_signals": [{"signal": string, "severity": "low"|"medium"|"high", "detail": string}],
  "overall_risk_level": "low"|"medium"|"high"|"unknown",
  "risk_summary": string | null
}"""


def _build_user_prompt(query: CompanyQuery, collected_data: list[RawCollectorData]) -> str:
    sections = "\n\n".join(
        f"=== SOURCE: {d.source} ===\n{json.dumps(d.raw, indent=2)}"
        for d in collected_data
    )
    return f"""\
Analyse this company and populate the JSON schema.

QUERY:
- Name: {query.company_name or '(not provided)'}
- Registration: {query.registration_number or '(not provided)'}
- Jurisdiction: {query.jurisdiction}

RAW DATA:
{sections}

Respond with a single JSON object only."""


def _build_messages(user_prompt: str, last_error: str | None, attempt: int) -> list[dict]:
    if attempt == 0 or not last_error:
        return [{"role": "user", "content": user_prompt}]
    return [
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": "I'll analyse the data and provide the structured JSON."},
        {"role": "user", "content": f"Your previous response had an error: {last_error}. Respond ONLY with valid JSON matching the schema. No other text."},
    ]


def _extract_text(response: anthropic.types.Message) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


def _try_parse_json(text: str) -> dict | None:
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        result = json.loads(cleaned)
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        return None


def _build_fallback_profile(
    query: CompanyQuery,
    collected_data: list[RawCollectorData],
) -> CompanyRiskProfile:
    return CompanyRiskProfile(
        canonical_name=query.company_name,
        registration_number=query.registration_number,
        jurisdiction=query.jurisdiction,
        filing_history=FilingHistory(),
        adverse_media=AdverseMedia(summary="Assessment incomplete — LLM structuring failed."),
        risk_signals=[RiskSignal(signal="assessment_failed", severity=Severity.HIGH, detail="Could not structure risk profile after maximum retries.")],
        overall_risk_level=RiskLevel.UNKNOWN,
        risk_summary="Assessment incomplete due to a processing error.",
        data_sources_used=[d.source for d in collected_data],
        completeness_score=0.0,
        prompt_version=PROMPT_VERSION,
    )