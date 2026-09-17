"""Simulation engine.

``run_scenario`` turns a :class:`~backend.simulation.scenarios.Scenario` into a
full, self-documented result:

* agent-based monthly simulation (people / businesses / government services)
* a baseline ("no decision applied") state for comparison
* 0-100 impact indices, risk score + risk breakdown
* an explanation built from the actual simulated values
* dataset context (GASTAT) when available

The engine is intentionally stateless and deterministic: the same scenario
always yields the same result (seeded from the scenario inputs).
"""

from __future__ import annotations

import random
from typing import Optional

from .. import config
from ..data.dataset import DatasetService, get_dataset
from ..ml.inference import ml_insight_for
from . import metrics
from . import risk as risk_model
from .agents import create_population
from .explain import build_explanation, build_recommendation
from .scenarios import Scenario, build_seed

PRESSURE_GAIN = 0.15  # documented in config as metric scaling assumption

# Sensitivity keys the ML sector-intelligence layer may adjust.
ML_SENSITIVITY_KEYS = ("social", "economic", "service", "behavioral", "business")


def _round(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def apply_ml_sensitivities(base_profile: dict, ml_insight: dict | None) -> tuple:
    """Blend the ML sector intelligence into the sector sensitivities.

    The base sensitivities remain the documented config assumptions; the ML
    multipliers (bounded by ``config.ML_MULTIPLIER_BOUNDS``) scale them and the
    product is clamped by ``config.ML_SENSITIVITY_MIN/MAX``. Returns
    ``(effective_profile, applied_sensitivities)`` where ``applied`` reports the
    exact values the simulation used (so the response stays auditable).
    """
    effective = dict(base_profile)
    applied = {
        key: base_profile[f"{key}_sensitivity"] for key in ML_SENSITIVITY_KEYS
    }
    multipliers = (ml_insight or {}).get("multipliers") or {}
    for key in ML_SENSITIVITY_KEYS:
        multiplier = multipliers.get(key)
        if multiplier is None:
            continue
        base = base_profile[f"{key}_sensitivity"]
        scaled = base * multiplier
        effective[f"{key}_sensitivity"] = min(
            config.ML_SENSITIVITY_MAX, max(config.ML_SENSITIVITY_MIN, scaled)
        )
        applied[key] = round(effective[f"{key}_sensitivity"], 4)
    return effective, applied


def _unavailable_ml_insight(note: str) -> dict:
    return {
        "enabled": False,
        "method": None,
        "cluster": None,
        "clusterLabel": None,
        "sectorProfile": {},
        "multipliers": {},
        "appliedSensitivities": {},
        "similarSectors": [],
        "keyFeatures": [],
        "quality": {},
        "explanation": note,
    }


def build_dataset_context(
    scenario: Scenario, dataset: DatasetService | None
) -> dict:
    """Attach relevant GASTAT context for the scenario's sector."""
    if dataset is None or not dataset.is_available():
        return {
            "used": False,
            "note": (
                "Dataset not available for this run; the simulation used "
                "documented configuration assumptions only."
            ),
        }

    profile = scenario.sector_profile
    source_sectors = profile["dataset_sectors"]

    summaries = []
    indicator_count = 0
    verified_count = 0
    ready_count = 0
    percent_indicator_candidates: list = []

    for sector in source_sectors:
        summary = dataset.summary_for(sector)
        summaries.append(summary)
        indicator_count += summary["indicatorCount"]
        verified_count += summary["verifiedIndicatorCount"]
        ready_count += summary["simulationReadyCount"]
        percent_indicator_candidates.extend(
            item
            for item in summary["indicators"]
            if item["unit"].lower() == "percent"
        )

    notable = percent_indicator_candidates[:8]

    return {
        "used": True,
        "sourceSectors": source_sectors,
        "indicatorCount": indicator_count,
        "verifiedIndicatorCount": verified_count,
        "simulationReadyCount": ready_count,
        "notableIndicators": notable,
        "baselineSatisfactionSource": profile["baseline_satisfaction_source"],
        "note": (
            "Observed GASTAT values shown as context. They inform baselines "
            "where directly relevant but are not model coefficients."
        ),
    }


def _monthly_series(
    scenario: Scenario,
    rng: random.Random,
    population: dict,
    sector: dict,
    decision: dict,
    base_pct: float,
) -> list:
    """Run one month of agent interaction; return the monthly record list.

    Also returns the final aggregates via a mutable dict ``totals``.
    """
    people = population["people"]
    businesses = population["businesses"]
    services = population["services"]

    monthly = []
    totals = {
        "behavior": [],
        "demand": [],
        "business": [],
        "pressure": [],
        "satisfaction": [],
    }

    for month in range(1, scenario.duration + 1):
        ramp = metrics.adoption_ramp(month, decision["adoption_rate_months"])

        # --- People ------------------------------------------------------
        person_effects = []
        for person in people:
            effect_pct = (
                base_pct
                * sector["behavioral_sensitivity"]
                * decision["behavioral_factor"]
                * person.reactivity(rng)
                * ramp
            )
            person.react(effect_pct)
            person_effects.append(effect_pct)
        behavior_pct = metrics.mean(person_effects)
        demand_pct = behavior_pct  # people drive demand through behaviour change

        # --- Businesses --------------------------------------------------
        business_input = (
            demand_pct * sector["business_sensitivity"] * decision["business_factor"]
        )
        business_effects = []
        for business in businesses:
            business_effects.append(abs(business.react(business_input * ramp)))
        business_pct = metrics.mean(business_effects)

        # --- Government services -----------------------------------------
        service_input = (
            demand_pct
            * sector["service_sensitivity"]
            * decision["service_factor"]
            * ramp
        )
        for service in services:
            service.react(service_input * PRESSURE_GAIN)
        pressure = metrics.mean([service.pressure for service in services])

        # --- Monthly impact indices --------------------------------------
        social_m = metrics.magnitude_to_score(
            behavior_pct, sector["social_sensitivity"], decision["social_factor"]
        )
        economic_m = metrics.magnitude_to_score(
            business_pct, sector["economic_sensitivity"], decision["economic_factor"]
        )
        service_m = metrics.magnitude_to_score(
            max(0.0, pressure - sector["baseline_service_pressure"]),
            1.0,
            decision["service_factor"],
        )
        satisfaction_m = metrics.satisfaction_from_impacts(
            sector["baseline_satisfaction"], social_m, service_m, economic_m
        )

        totals["behavior"].append(behavior_pct)
        totals["demand"].append(demand_pct)
        totals["business"].append(business_pct)
        totals["pressure"].append(pressure)
        totals["satisfaction"].append(satisfaction_m)

        monthly.append(
            {
                "month": month,
                "behavior": _round(behavior_pct),
                "demand": _round(demand_pct),
                "business": _round(business_pct),
                "service": _round(pressure),
                "satisfaction": _round(satisfaction_m),
            }
        )

    return monthly, totals


def run_scenario(
    scenario: Scenario, dataset: DatasetService | None = None
) -> dict:
    """Run the full simulation for a scenario and return the result dict."""
    if dataset is None:
        dataset = get_dataset()

    sector = scenario.sector_profile
    decision = scenario.decision_profile

    # ML sector intelligence: dataset-derived, bounded adjustments to the
    # documented sector sensitivities. Fails open — if the model is disabled or
    # unavailable the base profile is used unchanged.
    ml_insight = ml_insight_for(scenario.sector)
    effective_sector, applied_sensitivities = apply_ml_sensitivities(
        sector, ml_insight
    )
    if ml_insight is None:
        ml_insight = _unavailable_ml_insight(
            "ML sector intelligence is unavailable for this run; the simulation "
            "used the documented configuration profiles only."
        )
    else:
        ml_insight = dict(ml_insight)
        ml_insight["appliedSensitivities"] = applied_sensitivities

    # Deterministic population seeded from the scenario inputs.
    rng = random.Random(build_seed(scenario))
    population = create_population(rng, sector["baseline_service_pressure"])

    # Baseline ("no decision") state — documented configuration values.
    baseline = {
        "satisfaction": _round(sector["baseline_satisfaction"]),
        "servicePressure": _round(sector["baseline_service_pressure"]),
        "socialImpact": 0.0,
        "economicImpact": 0.0,
        "serviceImpact": 0.0,
        "behaviorChange": 0.0,
        "demandChange": 0.0,
        "businessImpact": 0.0,
    }

    base_pct = (
        scenario.change
        * (scenario.affected / 100.0)
        * scenario.target_factor
    )

    monthly, totals = _monthly_series(
        scenario, rng, population, effective_sector, decision, base_pct
    )

    avg_behavior = metrics.mean(totals["behavior"])
    avg_demand = metrics.mean(totals["demand"])
    avg_business = metrics.mean(totals["business"])
    avg_pressure = metrics.mean(totals["pressure"])
    avg_satisfaction = metrics.mean(totals["satisfaction"])

    # --- Final 0-100 impact indices --------------------------------------
    social = metrics.magnitude_to_score(
        avg_behavior, effective_sector["social_sensitivity"], decision["social_factor"]
    )
    economic = metrics.magnitude_to_score(
        avg_business, effective_sector["economic_sensitivity"], decision["economic_factor"]
    )
    service = metrics.magnitude_to_score(
        max(0.0, avg_pressure - effective_sector["baseline_service_pressure"]),
        1.0,
        decision["service_factor"],
    )

    behavior_change = avg_behavior
    demand_change = avg_demand
    business_impact = avg_business
    service_pressure = avg_pressure
    satisfaction = avg_satisfaction

    # --- Risk -------------------------------------------------------------
    sector_index = metrics.sector_sensitivity_index(effective_sector)
    contributors = {
        "socialImpact": social,
        "economicImpact": economic,
        "servicePressure": service,
        "populationExposure": scenario.affected,
        "duration": metrics.normalize_duration(scenario.duration),
        "behaviorChange": metrics.clip(abs(behavior_change)),
        "sectorSensitivity": sector_index,
    }
    risk_result = risk_model.compute_risk(contributors)
    risk = risk_result["risk"]
    risk_level = risk_result["riskLevel"]
    breakdown = risk_result["breakdown"]

    # Ambient baseline risk (doing nothing still exposes the system to time and
    # sector-specific sensitivity, but no decision-induced impacts).
    baseline_contributors = dict(contributors)
    for key in (
        "socialImpact",
        "economicImpact",
        "servicePressure",
        "populationExposure",
        "behaviorChange",
    ):
        baseline_contributors[key] = 0.0
    baseline_risk = risk_model.compute_risk(baseline_contributors)["risk"]

    # --- Explanation + recommendation ------------------------------------
    explanation = build_explanation(
        scenario,
        risk,
        risk_level,
        breakdown["items"],
        impacts={
            "social": social,
            "economic": economic,
            "service": service,
            "satisfaction": satisfaction,
            "servicePressure": service_pressure,
            "behaviorChange": behavior_change,
            "demandChange": demand_change,
            "businessImpact": business_impact,
        },
        sector_sensitivity_index=sector_index,
    )
    recommendation = build_recommendation(risk)

    dataset_context = build_dataset_context(scenario, dataset)

    # --- Assemble response -----------------------------------------------
    counts = config.AGENT_COUNTS
    return {
        "success": True,
        # Scenario echo
        "decisionType": scenario.decision_type,
        "sector": scenario.sector,
        "targetGroup": scenario.target_group,
        "duration": scenario.duration,
        "change": scenario.change,
        "affected": scenario.affected,
        # Headline results (kept compatible with the v1 frontend keys)
        "risk": risk,
        "riskLevel": risk_level,
        "social": round(social),
        "economic": round(economic),
        "service": round(service),
        "satisfaction": round(satisfaction),
        "behaviorChange": _round(behavior_change),
        "demandChange": _round(demand_change),
        "businessImpact": _round(business_impact),
        "servicePressure": _round(service_pressure),
        # Agent scope
        "agentsSimulated": sum(counts.values()),
        "peopleAgents": counts["people"],
        "businessAgents": counts["businesses"],
        "governmentAgents": counts["services"],
        "monthsSimulated": scenario.duration,
        # Detailed outputs
        "monthlyResults": monthly,
        "baseline": baseline,
        "baselineRisk": baseline_risk,
        "impactVsBaseline": {
            "risk": risk - baseline_risk,
            "social": round(social),
            "economic": round(economic),
            "service": round(service),
            "satisfaction": _round(satisfaction - sector["baseline_satisfaction"]),
            "servicePressure": _round(service_pressure - sector["baseline_service_pressure"]),
            "behaviorChange": _round(behavior_change),
            "demandChange": _round(demand_change),
            "businessImpact": _round(business_impact),
        },
        "riskBreakdown": breakdown,
        "explanation": explanation,
        "recommendation": recommendation,
        # Transparency
        "sectorProfileUsed": {
            "sector": scenario.sector,
            "sensitivities": {
                "social": sector["social_sensitivity"],
                "economic": sector["economic_sensitivity"],
                "service": sector["service_sensitivity"],
                "behavioral": sector["behavioral_sensitivity"],
                "business": sector["business_sensitivity"],
            },
            "baselineServicePressure": sector["baseline_service_pressure"],
            "baselineSatisfaction": sector["baseline_satisfaction"],
            "baselineSatisfactionSource": sector["baseline_satisfaction_source"],
            "note": (
                "Base sector sensitivities (documented simulation assumptions). "
                "The ML-adjusted sensitivities actually used by the agents are "
                "in mlInsights.appliedSensitivities."
            ),
        },
        "decisionProfileUsed": {
            "decisionType": scenario.decision_type,
            "factors": {
                key: decision[key]
                for key in (
                    "social_factor",
                    "economic_factor",
                    "service_factor",
                    "behavioral_factor",
                    "business_factor",
                )
            },
            "adoptionRateMonths": decision["adoption_rate_months"],
            "friction": decision["friction"],
            "summary": decision["summary"],
        },
        "datasetContext": dataset_context,
        # ML / sector intelligence (unsupervised, dataset-derived, bounded).
        "mlInsights": ml_insight,
        "methodologyNote": config.METHODOLOGY_NOTE,
        "mlMethodologyNote": config.ML_METHODOLOGY_NOTE,
    }


# ---------------------------------------------------------------------------
# Scenario comparison
# ---------------------------------------------------------------------------

LOWER_IS_BETTER = ("risk", "social", "economic", "service", "behaviorChange", "businessImpact")
NOT_LOWER_IS_BETTER = ("satisfaction",)

COMPARISON_METRICS = (
    ("risk", "Risk", True),
    ("social", "Social Impact", True),
    ("economic", "Economic Impact", True),
    ("service", "Service Pressure", True),
    ("satisfaction", "Satisfaction", False),
    ("behaviorChange", "Behavioral Change", True),
    ("businessImpact", "Business Impact", True),
)


def compare_scenarios(result_a: dict, result_b: dict) -> dict:
    """Build a structured comparison of two full simulation results."""
    items = []
    for key, label, lower_is_better in COMPARISON_METRICS:
        value_a = float(result_a.get(key, 0) or 0)
        value_b = float(result_b.get(key, 0) or 0)
        delta = _round(value_b - value_a)
        if lower_is_better:
            better = "A" if value_a < value_b else "B" if value_b < value_a else "Equal"
        else:
            better = "A" if value_a > value_b else "B" if value_b > value_a else "Equal"
        items.append(
            {
                "key": key,
                "metric": label,
                "valueA": _round(value_a),
                "valueB": _round(value_b),
                "delta": delta,
                "lowerIsBetter": lower_is_better,
                "better": better,
            }
        )

    risk_a = int(result_a.get("risk", 0) or 0)
    risk_b = int(result_b.get("risk", 0) or 0)
    if risk_a < risk_b:
        recommended = "A"
        summary = (
            f"Scenario A ('{result_a.get('decisionType')}' in {result_a.get('sector')}) "
            f"shows lower simulated risk ({risk_a}) than scenario B ({risk_b})."
        )
    elif risk_b < risk_a:
        recommended = "B"
        summary = (
            f"Scenario B ('{result_b.get('decisionType')}' in {result_b.get('sector')}) "
            f"shows lower simulated risk ({risk_b}) than scenario A ({risk_a})."
        )
    else:
        recommended = "Similar"
        summary = (
            "Both scenarios produce the same simulated risk "
            f"({risk_a}). Differences appear within the individual indicators."
        )

    return {
        "scenarioA": {
            "label": result_a.get("decisionType"),
            "sector": result_a.get("sector"),
            "risk": risk_a,
            "riskLevel": result_a.get("riskLevel"),
        },
        "scenarioB": {
            "label": result_b.get("decisionType"),
            "sector": result_b.get("sector"),
            "risk": risk_b,
            "riskLevel": result_b.get("riskLevel"),
        },
        "items": items,
        "recommendedScenario": recommended,
        "summary": summary,
        "note": "Comparison of simulated outputs only — not real-world values.",
    }