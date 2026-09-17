"""Central configuration for SABIQ.

Everything tunable about the simulation lives here so the project has a single
source of truth and no scattered magic numbers in the simulation code.

Sections
--------
* Deployment / security
* Simulation limits
* Agent population
* Target groups
* Risk model
* Sector profiles (which sector the user picks in the UI)
* Decision profiles (which decision type the user picks in the UI)
* Dataset mapping

IMPORTANT — status of the numbers
---------------------------------
The values in ``SECTOR_PROFILES`` and ``DECISION_PROFILES`` are **simulation
assumptions**. They are deliberately chosen to make the model explore outcomes
consistently and transparently; they are **not** empirically calibrated
coefficients and must not be presented as validated predictions.

Where the packaged GASTAT dataset provides a directly relevant observed value
(e.g. ``Education`` self-reported satisfaction 92.94% in 2024), that value is
referenced inside a profile as ``baseline_satisfaction`` and labelled with its
source. Everything labelled ``dataset_sectors`` maps a UI sector to the
GASTAT dataset sectors used to build the *context* shown in the response.
"""

import os

# ---------------------------------------------------------------------------
# Deployment / security
# ---------------------------------------------------------------------------

# Project root (the directory that holds index.html, the CSV, backend/, ...).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Also reachable via the package file location.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_PATH = os.path.join(BASE_DIR, "SABIQ_FINAL_DATASET.csv")

APP_ENV = os.environ.get("SABIQ_ENV", "development").lower()
DEBUG = os.environ.get("SABIQ_DEBUG", "0").lower() in ("1", "true", "yes")

# Frontend is normally served by this same Flask app (same origin), so CORS is
# only needed for the "open index.html directly from disk" workflow.
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "SABIQ_ALLOWED_ORIGINS",
        "http://127.0.0.1:5000,http://localhost:5000",
    ).split(",")
    if o.strip()
]

RATE_LIMIT_PER_MINUTE = int(os.environ.get("SABIQ_RATE_LIMIT", "120"))
# 64 KB is far more than a scenario payload needs (two scenarios for /compare).
MAX_JSON_BYTES = 64 * 1024

HOST = os.environ.get("SABIQ_HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "5000"))

# ---------------------------------------------------------------------------
# Simulation limits
# ---------------------------------------------------------------------------

MIN_DURATION_MONTHS = 1
MAX_DURATION_MONTHS = 36

# ---------------------------------------------------------------------------
# Agent population
# ---------------------------------------------------------------------------

AGENT_COUNTS = {
    "people": 1000,
    "businesses": 200,
    "services": 10,
}

# ---------------------------------------------------------------------------
# Target groups
# ---------------------------------------------------------------------------
# A relative weighting of how many agents are actually exposed to the decision
# for a given target group. Pure simulation assumption, documented in the
# technical documentation.
TARGET_GROUP_FACTORS = {
    "all": 1.00,
    "individuals": 0.80,
    "businesses": 0.70,
    "sme": 0.70,
}

# ---------------------------------------------------------------------------
# Metric scaling
# ---------------------------------------------------------------------------
# Maps a *magnitude* (a percentage reached by the agents, e.g. 30% behaviour
# change) on to the 0-100 impact index used by the dashboard.
# Single documented assumption so the conversion is transparent.
IMPACT_SCALE = 2.5

# Satisfaction is reduced by weighted impact components once a decision is
# applied (see simulation/metrics.py).
SATISFACTION_WEIGHTS = {"social": 0.25, "service": 0.20, "economic": 0.15}
SATISFACTION_FLOOR = 20.0

# ---------------------------------------------------------------------------
# Risk model
# ---------------------------------------------------------------------------
# All weights are normalised so they sum to 1.0. Every contributor is a 0-100
# value where higher == riskier. risk = SUM(weight * contributor).
RISK_WEIGHTS = {
    "socialImpact": 0.20,
    "economicImpact": 0.15,
    "servicePressure": 0.15,
    "populationExposure": 0.20,
    "duration": 0.10,
    "behaviorChange": 0.10,
    "sectorSensitivity": 0.10,
}

RISK_THRESHOLDS = {"low": 35, "medium": 65}  # <35 Low, <65 Medium, else High

# ---------------------------------------------------------------------------
# Sector profiles
# ---------------------------------------------------------------------------
# Each UI sector gets a sensitivity profile. Higher sensitivity means the
# agents / sector react more strongly to a decision of a given size.
#
# baseline_service_pressure (0-100): the steady state government-service load
#   the sector starts from (no decision applied).
# baseline_satisfaction (0-100): the steady state satisfaction of the
#   beneficiaries (no decision applied). Where a GASTAT value is directly
#   relevant it is used and the source recorded; otherwise it is an explicit
#   simulation assumption.
# dataset_sectors: GASTAT dataset sectors whose indicators are surfaced as
#   context alongside the simulation result.

SECTOR_PROFILES = {
    "Government Services": {
        "social_sensitivity": 1.0,
        "economic_sensitivity": 0.9,
        "service_sensitivity": 1.2,
        "behavioral_sensitivity": 1.0,
        "business_sensitivity": 0.7,
        "baseline_service_pressure": 40.0,
        "baseline_satisfaction": 72.0,
        "baseline_satisfaction_source": "Simulation assumption (no direct GASTAT satisfaction indicator mapped)",
        "dataset_sectors": ["GDP & National Accounts", "Prices & Inflation"],
    },
    "Economy and Commerce": {
        "social_sensitivity": 0.8,
        "economic_sensitivity": 1.3,
        "service_sensitivity": 0.9,
        "behavioral_sensitivity": 0.9,
        "business_sensitivity": 1.2,
        "baseline_service_pressure": 35.0,
        "baseline_satisfaction": 68.0,
        "baseline_satisfaction_source": "Simulation assumption (no direct GASTAT satisfaction indicator mapped)",
        "dataset_sectors": ["Business", "International Trade", "Prices & Inflation"],
    },
    "Transportation": {
        "social_sensitivity": 0.9,
        "economic_sensitivity": 1.0,
        "service_sensitivity": 1.2,
        "behavioral_sensitivity": 1.0,
        "business_sensitivity": 1.0,
        "baseline_service_pressure": 38.0,
        "baseline_satisfaction": 70.0,
        "baseline_satisfaction_source": "Simulation assumption (no direct GASTAT satisfaction indicator mapped)",
        "dataset_sectors": ["Transportation & Logistics"],
    },
    "Healthcare": {
        "social_sensitivity": 1.1,
        "economic_sensitivity": 0.9,
        "service_sensitivity": 1.3,
        "behavioral_sensitivity": 1.0,
        "business_sensitivity": 0.8,
        "baseline_service_pressure": 45.0,
        "baseline_satisfaction": 95.9,
        "baseline_satisfaction_source": "GASTAT Healthcare coverage 2024 (95.9% of total population) used as satisfaction proxy",
        "dataset_sectors": ["Healthcare", "Population & Demographics"],
    },
    "Education": {
        "social_sensitivity": 1.2,
        "economic_sensitivity": 0.7,
        "service_sensitivity": 1.1,
        "behavioral_sensitivity": 1.1,
        "business_sensitivity": 0.6,
        "baseline_service_pressure": 38.0,
        "baseline_satisfaction": 92.94,
        "baseline_satisfaction_source": "GASTAT Education satisfaction 2024 (92.94%, youth 15-19 enrolled)",
        "dataset_sectors": ["Education"],
    },
    "Technology and Innovation": {
        "social_sensitivity": 0.9,
        "economic_sensitivity": 1.1,
        "service_sensitivity": 1.0,
        "behavioral_sensitivity": 1.2,
        "business_sensitivity": 1.1,
        "baseline_service_pressure": 35.0,
        "baseline_satisfaction": 72.0,
        "baseline_satisfaction_source": "Simulation assumption (no direct GASTAT satisfaction indicator mapped)",
        "dataset_sectors": ["Technology & ICT", "Digital Economy & ICT"],
    },
}

# ---------------------------------------------------------------------------
# Decision profiles
# ---------------------------------------------------------------------------
# Each decision type multiplies the relevant channels of the model.
# * social/economic/service/behavioral/business factors scale the agent
#   reaction magnitude on that channel.
# * adoption_rate_months controls the ramp of the impact over time
#   (faster for digital roll-outs, slower for reorganisations).
# * friction is a qualitative 0-1 value describing implementation difficulty;
#   it is surfaced as context only and does not feed the formula.
#
# These are simulation assumptions, not validated coefficients.
DECISION_PROFILES = {
    "Modify Government Support Conditions": {
        "social_factor": 1.2,
        "economic_factor": 1.0,
        "service_factor": 0.9,
        "behavioral_factor": 1.2,
        "business_factor": 0.9,
        "adoption_rate_months": 2,
        "friction": 0.7,
        "summary": "Changing eligibility or amounts of government support affects beneficiaries directly and behaviour changes quickly.",
    },
    "Launch a New Digital Service": {
        "social_factor": 1.0,
        "economic_factor": 1.1,
        "service_factor": 1.3,
        "behavioral_factor": 1.3,
        "business_factor": 1.1,
        "adoption_rate_months": 3,
        "friction": 0.4,
        "summary": "New digital services shift demand and behaviour strongly, with relatively low implementation friction.",
    },
    "Modify Sector Requirements": {
        "social_factor": 0.9,
        "economic_factor": 1.2,
        "service_factor": 1.0,
        "behavioral_factor": 1.0,
        "business_factor": 1.3,
        "adoption_rate_months": 4,
        "friction": 0.8,
        "summary": "Changing sector requirements is felt hardest by businesses and usually takes longer to feed through.",
    },
    "Reorganize a Government Service": {
        "social_factor": 1.1,
        "economic_factor": 0.8,
        "service_factor": 1.4,
        "behavioral_factor": 0.9,
        "business_factor": 0.8,
        "adoption_rate_months": 6,
        "friction": 0.9,
        "summary": "Reorganising a service mainly increases pressure on the government service itself and on beneficiaries, with slow adoption.",
    },
}

# ---------------------------------------------------------------------------
# Machine learning / Sector intelligence
# ---------------------------------------------------------------------------
# The ML component is UNSUPERVISED. It identifies patterns and similarities in
# the packaged GASTAT dataset and turns them into bounded, evidence-weighted
# "sector intelligence" that scales the agent sensitivities inside the
# simulation. It does NOT predict actual decision outcomes: the dataset has no
# validated decision-outcome labels, so supervised learning would be
# scientifically inappropriate here (see TECHNICAL_DOCUMENTATION.md).
#
# All numbers are derived from the actual dataset fields (sector/indicator
# text, data_status, simulation_ready, unit) — nothing is invented.
#
# ML_ENABLED:
#   master switch. When disabled (or when the dataset cannot be loaded) the
#   engine falls back to the documented config-sector sensitivities exactly as
#   before, and "mlInsights" is returned with enabled=False.
ML_ENABLED = os.environ.get("SABIQ_ML_ENABLED", "1").lower() not in (
    "0",
    "false",
    "no",
    "off",
)

# Fixed seed => the same dataset + preprocessing + config always yields the
# same cluster assignments (reproducibility guarantee).
ML_RANDOM_STATE = 42

# KMeans candidates swept by the silhouette-based selection. The candidate
# range is additionally capped at floor(sqrt(n_sectors)) inside the model to
# avoid over-fragmenting a small dataset; the silhouette score then selects k
# within that range. For the packaged dataset (17 sectors) this means k ∈ {2,3,4}.
ML_K_RANGE = (2, 6)

# Topical dimensions the indicator tags are rolled up into. "other" collects
# every indicator that matches no topical keyword.
ML_PROFILE_DIMENSIONS = (
    "economic",
    "social",
    "service",
    "digital",
    "environment",
)

# How strongly an ML-derived profile may push a sensitivity away from its base
# value: multiplier = 1 ± verifiability * strength * (share − 0.5), clamped.
# With strength 0.18 the multiplier stays inside [0.82, 1.18].
ML_MULTIPLIER_STRENGTH = 0.18
ML_MULTIPLIER_BOUNDS = (1.0 - ML_MULTIPLIER_STRENGTH, 1.0 + ML_MULTIPLIER_STRENGTH)

# Map of simulation sensitivities to the dataset profile dimension(s) they
# follow. A sensitivity takes the MAX of the (min-max normalised) matching
# dimensions, so a sector is never penalised on a sensitivity for lacking
# indicators in an unrelated dimension. This is a documented modelling choice.
ML_SENSITIVITY_DIMENSIONS = {
    "social": ("social",),
    "economic": ("economic",),
    "service": ("service",),
    "behavioral": ("social", "digital"),
    "business": ("economic", "digital"),
}

# Hard bounds applied to the base sensitivity × ML multiplier product so the
# ML component can never push the simulation into unreasonable values.
ML_SENSITIVITY_MIN = 0.5
ML_SENSITIVITY_MAX = 1.6

# How many similar sectors are returned.
ML_SIMILAR_SECTOR_COUNT = 3

# Version metadata. Bump the (preprocessing) version whenever the feature
# extraction rules change so persisted models are not silently reused.
ML_MODEL_VERSION = "1.0.0"
ML_PREPROCESSING_VERSION = "1"

# Optional model persistence. The fitted model is always cached in memory once
# trained (never retrained per request). When persistence is enabled, the model
# is also written to MODELS_DIR and reloaded on boot if the dataset fingerprint
# and versions still match. Using JSON keeps the artifact small and auditable.
ML_PERSIST_MODEL = os.environ.get("SABIQ_ML_PERSIST", "0").lower() in (
    "1",
    "true",
    "yes",
)
MODELS_DIR = os.path.join(BASE_DIR, "models")
ML_MODEL_FILENAME = "sector_model.json"

# ---------------------------------------------------------------------------
# Methodology labels
# ---------------------------------------------------------------------------

METHODOLOGY_NOTE = (
    "Data-informed agent-based simulation for exploring potential decision "
    "impacts. Outputs are simulated, not real-world predictions."
)

ML_METHODOLOGY_NOTE = (
    "The ML component identifies patterns and similarities in the available "
    "dataset. It does not predict actual future policy outcomes because the "
    "dataset does not contain validated historical decision-outcome labels."
)