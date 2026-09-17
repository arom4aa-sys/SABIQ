"""Sector intelligence model (unsupervised clustering + profiles).

The model maps each GASTAT sector to:

* a **cluster** (KMeans run on the standardised, unit-agnostic feature matrix),
* a **profile** (topical shares + verifiability),
* **bounded sensitivity multipliers** derived from the profile,
* a **similarity ranking** against the other sectors,
* **key features** (largest deviations from the dataset average).

Method choice
-------------
* Dataset size: 17 fully-featured sectors → small-n setting. KMeans is used
  because it is deterministic (fixed ``random_state``), interpretable via
  cluster means, and cheap to evaluate with the silhouette index.
* Cluster count is **not** arbitrary: ``k`` is chosen by the best silhouette
  score over ``config.ML_K_RANGE``, with a fixed seed so the choice is
  reproducible.
* The silhouette score is reported as *cluster quality*. It is not an accuracy
  metric, and it is never described as prediction accuracy (no ground-truth
  target exists).

Scientific boundary: the clustering identifies patterns and similarities in
the packaged dataset only. It does not predict future decision outcomes.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from .. import config
from ..data.dataset import get_dataset
from . import preprocessing

ML_METHOD = "KMeans"
METHOD_NOTE = (
    "Unsupervised clustering on dataset-derived sector features. The output is "
    "a data-informed sector profile, not a prediction of policy outcomes."
)

_DIM_ORDER = list(config.ML_PROFILE_DIMENSIONS)


def _profile_from_features(features: Dict[str, float]) -> Dict[str, float]:
    """Topical shares + verifiability used by the profile and multipliers."""
    return {
        dim: float(features[f"share_{dim}"])
        for dim in _DIM_ORDER
    } | {
        "verifiability": float(features["verified_ratio"]),
        "other": float(features["share_other"]),
    }


def _normalize_share(value: float, low: float, high: float) -> float:
    """Min-max normalise a profile share against the dataset's sector range."""
    if high - low < 1e-9:
        return 0.5  # no spread in this dimension across sectors
    return (value - low) / (high - low)


def _multipliers_from_profile(
    profile: Dict[str, float],
    dim_min: Dict[str, float],
    dim_max: Dict[str, float],
) -> Dict[str, float]:
    """Bounded sensitivity multipliers derived from a sector profile.

    Each profile dimension is min-max normalised against the dataset range,
    then each sensitivity follows the strongest matching dimension:
    ``multiplier = clamp(1 + verifiability * strength * (norm − 0.5))``.
    ``verifiability`` is the share of the sector's dataset rows that are
    Verified, so sparse/unverified sectors are pushed closer to 1.0.
    """
    strength = config.ML_MULTIPLIER_STRENGTH
    lo, hi = config.ML_MULTIPLIER_BOUNDS
    verifiability = profile["verifiability"]
    normalized = {
        dim: _normalize_share(profile[dim], dim_min.get(dim, 0.0), dim_max.get(dim, 1.0))
        for dim in _DIM_ORDER
    }
    multipliers: Dict[str, float] = {}
    for sensitivity, dims in config.ML_SENSITIVITY_DIMENSIONS.items():
        blend = max(normalized[d] for d in dims)
        raw = 1.0 + verifiability * strength * (blend - 0.5)
        multipliers[sensitivity] = round(max(lo, min(hi, raw)), 4)
    return multipliers


class SectorModel:
    """Fitted, deterministic sector-intelligence model."""

    def __init__(self, preprocessed: Dict[str, Any]) -> None:
        self.preprocessing_version = preprocessed["preprocessing_version"]
        self.model_version = config.ML_MODEL_VERSION
        self.random_state = config.ML_RANDOM_STATE
        self.feature_names: List[str] = list(preprocessed["feature_names"])
        self.sectors: List[str] = list(preprocessed["sectors"])
        self.features: Dict[str, Dict[str, float]] = dict(preprocessed["features"])
        self.matrix_scaled = np.asarray(preprocessed["matrix_scaled"], dtype=float)
        self.scaler_mean = preprocessed["scaler_mean"]
        self.scaler_scale = preprocessed["scaler_scale"]
        self.fingerprint = preprocessed["fingerprint"]

        self.k: Optional[int] = None
        self.silhouette: Optional[float] = None
        self.labels: Optional[List[int]] = None
        self.cluster_means_scaled: Optional[np.ndarray] = None

        # Derived lookups (populated by fit()).
        self._profiles: Dict[str, Dict[str, float]] = {}
        self._sector_cluster: Dict[str, int] = {}
        self._cluster_labels: Dict[int, str] = {}
        self._similarity: Dict[str, List[Dict[str, Any]]] = {}
        self._global_share_mean: Dict[str, float] = {}
        self._dim_min: Dict[str, float] = {}
        self._dim_max: Dict[str, float] = {}
        self._key_features: Dict[str, List[Dict[str, Any]]] = {}
        self._multipliers: Dict[str, Dict[str, float]] = {}

    # ------------------------------------------------------------------
    # Fitting
    # ------------------------------------------------------------------

    @property
    def is_fitted(self) -> bool:
        return self.k is not None and self.labels is not None

    def _select_k(self) -> None:
        """Pick k by the best silhouette over a documented candidate range.

        The range is ``config.ML_K_RANGE`` capped at ``floor(sqrt(n))`` and at
        ``n - 1``. Capping at ``sqrt(n)`` is the standard small-n guard against
        over-fragmenting the data (silhouette tends to rise with k for tiny
        samples), so the choice is principled rather than arbitrary.
        """
        X = self.matrix_scaled
        n = X.shape[0]
        k_min, k_max = config.ML_K_RANGE
        k_max = max(k_min, min(k_max, int(math.sqrt(n)), n - 1))

        best_k: Optional[int] = None
        best_score = -math.inf
        best_labels: Optional[np.ndarray] = None

        for k in range(k_min, k_max + 1):
            kmeans = KMeans(
                n_clusters=k,
                random_state=self.random_state,
                n_init=10,
            )
            labels = kmeans.fit_predict(X)
            if len(set(labels.tolist())) < 2:
                continue  # degenerate split; cannot score
            try:
                score = float(silhouette_score(X, labels))
            except ValueError:
                continue
            if score > best_score:
                best_score = score
                best_k = k
                best_labels = labels

        if best_k is None:
            best_k = max(k_min, min(2, n - 1))
            kmeans = KMeans(n_clusters=best_k, random_state=self.random_state, n_init=10)
            best_labels = kmeans.fit_predict(X)
            best_score = float("nan")

        self.k = best_k
        self.labels = [int(i) for i in best_labels.tolist()]

        # Final fit for cluster means / deterministic artefacts.
        kmeans = KMeans(n_clusters=self.k, random_state=self.random_state, n_init=10)
        kmeans.fit(X)
        self.labels = [int(i) for i in kmeans.labels_.tolist()]
        self.cluster_means_scaled = kmeans.cluster_centers_
        if math.isnan(best_score) or math.isnan(float(best_score)):
            self.silhouette = None
        else:
            try:
                self.silhouette = round(float(silhouette_score(X, self.labels)), 4)
            except ValueError:
                self.silhouette = None

    def fit(self) -> "SectorModel":
        """Fit the clustering model and derive per-sector intelligence."""
        self._select_k()

        sector_index = {s: i for i, s in enumerate(self.sectors)}
        self._compute_global_means()
        for s in self.sectors:
            self._profiles[s] = _profile_from_features(self.features[s])
            self._sector_cluster[s] = self.labels[sector_index[s]]
            self._multipliers[s] = _multipliers_from_profile(
                self._profiles[s], self._dim_min, self._dim_max
            )

        self._compute_cluster_labels()
        self._compute_similarity()
        for s in self.sectors:
            self._key_features[s] = self._top_key_features(s)
        return self

    def _compute_global_means(self) -> None:
        """Dataset-average share and min/max range for each profile dimension."""
        n = len(self.sectors)
        self._global_share_mean = {
            dim: round(sum(self.features[s][f"share_{dim}"] for s in self.sectors) / n, 4)
            for dim in _DIM_ORDER
        }
        self._dim_min = {
            dim: min(self.features[s][f"share_{dim}"] for s in self.sectors)
            for dim in _DIM_ORDER
        }
        self._dim_max = {
            dim: max(self.features[s][f"share_{dim}"] for s in self.sectors)
            for dim in _DIM_ORDER
        }

    def _compute_cluster_labels(self) -> None:
        """Describe each cluster from its member-average topical profile.

        Only dimensions with a clearly above-average share are used, so labels
        are computed from the data instead of being hard-coded.
        """
        clusters = sorted({self._sector_cluster[s] for s in self.sectors})
        for cluster in clusters:
            members = [s for s in self.sectors if self._sector_cluster[s] == cluster]
            means = {
                dim: sum(self._profiles[s][dim] for s in members) / len(members)
                for dim in _DIM_ORDER
            }
            above = [
                (dim, means[dim] - self._global_share_mean[dim])
                for dim in _DIM_ORDER
                if means[dim] - self._global_share_mean[dim] >= 0.05
            ]
            above.sort(key=lambda item: item[1], reverse=True)
            if not above:
                self._cluster_labels[cluster] = "Balanced dataset profile"
            else:
                label = " & ".join(above[0] for above in above[:2]).title()
                self._cluster_labels[cluster] = f"{label}-oriented"

    def _compute_similarity(self) -> None:
        """Euclidean distance on the standardised vectors → similarity.

        ``similarity = 1 / (1 + distance)`` so scores sit in (0, 1] and are
        ordered by closeness. Excludes the sector itself.
        """
        X = self.matrix_scaled
        count = config.ML_SIMILAR_SECTOR_COUNT
        for i, sector in enumerate(self.sectors):
            deltas = X - X[i]
            distances = np.sqrt(np.sum(deltas * deltas, axis=1))
            order = np.argsort(distances)
            ranked = []
            for j in order:
                if int(j) == i:
                    continue
                d = float(distances[j])
                ranked.append(
                    {
                        "sector": self.sectors[int(j)],
                        "similarity": round(1.0 / (1.0 + d), 4),
                    }
                )
                if len(ranked) >= count:
                    break
            self._similarity[sector] = ranked

    def _top_key_features(self, sector: str) -> List[Dict[str, Any]]:
        """Dimensions where the sector deviates most from the dataset mean."""
        profile = self._profiles[sector]
        deviations = [
            (dim, profile[dim], self._global_share_mean[dim])
            for dim in _DIM_ORDER
        ]
        deviations.sort(key=lambda item: abs(item[1] - item[2]), reverse=True)
        return [
            {
                "feature": dim,
                "share": round(profile[dim], 4),
                "datasetAverage": avg,
                "deviation": round(value - avg, 4),
            }
            for dim, value, avg in deviations[:3]
        ]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def quality(self) -> Dict[str, Any]:
        return {
            "method": ML_METHOD,
            "silhouetteScore": self.silhouette,
            "clusterCount": self.k,
            "randomState": self.random_state,
            "modelVersion": self.model_version,
            "preprocessingVersion": self.preprocessing_version,
            "note": METHOD_NOTE,
        }

    def is_dataset_sector(self, sector: str) -> bool:
        return sector in self._profiles

    def insight_for_dataset_sector(self, sector: str) -> Optional[Dict[str, Any]]:
        """Full ML insight object for a single GASTAT dataset sector."""
        if not self.is_fitted or not self.is_dataset_sector(sector):
            return None

        cluster = self._sector_cluster[sector]
        return {
            "enabled": True,
            "method": ML_METHOD,
            "cluster": cluster,
            "clusterLabel": self._cluster_labels.get(cluster, ""),
            "sectorProfile": self._profiles[sector],
            "multipliers": self._multipliers[sector],
            "similarSectors": list(self._similarity[sector]),
            "keyFeatures": list(self._key_features[sector]),
            "quality": self.quality(),
            "source": sector,
        }

    def global_profile_mean(self) -> Dict[str, float]:
        return dict(self._global_share_mean)

    def dimension_stats(self) -> Dict[str, Dict[str, float]]:
        """Per-dimension dataset min/max used to normalise profiles."""
        return {"min": dict(self._dim_min), "max": dict(self._dim_max)}

    def recorded_counts(self, records: List[Dict]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in records:
            counts[r["sector"]] = counts.get(r["sector"], 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        if not self.is_fitted:
            raise ValueError("Cannot serialise an unfitted model.")
        return {
            "modelVersion": self.model_version,
            "preprocessingVersion": self.preprocessing_version,
            "randomState": self.random_state,
            "method": ML_METHOD,
            "featureNames": self.feature_names,
            "sectors": self.sectors,
            "features": {s: dict(v) for s, v in self.features.items()},
            "matrixScaled": self.matrix_scaled.tolist(),
            "scalerMean": self.scaler_mean,
            "scalerScale": self.scaler_scale,
            "fingerprint": self.fingerprint,
            "k": self.k,
            "labels": self.labels,
            "silhouette": self.silhouette,
            "clusterMeansScaled": [
                list(map(float, row)) for row in self.cluster_means_scaled.tolist()
            ],
        }

    def save(self, path: Optional[str] = None) -> str:
        path = path or os.path.join(config.MODELS_DIR, config.ML_MODEL_FILENAME)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2)
        return path

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SectorModel":
        model = cls.__new__(cls)
        model.model_version = data["modelVersion"]
        model.preprocessing_version = data["preprocessingVersion"]
        model.random_state = data["randomState"]
        model.feature_names = list(data["featureNames"])
        model.sectors = list(data["sectors"])
        model.features = data["features"]
        model.matrix_scaled = np.asarray(data["matrixScaled"], dtype=float)
        model.scaler_mean = data.get("scalerMean")
        model.scaler_scale = data.get("scalerScale")
        model.fingerprint = data["fingerprint"]
        model.k = data["k"]
        model.labels = [int(i) for i in data["labels"]]
        model.silhouette = data.get("silhouette")
        model.cluster_means_scaled = np.asarray(data["clusterMeansScaled"], dtype=float)
        model._profiles = {s: _profile_from_features(model.features[s]) for s in model.sectors}
        model._sector_cluster = {s: model.labels[i] for i, s in enumerate(model.sectors)}
        model._cluster_labels = {}
        model._similarity = {}
        model._key_features = {}
        model._compute_global_means()
        model._multipliers = {
            s: _multipliers_from_profile(
                model._profiles[s], model._dim_min, model._dim_max
            )
            for s in model.sectors
        }
        model._compute_cluster_labels()
        model._compute_similarity()
        model._key_features = {s: model._top_key_features(s) for s in model.sectors}
        return model

    @classmethod
    def load(cls, path: str) -> Optional["SectorModel"]:
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError, TypeError):
            return None
        try:
            return cls.from_dict(data)
        except (KeyError, TypeError, ValueError):
            return None


# ---------------------------------------------------------------------------
# Process-wide cached instance (trained/loaded once per process).
# ---------------------------------------------------------------------------

_model: Optional[SectorModel] = None


def _build_model() -> Optional[SectorModel]:
    """Build the model from the cached dataset service (or None on failure)."""
    try:
        dataset = get_dataset()
        if dataset is None or not dataset.is_available() or not dataset.records:
            return None
        preprocessed = preprocessing.preprocess(dataset.records, scale=True)
    except Exception:
        return None

    if config.ML_PERSIST_MODEL:
        path = os.path.join(config.MODELS_DIR, config.ML_MODEL_FILENAME)
        if os.path.exists(path):
            loaded = SectorModel.load(path)
            if (
                loaded is not None
                and loaded.fingerprint == preprocessed["fingerprint"]
                and loaded.preprocessing_version == config.ML_PREPROCESSING_VERSION
                and loaded.model_version == config.ML_MODEL_VERSION
            ):
                return loaded
        fresh = SectorModel(preprocessed).fit()
        fresh.save(path)
        return fresh

    return SectorModel(preprocessed).fit()


def get_sector_model() -> Optional[SectorModel]:
    """Return the cached sector model, fitting it once if needed.

    The model is trained at startup (or loaded from the persisted artifact),
    then cached — never retrained per simulation request. To force a rebuild
    after a dataset change, delete the persisted model file (when persistence
    is enabled) or restart the process.
    """
    if not config.ML_ENABLED:
        return None
    global _model
    if _model is None:
        _model = _build_model()
    return _model