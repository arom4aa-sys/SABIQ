"""Explainability for the ML / sector-intelligence component.

The explanation is generated **only** from the computed insight object
(profile shares, multipliers, key features, similarities). There is no template
boilerplate that ignores the model output: every sentence references a number
produced by the clustering/profile calculation.
"""

from __future__ import annotations

from typing import Any, Dict

_FEATURE_LABELS = {
    "economic": "economic",
    "social": "social",
    "service": "service",
    "digital": "digital/technology",
    "environment": "environmental",
}


def build_ml_explanation(ui_sector: str, parts: Dict[str, Any]) -> str:
    """One-paragraph, data-derived explanation of how ML influenced the run."""

    profile = parts["sectorProfile"]
    key_features = parts["keyFeatures"] or []
    similar = parts["similarSectors"] or []
    multipliers = parts.get("multipliers") or {}

    sentences: list[str] = []

    sentences.append(
        f"The ML sector-intelligence model grouped '{ui_sector}' into cluster "
        f"{parts['cluster']} ({parts['clusterLabel']}) using dataset-derived "
        "features, and used this profile to adjust the simulation's sector "
        "sensitivities within a bounded range."
    )

    # --- Key features (only what actually deviates) ------------------------
    if key_features:
        strongest = key_features[0]
        label = _FEATURE_LABELS.get(strongest["feature"], strongest["feature"])
        direction = "more strongly" if strongest["deviation"] > 0 else "less strongly"
        sentences.append(
            f"Key driver: the sector's dataset shows {label} indicators at share "
            f"{strongest['share']:.2f} versus the dataset average of "
            f"{strongest['datasetAverage']:.2f}, so it is associated "
            f"{direction} with {label} demand patterns than the typical sector."
        )

    # --- Multiplier effects (only deviations that actually change numbers) --
    effects = []
    for sensitivity, multiplier in multipliers.items():
        delta_pct = (multiplier - 1.0) * 100.0
        if abs(delta_pct) >= 1.0:
            word = "raised" if delta_pct > 0 else "lowered"
            effects.append(
                f"{sensitivity} sensitivity {word} by {abs(delta_pct):.1f}%"
            )
    if effects:
        sentences.append(
            "Impact on the simulation: " + "; ".join(effects) + "."
        )
    else:
        sentences.append(
            "Impact on the simulation: the profile adjustments were within ±1% "
            "and therefore negligible for this sector."
        )

    # --- Similar sectors ---------------------------------------------------
    if similar:
        names = ", ".join(
            f"{item['sector']} (similarity {item['similarity']:.2f})"
            for item in similar
        )
        sentences.append(
            f"Most similar sectors in the dataset feature space: {names}."
        )

    sentences.append(
        "This is an unsupervised pattern derived from the available dataset; "
        "it is a simulation input, not a prediction of decision outcomes."
    )

    return " ".join(sentences)