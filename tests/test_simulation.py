"""Tests for the simulation engine (determinism, ranges, structure)."""

import pytest

from backend import config
from backend.schemas.simulation import Scenario
from backend.simulation.engine import compare_scenarios, run_scenario
from backend.simulation.risk import compute_risk
from backend.data.dataset import DatasetService


def _run(payload):
    return run_scenario(Scenario.from_dict(payload))


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def test_same_scenario_is_reproducible(sample_scenario):
    first = _run(sample_scenario)
    second = _run(sample_scenario)
    assert first["risk"] == second["risk"]
    assert first["monthlyResults"] == second["monthlyResults"]
    assert first["social"] == second["social"]
    assert first["explanation"]["summary"] == second["explanation"]["summary"]


def test_different_scenarios_differ(sample_scenario):
    a = _run(sample_scenario)
    altered = dict(sample_scenario, change=10, affected=30)
    b = _run(altered)
    assert a["risk"] != b["risk"]


# ---------------------------------------------------------------------------
# Sector and decision type have an effect
# ---------------------------------------------------------------------------

def test_sector_affects_results(sample_scenario):
    results = {
        sector: _run(dict(sample_scenario, sector=sector))["risk"]
        for sector in config.SECTOR_PROFILES
    }
    assert len(set(results.values())) > 1


def test_decision_type_affects_results(sample_scenario):
    results = {
        dtype: _run(dict(sample_scenario, decisionType=dtype))["social"]
        for dtype in config.DECISION_PROFILES
    }
    assert len(set(results.values())) > 1


def test_target_group_affects_results(sample_scenario):
    results = {
        grp: _run(dict(sample_scenario, targetGroup=grp))["social"]
        for grp in config.TARGET_GROUP_FACTORS
    }
    assert len(set(results.values())) > 1


# ---------------------------------------------------------------------------
# Ranges and structure
# ---------------------------------------------------------------------------

def test_risk_is_within_range(sample_scenario):
    result = _run(sample_scenario)
    assert 0 <= result["risk"] <= 100


def test_impact_indices_are_within_range(sample_scenario):
    result = _run(sample_scenario)
    for key in ("social", "economic", "service", "satisfaction"):
        assert 0 <= result[key] <= 100, key


def test_monthly_results_length_matches_duration(sample_scenario):
    for duration in (3, 6, 12):
        result = _run(dict(sample_scenario, duration=duration))
        assert len(result["monthlyResults"]) == duration


def test_agent_counts(sample_scenario):
    result = _run(sample_scenario)
    assert result["peopleAgents"] == config.AGENT_COUNTS["people"]
    assert result["businessAgents"] == config.AGENT_COUNTS["businesses"]
    assert result["governmentAgents"] == config.AGENT_COUNTS["services"]
    assert result["agentsSimulated"] == sum(config.AGENT_COUNTS.values())
    assert result["monthsSimulated"] == sample_scenario["duration"]


def test_risk_breakdown_present_and_weighted(sample_scenario):
    result = _run(sample_scenario)
    breakdown = result["riskBreakdown"]
    items = breakdown["items"]
    assert len(items) == len(config.RISK_WEIGHTS)
    weight_sum = sum(item["weight"] for item in items)
    assert abs(weight_sum - 1.0) < 1e-6
    # risk matches the weighted sum (within rounding)
    assert abs(sum(item["contribution"] for item in items) - result["risk"]) <= 1.0


def test_risk_model_clamps():
    result = compute_risk({"socialImpact": 500, "economicImpact": -5})
    assert result["breakdown"]["items"]  # covers clamping, no exceptions
    assert 0 <= result["risk"] <= 100


def test_baseline_and_delta_present(sample_scenario):
    result = _run(sample_scenario)
    assert "baseline" in result
    assert "impactVsBaseline" in result
    vs = result["impactVsBaseline"]
    assert vs["risk"] == result["risk"] - result["baselineRisk"]


def test_explanation_is_generated_from_values(sample_scenario):
    result = _run(sample_scenario)
    explanation = result["explanation"]
    assert explanation["summary"]
    assert explanation["topDrivers"]
    assert explanation["majorAffectedGroup"]
    assert "Simulated impact only" in explanation["note"]


def test_recommendation_shape(sample_scenario):
    result = _run(sample_scenario)
    assert result["recommendation"]["title"]
    assert result["recommendation"]["text"]


def test_sector_profile_and_decision_profile_reported(sample_scenario):
    result = _run(sample_scenario)
    assert result["sectorProfileUsed"]["sector"] == "Healthcare"
    assert result["decisionProfileUsed"]["decisionType"] == "Launch a New Digital Service"


def test_dataset_context():
    dataset = DatasetService()
    result = _run(
        {
            "decisionType": "Launch a New Digital Service",
            "sector": "Healthcare",
            "targetGroup": "all",
            "duration": 6,
            "change": 20,
            "affected": 50,
        }
    )
    assert result["datasetContext"]["used"] is True
    assert "Healthcare" in result["datasetContext"]["sourceSectors"]


def test_compare_scenarios(sample_scenario):
    a = _run(sample_scenario)
    b = _run(dict(sample_scenario, decisionType="Modify Sector Requirements"))
    comparison = compare_scenarios(a, b)
    assert comparison["scenarioA"]["risk"] == a["risk"]
    assert comparison["scenarioB"]["risk"] == b["risk"]
    assert len(comparison["items"]) >= 7
    assert comparison["recommendedScenario"] in ("A", "B", "Similar")
    assert all(item["metric"] for item in comparison["items"])


def test_mild_scenario_has_low_risk(sample_scenario):
    result = _run(
        dict(sample_scenario, change=5, affected=20, duration=3)
    )
    assert result["risk"] < 35