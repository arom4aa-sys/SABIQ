"""Shared fixtures for the SABIQ test-suite."""

import os
import sys

import pytest

# Make the project root importable regardless of the invocation directory.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


SAMPLE_SCENARIO = {
    "decisionType": "Launch a New Digital Service",
    "sector": "Healthcare",
    "targetGroup": "all",
    "duration": 12,
    "change": 30,
    "affected": 65,
}


@pytest.fixture
def sample_scenario() -> dict:
    return dict(SAMPLE_SCENARIO)


@pytest.fixture
def client():
    """A Flask test client with the application factory."""
    from backend.app import create_app

    app = create_app(testing=True)
    return app.test_client()