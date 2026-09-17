"""ML / sector-intelligence API routes.

Exposes the fitted unsupervised model as plain JSON. No filesystem paths,
internal Python objects or stack traces are ever returned.

Endpoints
---------
* ``GET /api/ml/status``          — availability, versions, cluster count.
* ``GET /api/ml/sectors``         — UI sectors (with ML info) + dataset sectors.
* ``GET /api/ml/sector-profile/<sector>`` — full insight for one sector.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Blueprint, jsonify

from .. import config
from ..data.dataset import get_dataset
from ..ml import is_ml_available
from ..ml.inference import ml_insight_for
from ..ml.sector_model import get_sector_model

ml_bp = Blueprint("ml", __name__)


def _error(code: str, message: str, status: int = 400):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status


def _model_or_none():
    """Fitted cached model when ML is enabled, else None."""
    model = get_sector_model()
    if model is None or not model.is_fitted:
        return None
    return model


@ml_bp.get("/api/ml/status")
def ml_status():
    """Model availability, method and cluster-quality summary."""
    model = _model_or_none()
    dataset = get_dataset()
    available = model is not None
    return jsonify(
        {
            "success": True,
            "enabled": bool(config.ML_ENABLED),
            "available": available,
            "method": model.quality()["method"] if available else None,
            "modelVersion": config.ML_MODEL_VERSION,
            "preprocessingVersion": config.ML_PREPROCESSING_VERSION,
            "clusterCount": model.k if available else None,
            "randomState": config.ML_RANDOM_STATE,
            "methodology": config.ML_METHODOLOGY_NOTE,
            "datasetFingerprint": model.fingerprint if available else None,
            "datasetLoaded": dataset.is_available(),
            "datasetSectorCount": len(model.sectors) if available else 0,
            "uiSectorCount": len(config.SECTOR_PROFILES),
            "quality": model.quality() if available else {},
            "note": config.ML_METHODOLOGY_NOTE,
        }
    )


@ml_bp.get("/api/ml/sectors")
def ml_sectors():
    """List UI sectors (with ML-derived info) and GASTAT dataset sectors."""
    if not config.ML_ENABLED or not is_ml_available():
        return _error(
            "ML_UNAVAILABLE",
            "ML sector intelligence is not available.",
            status=503,
        )

    model = get_sector_model()

    dataset_sectors = []
    for sector in model.sectors:
        insight = model.insight_for_dataset_sector(sector)
        dataset_sectors.append(
            {
                "sector": sector,
                "cluster": insight["cluster"],
                "clusterLabel": insight["clusterLabel"],
                "sectorProfile": insight["sectorProfile"],
            }
        )

    ui_sectors: list = []
    for sector in sorted(config.SECTOR_PROFILES):
        insight = ml_insight_for(sector)
        if insight is None:
            ui_sectors.append({"sector": sector, "available": False})
            continue
        ui_sectors.append(
            {
                "sector": sector,
                "available": True,
                "cluster": insight["cluster"],
                "clusterLabel": insight["clusterLabel"],
                "multipliers": insight["multipliers"],
                "sourceSectors": insight["sourceSectors"],
                "similarSectors": insight["similarSectors"],
                "keyFeatures": insight["keyFeatures"],
            }
        )

    return jsonify(
        {
            "success": True,
            "method": model.quality()["method"],
            "quality": model.quality(),
            "datasetSectors": dataset_sectors,
            "uiSectors": ui_sectors,
        }
    )


@ml_bp.get("/api/ml/sector-profile/<path:sector>")
def ml_sector_profile(sector: str):
    """Full ML insight for a UI sector (or a GASTAT dataset sector)."""
    if not config.ML_ENABLED:
        return _error(
            "ML_DISABLED",
            "ML sector intelligence is disabled.",
            status=503,
        )

    model = _model_or_none()
    if model is None:
        return _error(
            "ML_UNAVAILABLE",
            "ML sector intelligence is not available.",
            status=503,
        )

    name = (sector or "").strip()

    insight: Optional[Dict[str, Any]] = None
    if name in config.SECTOR_PROFILES:
        insight = ml_insight_for(name)
    elif model.is_dataset_sector(name):
        insight = model.insight_for_dataset_sector(name)

    if insight is None:
        return _error(
            "INVALID_SECTOR",
            f"Unknown sector '{name}'. Use GET /api/ml/sectors to list valid sectors.",
            status=404,
        )

    return jsonify({"success": True, "sector": name, "mlInsights": insight})