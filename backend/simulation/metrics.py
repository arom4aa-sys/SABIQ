"""Metric helpers: normalisation, impact scoring, satisfaction, adoption ramp.

All formulas here are intentionally small and explicit so reviewers can see
exactly how a simulated number is produced. Constants live in
:mod:`backend.config`.
"""

from __future__ import annotations

import math
from typing import Sequence

from .. import config


def clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp *value* into [low, high]."""
    return max(low, min(high, value))


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean (0.0 for an empty sequence)."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def magnitude_to_score(
    magnitude: float,
    sensitivity: float,
    factor: float,
    scale: float = config.IMPACT_SCALE,
) -> float:
    """Map a raw magnitude (a percentage) to the 0-100 impact index.

    ``impact = clip(magnitude * sensitivity * factor * scale)``.
    ``scale`` is the single documented assumption that converts percentage
    magnitudes into the 0-100 index.
    """
    return clip(magnitude * sensitivity * factor * scale)


def adoption_ramp(month: int, rate_months: float) -> float:
    """Fraction of full impact reached by month ``month``.

    An exponential adoption curve: ``1 - exp(-month / rate_months)``.
    The rate comes from the decision profile (digital roll-outs adopt faster
    than reorganisations).
    """
    if rate_months <= 0:
        return 1.0
    return 1.0 - math.exp(-month / rate_months)


def satisfaction_from_impacts(
    baseline_satisfaction: float,
    social_impact: float,
    service_impact: float,
    economic_impact: float,
    weights: dict[str, float] | None = None,
    floor: float = config.SATISFACTION_FLOOR,
) -> float:
    """Satisfaction after applying weighted impact penalties.

    ``satisfaction = clip(baseline - w_social*social - w_service*service
    - w_econ*economic, floor, 100)``
    """
    weights = weights or config.SATISFACTION_WEIGHTS
    penalty = (
        weights["social"] * social_impact
        + weights["service"] * service_impact
        + weights["economic"] * economic_impact
    )
    return clip(baseline_satisfaction - penalty, floor, 100.0)


def normalize_duration(duration: int) -> float:
    """Duration contributor for the risk model (0-100)."""
    return clip(
        duration * 100.0 / float(config.MAX_DURATION_MONTHS),
        low=0.0,
        high=100.0,
    )


def sector_sensitivity_index(profile: dict) -> float:
    """Aggregate the sector sensitivity profile onto a 0-100 index.

    Average of the five sensitivities divided by the maximum plausible
    sensitivity (1.5) — documented as a weight-neutral normalisation.
    """
    sensitivities = [
        profile["social_sensitivity"],
        profile["economic_sensitivity"],
        profile["service_sensitivity"],
        profile["behavioral_sensitivity"],
        profile["business_sensitivity"],
    ]
    return clip(mean(sensitivities) / 1.5 * 100.0, 0.0, 100.0)