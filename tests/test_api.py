"""API tests: validation, response structure, errors, comparison, health."""

import pytest

from backend import config


def _payload(**overrides):
    payload = {
        "decisionType": "Launch a New Digital Service",
        "sector": "Healthcare",
        "targetGroup": "all",
        "duration": 12,
        "change": 30,
        "affected": 65,
    }
    payload.update(overrides)
    return payload


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert "datasetLoaded" in body


def test_valid_simulation_request(client):
    response = client.post("/simulate", json=_payload())
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True

    for key in (
        "risk",
        "riskLevel",
        "social",
        "economic",
        "service",
        "satisfaction",
        "behaviorChange",
        "demandChange",
        "businessImpact",
        "servicePressure",
        "agentsSimulated",
        "peopleAgents",
        "businessAgents",
        "governmentAgents",
        "monthsSimulated",
        "monthlyResults",
        "recommendation",
        "riskBreakdown",
        "explanation",
        "baseline",
        "impactVsBaseline",
        "datasetContext",
        "sectorProfileUsed",
        "decisionProfileUsed",
        "methodologyNote",
        "decisionType",
        "sector",
        "targetGroup",
        "duration",
    ):
        assert key in body, f"missing key: {key}"


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field, code",
    [
        ("duration", "INVALID_DURATION"),
        ("change", "INVALID_CHANGE"),
        ("affected", "INVALID_AFFECTED"),
    ],
)
def test_missing_required_fields(client, field, code):
    payload = _payload()
    payload.pop(field)
    response = client.post("/simulate", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] in ("MISSING_FIELD", code)


@pytest.mark.parametrize("duration", [-1, 0, 37, 9999])
def test_invalid_duration(client, duration):
    response = client.post("/simulate", json=_payload(duration=duration))
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_DURATION"


def test_duration_as_string_of_number_is_accepted(client):
    response = client.post("/simulate", json=_payload(duration="6"))
    assert response.status_code == 200


@pytest.mark.parametrize("value", [-0.1, -5, 101, 500])
def test_change_out_of_range(client, value):
    response = client.post("/simulate", json=_payload(change=value))
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_CHANGE"


def test_change_non_numeric(client):
    response = client.post("/simulate", json=_payload(change="abc"))
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_CHANGE"


@pytest.mark.parametrize("value", [-1, -100, 101, 250])
def test_affected_out_of_range(client, value):
    response = client.post("/simulate", json=_payload(affected=value))
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_AFFECTED"


def test_invalid_sector(client):
    response = client.post("/simulate", json=_payload(sector="Nuclear Physics"))
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_SECTOR"


def test_invalid_decision_type(client):
    response = client.post("/simulate", json=_payload(decisionType="Declare War"))
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_DECISION_TYPE"


def test_invalid_target_group(client):
    response = client.post("/simulate", json=_payload(targetGroup="aliens"))
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_TARGET_GROUP"


def test_non_json_body(client):
    response = client.post("/simulate", data="not json", content_type="text/plain")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_JSON"


def test_malformed_json_body(client):
    response = client.post(
        "/simulate", data='{"decisionType": ', content_type="application/json"
    )
    assert response.status_code == 400


def test_empty_body(client):
    response = client.post("/simulate", data="{}", content_type="application/json")
    assert response.status_code == 400


def test_error_response_never_returns_stack_trace(client):
    response = client.post("/simulate", json=_payload(duration="abc"))
    body = response.get_json()
    assert "traceback" not in str(body).lower()
    error = body.get("error") or {}
    assert "File" not in str(error.get("message", ""))


# ---------------------------------------------------------------------------
# Structure / reproducibility through the API
# ---------------------------------------------------------------------------

def test_reproducibility_via_api(client):
    first = client.post("/simulate", json=_payload()).get_json()
    second = client.post("/simulate", json=_payload()).get_json()
    assert first["risk"] == second["risk"]
    assert first["monthlyResults"] == second["monthlyResults"]


def test_risk_in_range_via_api(client):
    for change, affected in ((0, 0), (5, 20), (50, 50), (100, 100)):
        body = client.post("/simulate", json=_payload(change=change, affected=affected)).get_json()
        assert 0 <= body["risk"] <= 100


def test_monthly_results_length_via_api(client):
    body = client.post("/simulate", json=_payload(duration=6)).get_json()
    assert len(body["monthlyResults"]) == 6


def test_agent_counts_via_api(client):
    body = client.post("/simulate", json=_payload()).get_json()
    assert body["agentsSimulated"] == 1210


def test_dataset_reported_via_api(client):
    body = client.post("/simulate", json=_payload()).get_json()
    assert body["datasetContext"]["sourceSectors"] == ["Healthcare", "Population & Demographics"]


# ---------------------------------------------------------------------------
# Compare endpoint
# ---------------------------------------------------------------------------

def test_compare_endpoint(client):
    response = client.post(
        "/compare",
        json={
            "scenarioA": _payload(),
            "scenarioB": _payload(decisionType="Modify Sector Requirements", sector="Economy and Commerce"),
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert "comparison" in body
    assert len(body["comparison"]["items"]) >= 7
    assert body["comparison"]["recommendedScenario"] in ("A", "B", "Similar")


def test_compare_missing_scenario(client):
    response = client.post("/compare", json={"scenarioA": _payload()})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "MISSING_FIELD"


def test_compare_invalid_scenario(client):
    response = client.post(
        "/compare",
        json={"scenarioA": _payload(sector="Bad"), "scenarioB": _payload()},
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_SECTOR"


# ---------------------------------------------------------------------------
# Static serving
# ---------------------------------------------------------------------------

def test_index_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"SABIQ" in response.data


def test_static_assets_served(client):
    assert client.get("/style.css").status_code == 200
    assert client.get("/script.js").status_code == 200
    assert client.get("/simulation.html").status_code == 200
    assert client.get("/results.html").status_code == 200
    assert client.get("/reports.html").status_code == 200


def test_source_files_are_not_served(client):
    assert client.get("/backend/app.py").status_code == 404
    assert client.get("/tests/conftest.py").status_code == 404
    assert client.get("/run.py").status_code == 404
    assert client.get("../app.py").status_code == 404


def test_results_page_serves_ml_section(client):
    html = client.get("/results.html").get_data(as_text=True)
    assert 'id="mlSection"' in html
    assert "AI / ML Sector Intelligence" in html
    script = client.get("/script.js").get_data(as_text=True)
    assert "function renderMLInsights" in script
    assert 'getElementById("mlSection")' in script


def test_unknown_page_returns_404(client):
    assert client.get("/definitely-not-a-page.html").status_code == 404