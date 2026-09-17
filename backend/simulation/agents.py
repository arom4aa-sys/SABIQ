"""Agent classes for the SABIQ agent-based simulation.

Three agent types model the three groups in the system:
* PersonAgent            — beneficiaries whose behaviour and spending respond
                            to a decision.
* BusinessAgent          — businesses whose sales respond to demand changes.
* GovernmentServiceAgent — services whose operational pressure responds to
                            demand changes.

All randomness is driven by an explicit ``random.Random`` instance injected by
the engine, so a scenario is fully reproducible given its inputs (see
:func:`backend.simulation.scenarios.build_seed`).
"""

from __future__ import annotations

import random
from typing import Any

from .. import config


class PersonAgent:
    """A single beneficiary."""

    def __init__(self, rng: random.Random, spending: float = 100.0) -> None:
        self.sensitivity = rng.uniform(0.6, 1.4)
        self.spending = float(spending)

    def reactivity(self, rng: random.Random) -> float:
        """Per-reaction jitter around the person's base sensitivity."""
        return self.sensitivity * rng.uniform(0.9, 1.1)

    def react(self, effect_pct: float) -> float:
        """Apply a behavioural effect (percent) and return the magnitude."""
        self.spending *= max(0.4, 1.0 - effect_pct / 100.0)
        return effect_pct


class BusinessAgent:
    """A single business that reacts to demand changes."""

    def __init__(self, rng: random.Random, sales: float = 100.0) -> None:
        self.sensitivity = rng.uniform(0.6, 1.4)
        self.sales = float(sales)

    def react(self, demand_shift_pct: float) -> float:
        """Apply a demand shift (signed percent) and return sales change %."""
        change_pct = demand_shift_pct * self.sensitivity
        self.sales *= max(0.4, 1.0 + change_pct / 100.0)
        return change_pct


class GovernmentServiceAgent:
    """A single government service that accumulates operational pressure."""

    def __init__(
        self, rng: random.Random, initial_pressure: float = 40.0
    ) -> None:
        self.sensitivity = rng.uniform(0.7, 1.3)
        self.pressure = float(initial_pressure)

    def react(self, demand_pct: float) -> float:
        """Add pressure caused by demand movement; returns the increment."""
        increment = (abs(demand_pct) / 100.0) * self.sensitivity * 100.0
        self.pressure = min(100.0, self.pressure + increment)
        return increment


def create_population(
    rng: random.Random,
    service_pressure_baseline: float,
) -> dict[str, list[Any]]:
    """Create the standard agent population used by the engine."""
    counts = config.AGENT_COUNTS
    return {
        "people": [PersonAgent(rng) for _ in range(counts["people"])],
        "businesses": [BusinessAgent(rng) for _ in range(counts["businesses"])],
        "services": [
            GovernmentServiceAgent(rng, service_pressure_baseline)
            for _ in range(counts["services"])
        ],
    }