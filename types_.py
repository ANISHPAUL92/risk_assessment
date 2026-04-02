"""
types_.py — All shared Pydantic models.

Lives at the root of risk_assessment/ so every module can import it simply:
    from types_ import CompanyQuery, CompanyRiskProfile, ...
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ── Input ──────────────────────────────────────────────────────────────────────

class CompanyQuery(BaseModel):
    company_name: str | None = None
    registration_number: str | None = None
    jurisdiction: str = "GB"

    @model_validator(mode="after")
    def at_least_one_identifier(self) -> "CompanyQuery":
        if not self.company_name and not self.registration_number:
            raise ValueError("Provide company_name or registration_number")
        return self


# ── Risk profile sub-models ────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Director(BaseModel):
    name: str
    appointed_on: str | None = None
    resigned_on: str | None = None
    other_directorships_count: int | None = None
    country_of_residence: str | None = None


class FilingHistory(BaseModel):
    total_filings: int | None = None
    last_filed_date: str | None = None
    has_overdue_filings: bool | None = None
    years_of_history: float | None = None


class AdverseMedia(BaseModel):
    has_adverse_media: bool | None = None
    scam_mentions: int | None = None
    regulatory_actions: int | None = None
    summary: str | None = None
    sources: list[str] = Field(default_factory=list)


class RiskSignal(BaseModel):
    signal: str
    severity: Severity
    detail: str


class CompanyRiskProfile(BaseModel):
    """Canonical output schema — every field nullable so partial data never breaks."""
    canonical_name: str | None = None
    registration_number: str | None = None
    jurisdiction: str
    incorporation_date: str | None = None
    company_status: str | None = None
    company_type: str | None = None
    registered_address: str | None = None
    sic_codes: list[str] = Field(default_factory=list)
    directors: list[Director] = Field(default_factory=list)
    filing_history: FilingHistory = Field(default_factory=FilingHistory)
    adverse_media: AdverseMedia = Field(default_factory=AdverseMedia)
    risk_signals: list[RiskSignal] = Field(default_factory=list)
    overall_risk_level: RiskLevel = RiskLevel.UNKNOWN
    risk_summary: str | None = None
    data_sources_used: list[str] = Field(default_factory=list)
    completeness_score: float = Field(0.0, ge=0.0, le=1.0)
    assessed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    prompt_version: str = "unknown"


# ── Streaming event types ──────────────────────────────────────────────────────

class CollectorStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class RawCollectorData(BaseModel):
    source: str
    raw: Any


class CollectorUpdate(BaseModel):
    collector: str
    status: CollectorStatus
    data: RawCollectorData | None = None
    error: str | None = None


class CompanyMatch(BaseModel):
    company_name: str
    registration_number: str
    company_status: str
    incorporation_date: str | None = None
    address: str | None = None
