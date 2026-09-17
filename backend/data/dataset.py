"""GASTAT dataset loader and analysis service.

SABIQ_FINAL_DATASET.csv is a curated snapshot of official GASTAT indicators.
This module loads it (no pandas dependency), cleans it, and provides sector
level summaries. The simulation engine uses these summaries to (a) show the
dataset context behind a sector (so users see the observed values) and
(b) reference dataset-derived baselines where directly relevant.

What is *not* done here: aggregate numeric values across different units
(the dataset itself notes this would be statistically invalid), or turn
dataset rows into calibrated model coefficients.
"""

from __future__ import annotations

import csv
import os
from typing import Any, Dict, List, Optional

from .. import config

# Columns we care about.
REQUIRED_COLUMNS = (
    "sector",
    "indicator",
    "verified_value",
    "unit",
    "year",
    "data_status",
    "simulation_ready",
)


class DatasetError(RuntimeError):
    """Raised when the dataset file cannot be loaded."""


def _normalize_record(raw: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Turn one CSV row into a clean internal record (None if unusable)."""

    sector = (raw.get("sector") or "").strip()
    indicator = (raw.get("indicator") or "").strip()
    if not sector or not indicator:
        return None

    data_status = (raw.get("data_status") or "").strip() or "Unknown"
    simulation_ready = (raw.get("simulation_ready") or "").strip().lower() in (
        "yes",
        "true",
        "1",
    )

    verified_value: Optional[float] = None
    verified_value_raw = (raw.get("verified_value_raw") or "").strip()
    verified_value_text = (raw.get("verified_value") or "").strip()
    if verified_value_text:
        try:
            verified_value = float(verified_value_text)
        except ValueError:
            verified_value = None

    return {
        "sector": sector,
        "indicator": indicator,
        "description": (raw.get("description") or "").strip(),
        "verified_value_raw": verified_value_raw,
        "verified_value": verified_value,
        "unit": (raw.get("unit") or "").strip(),
        "year": (raw.get("year") or "").strip(),
        "geography": (raw.get("geography") or "").strip(),
        "data_status": data_status,
        "imputation_method": (raw.get("imputation_method") or "").strip(),
        "imputation_note": (raw.get("imputation_note") or "").strip(),
        "source": (raw.get("source") or "").strip(),
        "dataset": (raw.get("dataset") or "").strip(),
        "source_url": (raw.get("source_url") or "").strip(),
        "simulation_ready": simulation_ready,
        # True only when numeric AND status Verified (used for aggregations).
        "verified": data_status.lower() == "verified" and verified_value is not None,
    }


class DatasetService:
    """Loads the GASTAT CSV once and exposes analysis helpers."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or config.DATASET_PATH
        self.records: List[Dict[str, Any]] = []
        self.error: Optional[str] = None
        try:
            self._load()
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            self.error = f"Failed to load dataset: {exc}"
            self.records = []

    def _load(self) -> None:
        if not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        if not os.path.isfile(self.path):
            raise IsADirectoryError(self.path)

        with open(self.path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise csv.Error(f"Missing columns: {', '.join(missing)}")
            for raw in reader:
                record = _normalize_record(raw)
                if record is not None:
                    self.records.append(record)

        self._deduplicate()

    def _deduplicate(self) -> None:
        """Remove duplicate rows on (sector, indicator, year).

        Prefers the row that carries a verified numeric value and a source URL.
        """
        seen: Dict[tuple, Dict[str, Any]] = {}

        def _quality(rec: Dict[str, Any]) -> int:
            score = 0
            if rec["verified"]:
                score += 2
            if rec["source_url"]:
                score += 1
            return score

        for record in self.records:
            key = (
                record["sector"],
                record["indicator"],
                record["year"],
            )
            current = seen.get(key)
            if current is None or _quality(record) > _quality(current):
                seen[key] = record

        self.records = list(seen.values())

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def sectors(self) -> List[str]:
        return sorted({r["sector"] for r in self.records})

    def indicators_for(self, sector: str) -> List[Dict[str, Any]]:
        return [r for r in self.records if r["sector"] == sector]

    def verified_for(self, sector: str) -> List[Dict[str, Any]]:
        return [r for r in self.records if r["sector"] == sector and r["verified"]]

    def summary_for(self, sector: str) -> Dict[str, Any]:
        """Sector summary.

        Only *percent* unit values are averaged together, because mixing units
        (tons, SAR, beds, ...) is statistically invalid — a constraint the
        dataset itself enforces.
        """
        records = self.indicators_for(sector)
        verified = [r for r in records if r["verified"]]
        percent_values = [
            r["verified_value"] for r in verified if r["unit"].lower() == "percent"
        ]

        notable: List[Dict[str, Any]] = []
        for record in verified:
            notable.append(
                {
                    "indicator": record["indicator"] or record["description"],
                    "value": record["verified_value"],
                    "unit": record["unit"],
                    "year": record["year"],
                    "source": record["source"],
                }
            )
        notable.sort(key=lambda item: item["year"])

        return {
            "sector": sector,
            "indicatorCount": len(records),
            "verifiedIndicatorCount": len(verified),
            "missingIndicatorCount": len(records) - len(verified),
            "simulationReadyCount": sum(
                1 for r in records if r["simulation_ready"] and r["verified"]
            ),
            "meanPercentValue": round(sum(percent_values) / len(percent_values), 2)
            if percent_values
            else None,  # only percent-unit verified values averaged together
            "percentIndicatorCount": len(percent_values),
            "indicators": notable,
        }

    def global_report(self) -> Dict[str, Any]:
        """Summary of the whole dataset (for the documentation endpoint)."""
        verified = [r for r in self.records if r["verified"]]
        ready = [r for r in self.records if r["simulation_ready"] and r["verified"]]
        sources = sorted({r["source"] for r in self.records if r["source"]})
        return {
            "loaded": self.error is None,
            "error": self.error,
            "path": self.path,
            "totalRows": len(self.records),
            "sectorCount": len(self.sectors()),
            "sectors": self.sectors(),
            "verifiedRows": len(verified),
            "simulationReadyRows": len(ready),
            "sources": sources,
        }

    def is_available(self) -> bool:
        return self.error is None and bool(self.records)


# ---------------------------------------------------------------------------
# Module-level cached instance (loaded once per process).
# ---------------------------------------------------------------------------

_dataset_service: Optional[DatasetService] = None


def get_dataset() -> DatasetService:
    """Return the (cached) dataset service."""
    global _dataset_service
    if _dataset_service is None:
        _dataset_service = DatasetService()
    return _dataset_service