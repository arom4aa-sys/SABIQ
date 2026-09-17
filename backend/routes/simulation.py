"""Simulation API routes: POST /simulate and POST /compare."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..schemas.simulation import Scenario, ScenarioError
from ..simulation.engine import compare_scenarios, run_scenario

simulation_bp = Blueprint("simulation", __name__)


def _handle_scenario_error(exc: ScenarioError):
    return (
        jsonify({"success": False, "error": {"code": exc.code, "message": exc.message}}),
        400,
    )


@simulation_bp.route("/simulate", methods=["POST"])
def simulate():
    """Validate a scenario, run the engine, return the full result."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_JSON",
                        "message": "Request body must be a JSON object.",
                    },
                }
            ),
            400,
        )

    try:
        scenario = Scenario.from_dict(data)
    except ScenarioError as exc:
        return _handle_scenario_error(exc)

    dataset = current_app.extensions["sabiq_dataset"]
    result = run_scenario(scenario, dataset=dataset)
    return jsonify(result)


@simulation_bp.route("/compare", methods=["POST"])
def compare():
    """Compare two scenarios and return a structured comparison."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_JSON",
                        "message": "Request body must be a JSON object.",
                    },
                }
            ),
            400,
        )

    scenario_a_data = data.get("scenarioA")
    scenario_b_data = data.get("scenarioB")
    if not isinstance(scenario_a_data, dict) or not isinstance(scenario_b_data, dict):
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "MISSING_FIELD",
                        "message": "Both 'scenarioA' and 'scenarioB' objects are required.",
                    },
                }
            ),
            400,
        )

    try:
        scenario_a = Scenario.from_dict(scenario_a_data)
        scenario_b = Scenario.from_dict(scenario_b_data)
    except ScenarioError as exc:
        return _handle_scenario_error(exc)

    dataset = current_app.extensions["sabiq_dataset"]
    result_a = run_scenario(scenario_a, dataset=dataset)
    result_b = run_scenario(scenario_b, dataset=dataset)

    comparison = compare_scenarios(result_a, result_b)

    return jsonify(
        {
            "success": True,
            "scenarioA": result_a,
            "scenarioB": result_b,
            "comparison": comparison,
        }
    )