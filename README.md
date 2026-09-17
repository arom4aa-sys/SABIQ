# SABIQ — Decision Impact Simulation Platform

**SABIQ** is a *data-informed agent-based simulation platform* for exploring
the potential impacts of government decisions before they are implemented.

> **Important framing:** SABIQ is **not** a scientific predictor. Its outputs
> are **simulated** results built from clearly documented assumptions, a
> curated GASTAT dataset used as context/baselines, and a deterministic agent
> model. Every result page labels its numbers as "Simulated Impact".

---

## 1. Project overview

SABIQ models three agent groups:

| Agent group          | Count (configurable) | Role |
|----------------------|----------------------|------|
| Person               | 1000                 | Beneficiaries whose behaviour and spending respond to a decision |
| Business             | 200                  | Businesses whose sales respond to demand changes |
| GovernmentService    | 10                   | Services whose operational pressure responds to demand changes |

The user defines a scenario (decision type, sector, target group, duration,
change strength, affected population). The engine runs an agent-based monthly
simulation and returns:

- overall **risk** score (0–100) with a transparent **risk breakdown**
- **social / economic / service** impact indices (0–100)
- **satisfaction**, **behaviour change**, **demand change**,
  **business impact**, **service pressure**
- a **baseline** ("no decision") and the **difference from baseline**
- an **explanation** of why the score occurred, generated from real simulated
  values
- monthly time-series data for charts
- optional **scenario comparison** (A vs B)

---

## 2. Architecture

```
project root/
├── app.py                  # Thin entry point (backward compatible)
├── run.py                  # Development entry point
├── backend/
│   ├── app.py              # Flask create_app() factory + security + static serving
│   ├── config.py           # ALL tunable parameters (single source of truth)
│   ├── routes/
│   │   ├── simulation.py   # POST /simulate, POST /compare
│   │   └── ml.py           # GET /api/ml/status|sectors|sector-profile/<sector>
│   ├── schemas/
│   │   └── simulation.py   # Scenario validation (ScenarioError)
│   ├── simulation/
│   │   ├── agents.py       # PersonAgent, BusinessAgent, GovernmentServiceAgent
│   │   ├── engine.py       # run_scenario() + compare_scenarios()
│   │   ├── metrics.py      # normalisation, impact scores, adoption ramp
│   │   ├── risk.py         # weighted risk model + breakdown
│   │   ├── scenarios.py    # Scenario dataclass, profile resolution, seeding
│   │   └── explain.py      # explanation + recommendation text
│   ├── ml/                 # unsupervised sector intelligence (see §8)
│   │   ├── preprocessing.py# unit-agnostic feature matrix + StandardScaler
│   │   ├── features.py     # 9 features + keyword topical tagging
│   │   ├── sector_model.py # KMeans + silhouette k selection + persistence
│   │   ├── inference.py    # UI-sector insight aggregation (evidence-weighted)
│   │   ├── explain.py      # plain-language ML explanation
│   │   └── __init__.py     # cached model access, is_ml_available()
│   └── data/
│       └── dataset.py      # GASTAT CSV loader + sector summaries
├── models/                 # optional persisted sector model (sector_model.json)
├── index.html              # Landing page
├── simulation.html         # Scenario builder
├── results.html            # Results dashboard (incl. AI/ML sector intelligence)
├── reports.html            # Simulation history
├── script.js               # Frontend logic (vanilla JS)
├── style.css               # Styling
├── SABIQ_FINAL_DATASET.csv # GASTAT dataset (2024–2025 snapshot)
├── tests/                  # pytest suite (93 tests incl. ML consistency)
└── requirements.txt
```

The Flask app stays thin: it validates the request, calls the engine, returns
the response.

---

## 3. Installation

Requires **Python 3.9+** (developed on 3.11).

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## 4. Running locally

```bash
python app.py
# or
python run.py
```

Then open <http://127.0.0.1:5000>.

Environment variables (all optional):

| Variable              | Default                        | Purpose |
|-----------------------|--------------------------------|---------|
| `PORT`                | `5000`                         | Server port |
| `SABIQ_HOST`          | `127.0.0.1`                    | Bind host |
| `SABIQ_ENV`           | `development`                  | `development` / `production` |
| `SABIQ_DEBUG`         | `0`                            | Enable Flask debug mode (`1`) |
| `SABIQ_ALLOWED_ORIGINS` | `http://127.0.0.1:5000,http://localhost:5000` | CORS allow-list |
| `SABIQ_RATE_LIMIT`    | `120`                          | Simulate/compare requests per minute |
| `SABIQ_ML_ENABLED`    | `1`                            | Master switch for the ML sector intelligence (`0`/`false` disables) |
| `SABIQ_ML_PERSIST`    | `0`                            | Persist/load the fitted sector model as JSON (`1` enables) |

---

## 5. API

### `POST /simulate`

Body (all fields required):

```json
{
  "decisionType": "Launch a New Digital Service",
  "sector": "Healthcare",
  "targetGroup": "all",
  "duration": 12,
  "change": 30,
  "affected": 65
}
```

Validation rules:

| Field          | Rule |
|----------------|------|
| `decisionType` | one of `Modify Government Support Conditions`, `Launch a New Digital Service`, `Modify Sector Requirements`, `Reorganize a Government Service` |
| `sector`       | one of `Government Services`, `Economy and Commerce`, `Transportation`, `Healthcare`, `Education`, `Technology and Innovation` |
| `targetGroup`  | one of `all`, `individuals`, `businesses`, `sme` |
| `duration`     | integer `1–36` |
| `change`       | number `0–100` |
| `affected`     | number `0–100` |

Example response (200) — values below come from a real smoke run with the
above body:

```json
{
  "success": true,
  "decisionType": "...",
  "sector": "...",
  "targetGroup": "...",
  "duration": 12,
  "change": 30,
  "affected": 65,
  "risk": 52,
  "riskLevel": "Medium",
  "social": 55,
  "economic": 37,
  "service": 72,
  "satisfaction": 65,
  "behaviorChange": 20.02,
  "demandChange": 20.02,
  "businessImpact": 15.09,
  "servicePressure": 67.23,
  "agentsSimulated": 1210,
  "peopleAgents": 1000,
  "businessAgents": 200,
  "governmentAgents": 10,
  "monthsSimulated": 12,
  "monthlyResults": [ { "month": 1, "behavior": 5.6, "demand": 5.6, "business": 4.9, "service": 48.4, "satisfaction": 85.0 } ],
  "baseline": { "satisfaction": 95.9, "servicePressure": 45.0, "socialImpact": 0, "...": 0 },
  "baselineRisk": 42,
  "impactVsBaseline": { "risk": 10, "social": 55, "economic": 37, "service": 72, "satisfaction": -30.9, "servicePressure": 22.2, "behaviorChange": 20.02, "demandChange": 20.02, "businessImpact": 15.09 },
  "riskBreakdown": { "formula": "...", "weights": { }, "items": [ { "key": "...", "factor": "...", "value": 65, "weight": 0.2, "contribution": 13 } ] },
  "explanation": { "summary": "...", "topDrivers": [ "..." ], "majorAffectedGroup": "...", "evidence": "...", "note": "Simulated impact only..." },
  "recommendation": { "title": "...", "text": "..." },
  "sectorProfileUsed": { "sector": "...", "sensitivities": { }, "baselineServicePressure": 45, "baselineSatisfaction": 95.9, "baselineSatisfactionSource": "..." },
  "decisionProfileUsed": { "decisionType": "...", "factors": { }, "adoptionRateMonths": 3, "friction": 0.4, "summary": "..." },
  "datasetContext": { "used": true, "sourceSectors": ["Healthcare", "Population & Demographics"], "notableIndicators": [], "...": "" },
  "mlInsights": { "enabled": true, "method": "KMeans", "cluster": 2, "clusterLabel": "Social-oriented", "sectorProfile": {}, "multipliers": {}, "similarSectors": [], "keyFeatures": [], "quality": {}, "sourceSectors": ["Healthcare", "Population & Demographics"], "appliedSensitivities": { "social": 1.18, "economic": 0.83, "service": 1.19, "behavioral": 1.08, "business": 0.74 }, "explanation": "..." },
  "methodologyNote": "Data-informed agent-based simulation for exploring potential decision impacts. Outputs are simulated, not real-world predictions.",
  "mlMethodologyNote": "The ML component identifies patterns and similarities in the available dataset. It does not predict actual future policy outcomes..."
}
```

Error response (4xx/5xx):

```json
{
  "success": false,
  "error": { "code": "INVALID_DURATION", "message": "Duration must be between 1 and 36." }
}
```

Standard error codes: `INVALID_JSON`, `MISSING_FIELD`, `INVALID_DECISION_TYPE`,
`INVALID_SECTOR`, `INVALID_TARGET_GROUP`, `INVALID_DURATION`, `INVALID_CHANGE`,
`INVALID_AFFECTED`, `BAD_REQUEST`, `RATE_LIMITED`, `PAYLOAD_TOO_LARGE`,
`NOT_FOUND`, `INTERNAL_ERROR`.

### `POST /compare`

```json
{
  "scenarioA": { "...same shape as /simulate..." },
  "scenarioB": { "...same shape as /simulate..." }
}
```

Returns `scenarioA`, `scenarioB` (full results) and a `comparison` object with
per-metric rows and a recommended scenario (`A`, `B` or `Similar`).

### `GET /health`

Returns

```json
{
  "success": true,
  "status": "ok",
  "datasetLoaded": true,
  "mlReady": true,
  "mlMethod": "KMeans"
}
```

### `GET /api/ml/status`

Machine-learning service status:

```json
{
  "enabled": true,
  "available": true,
  "modelVersion": "2.1.0",
  "preprocessingVersion": "1.0.0",
  "clusterCount": 4,
  "methodology": "KMeans clustering on a dataset-derived feature matrix with silhouette-based k selection; identifies patterns only.",
  "datasetFingerprint": "...",
  "datasetSectorCount": 17,
  "quality": { "silhouette": 0.3089 }
}
```

### `GET /api/ml/sectors`

Lists dataset sectors (cluster + profile) and the 6 UI sectors with their ML
info (cluster, multipliers, source sectors, similar sectors, key features).

### `GET /api/ml/sector-profile/<sector>`

Full ML insight for a UI (or dataset) sector. Unknown sector:
`404 {"success": false, "error": {"code": "INVALID_SECTOR", ...}}`.
ML disabled/unavailable: `503` with `ML_DISABLED` / `ML_UNAVAILABLE`.

---

## 6. Simulation methodology

The engine is deterministic: the whole agent population is drawn from a seed
derived from the scenario inputs (`backend/simulation/scenarios.py`), so the
same scenario always produces the same result.

Each month the engine:

1. **People** react to the decision. The per-person effect is a percentage
   magnitude scaled by the person's sensitivity, the **sector's behavioural
   sensitivity**, the **decision's behavioural factor** and an adoption ramp
   (`1 − exp(−month / adoption_rate)`).
2. **Demand** changes follow behaviour change.
3. **Businesses** react to demand changes (scaled by business sensitivity and
   the decision's economic/business factors).
4. **Government services** accumulate pressure driven by demand (scaled by
   service sensitivity and the decision's service factor), capped at 100.

Final 0–100 indices are produced with one documented scale assumption
(`IMPACT_SCALE = 2.5`, see `backend/config.py`):

```
impact = clip(magnitude(%) × sensitivity × factor × 2.5, 0, 100)
satisfaction = clip(baseline − 0.25×social − 0.20×service − 0.15×economic, 20, 100)
```

### Risk

```
risk = SUM(weight × contributor)
```

| Contributor          | Weight | Meaning |
|----------------------|--------|---------|
| socialImpact         | 0.20   | 0–100 social impact index |
| economicImpact       | 0.15   | 0–100 economic impact index |
| servicePressure      | 0.15   | 0–100 service impact index |
| populationExposure   | 0.20   | affected % of beneficiaries |
| duration             | 0.10   | months / 36 × 100 |
| behaviorChange       | 0.10   | magnitude of behaviour change |
| sectorSensitivity    | 0.10   | average sector sensitivity, normalised |

`Low < 35 ≤ Medium < 65 ≤ High`.

---

## 7. Dataset

`SABIQ_FINAL_DATASET.csv` is a curated snapshot of **official GASTAT
indicators (2024–2025)**. Columns:

`sector, indicator, description, verified_value_raw, verified_value, unit,
year, geography, data_status, imputation_method, imputation_note, source,
dataset, source_url, simulation_ready`

The loader (`backend/data/dataset.py`):

- parses the CSV without a pandas dependency
- flags `Verified` vs `Missing` rows
- deduplicates repeated rows (e.g. Environment duplicates) keeping the best one
- only averages **percent-unit verified values together** (the dataset itself
  warns that mixing units is statistically invalid)
- exposes per-sector summaries used as **context** in the API response

The simulation only uses dataset values as **baselines where directly relevant**
(e.g. Healthcare coverage 95.9% → Healthcare baseline satisfaction proxy,
Education satisfaction 92.94% → Education baseline satisfaction). Everything
else in the model is an explicitly documented simulation assumption.

---

## 8. ML / sector intelligence (`backend/ml/`)

> **Critical framing.** This is an **unsupervised, data-informed sector
> intelligence** component. It identifies **patterns and similarities in the
> available dataset**. It is **NOT** a supervised predictive model and does
> **NOT** establish causal relationships or predict actual future policy
> outcomes.

Why **unsupervised**? The GASTAT dataset has no decision→outcome labels, so a
supervised predictor would require fabricated labels and would falsely imply
predictive accuracy.

What it does (see TECHNICAL_DOCUMENTATION.md §8 for full detail):

- **Dataset limitations:** a 2024–2025 snapshot of 82 rows → 81 deduplicated
  records across 17 GASTAT sectors. Units are heterogeneous, so cross-unit
  averaging is never performed.
- **9 features** per dataset sector (`backend/ml/features.py`): topical shares
  (`economic`, `social`, `service`, `digital`, `environment`, `other`)
  computed by **keyword tagging** of sector+indicator+description text,
  plus `verified_ratio`, `simulation_ready_ratio`, and `percent_unit_ratio`.
- **StandardScaler** normalises the 9-dimension feature matrix before
  clustering so no feature dominates KMeans distance.
- **KMeans** (deterministic seed, `n_init=10`) with **silhouette-based k
  selection** over `ML_K_RANGE`. Current fit: **k = 4, silhouette ≈ 0.3089**.
- **Four data-derived cluster labels:** `Economic-oriented`,
  `Service & Digital-oriented`, `Social-oriented`, `Environment-oriented`.
- **UI sector → dataset sectors** mapping via `SECTOR_PROFILES[sector][
  "dataset_sectors"]` (e.g. Healthcare → Healthcare + Population &
  Demographics).
- **Evidence-weighted aggregation:** dataset sectors are merged by their
  **verified-indicator counts**, so well-evidenced sectors dominate.
- **Multipliers** of each base sensitivity:
  `clamp(1 + verifiability × 0.18 × (blend − 0.5), 0.82, 1.18)`. Verifiability
  **damping** pulls sparse/unverified sectors back toward `1.0`; effective
  sensitivities are then clamped to `[0.5, 1.6]` (`ML_SENSITIVITY_MIN/MAX`).
- **Model caching:** the model is fitted once per process and cached
  (`get_sector_model()`); never retrained per request.
- **Optional persistence:** `SABIQ_ML_PERSIST=1` saves it to
  `models/sector_model.json`, reloaded only when dataset fingerprint and
  versions match.
- **API:** `GET /api/ml/status`, `/api/ml/sectors`,
  `/api/ml/sector-profile/<sector>` (see §5); `/simulate` and `/compare`
  embed `mlInsights.appliedSensitivities` + `mlMethodologyNote`.
- **Effect on sensitivities:** the **documented** base profile stays in
  `sectorProfileUsed.sensitivities`; ML-adjusted values are applied as
  `clamp(base × multiplier)` and reported in `mlInsights.appliedSensitivities`.
  If ML is disabled/unavailable the base profile is used unchanged
  (**fail-open**, deterministic).
- **Scientific limits:** no prediction, no causality, no accuracy claim —
  silhouette measures cluster quality only; labels are data-derived
  descriptions, not policy findings.

---

## 9. Configuration

All tunables live in `backend/config.py`:

- `AGENT_COUNTS`
- `MIN/MAX_DURATION_MONTHS`
- `TARGET_GROUP_FACTORS`
- `IMPACT_SCALE`, `SATISFACTION_WEIGHTS`, `SATISFACTION_FLOOR`
- `RISK_WEIGHTS`, `RISK_THRESHOLDS`
- `SECTOR_PROFILES` (6 UI sectors)
- `DECISION_PROFILES` (4 decision types)
- ML settings (`ML_ENABLED`, `ML_K_RANGE`, `ML_MULTIPLIER_STRENGTH`,
  `ML_MULTIPLIER_BOUNDS`, `ML_SENSITIVITY_MIN/MAX`, model/preprocessing
  versions, methodology note)
- security/deployment settings (origins, rate limit, paths)

Change values there rather than in the engine code.

---

## 10. Testing

```bash
python -m pytest tests -v
```

The suite (93 tests) covers:

- dataset loading, deduplication, verified/missing handling
- simulation reproducibility, ranges, structure, agent counts
- sector / decision type / target group having an effect
- API validation (missing fields, out-of-range values, bad JSON, unknown
  sectors/decisions)
- error responses never leaking tracebacks
- `/compare` endpoint, static serving, and source-file protection
- ML consistency: model trains, k within `ML_K_RANGE`, labels valid,
  silhouette finite, every UI sector JSON-serialisable, multipliers and
  applied sensitivities within bounds, ML failure never breaks the simulation,
  `/api/ml/*` and `mlReady` behaviour

The ML tests assert **implementation consistency**, not predictive accuracy —
SABIQ makes no ML accuracy claim.

---

## 11. Deployment

Use a production WSGI server on Linux:

```bash
pip install gunicorn
SABIQ_ENV=production SABIQ_DEBUG=0 gunicorn app:app --bind 0.0.0.0:8000 --workers 2 --timeout 60
```

Set `ALLOWED_ORIGINS` to your production domain. Add TLS, a reverse proxy
(Nginx/Caddy), and request-size limits at the proxy level. The included rate
limiter is a simple in-memory guard; for multi-process deployments prefer a
shared limiter (e.g. Redis) or leave it to the proxy.

Static pages and assets are served by Flask; the API sits on the same origin.
The frontend talks to `window.location.origin` when served by the app, so no
hard-coded API URL is needed.

---

## 12. Known assumptions

- Sector and decision "sensitivities"/"factors" are **modelling assumptions**,
  not empirically calibrated coefficients.
- `IMPACT_SCALE`, satisfaction penalty weights, target-group factors and the
  adoption ramp parameters are assumptions.
- Baseline satisfaction is a GASTAT value where directly relevant (Education,
  Healthcare) and a documented assumption elsewhere.
- Agent population (1000/200/10) is a small representative sample, not a
  census-scale digital twin.
- ML sector intelligence adjusts sector sensitivities from dataset-derived
  patterns; the multipliers are bounded, damping, **assumption-level**
  adjustments — never calibrated coefficients.

## 13. Known limitations

- Not calibrated against historical decisions; **not a real-world predictor**.
- Risk model is a transparent weighted index, not a statistical estimator.
- In-memory rate limiter is per-process only.
- No user accounts/auth yet (login is a demo placeholder).
- Dataset is a 2024–2025 snapshot; some sectors have no percent-unit values.
- The ML component is unsupervised and descriptive: it does **not** predict
  actual future policy outcomes and establishes no causal relationships; its
  keyword tags and cluster labels are heuristic, data-derived descriptions
  from a small 17-sector / 81-record snapshot.

---

## 14. Developer guide

- To add a **decision type**: add a profile to `DECISION_PROFILES` in
  `backend/config.py` (and an `<option>` in `simulation.html`).
- To add a **sector**: add a profile to `SECTOR_PROFILES` in
  `backend/config.py` (and an `<option>` in `simulation.html`).
- To tune **risk**: edit `RISK_WEIGHTS` in `backend/config.py`.
- To tune **ML**: edit the `ML_*` settings in `backend/config.py` and the
  feature/tagging logic in `backend/ml/features.py`; the model is cached, so
  restart the process after changes (or set `SABIQ_ML_PERSIST=0`).
- To change agents: edit `backend/simulation/agents.py`.
- The explanation text is generated in `backend/simulation/explain.py` and is
  always derived from computed values — keep it that way.

See **TECHNICAL_DOCUMENTATION.md** for the full model reference.