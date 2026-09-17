"""Inference layer between the fitted sector model and the simulation engine.

The simulation works on **UI sectors** (e.g. "Healthcare"), while the ML model
is fitted on **GASTAT dataset sectors**. A UI sector maps to one or more
dataset sectors via ``config.SECTOR_PROFILES[sector]["dataset_sectors"]``.

This module aggregates the per-dataset-sector intelligence into one UI-sector
insight object, weighting each dataset sector by the number of its *verified*
indicators (evidence weighting). The result is plain JSON-safe data — internal
Python objects are never exposed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import config
from .explain import build_ml_explanation
from .sector_model import _multipliers_from_profile, get_sector_model

_DIM_ORDER = list(config.ML_PROFILE_DIMENSIONS)


def _dataset_sectors_for_ui(ui_sector: str) -> List[str]:
    profile = config.SECTOR_PROFILES.get(ui_sector)
    if not profile:
        return []
    return list(profile.get("dataset_sectors") or [])


def _verified_weights(records) -> Dict[str, int]:
    """Verified-indicator counts per dataset sector (evidence weights)."""
    weights: Dict[str, int] = {}
    for record in records:
        if record["verified"]:
            weights[record["sector"]] = weights.get(record["sector"], 0) + 1
    return weights


def _aggregate_profile(
    insights: List[Dict[str, Any]], weights: Dict[str, float]
) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        total = len(insights)
        weights = {ins["source"]: 1.0 for ins in insights}
    profile: Dict[str, float] = {}
    for dim in _DIM_ORDER:
        profile[dim] = round(
            sum(insights[i]["sectorProfile"][dim] * weights.get(insights[i]["source"], 0.0)
                for i in range(len(insights))) / total,
            4,
        )
    profile["verifiability"] = round(
        sum(insights[i]["sectorProfile"]["verifiability"]
            * weights.get(insights[i]["source"], 0.0)
            for i in range(len(insights))) / total,
        4,
    )
    profile["other"] = round(
        sum(insights[i]["sectorProfile"].get("other", 0.0)
            * weights.get(insights[i]["source"], 0.0)
            for i in range(len(insights))) / total,
        4,
    )
    return profile


def _aggregate_similar(
    insights: List[Dict[str, Any]],
    weights: Dict[str, float],
    exclude: List[str],
) -> List[Dict[str, Any]]:
    scores: Dict[str, float] = {}
    total = sum(weights.values()) or len(insights)
    for ins in insights:
        weight = weights.get(ins["source"], 1.0)
        for item in ins["similarSectors"]:
            name = item["sector"]
            if name in exclude:
                continue
            scores[name] = scores.get(name, 0.0) + item["similarity"] * weight
    ranked = sorted(
        (
            {"sector": name, "similarity": round(score / total, 4)}
            for name, score in scores.items()
        ),
        key=lambda item: item["similarity"],
        reverse=True,
    )
    return ranked[: config.ML_SIMILAR_SECTOR_COUNT]


def _aggregate_key_features(profile: Dict[str, float], model) -> List[Dict[str, Any]]:
    avg = model.global_profile_mean()
    deviations = [(dim, profile[dim], avg.get(dim, 0.0)) for dim in _DIM_ORDER]
    deviations.sort(key=lambda item: abs(item[1] - item[2]), reverse=True)
    return [
        {
            "feature": dim,
            "share": round(value, 4),
            "datasetAverage": round(avg_value, 4),
            "deviation": round(value - avg_value, 4),
        }
        for dim, value, avg_value in deviations[:3]
    ]


def ml_insight_for(ui_sector: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the serializable ML insight for a UI sector (or None).

    Works for every sector known to ``config.SECTOR_PROFILES``. Unknown
    sectors return ``None`` so callers can degrade gracefully.
    """
    if not ui_sector or not config.ML_ENABLED:
        return None
    model = get_sector_model()
    if model is None or not model.is_fitted:
        return None

    dataset_sectors = _dataset_sectors_for_ui(ui_sector)
    if not dataset_sectors:
        return None

    insights = [model.insight_for_dataset_sector(s) for s in dataset_sectors]
    insights = [i for i in insights if i is not None]
    if not insights:
        return None

    weights = _verified_weights(get_sector_model_dataset_records())
    weights = {
        s: float(weights.get(s, 0) or 1.0)
        for s in dataset_sectors
    }

    profile = _aggregate_profile(insights, weights)
    dim_stats = model.dimension_stats()
    multipliers = _multipliers_from_profile(
        profile, dim_stats["min"], dim_stats["max"]
    )

    parts = {
        "enabled": True,
        "method": model.quality()["method"],
        "cluster": _dominant_cluster(insights, weights),
        "clusterLabel": _dominant_cluster_label(model, insights, weights),
        "sectorProfile": profile,
        "multipliers": multipliers,
        "similarSectors": _aggregate_similar(
            insights, weights, exclude=set(dataset_sectors)
        ),
        "keyFeatures": _aggregate_key_features(profile, model),
        "quality": model.quality(),
        "sourceSectors": dataset_sectors,
    }
    parts["explanation"] = build_ml_explanation(ui_sector, parts)
    return parts


def _dominant_cluster(
    insights: List[Dict[str, Any]], weights: Dict[str, float]
) -> int:
    total = sum(weights.values()) or 1.0
    cluster_score: Dict[int, float] = {}
    for ins in insights:
        w = weights.get(ins["source"], 1.0)
        cluster_score[ins["cluster"]] = cluster_score.get(ins["cluster"], 0.0) + w
    best = max(sorted(cluster_score), key=lambda c: cluster_score[c])
    return best


def _dominant_cluster_label(model, insights: List[Dict[str, Any]], weights) -> str:
    cluster = _dominant_cluster(insights, weights)
    return getattr(model, "_cluster_labels", {}).get(cluster, "")


_records_cache: Optional[List[Dict]] = None


def get_sector_model_dataset_records() -> List[Dict]:
    """Cached raw records used for evidence weighting (avoid re-reads)."""
    global _records_cache
    if _records_cache is None:
        from ..data.dataset import get_dataset

        dataset = get_dataset()
        _records_cache = list(dataset.records) if dataset else []
    return _records_cache