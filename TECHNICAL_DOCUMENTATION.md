# SABIQ — Technical Documentation

Internal reference for the SABIQ simulation platform. It explains what is
**implemented**, what is **assumed**, and what is **dataset-derived**, how the
risk score is computed, and how to extend the system.

---

## 1. Separation of "dataset-derived" vs "assumption" vs "implemented"

Every number in the platform falls into one of three classes. Keeping these
separate is a core requirement of the project.

| Class | What it is | Where it lives |
|-------|-----------|----------------|
| **Dataset-derived** | Values read from `SABIQ_FINAL_DATASET.csv` (GASTAT 2024–2025), with a recorded source and verification flag | `backend/data/dataset.py`; surfaced as `datasetContext`, `sectorProfileUsed.baseline_satisfaction*`, notable indicators |
| **Simulation assumption** | Explicit, documented modelling choices (sensitivities, factors, scales, weights) that are NOT calibrated against outcome data | `backend/config.py` — headers and docstrings state these are assumptions |
| **Implemented** | Deterministic behaviour of the engine/agents/risk model | `backend/simulation/*.py` |

Example: the `Healthcare` sector baseline satisfaction is **dataset-derived**
(GASTAT Healthcare coverage 95.9% used as a proxy, source recorded). The
`Education` baseline satisfaction uses the GASTAT self-reported education
satisfaction (92.94%). All other sector baselines are **stated assumptions**.

---

## 2. Dataset processing (`backend/data/dataset.py`)

- CSV parsed with the stdlib `csv` module (no pandas).
- Each row classified `Verified` or `Missing`; `simulation_ready == "Yes"`
  rows are the trusted pool.
- Duplicate rows (e.g. repeated Environment entries) are deduplicated keeping
  the best copy (Verified wins; otherwise most complete).
- Sector summaries list indicators per GASTAT sector, flagging missing vs
  verified and only aggregating percent-unit values (the dataset itself notes
  cross-unit averaging is statistically invalid).
- A global report is cached (`functools.lru_cache`), so repeated requests do
  not re-read the file; dataset read failures degrade gracefully to
  `datasetLoaded: false` with context still operating on profiles.

---

## 3. Agent model (`backend/simulation/agents.py`)

Three agent types. All randomness comes from a seeded `random.Random`, so a
scenario is fully deterministic.

### PersonAgent
Fields: `id`, `sensitivity` (0.3–1.0), `behavior_elasticity`, `spending_elasticity`.
`reaction(magnitude, friction)` applies an adoption ramp and its own
elasticity, returning the person-effected percentage change in behaviour.

### BusinessAgent
Fields: `sensitivity`, `demand_elasticity`. `reaction(demand_change)` converts
demand change into a business-facing percentage impact (amplified for
low-sensitivity/high-leverage firms by the decision's business factor).

### GovernmentServiceAgent
Fields: `utilization`, `service_pressure`. `react(demand_change, factor)`
accumulates pressure from demand, bounded ×60% above utilisation, capped at 100.

### Population (`create_population`)
`AGENT_COUNTS = {"people": 1000, "businesses": 200, "services": 10}`. Each agent
gets a deterministic random draw from the scenario seed.

---

## 4. Scenario pipeline (`backend/simulation/`)

### Resolution (`scenarios.py`)
`Scenario.from_dict` validates input. Profile resolution:

```
sector_profile  = SECTOR_PROFILES[sector]
decision_profile = DECISION_PROFILES[decisionType]
affected_weight = TARGET_GROUP_FACTORS[targetGroup]
```

### Seeding (`build_seed`)
`sha256(f"{decisionType}|{sector}|{targetGroup}|{duration}|{change}|{affected}")`
→ used as `seed` for `random.Random`. Same inputs ⇒ same results (guaranteed
reproducibility: covered by tests).

### Engine loop (`engine.py`) — per month for `duration` months
1. `adoption = 1 − exp(−month / decision_profile["adoption_rate_months"])`
   — a gradual ramp (digital services adopt faster than reorganisations).
2. Per person: `magnitude = change × adoption × behavior_elasticity ×
   sector.behavioral_sensitivity × decision.behavioral_factor`
   weighted by `affected_weight`. Running mean of these is the monthly
   `behavior_change`.
3. `demand_change = behavior_change` (from demand elasticity ~1.0 population
   mean; reported as demand change).
4. Per business: `business_change = demand_change × demand_elasticity ×
   sector.business_sensitivity × decision.business_factor`, mean reported as
   `business_impact`.
5. Per service: `pressure += demand_change × sector.service_sensitivity ×
   decision.service_factor` (bounded, max 100). Mean reported as
   `service_pressure`.
6. Monthly social/economic/service indices use the documented scale below;
   monthly satisfaction uses the documented penalty formula.

### Metric conversion (`metrics.py`)
Single documented scale assumption:

```
impact         = clip(magnitude_mean × sensitivity × factor × IMPACT_SCALE, 0, 100)
                where IMPACT_SCALE = 2.5
satisfaction   = clip(baseline − 0.25×social − 0.20×service − 0.15×economic, 20, 100)
```

`baseline` is the state with **no decision applied**:
- `service_pressure = sector.baseline_service_pressure`
- `satisfaction = sector.baseline_satisfaction`
- social/economic/service indices `0`; behaviour/demand/business change `0`

Since the impact formula is linear in magnitude, the average of the monthly
indices equals the final index for the whole run.

### Baseline risk
The baseline risk reuses the same `RISK_WEIGHTS` but zeroes every contributor
except `duration` (unknown at baseline → 0), `populationExposure` (0) and
`behaviorChange` (0). Social/economic/service/sector sensitivity feed the
baseline, so a high-sensitivity sector can still have a non-zero baseline risk.

`impactVsBaseline` = final − baseline per metric (the headline "what would
change" table).

---

## 5. Risk model (`backend/simulation/risk.py`)

```
risk = SUM over contributors of weight × contributor, clipped to 0–100
```

| Contributor          | Value used                                    | Weight |
|----------------------|-----------------------------------------------|--------|
| `socialImpact`       | final social index (0–100)                    | 0.20   |
| `economicImpact`     | final economic index (0–100)                  | 0.15   |
| `servicePressure`    | final service index (0–100)                   | 0.15   |
| `populationExposure` | `affected` (%)                                | 0.20   |
| `duration`           | `duration / 36 × 100`                         | 0.10   |
| `behaviorChange`     | behaviour change (0–100 magnitude)            | 0.10   |
| `sectorSensitivity`  | average of sector sensitivities, normalised   | 0.10   |

Weights sum to exactly `1.0`; they are returned in
`riskBreakdown.weights` and each computed `contributor`, `factor`, and
`contribution` (value × weight) is returned in `riskBreakdown.items` so the
score is fully transparent.

Level buckets: **Low** `< 35`, **Medium** `35–64`, **High** `≥ 65`
(`RISK_THRESHOLDS`).

The **top risk drivers** in the explanation are derived from the largest
`contribution` values in the breakdown — real computed data, not canned text.

---

## 6. Explanation engine (`backend/simulation/explain.py`)

Builds a deterministic textual explanation from the actual result:
- summary composed from levels and the top contributing factors,
- `topDrivers` listed with their percentage contribution to risk,
- `majorAffectedGroup` derived from the scenario's target group and the
  behavioural response,
- `evidence` pointing at the baseline delta of the strongest metric,
- `recommendation` chosen from the result's own shape (e.g. high service
  pressure ⇒ recommend staging; low economic risk and fast adoption ⇒ no hard
  blockers).

---

## 7. Comparison (`POST /compare`)

Runs both scenarios through the same engine, then builds rows per metric:

```
row = {"metric", "scenarioA", "scenarioB", "difference"}
```

Recommendation: pick the lower risk; small absolute risk difference (≤ 2)
yields "Similar". Response contains both full results (for re-render) plus the
comparison table.

---

## 8. Machine learning / sector intelligence (`backend/ml/`)

> **Critical framing.** This is an **unsupervised, data-informed sector
> intelligence** component. It identifies **patterns and similarities in the
> available dataset**. It is **NOT** a supervised predictive model and does
> **NOT** establish causal relationships or predict actual future policy
> outcomes.
>
> No ML accuracy is claimed anywhere: the silhouette score is a *cluster
> quality* metric, not an accuracy or forecast metric (the dataset has no
> ground-truth decision outcomes to measure accuracy against).

### 8.1 Why unsupervised, not supervised

The packaged GASTAT dataset has no validated historical *decision → outcome*
labels. Supervised learning would require ground-truth outcomes per sector,
which do not exist here; using it would fabricate labels and imply predictive
validity. Unsupervised clustering instead:

- needs no invented labels,
- describes *what the dataset itself looks like* (topical composition and data
  quality) per sector,
- produces bounded, evidence-weighted adjustments to the **documented** sector
  sensitivities.

### 8.2 Dataset limitations

- Small snapshot: 82 raw rows → **81 deduplicated records** across **17 GASTAT
  sectors** (2024–2025).
- Heterogeneous units (tonnes, SAR, beds, minutes, %) — cross-unit averaging
  is statistically invalid and is never performed.
- No decision-outcome labels ⇒ the component cannot and does not learn the
  effectiveness of policies.
- Text fields (sector / indicator / description) are the main signal; numeric
  values are only used as a Verified/Missing **quality flag**, never averaged
  across units.

### 8.3 The 9 ML features (`features.py`)

For each of the 17 dataset sectors a 9-dimension vector is computed:

| # | Feature | Meaning |
|---|---------|---------|
| 1 | `share_economic` | topical composition: fraction of indicator mass tagging the economic dimension |
| 2 | `share_social` | topical composition: fraction tagging the social dimension |
| 3 | `share_service` | topical composition: fraction tagging the service dimension |
| 4 | `share_digital` | topical composition: fraction tagging the digital dimension |
| 5 | `share_environment` | topical composition: fraction tagging the environment dimension |
| 6 | `share_other` | fraction of indicator mass matching no topical keyword |
| 7 | `verified_ratio` | fraction of the sector's rows flagged Verified with a numeric value |
| 8 | `simulation_ready_ratio` | fraction Verified **and** `simulation_ready` |
| 9 | `percent_unit_ratio` | fraction of percent-unit rows |

Every feature is a fraction in `[0, 1]`, and the topical shares partition a
sector's indicators (they sum to ~1.0), so no cross-unit numeric aggregation is
performed.

### 8.4 Keyword-based topical tagging

`TOPIC_KEYWORDS` maps each dimension to lowercase substrings matched against
`"sector + indicator + description"`. `tag_indicator` splits a mass of `1.0`
**equally** among every matched dimension; an indicator matching nothing is
tagged `other`. This derives *what a sector reports on* directly from the
dataset's text rather than from any invented value.

### 8.5 StandardScaler

The 9 features are standardised (`preprocessing.preprocess(..., scale=True)`)
so KMeans distances are not dominated by feature magnitude. The
`scaler_mean` / `scaler_scale` pair is stored on the model and reproduced on
load when model persistence is used.

### 8.6 KMeans

KMeans with a fixed `random_state` (`ML_RANDOM_STATE = 42`) and `n_init = 10`
is used because it is deterministic, interpretable via cluster means, and
cheap to evaluate on a 17-row matrix. The input is the standardised matrix
from 8.5.

### 8.7 Silhouette-based k selection

`k` is **not** arbitrary. The model sweeps `config.ML_K_RANGE` (`2..6`), capped
at `floor(sqrt(n_sectors))` and at `n − 1` (a small-n guard against
over-fragmenting the data), and selects the `k` with the best silhouette
score; degenerate splits are skipped.

### 8.8 Current fitted values

For the packaged dataset: **k = 4**, **silhouette = 0.3089** (deterministic
given the fixed seed and dataset).

### 8.9 The four cluster labels

Cluster labels are **computed from the data** (`_compute_cluster_labels`):
each cluster is named after the topical dimensions whose member-average share
exceeds the dataset average by ≥ 0.05. Result for the packaged dataset:

| Cluster | Label | Members |
|---------|-------|---------|
| 0 | `Economic-oriented` | Business; GDP & National Accounts; Prices & Inflation |
| 1 | `Service & Digital-oriented` | Digital Economy & ICT; Industry; Technology & ICT; Tourism & Hajj; Transportation & Logistics |
| 2 | `Social-oriented` | Education; Healthcare; Housing; Labor Market; Population & Demographics |
| 3 | `Environment-oriented` | Agriculture; Energy & Water; Environment; International Trade |

### 8.10 UI-sector → dataset-sector mapping

A UI sector (what the user picks in the simulation form) maps to one or more
GASTAT dataset sectors via `SECTOR_PROFILES[sector]["dataset_sectors"]`:

| UI sector | Dataset sectors |
|-----------|-----------------|
| Government Services | GDP & National Accounts, Prices & Inflation |
| Economy and Commerce | Business, International Trade, Prices & Inflation |
| Transportation | Transportation & Logistics |
| Healthcare | Healthcare, Population & Demographics |
| Education | Education |
| Technology and Innovation | Technology & ICT, Digital Economy & ICT |

### 8.11 Evidence-weighted aggregation

`ml_insight_for` aggregates the per-dataset-sector insights of a UI sector,
weighting each dataset sector by its **verified-indicator count**
(`inference._verified_weights`). Verified counts for the packaged dataset
(e.g. Transportation & Logistics 9, Industry 8, Education/Healthcare 7) mean
well-evidenced sectors dominate the aggregated profile; weights fall back to
equal weighting only if no verified counts are available.

### 8.12 Sensitivity multiplier methodology

```
profile dimension norm = min-max normalise(share, dataset min, dataset max)
sensitivity blend      = max(norm over the matching dimensions)   # ML_SENSITIVITY_DIMENSIONS
multiplier             = clamp(1 + verifiability × strength × (blend − 0.5), bounds)
```

Each simulation sensitivity follows its strongest matching dimension
(`ML_SENSITIVITY_DIMENSIONS`: `social←social`, `economic←economic`,
`service←service`, `behavioral←(social, digital)`, `business←(economic,
digital)`), so a sector is never penalised on a sensitivity for lacking
indicators in an unrelated dimension.

### 8.13 Verifiability damping

Every multiplier is damped by the sector's `verified_ratio` (verifiability,
`[0, 1]`): sectors whose rows are mostly Verified deviate further from `1.0`,
while sparse or unverified sectors are pulled back towards `1.0` (no change).
Data quality — not raw magnitude — sets how strongly the ML component moves a
sensitivity.

### 8.14 Multiplier bounds

- `ML_MULTIPLIER_STRENGTH = 0.18` ⇒ multiplier bounds `[0.82, 1.18]`
  (`ML_MULTIPLIER_BOUNDS`).
- The **effective** sensitivity, `clamp(base × multiplier, 0.5, 1.6)`
  (`ML_SENSITIVITY_MIN/MAX`), can never leave the documented sensitivity range,
  so ML cannot push the simulation into unreasonable values.

### 8.15 Model caching

`get_sector_model()` (`ml/sector_model.py`) builds the model **once** per
process at first use and caches it; it is **never retrained per request**. The
engine consumes it through `ml_insight_for` on every `/simulate` call.

### 8.16 Optional model persistence

`SABIQ_ML_PERSIST=1` (default off) writes the fitted model to
`models/sector_model.json`. On boot, if the file exists and its `fingerprint`,
`preprocessing_version`, and `model_version` match the current dataset and
config, it is loaded without refitting; otherwise it is refitted and
rewritten. JSON keeps the artifact small and auditable.

### 8.17 API endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/ml/status` | `enabled` / `available` flags, `modelVersion`, `preprocessingVersion`, `clusterCount`, `methodology`, `datasetFingerprint`, dataset sector count, quality |
| `GET /api/ml/sectors` | dataset sectors (cluster + profile) and UI sectors with their ML info (cluster, multipliers, source sectors, similar sectors, key features) |
| `GET /api/ml/sector-profile/<sector>` | full ML insight for a UI (or dataset) sector; `404 INVALID_SECTOR` for unknown names |
| `GET /health` | reports `mlReady` and `mlMethod` |
| `POST /simulate`, `POST /compare` | response embeds `mlInsights` (with `appliedSensitivities`) and `mlMethodologyNote` |

Disabled/unavailable model states never break the simulation: the API returns
`ML_DISABLED` / `ML_UNAVAILABLE` errors with HTTP `503`, the sector-profile
endpoint returns `404` for a truly unknown sector, and the engine always falls
back to the base sensitivities when ML is unavailable.

### 8.18 How ML affects agent sensitivities

`apply_ml_sensitivities` in `engine.py` blends the ML multipliers into the
**documented** base sensitivities while keeping both auditable:

- `sectorProfileUsed.sensitivities` documents the **original assumptions**
  (unchanged by ML),
- the **effective** sensitivities (`clamp(base × multiplier, min, max)`) drive
  the monthly agent loop, the impact indices, the metrics, and the sector
  sensitivity index,
- `mlInsights.appliedSensitivities` reports exactly the values the simulation
  used.

If ML is disabled or unavailable, no adjustment happens: the base profile is
used unchanged and `mlInsights.enabled = false`. This keeps `/simulate`
deterministic and fail-open.

### 8.19 Scientific limitations

- **No prediction or causality:** the component only describes patterns inside
  the packaged dataset. It does not predict actual future policy outcomes.
- The silhouette score measures cluster compactness/separation, **not** the
  accuracy of any forecast.
- Keyword tags are heuristic substring matches, not a curated taxonomy.
- The dataset is a small 2024–2025 snapshot (17 sectors, 81 deduplicated
  records).
- Cluster labels are data-derived descriptions, not policy findings.
- ML-adjusted sensitivities are bounded and damped, yet remain **simulation
  assumptions** — never calibrated coefficients.

---

## 9. Security / hardening (`backend/app.py`)

- `app.config["MAX_CONTENT_LENGTH"] = 64 KB` → `PAYLOAD_TOO_LARGE` (413)
- CORS restricted to `ALLOWED_ORIGINS` (SPA same-origin; listed origins only).
- In-memory sliding-window rate limiter (`RATE_LIMIT_PER_MINUTE`) →
  `RATE_LIMITED` (429).
- Error handlers return JSON, never tracebacks (`INTERNAL_ERROR`).
- Static serving: only GET, path normalised, denies `backend/`, `tests/`,
  `.git`, `..` traversal and any extension outside the allow-list
  (`html`, `css`, `js`, `svg`, `json`, `md`). Backend sources return 404.
- `GET /health` with `datasetLoaded`, `mlReady`, and `mlMethod` status.
- The `/api/ml/*` routes are covered by the same CORS allow-list and JSON error
  handling; unknown API routes fall through to `404 NOT_FOUND`.
- The app is created through a factory (`create_app`) and the WSGI global is
  `app` (Gunicorn compatible), plus `run.py` for development.

---

## 10. Extending the platform

### New decision type
1. Add profile to `DECISION_PROFILES` in `backend/config.py`
   (5 factors + `adoption_rate_months` + `friction` + `summary`).
2. Add an `<option>` in `simulation.html`.
3. Tests in `tests/` already assert "different decision types give different
   results"; the new type will participate automatically.

### New sector
1. Add profile to `SECTOR_PROFILES` in `backend/config.py`
   (5 sensitivities + baselines + `dataset_sectors`).
2. Add an `<option>` in `simulation.html`.
3. Optionally map to GASTAT sectors for richer `datasetContext`.

### Tuning
- Risk weights → `RISK_WEIGHTS`.
- Risk labels → `RISK_THRESHOLDS`.
- Impact magnitude → `IMPACT_SCALE`.
- Satisfaction sensitivity → `SATISFACTION_WEIGHTS` / `SATISFACTION_FLOOR`.
- Adoption speed → `adoption_rate_months` per decision.
- Agent counts → `AGENT_COUNTS`.
- Rate limit → `SABIQ_RATE_LIMIT` env or `RATE_LIMIT_PER_MINUTE`.

### Adding a dataset field
The loader reads all CSV columns; expose new aggregations in
`DatasetService.sector_summaries()` and render them in `script.js`
(`datasetContext`).

---

## 11. Reproducibility & test strategy

- All agents derive from the scenario seed ⇒ **same input, same output**
  (asserted in `tests/test_simulation.py`).
- Ranges asserted (risk 0–100, indices 0–100, satisfaction 20–100,
  agents = 1210, positivity of behaviour change for change > 0).
- Structural `<keys of result>` asserted so the dashboard contract is stable.
- API tests: missing fields, out-of-range values, unknown sector/decision,
  non-object JSON, unknown routes, oversized body, rate-limit code path.
- Dataset tests: file exists, dedupe works, verified/missing flags, sector
  summary structure, cross-unit averaging guard.
- ML tests (implementation consistency — **not** predictive accuracy): model
  trains; `k` comes from the configured range; cluster labels valid; silhouette
  exists and is finite; every UI sector yields a JSON-serialisable insight;
  multipliers stay inside `ML_MULTIPLIER_BOUNDS`; applied sensitivities stay
  inside `ML_SENSITIVITY_MIN/MAX`; ML failure never breaks the simulation; the
  `/api/ml/*` endpoints and `mlReady` health field behave correctly.

Run: `python -m pytest tests -v`