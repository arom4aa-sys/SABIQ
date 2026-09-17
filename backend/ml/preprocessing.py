"""Preprocessing pipeline for the ML sector-intelligence model.

The pipeline turns the deduplicated GASTAT records into the design matrix the
clustering model consumes:

1. **Feature extraction** (`features.build_sector_features`) — unit-agnostic
   topical shares + data-quality ratios per sector. No cross-unit averaging is
   performed (matches the constraint already enforced by the dataset loader).
2. **Feature selection / exclusion** — the following columns are metadata and
   never enter the model: ``indicator``, ``description``, ``verified_value``,
   ``unit``, ``year``, ``geography``, ``data_status``, ``imputation_*``,
   ``source``, ``dataset``, ``source_url``, ``simulation_ready``. Sector
   identity is preserved as a separate label array (no leakage).
3. **Standardisation** — every feature is z-scored with a scaler fitted on the
   whole training matrix *before* clustering. This is global standardisation
   (unsupervised), so no label information leaks.
4. **Missing values** — the engineered features are all fractions in [0, 1]
   and are *defined for every sector*, so no NaN imputation is needed for the
   model matrix. Missing dataset rows instead surface as lower
   ``verified_ratio`` / ``simulation_ready_ratio`` — i.e. missingness is
   encoded as a feature rather than silently deleted.
5. **Reproducibility** — a dataset fingerprint (hash of the normalised
   records) links a fitted model to exactly the dataset it was trained on.

No original CSV row is modified or deleted by this module.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

import numpy as np
from sklearn.preprocessing import StandardScaler

from .. import config
from . import features

# Metadata columns that must not influence the model.
METADATA_FIELDS = (
    "sector",
    "indicator",
    "description",
    "verified_value_raw",
    "verified_value",
    "unit",
    "year",
    "geography",
    "data_status",
    "imputation_method",
    "imputation_note",
    "source",
    "dataset",
    "source_url",
)


class PreprocessingError(RuntimeError):
    """Raised when the preprocessing pipeline cannot build a feature matrix."""


def fingerprint_dataset(records: List[Dict]) -> str:
    """Hash the normalised records so models are only reused for the exact,
    unchanged dataset they were trained on."""
    normalised = []
    for record in sorted(records, key=lambda r: json.dumps(r, sort_keys=True)):
        digestable = {
            key: record.get(key)
            for key in (
                "sector",
                "indicator",
                "year",
                "unit",
                "data_status",
                "simulation_ready",
                "verified_value",
            )
        }
        normalised.append(json.dumps(digestable, sort_keys=True))
    payload = "|".join(normalised).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def preprocess(
    records: List[Dict],
    scale: bool = True,
) -> Dict:
    """Build the design matrix, labels and per-sector features.

    Returns a dict with:
    * ``sectors``        — sector labels aligned with the matrix rows,
    * ``feature_names``  — ordered feature names,
    * ``features``       — per-sector feature dicts (raw fractions),
    * ``matrix``         — raw feature matrix (numpy, before scaling),
    * ``matrix_scaled``  — z-scored matrix (when ``scale=True``),
    * ``scaler_mean`` / ``scaler_scale`` — fitted scaler statistics,
    * ``fingerprint``    — dataset fingerprint.
    """
    feature_names = features.sector_feature_names()
    sector_features = features.build_sector_features(records)
    sectors = sorted(sector_features.keys())

    if not sectors:
        raise PreprocessingError("No complete sectors available for the ML model.")

    matrix = np.array(
        [[sector_features[s][col] for col in feature_names] for s in sectors],
        dtype=float,
    )

    scaler_mean: Optional[List[float]] = None
    scaler_scale: Optional[List[float]] = None
    matrix_scaled = matrix
    if scale:
        scaler = StandardScaler().fit(matrix)
        scaler_mean = scaler.mean_.tolist()
        scaler_scale = scaler.scale_.tolist()
        matrix_scaled = scaler.transform(matrix)

    return {
        "sectors": sectors,
        "feature_names": feature_names,
        "features": sector_features,
        "matrix": matrix,
        "matrix_scaled": matrix_scaled,
        "scaler_mean": scaler_mean,
        "scaler_scale": scaler_scale,
        "fingerprint": fingerprint_dataset(records),
        "preprocessing_version": config.ML_PREPROCESSING_VERSION,
    }


def serialize_preprocessing(result: Dict) -> Dict:
    """Turn a preprocess() result into JSON-safe plain data (for persistence)."""
    return {
        "sectors": list(result["sectors"]),
        "feature_names": list(result["feature_names"]),
        "features": {s: dict(v) for s, v in result["features"].items()},
        "matrix_scaled": result["matrix_scaled"].tolist(),
        "scaler_mean": result["scaler_mean"],
        "scaler_scale": result["scaler_scale"],
        "fingerprint": result["fingerprint"],
        "preprocessing_version": result["preprocessing_version"],
    }