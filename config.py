"""
config.py — Central configuration.

All constants and environment-derived settings live here.
Nothing else should read os.getenv() directly.

To change a timeout: edit it here. One place, picked up everywhere.
"""
from __future__ import annotations

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

# ── API keys ───────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
COMPANIES_HOUSE_API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY", "")
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")

# ── LLM settings ──────────────────────────────────────────────────────────────

LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1500"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# ── Timeouts (seconds) ────────────────────────────────────────────────────────

# Hard ceiling for the entire assessment (collectors + LLM combined).
# Matches the product requirement of "data within 10 seconds in most cases".
ASSESSMENT_TIMEOUT_SECS: float = float(os.getenv("ASSESSMENT_TIMEOUT_SECS", "10"))

# Each data source gets this long independently before being marked as failed.
# Must be less than ASSESSMENT_TIMEOUT_SECS.
COLLECTOR_TIMEOUT_SECS: float = float(os.getenv("COLLECTOR_TIMEOUT_SECS", "6"))

# Claude structuring step. Sits inside the overall ceiling.
LLM_TIMEOUT_SECS: float = float(os.getenv("LLM_TIMEOUT_SECS", "8"))

# /api/search is expected to be faster than a full assessment.
SEARCH_TIMEOUT_SECS: float = float(os.getenv("SEARCH_TIMEOUT_SECS", "5"))
