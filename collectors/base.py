"""collectors/base.py — DataCollector interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types_ import CompanyQuery, RawCollectorData


class DataCollector(ABC):
    name: str
    supported_jurisdictions: list[str]

    @abstractmethod
    async def collect(self, query: "CompanyQuery") -> "RawCollectorData":
        ...

    def supports(self, jurisdiction: str) -> bool:
        return (
            "*" in self.supported_jurisdictions
            or jurisdiction.upper() in self.supported_jurisdictions
        )
