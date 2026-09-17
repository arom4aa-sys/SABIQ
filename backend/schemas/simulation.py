"""Simulation request schema (thin wrapper around Scenario validation)."""

from ..simulation.scenarios import Scenario, ScenarioError

__all__ = ["Scenario", "ScenarioError"]