"""
collectors/__init__.py — Master registry of all data collectors.

To add a new source: create a DataCollector subclass here, add to ALL_COLLECTORS.
"""
from collectors.adverse_media import AdverseMediaCollector
from collectors.base import DataCollector
from collectors.companies_house import CompaniesHouseCollector

ALL_COLLECTORS: list[DataCollector] = [
    CompaniesHouseCollector(),
    AdverseMediaCollector(),
]


def get_collectors_for_jurisdiction(jurisdiction: str) -> list[DataCollector]:
    return [c for c in ALL_COLLECTORS if c.supports(jurisdiction)]
