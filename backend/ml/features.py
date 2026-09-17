"""Dataset feature extraction for the ML layer.

The GASTAT dataset rows carry *heterogeneous units* (tons, SAR, beds,
minutes, ...). The dataset itself states that averaging values across units is
statistically invalid, so the ML layer does **not** compare raw indicator
values across sectors.

Instead, each sector is described by a **unit-agnostic feature vector** that is
derived entirely from real dataset fields:

1. **Topical composition** — the fraction of a sector's indicators whose text
   (sector + indicator + description) tag onto economic / social / service /
   digital / environment / other dimensions. This is a text-derived signature
   of *what* a sector reports on, not a fake numeric label.
2. **Data quality** — fraction of indicators marked ``Verified``,
   ``simulation_ready`` and percent-unit. These measure how usable the sector's
   rows are for evidence weighting.
"""

from __future__ import annotations

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Topical keyword tags
# ---------------------------------------------------------------------------
# Each keyword is a lowercase substring test against
# "sector + indicator + description". An indicator may tag onto several
# dimensions; its mass (1.0) is split equally among the dimensions it matches,
# so no unit-agnostic value is invented and every indicator contributes
# exactly 1.0 of tagging mass.
TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "economic": [
        "gdp",
        "revenue",
        "expenditure",
        "compensation",
        "inflation",
        "price",
        "export",
        "import",
        "trade",
        "enterprise",
        "turnover",
        "mineral",
        "mining",
        "manufacturing",
        "growth",
        "economy",
        "establishment",
        "business",
    ],
    "social": [
        "education",
        "school",
        "student",
        "satisfaction",
        "health",
        "healthcare",
        "dentist",
        "nurse",
        "physician",
        "pharmac",
        "hospital",
        "bed",
        "household",
        "dwelling",
        "housing",
        "population",
        "demograph",
        "people",
        "labor",
        "labour",
        "employment",
        "unemployment",
        "worker",
    ],
    "service": [
        "transport",
        "logistics",
        "freight",
        "warehouse",
        "delivery",
        "tourism",
        "hajj",
        "license",
        "licensed",
        "centre",
        "center",
        "driver",
        "order",
        "service",
        "utiliz",
    ],
    "digital": ["ict", "digital", "technology"],
    "environment": [
        "agriculture",
        "crop",
        "vegetable",
        "date production",
        "palm",
        "organic",
        "energy",
        "solar",
        "renewable",
        "water",
        "sanitation",
        "electricity",
        "consumption",
        "environment",
        "gas",
    ],
}

# Order of the topical dimensions in feature vectors and profiles.
DIMENSIONS = (
    "economic",
    "social",
    "service",
    "digital",
    "environment",
)


# Precompiled lowercase keyword lists (sorted for determinism).
_TOPIC_TERMS = {
    dim: sorted(keywords) for dim, keywords in TOPIC_KEYWORDS.items()
}


def tag_indicator(text: str) -> Dict[str, float]:
    """Return {dimension: fraction} tags for one indicator's text.

    Mass (1.0) is split equally among every dimension the text matches; when
    nothing matches the indicator is tagged ``other``.
    """
    haystack = " ".join(str(text).lower().split())
    matched = [dim for dim in DIMENSIONS if any(t in haystack for t in _TOPIC_TERMS[dim])]
    if not matched:
        return {"other": 1.0}
    fraction = 1.0 / len(matched)
    return {dim: fraction for dim in matched}


def sector_feature_names() -> List[str]:
    """Stable, ordered list of feature names (reproducibility contract)."""
    return [
        "share_economic",
        "share_social",
        "share_service",
        "share_digital",
        "share_environment",
        "share_other",
        "verified_ratio",
        "simulation_ready_ratio",
        "percent_unit_ratio",
    ]


def sectors_from_records(records: List[Dict[str, Any]]) -> List[str]:
    """Sorted unique sector names present in the (deduplicated) records."""
    return sorted({r["sector"] for r in records})


def build_sector_features(
    records: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    """Compute the unit-agnostic feature vector for every sector.

    Returns ``{sector: {feature: value}}``. Every feature is a fraction in
    [0, 1] so no cross-unit aggregation is ever performed.
    """
    sectors = sectors_from_records(records)
    result: Dict[str, Dict[str, float]] = {}

    for sector in sectors:
        rows = [r for r in records if r["sector"] == sector]
        n = len(rows)
        if n == 0:
            continue

        verified_n = sum(1 for r in rows if r["verified"])
        ready_n = sum(1 for r in rows if r["simulation_ready"] and r["verified"])
        percent_n = sum(1 for r in rows if (r["unit"] or "").lower() == "percent")

        topic_totals = {"economic": 0.0, "social": 0.0, "service": 0.0,
                        "digital": 0.0, "environment": 0.0, "other": 0.0}
        for row in rows:
            text = " ".join(
                str(part)
                for part in (row["sector"], row["indicator"], row["description"])
                if part
            )
            for dim, mass in tag_indicator(text).items():
                topic_totals[dim] += mass

        other_total = max(0.0, min(1.0, topic_totals["other"] / n))
        # Guard against floating-point drift pushing the total past 1.0.
        topical = {
            f"share_{dim}": round(max(0.0, min(1.0, topic_totals[dim] / n)), 6)
            for dim in DIMENSIONS
        }
        topical_sum = sum(topical.values())
        if topical_sum + other_total > 1.0:
            other_total = max(0.0, 1.0 - topical_sum)

        result[sector] = {
            "share_economic": topical["share_economic"],
            "share_social": topical["share_social"],
            "share_service": topical["share_service"],
            "share_digital": topical["share_digital"],
            "share_environment": topical["share_environment"],
            "share_other": round(other_total, 6),
            "verified_ratio": round(verified_n / n, 6),
            "simulation_ready_ratio": round(ready_n / n, 6),
            "percent_unit_ratio": round(percent_n / n, 6),
        }

    return result