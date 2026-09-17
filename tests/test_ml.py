"""Tests for the ML / sector-intelligence component.

Covers preprocessing, feature extraction, model training, reproducibility,
cluster assignment, profiles, similarity, output structure, simulation
integration, model persistence and the API surface — plus regression tests
proving the existing /simulate and /compare contracts still hold.
"""

import json
import math

import pytest

from backend import config
from backend.data.dataset import DatasetService
from backend.ml import features, preprocessing
from backend.ml.inference import ml_insight_for
from backend.ml.preprocessing import PreprocessingError, preprocess
from backend.ml.sector_model import SectorModel, get_sector_model
from backend.schemas.simulation import Scenario
from backend.simulation.engine import run_scenario

SCENARIO = {
    "decisionType": "Launch a New Digital Service",
    "sector": "Healthcare",
    "targetGroup": "all",
    "duration": 12,
    "change": 30,
    "affected": 65,
}


# ---------------------------------------------------------------------------
# 1-3. Preprocessing, missing values, feature extraction
# ---------------------------------------------------------------------------

def test_preprocessing_builds_valid_matrix():
    records = DatasetService().records
    result = preprocess(records)
    n = len(result["sectors"])
    assert n >= 15
    assert result["matrix"].shape == (n, len(result["feature_names"]))
    assert result["matrix_scaled"].shape == result["matrix"].shape
    # Every engineered feature is a fraction in [0, 1] — no NaN, no cross-unit
    # aggregation.
    for row in result["matrix"]:
        for value in row:
            assert not math.isnan(float(value))
            assert 0.0 <= float(value) <= 1.0
    assert result["preprocessing_version"] == config.ML_PREPROCESSING_VERSION


def test_fingerprint_is_stable_and_content_sensitive():
    records = DatasetService().records
    assert preprocessing.fingerprint_dataset(records) == \
        preprocessing.fingerprint_dataset(list(records))
    mutated = [dict(r) for r in records]
    mutated[0] = dict(mutated[0], data_status="Missing", verified=False)
    assert preprocessing.fingerprint_dataset(mutated) != \
        preprocessing.fingerprint_dataset(records)


def test_missing_rows_are_encoded_not_deleted():
    records = DatasetService().records
    result = preprocess(records)
    # Every dataset sector with rows survives preprocessing.
    expected = sorted({r["sector"] for r in records})
    assert result["sectors"] == expected
    # A sector containing "Missing" rows has a verifiability below 1.0.
    sectors_with_missing = {
        r["sector"] for r in records if r["data_status"] == "Missing"
    }
    assert sectors_with_missing
    for sector in sectors_with_missing:
        assert result["features"][sector]["verified_ratio"] < 1.0


def test_preprocessing_rejects_empty_input():
    with pytest.raises(PreprocessingError):
        preprocess([])


def test_feature_extraction_topical_signatures():
    records = DatasetService().records
    result = features.build_sector_features(records)
    # The topical signature must reflect what each sector actually reports on.
    assert result["Transportation & Logistics"]["share_service"] == max(
        result["Transportation & Logistics"][f"share_{d}"]
        for d in features.DIMENSIONS
    )
    assert result["Healthcare"]["share_social"] == max(
        result["Healthcare"][f"share_{d}"] for d in features.DIMENSIONS
    )
    assert result["Agriculture"]["share_environment"] == max(
        result["Agriculture"][f"share_{d}"] for d in features.DIMENSIONS
    )
    # Shares partition the indicators.
    for sector, vector in result.items():
        total = sum(vector[f"share_{d}"] for d in features.DIMENSIONS)
        total += vector["share_other"]
        assert abs(total - 1.0) < 1e-3, sector


# ---------------------------------------------------------------------------
# 4-6. Model training, cluster selection, reproducibility
# ---------------------------------------------------------------------------

def _fit_model() -> SectorModel:
    return SectorModel(preprocess(DatasetService().records)).fit()


def test_model_trains_and_selects_reasonable_k():
    model = _fit_model()
    n = len(model.sectors)
    assert model.is_fitted
    assert config.ML_K_RANGE[0] <= model.k <= config.ML_K_RANGE[1]
    assert model.k <= max(2, int(math.sqrt(n)))
    assert len(model.labels) == n
    assert set(model.labels) == set(range(model.k))
    assert model.silhouette is not None
    assert -1.0 <= model.silhouette <= 1.0


def test_model_is_reproducible():
    first = _fit_model()
    second = _fit_model()
    assert first.k == second.k
    assert first.labels == second.labels
    assert first.silhouette == second.silhouette
    assert first._similarity == second._similarity
    assert first._multipliers == second._multipliers
    assert first._cluster_labels == second._cluster_labels


def test_cluster_assignment_is_stable_for_every_sector():
    model = get_sector_model()
    assert model is not None and model.is_fitted
    for sector in model.sectors:
        insight = model.insight_for_dataset_sector(sector)
        assert isinstance(insight["cluster"], int)
        assert 0 <= insight["cluster"] < model.k
        assert insight["clusterLabel"]


def test_model_is_cached_singleton():
    assert get_sector_model() is get_sector_model()


# ---------------------------------------------------------------------------
# 7-9. Profiles, similarity, output structure
# ---------------------------------------------------------------------------

def test_sector_profile_generation():
    insight = ml_insight_for("Healthcare")
    profile = insight["sectorProfile"]
    for dim in config.ML_PROFILE_DIMENSIONS:
        assert dim in profile
        assert 0.0 <= profile[dim] <= 1.0
    assert 0.0 <= profile["verifiability"] <= 1.0
    # Healthcare is a social/service sector in the dataset.
    assert profile["social"] == max(
        profile[d] for d in config.ML_PROFILE_DIMENSIONS
    )


def test_sector_similarity_is_data_derived():
    insight = ml_insight_for("Healthcare")
    similar = insight["similarSectors"]
    assert similar
    assert len(similar) <= config.ML_SIMILAR_SECTOR_COUNT
    names = [item["sector"] for item in similar]
    assert "Healthcare" not in names  # never lists itself
    assert len(names) == len(set(names))
    scores = [item["similarity"] for item in similar]
    assert all(0.0 < s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)
    # Similarity is computed from features, not hard-coded: Housing has the
    # same pure-social profile as Healthcare and must score highly.
    assert similar[0]["similarity"] >= max(scores)


def test_ml_output_structure_and_serialisability():
    insight = ml_insight_for("Education")
    for key in (
        "enabled",
        "method",
        "cluster",
        "clusterLabel",
        "sectorProfile",
        "multipliers",
        "similarSectors",
        "keyFeatures",
        "quality",
        "sourceSectors",
        "explanation",
    ):
        assert key in insight, key
    assert insight["method"] == "KMeans"
    for key in ("silhouetteScore", "clusterCount", "modelVersion",
                "preprocessingVersion", "randomState"):
        assert key in insight["quality"], key
    json.dumps(insight)  # must be JSON-safe, no internal objects


def test_multipliers_are_bounded():
    lo, hi = config.ML_MULTIPLIER_BOUNDS
    for sector in config.SECTOR_PROFILES:
        multipliers = ml_insight_for(sector)["multipliers"]
        assert set(multipliers) == set(config.ML_SENSITIVITY_DIMENSIONS)
        for value in multipliers.values():
            assert lo <= value <= hi


def test_explanation_uses_computed_values():
    insight = ml_insight_for("Healthcare")
    text = insight["explanation"]
    assert insight["clusterLabel"] in text
    assert "Impact on the simulation" in text
    assert "not a prediction" in text.lower()
    # Explanation is deterministic.
    assert text == ml_insight_for("Healthcare")["explanation"]


# ---------------------------------------------------------------------------
# 10-12. Simulation integration + invalid sectors
# ---------------------------------------------------------------------------

def test_simulation_includes_ml_insights():
    result = run_scenario(Scenario.from_dict(SCENARIO))
    ml = result["mlInsights"]
    assert ml["enabled"] is True
    assert ml["method"] == "KMeans"
    assert ml["appliedSensitivities"]
    for value in ml["appliedSensitivities"].values():
        assert config.ML_SENSITIVITY_MIN <= value <= config.ML_SENSITIVITY_MAX


def test_applied_sensitivities_match_base_times_multiplier():
    result = run_scenario(Scenario.from_dict(SCENARIO))
    base = config.SECTOR_PROFILES["Healthcare"]
    ml = result["mlInsights"]
    for key, multiplier in ml["multipliers"].items():
        expected = base[f"{key}_sensitivity"] * multiplier
        expected = min(config.ML_SENSITIVITY_MAX,
                       max(config.ML_SENSITIVITY_MIN, expected))
        assert abs(ml["appliedSensitivities"][key] - round(expected, 4)) < 1e-6


def test_ml_actually_changes_the_simulation(monkeypatch):
    """Regression guard proving the ML layer has a computational role."""
    scenario = Scenario.from_dict(SCENARIO)
    with_ml = run_scenario(scenario)

    monkeypatch.setattr(
        "backend.simulation.engine.ml_insight_for", lambda _sector: None
    )
    without_ml = run_scenario(scenario)

    assert without_ml["mlInsights"]["enabled"] is False
    assert with_ml["social"] != without_ml["social"]


def test_invalid_ui_sector_returns_none():
    assert ml_insight_for("Not A Real Sector") is None
    assert ml_insight_for("") is None


def test_unknown_sector_api_returns_error(client):
    response = client.get("/api/ml/sector-profile/Nonsense")
    assert response.status_code == 404
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_SECTOR"


# ---------------------------------------------------------------------------
# 13-15. API surface, availability, model persistence / loading
# ---------------------------------------------------------------------------

def test_ml_status_api(client):
    body = client.get("/api/ml/status").get_json()
    assert body["success"] is True
    assert body["enabled"] is True
    assert body["method"] == "KMeans"
    assert body["datasetSectorCount"] >= 15
    assert body["quality"]["clusterCount"] >= 2


def test_ml_sectors_api(client):
    body = client.get("/api/ml/sectors").get_json()
    assert body["success"] is True
    assert len(body["datasetSectors"]) >= 15
    assert body["uiSectors"]
    for item in body["datasetSectors"]:
        assert "sector" in item and "cluster" in item and "sectorProfile" in item


def test_ml_sector_profile_api_for_ui_and_dataset_sector(client):
    ui = client.get("/api/ml/sector-profile/Healthcare").get_json()
    assert ui["success"] is True
    assert ui["mlInsights"]["enabled"] is True

    dataset = client.get(
        "/api/ml/sector-profile/Transportation & Logistics"
    ).get_json()
    assert dataset["success"] is True
    assert dataset["mlInsights"]["cluster"] >= 0


def test_ml_available_and_health_reports_it(client):
    from backend.ml import is_ml_available

    assert is_ml_available() is True
    health = client.get("/health").get_json()
    assert health["mlReady"] is True
    assert health["mlMethod"] == "KMeans"


def test_model_save_and_load_roundtrip(tmp_path):
    model = _fit_model()
    path = str(tmp_path / "sector_model.json")
    model.save(path)
    loaded = SectorModel.load(path)
    assert loaded is not None
    assert loaded.k == model.k
    assert loaded.labels == model.labels
    assert loaded.silhouette == model.silhouette
    assert loaded.feature_names == model.feature_names
    # Reloaded model produces identical intelligence.
    for sector in model.sectors:
        assert loaded.insight_for_dataset_sector(sector) == \
            model.insight_for_dataset_sector(sector)


def test_model_load_handles_missing_or_bad_file(tmp_path):
    assert SectorModel.load(str(tmp_path / "does-not-exist.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json ", encoding="utf-8")
    assert SectorModel.load(str(bad)) is None


# ---------------------------------------------------------------------------
# 16-17. Regression: existing /simulate and /compare still work
# ---------------------------------------------------------------------------

def test_regression_simulate_endpoint_still_works(client):
    response = client.post("/simulate", json=SCENARIO)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    for key in (
        "risk",
        "riskLevel",
        "social",
        "economic",
        "service",
        "satisfaction",
        "monthlyResults",
        "baseline",
        "impactVsBaseline",
        "riskBreakdown",
        "explanation",
        "recommendation",
        "sectorProfileUsed",
        "decisionProfileUsed",
        "datasetContext",
        "methodologyNote",
    ):
        assert key in body, f"legacy key missing: {key}"
    assert 0 <= body["risk"] <= 100
    assert len(body["monthlyResults"]) == SCENARIO["duration"]


def test_regression_compare_endpoint_still_works(client):
    response = client.post(
        "/compare",
        json={
            "scenarioA": SCENARIO,
            "scenarioB": {**SCENARIO, "decisionType": "Modify Sector Requirements"},
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert len(body["comparison"]["items"]) >= 7
    assert body["comparison"]["recommendedScenario"] in ("A", "B", "Similar")
    # Both nested scenario results carry the ML block too.
    assert "mlInsights" in body["scenarioA"]
    assert "mlInsights" in body["scenarioB"]


def test_regression_simulation_reproducible_with_ml(client):
    first = client.post("/simulate", json=SCENARIO).get_json()
    second = client.post("/simulate", json=SCENARIO).get_json()
    assert first["risk"] == second["risk"]
    assert first["mlInsights"] == second["mlInsights"]
    assert first["monthlyResults"] == second["monthlyResults"]