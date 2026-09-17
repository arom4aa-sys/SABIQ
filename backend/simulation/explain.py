"""Explanation and recommendation builders.

The explanation text is generated strictly from the actual simulation values
returned by the engine. It is not hard-coded ad-hoc text — the drivers are the
top contributors of the risk breakdown.
"""

from __future__ import annotations

import textwrap

from .. import config

# Group labels used by the explanation "major affected group" field, keyed by
# the dominant channel of impact.
GROUP_BY_IMPACT = {
    "socialImpact": "Beneficiaries (people)",
    "behaviorChange": "Beneficiaries (people)",
    "economicImpact": "Businesses",
    "servicePressure": "Government services",
    "sectorSensitivity": "Sector-level systems",
    "populationExposure": "Beneficiaries (people)",
}


def _risk_level_text(level: str) -> str:
    return {
        "Low": "low",
        "Medium": "moderate",
        "High": "high",
    }.get(level, level.lower())


def build_explanation(
    scenario: "object",
    risk: int,
    risk_level: str,
    risk_items: list,
    impacts: dict,
    sector_sensitivity_index: float,
) -> dict:
    """Build the ``explanation`` object from real simulation values.

    ``scenario`` needs attributes: decision_type, sector, target_group,
    duration.
    ``impacts`` must contain: social, economic, service, satisfaction,
    servicePressure, behaviorChange, demandChange, businessImpact.
    ``risk_items`` is ``risk.breakdown["items"]`` (already sorted by
    contribution).
    """
    top_items = sorted(risk_items, key=lambda item: item["contribution"], reverse=True)
    top_drivers = top_items[:3]

    drivers_text = [
        f"{item['factor']} contributes {item['contribution']:.0f}/100 points to the "
        f"risk score (value {item['value']:.0f} × weight {item['weight']:.2f})."
        for item in top_drivers
    ]

    major_group = GROUP_BY_IMPACT.get(
        top_drivers[0]["key"] if top_drivers else "socialImpact",
        "Sector-level systems",
    )

    summary = (
        f"A '{scenario.decision_type}' decision in the '{scenario.sector}' sector, "
        f"applied to '{scenario.target_group}' over {scenario.duration} month(s) "
        f"with a {scenario.change:.0f}% change affecting {scenario.affected:.0f}% of "
        f"beneficiaries, produces a {_risk_level_text(risk_level)} simulated risk "
        f"score of {risk}/100. "
        f"The largest risk drivers are {top_drivers[0]['factor'].lower()}"
        f"{', ' + top_drivers[1]['factor'].lower() if len(top_drivers) > 1 else ''}"
        f"{' and ' + top_drivers[2]['factor'].lower() if len(top_drivers) > 2 else ''}."
    )

    # Display numbers used to sanity-check the narrative.
    evidence = (
        f"Simulated values feeding this result: social impact {impacts['social']:.0f}/100, "
        f"economic impact {impacts['economic']:.0f}/100, service pressure "
        f"{impacts['servicePressure']:.1f}/100, satisfaction "
        f"{impacts['satisfaction']:.0f}/100, behavioural change "
        f"{impacts['behaviorChange']:.1f}%, business impact "
        f"{impacts['businessImpact']:.1f}%. Sector sensitivity index "
        f"{sector_sensitivity_index:.0f}/100."
    )

    return {
        "summary": summary,
        "topDrivers": drivers_text,
        "majorAffectedGroup": major_group,
        "evidence": evidence,
        "note": (
            "Simulated impact only. These numbers come from the model's "
            "assumptions, not from real-world forecasting."
        ),
    }


def build_recommendation(risk: int) -> dict:
    """Three-tier recommendation based on the simulated risk score."""
    if risk >= config.RISK_THRESHOLDS["medium"]:
        return {
            "title": "Decision Review Recommended",
            "text": (
                "The simulation indicates a high level of risk. The decision "
                "should be reviewed to assess its impact on beneficiaries, "
                "government services, and the economic sector."
            ),
        }
    if risk >= config.RISK_THRESHOLDS["low"]:
        return {
            "title": "Decision Modification Recommended",
            "text": (
                "The simulation indicates a moderate level of impact. Risks can "
                "be reduced by adjusting the scale of change or the target group."
            ),
        }
    return {
        "title": "Decision Can Be Implemented",
        "text": (
            "The simulation indicates a low level of risk. The decision can be "
            "implemented while monitoring its expected impacts."
        ),
    }