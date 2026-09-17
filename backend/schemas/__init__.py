"""Validation schemas for SABIQ API requests.

The public methods raise :class:`ScenarioError` (from the scenarios module)
with a stable error ``code``; the API layer converts these into clean HTTP 400
responses.
"""

from ..simulation.scenarios import Scenario, ScenarioError

__all__ = ["Scenario", "ScenarioError"]