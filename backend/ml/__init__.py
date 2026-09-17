"""Machine learning / sector intelligence layer for SABIQ.

This layer is deliberately **unsupervised**. The packaged GASTAT dataset has
no validated decision-outcome labels, so the ML component:

* extracts unit-agnostic, dataset-derived features per GASTAT sector
  (``preprocessing`` / ``features``),
* finds sector clusters with a reproducible KMeans run (``sector_model``),
* produces per-sector profiles, confidence/quality metrics and similarity,
* converts those profiles into *bounded* multiplier factors that the agent
  simulation applies to its documented sensitivities (``inference``),
* explains, in plain language, why the ML component influenced a given run
  (``explain``).

The ML component identifies patterns and similarities in the available
dataset. It does **not** predict actual future policy outcomes.
"""

from .. import config

__all__ = ["get_sector_model", "is_ml_available", "ml_insight_for"]


def get_sector_model():
    """Return the process-wide cached sector model (fit once)."""
    from .sector_model import get_sector_model as _impl

    return _impl()


def is_ml_available() -> bool:
    """True when the ML component is enabled and a fitted model exists."""
    if not config.ML_ENABLED:
        return False
    model = get_sector_model()
    return model is not None and model.is_fitted


def ml_insight_for(sector: str):
    """Return the serializable ML insight object for a UI sector."""
    from .inference import ml_insight_for as _impl

    return _impl(sector)


__version__ = "2.1.0"