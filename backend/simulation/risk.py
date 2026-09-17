"""Transparent risk model.

Risk is defined as a weighted combination of independent, 0-100 contributors
where higher is riskier:

    risk = round(SUM(weight_i * contributor_i))

All weights are defined centrally in :mod:`backend.config` and returned in the
API response so the formula is fully auditable. The breakdown exposes each
contributor, its weight and its weighted contribution.
"""

from __future__ import annotations

from .. import config

FACTOR_LABELS = {
    "socialImpact": "Social impact",
    "economicImpact": "Economic impact",
    "servicePressure": "Government service pressure",
    "populationExposure": "Population exposure",
    "duration": "Duration",
    "behaviorChange": "Behavioral change",
    "sectorSensitivity": "Sector sensitivity",
}


def _check_weights() -> None:
    total = sum(config.RISK_WEIGHTS.values())
    if abs(total - 1.0) > 1e-6:  # weights must stay normalised
        raise ValueError(f"Risk weights must sum to 1.0, got {total}")


def compute_risk(contributors: dict) -> dict:
    """Compute the risk score, level and a factor-by-factor breakdown.

    ``contributors`` maps risk keys to 0-100 values (higher == riskier).
    Returns ``{"risk", "riskLevel", "breakdown"}``.
    """
    _check_weights()

    items = []
    for key, weight in config.RISK_WEIGHTS.items():
        value = max(0.0, min(100.0, float(contributors.get(key, 0.0))))
        items.append(
            {
                "key": key,
                "factor": FACTOR_LABELS.get(key, key),
                "value": round(value, 1),
                "weight": weight,
                "contribution": round(value * weight, 1),
            }
        )

    risk = round(sum(item["contribution"] for item in items))
    risk = max(0, min(100, risk))

    level = "Low"
    if risk >= config.RISK_THRESHOLDS["medium"]:
        level = "High"
    elif risk >= config.RISK_THRESHOLDS["low"]:
        level = "Medium"

    return {
        "risk": risk,
        "riskLevel": level,
        "breakdown": {
            "formula": "risk = SUM(factor value * weight); weights sum to 1.0",
            "weights": config.RISK_WEIGHTS,
            "items": items,
        },
    }