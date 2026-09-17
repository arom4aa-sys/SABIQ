"""Scenario definitions and profile resolution.

A :class:`Scenario` is the validated set of user inputs. Profile resolution
looks up the sector and decision profiles from configuration and raises
``ScenarioError`` for unknown values (which the API layer turns into 400
responses).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .. import config


class ScenarioError(ValueError):
    """Raised when a scenario references an unknown sector/decision/target."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Scenario:
    decision_type: str
    sector: str
    target_group: str
    duration: int
    change: float  # 0-100: the strength of the change being tested
    affected: float  # 0-100: share of the population exposed

    # ------------------------------------------------------------------
    # Validation helpers (range checks that do not need profiles)
    # ------------------------------------------------------------------

    @staticmethod
    def _positive_int(value: object, name: str) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ScenarioError(
                f"INVALID_{name.upper()}", f"{name.capitalize()} must be an integer."
            ) from exc
        if number < config.MIN_DURATION_MONTHS or number > config.MAX_DURATION_MONTHS:
            raise ScenarioError(
                f"INVALID_{name.upper()}",
                f"{name.capitalize()} must be between {config.MIN_DURATION_MONTHS} "
                f"and {config.MAX_DURATION_MONTHS}.",
            )
        return number

    @staticmethod
    def _range_float(value: object, name: str, code: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ScenarioError(
                code, f"{name.capitalize()} must be a number between 0 and 100."
            ) from exc
        if number < 0 or number > 100:
            raise ScenarioError(
                code, f"{name.capitalize()} must be between 0 and 100."
            )
        return number

    # ------------------------------------------------------------------
    # Factory used by the API layer
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict) -> "Scenario":
        if not isinstance(data, dict):
            raise ScenarioError("INVALID_BODY", "Request body must be a JSON object.")

        decision_type = data.get("decisionType")
        sector = data.get("sector")
        target_group = data.get("targetGroup")

        for field, value in (
            ("decisionType", decision_type),
            ("sector", sector),
            ("targetGroup", target_group),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ScenarioError(
                    "MISSING_FIELD",
                    f"Missing or empty field: {field}.",
                )

        decision_type = decision_type.strip()
        sector = sector.strip()
        target_group = target_group.strip()

        if decision_type not in config.DECISION_PROFILES:
            raise ScenarioError(
                "INVALID_DECISION_TYPE",
                f"Unknown decisionType '{decision_type}'. Must be one of: "
                + ", ".join(config.DECISION_PROFILES),
            )
        if sector not in config.SECTOR_PROFILES:
            raise ScenarioError(
                "INVALID_SECTOR",
                f"Unknown sector '{sector}'. Must be one of: "
                + ", ".join(config.SECTOR_PROFILES),
            )
        if target_group not in config.TARGET_GROUP_FACTORS:
            raise ScenarioError(
                "INVALID_TARGET_GROUP",
                f"Unknown targetGroup '{target_group}'. Must be one of: "
                + ", ".join(config.TARGET_GROUP_FACTORS),
            )

        duration = cls._positive_int(data.get("duration"), "duration")
        change = cls._range_float(data.get("change"), "change", "INVALID_CHANGE")
        affected = cls._range_float(
            data.get("affected"), "affected", "INVALID_AFFECTED"
        )

        return cls(
            decision_type=decision_type,
            sector=sector,
            target_group=target_group,
            duration=duration,
            change=change,
            affected=affected,
        )

    # ------------------------------------------------------------------
    # Profile accessors
    # ------------------------------------------------------------------

    @property
    def sector_profile(self) -> dict:
        return config.SECTOR_PROFILES[self.sector]

    @property
    def decision_profile(self) -> dict:
        return config.DECISION_PROFILES[self.decision_type]

    @property
    def target_factor(self) -> float:
        return config.TARGET_GROUP_FACTORS[self.target_group]


def build_seed(scenario: Scenario) -> int:
    """Deterministic seed derived from every scenario input.

    Reproducibility guarantee: the same scenario always produces the same
    simulated result because the whole population is drawn from this seed.
    """
    payload = "|".join(
        [
            str(scenario.decision_type),
            str(scenario.sector),
            str(scenario.target_group),
            str(scenario.duration),
            f"{scenario.change:.6f}",
            f"{scenario.affected:.6f}",
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)