// ============================
// SABIQ Frontend Script
// ============================

// The API base URL is configurable. When the pages are served by the Flask
// app we talk to the same origin; when opened directly from disk we fall back
// to the local development server.
const API_BASE = (function () {
    const protocol = window.location.protocol;
    if (protocol === "http:" || protocol === "https:") {
        return window.location.origin;
    }
    return "http://127.0.0.1:5000";
})();

const STORAGE_CURRENT = "govTwinSimulation";
const STORAGE_HISTORY = "sabiqHistory";
const STORAGE_SCENARIO_A = "sabiqScenarioA";
const STORAGE_COMPARISON = "sabiqComparison";
const SESSION_COMPARE_MODE = "sabiqCompareMode";

// ----------------------------
// Helpers
// ----------------------------

function getQueryParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name);
}

function storeSimulation(result) {
    result.simulationDate = new Date().toISOString();
    localStorage.setItem(STORAGE_CURRENT, JSON.stringify(result));
    addToHistory(result);
}

function addToHistory(result) {
    let history = [];
    try {
        history = JSON.parse(localStorage.getItem(STORAGE_HISTORY) || "[]");
    } catch (e) {
        history = [];
    }
    history.unshift({
        decisionType: result.decisionType || "Decision",
        sector: result.sector || "--",
        risk: result.risk,
        riskLevel: result.riskLevel || "--",
        simulationDate: result.simulationDate || new Date().toISOString()
    });
    if (history.length > 50) {
        history = history.slice(0, 50);
    }
    localStorage.setItem(STORAGE_HISTORY, JSON.stringify(history));
}

function formatDate(isoString) {
    try {
        return new Date(isoString).toLocaleDateString("en-US", {
            year: "numeric",
            month: "long",
            day: "numeric"
        });
    } catch (e) {
        return isoString || "--";
    }
}

function friendlyError(error) {
    if (error && error.error) {
        return error.error.message || "The request could not be processed.";
    }
    return "Unable to connect to the simulation engine. Please make sure the server is running.";
}

// ----------------------------
// Page actions
// ----------------------------

function startSimulation() {
    window.location.href = "simulation.html";
}

function login() {
    alert("Login will be activated in the next version.");
}

function learnMore() {
    const about = document.getElementById("about");
    if (about) {
        about.scrollIntoView({ behavior: "smooth" });
    }
}

// ----------------------------
// Sliders
// ----------------------------

const changeSlider = document.getElementById("changeSlider");
const changeValue = document.getElementById("changeValue");

if (changeSlider && changeValue) {
    changeSlider.addEventListener("input", function () {
        changeValue.textContent = this.value + "%";
    });
}

const peopleSlider = document.getElementById("peopleSlider");
const peopleValue = document.getElementById("peopleValue");

if (peopleSlider && peopleValue) {
    peopleSlider.addEventListener("input", function () {
        peopleValue.textContent = this.value + "%";
    });
}

// ----------------------------
// Comparison mode banner
// ----------------------------

(function setupCompareBanner() {
    if (sessionStorage.getItem(SESSION_COMPARE_MODE) === "1") {
        const banner = document.getElementById("compareBanner");
        if (banner) {
            banner.style.display = "block";
        }
    }
})();

// ----------------------------
// Run Simulation
// ----------------------------

function readScenarioInputs() {
    const durationInput = document.querySelector('input[name="duration"]:checked');
    return {
        decisionType: document.getElementById("decisionType").value,
        sector: document.getElementById("sector").value,
        targetGroup: document.getElementById("targetGroup").value,
        duration: Number(durationInput ? durationInput.value : 12),
        change: Number(document.getElementById("changeSlider").value),
        affected: Number(document.getElementById("peopleSlider").value)
    };
}

async function runSimulation() {
    const simulationData = readScenarioInputs();

    const button = document.querySelector('.form-actions .primary-btn');
    if (button) {
        button.disabled = true;
        button.textContent = "Running...";
    }

    try {
        const response = await fetch(API_BASE + "/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(simulationData)
        });

        const body = await response.json().catch(function () { return null; });

        if (!response.ok) {
            throw new Error(friendlyError(body));
        }

        storeSimulation(body);

        // Comparison flow: scenario A was stored earlier, B is the run just made.
        if (sessionStorage.getItem(SESSION_COMPARE_MODE) === "1") {
            let scenarioA = null;
            try {
                scenarioA = JSON.parse(localStorage.getItem(STORAGE_SCENARIO_A) || "null");
            } catch (e) {
                scenarioA = null;
            }

            if (scenarioA && scenarioA.inputs) {
                const compareResponse = await fetch(API_BASE + "/compare", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        scenarioA: scenarioA.inputs,
                        scenarioB: simulationData
                    })
                });

                const compareBody = await compareResponse.json().catch(function () { return null; });

                if (!compareResponse.ok) {
                    throw new Error(friendlyError(compareBody));
                }

                localStorage.setItem(STORAGE_COMPARISON, JSON.stringify(compareBody));
                sessionStorage.removeItem(SESSION_COMPARE_MODE);
                localStorage.removeItem(STORAGE_SCENARIO_A);

                window.location.href = "results.html?comparison=1";
                return;
            }
        }

        window.location.href = "results.html";
    } catch (error) {
        console.error(error);
        alert(error.message || "Unable to connect to the simulation engine. Please make sure the server is running.");
        if (button) {
            button.disabled = false;
            button.textContent = "Run Simulation";
        }
    }
}

// Save the current result as "Scenario A" and go configure scenario B.
function compareScenario() {
    const savedData = localStorage.getItem(STORAGE_CURRENT);
    if (!savedData) {
        alert("No previous simulation is available to compare against.");
        return;
    }

    let result = null;
    try {
        result = JSON.parse(savedData);
    } catch (e) {
        result = null;
    }
    if (!result) {
        alert("The stored simulation could not be read.");
        return;
    }

    const inputs = {
        decisionType: result.decisionType,
        sector: result.sector,
        targetGroup: result.targetGroup,
        duration: result.duration,
        change: result.change,
        affected: result.affected
    };

    localStorage.setItem(STORAGE_SCENARIO_A, JSON.stringify({ inputs: inputs, result: result }));
    sessionStorage.setItem(SESSION_COMPARE_MODE, "1");
    window.location.href = "simulation.html";
}

// ----------------------------
// Results Renderer
// ----------------------------

function renderSimulationResults() {
    const savedData = localStorage.getItem(STORAGE_CURRENT);
    if (!savedData) {
        const status = document.getElementById("simulationStatus");
        if (status) {
            status.textContent = "No simulation data found. Please run a simulation first.";
        }
        return;
    }

    let data = null;
    try {
        data = JSON.parse(savedData);
    } catch (e) {
        data = null;
    }
    if (!data) {
        return;
    }

    // Scenario header / meta -------------------------------------------
    const subtitle = document.getElementById("resultSubtitle");
    if (subtitle) {
        subtitle.textContent =
            (data.decisionType || "Decision") +
            " — " + (data.sector || "Sector") +
            " — simulated over " + (data.duration || 12) + " month(s)";
    }

    const status = document.getElementById("simulationStatus");
    if (status) {
        status.textContent =
            "The hypothetical scenario was analyzed for " +
            (data.duration || 12) + " month(s). " +
            (data.methodologyNote || "");
    }

    const dateElement = document.getElementById("simulationDate");
    if (dateElement) {
        dateElement.textContent = formatDate(data.simulationDate);
    }

    // Risk --------------------------------------------------------------
    const risk = Number(data.risk) || 0;
    const riskLevelName = data.riskLevel || (risk >= 65 ? "High" : risk >= 35 ? "Medium" : "Low");

    const riskScore = document.getElementById("riskScore");
    if (riskScore) {
        riskScore.textContent = risk;
    }

    const riskLevel = document.getElementById("riskLevel");
    if (riskLevel) {
        riskLevel.textContent = "Risk Level: " + riskLevelName;
    }

    const riskBar = document.querySelector(".risk-bar div");
    if (riskBar) {
        riskBar.style.width = risk + "%";
    }

    const riskDescription = document.getElementById("riskDescription");
    if (riskDescription) {
        if (riskLevelName === "High") {
            riskDescription.textContent =
                "The scenario carries a high simulated level of risk and requires careful review before implementation.";
        } else if (riskLevelName === "Medium") {
            riskDescription.textContent =
                "The scenario carries a moderate simulated level of risk and can be improved by modifying the decision.";
        } else {
            riskDescription.textContent =
                "The scenario carries a low simulated level of risk and its expected impacts can be managed.";
        }
    }

    // Impact summary (displayed values come straight from the engine) ---
    const socialImpact = document.getElementById("socialImpact");
    const economicImpact = document.getElementById("economicImpact");
    const servicePressure = document.getElementById("servicePressure");
    const satisfaction = document.getElementById("satisfaction");

    if (socialImpact) { socialImpact.textContent = Math.round(Number(data.social) || 0); }
    if (economicImpact) { economicImpact.textContent = Math.round(Number(data.economic) || 0); }
    if (servicePressure) { servicePressure.textContent = Math.round(Number(data.service) || 0); }
    if (satisfaction) { satisfaction.textContent = Math.round(Number(data.satisfaction) || 0) + "%"; }

    // Risk breakdown -----------------------------------------------------
    renderRiskBreakdown(data.riskBreakdown);

    // Explanation --------------------------------------------------------
    renderExplanation(data.explanation);

    // Baseline / before-vs-after ----------------------------------------
    renderBaseline(data);

    // Scenario context / assumptions -------------------------------------
    renderScenarioContext(data);

    // AI / ML sector intelligence -----------------------------------------
    renderMLInsights(data);

    // Agent statistics ---------------------------------------------------
    const agentsSimulated = document.getElementById("agentsSimulated");
    if (agentsSimulated) { agentsSimulated.textContent = data.agentsSimulated ?? "--"; }

    const peopleAgents = document.getElementById("peopleAgents");
    if (peopleAgents) { peopleAgents.textContent = data.peopleAgents ?? "--"; }

    const businessAgents = document.getElementById("businessAgents");
    if (businessAgents) { businessAgents.textContent = data.businessAgents ?? "--"; }

    const governmentAgents = document.getElementById("governmentAgents");
    if (governmentAgents) { governmentAgents.textContent = data.governmentAgents ?? "--"; }

    // Detailed impact -----------------------------------------------------
    const behaviorChange = document.getElementById("behaviorChange");
    if (behaviorChange) {
        behaviorChange.textContent = data.behaviorChange != null ? data.behaviorChange + "%" : "--";
    }

    const demandChange = document.getElementById("demandChange");
    if (demandChange) {
        demandChange.textContent = data.demandChange != null ? data.demandChange + "%" : "--";
    }

    const businessImpact = document.getElementById("businessImpact");
    if (businessImpact) { businessImpact.textContent = data.businessImpact ?? "--"; }

    const governmentPressure = document.getElementById("governmentPressure");
    if (governmentPressure) { governmentPressure.textContent = data.servicePressure ?? "--"; }

    // Butterfly effect ----------------------------------------------------
    const decision = data.decisionType || "Selected Decision";

    const dominoDecision = document.getElementById("dominoDecision");
    if (dominoDecision) { dominoDecision.textContent = decision; }

    const dominoBehavior = document.getElementById("dominoBehavior");
    if (dominoBehavior) { dominoBehavior.textContent = "Changed by " + (data.behaviorChange ?? 0) + "%"; }

    const dominoService = document.getElementById("dominoService");
    if (dominoService) { dominoService.textContent = "Demand changed by " + (data.demandChange ?? 0) + "%"; }

    const dominoEconomic = document.getElementById("dominoEconomic");
    if (dominoEconomic) { dominoEconomic.textContent = "Economic impact: " + (data.businessImpact ?? 0); }

    // Recommendation -------------------------------------------------------
    const recommendationTitle = document.getElementById("recommendationTitle");
    const recommendationText = document.getElementById("recommendationText");

    if (recommendationTitle && recommendationText) {
        recommendationTitle.textContent = (data.recommendation && data.recommendation.title) || "--";
        recommendationText.textContent = (data.recommendation && data.recommendation.text) || "No recommendation is available.";
    }

    // Monthly chart (uses engine data; no fabricated fallback) ------------
    createSimulationChart(Array.isArray(data.monthlyResults) ? data.monthlyResults : [], data.duration);
}

// ----------------------------
// Risk Breakdown
// ----------------------------

function renderRiskBreakdown(breakdown) {
    const container = document.getElementById("riskBreakdownList");
    if (!container) { return; }

    container.innerHTML = "";

    if (!breakdown || !breakdown.items || !breakdown.items.length) {
        container.innerHTML = "<p>No risk breakdown is available.</p>";
        return;
    }

    breakdown.items.forEach(function (item) {
        const row = document.createElement("div");
        row.className = "breakdown-row";

        const info = document.createElement("div");
        info.className = "breakdown-info";

        const label = document.createElement("span");
        label.className = "breakdown-label";
        label.textContent = item.factor + " (weight " + item.weight.toFixed(2) + ")";

        const value = document.createElement("strong");
        value.textContent = item.value + " / 100";

        info.appendChild(label);
        info.appendChild(value);

        const track = document.createElement("div");
        track.className = "breakdown-track";

        const fill = document.createElement("div");
        fill.className = "breakdown-fill";
        fill.style.width = Math.max(2, Math.min(100, item.value)) + "%";
        fill.title = item.factor;

        track.appendChild(fill);

        const contribution = document.createElement("span");
        contribution.className = "breakdown-contribution";
        contribution.textContent = "→ " + item.contribution.toFixed(1) + " risk points";

        row.appendChild(info);
        row.appendChild(track);
        row.appendChild(contribution);

        container.appendChild(row);
    });
}

// ----------------------------
// Explanation
// ----------------------------

function renderExplanation(explanation) {
    const summary = document.getElementById("explanationSummary");
    if (summary && explanation) {
        summary.textContent = explanation.summary || "--";
    }

    const drivers = document.getElementById("explanationDrivers");
    if (drivers) {
        drivers.innerHTML = "";
        const list = explanation && explanation.topDrivers && explanation.topDrivers.length
            ? explanation.topDrivers
            : ["No drivers available."];
        list.forEach(function (text) {
            const item = document.createElement("li");
            item.textContent = text;
            drivers.appendChild(item);
        });
    }

    const group = document.getElementById("explanationGroup");
    if (group && explanation) {
        group.textContent = explanation.majorAffectedGroup || "--";
    }

    const evidence = document.getElementById("explanationEvidence");
    if (evidence && explanation) {
        evidence.textContent = explanation.evidence || "--";
    }
}

// ----------------------------
// Baseline (before vs after)
// ----------------------------

function signed(value, decimals) {
    if (value === null || value === undefined || isNaN(value)) {
        return "";
    }
    const number = Number(value);
    const prefix = number > 0 ? "+" : "";
    return "(" + prefix + number.toFixed(decimals != null ? decimals : 1) + ")";
}

function renderBaseline(data) {
    const vs = data.impactVsBaseline || {};
    const base = data.baseline || {};

    const map = {
        blSocialValue: { v: data.social, d: vs.social },
        blEconomicValue: { v: data.economic, d: vs.economic },
        blServiceValue: { v: data.servicePressure, d: vs.servicePressure },
        blSatisfactionValue: { v: data.satisfaction != null ? data.satisfaction + "%" : "--", d: vs.satisfaction },
        blBehaviorValue: { v: data.behaviorChange != null ? data.behaviorChange + "%" : "--", d: vs.behaviorChange },
        blBusinessValue: { v: data.businessImpact, d: vs.businessImpact },
        blRiskValue: { v: data.risk, d: vs.risk }
    };

    Object.keys(map).forEach(function (valueId) {
        const suffix = valueId.replace("Value", "Delta");
        const valueEl = document.getElementById(valueId);
        const deltaEl = document.getElementById(suffix);
        if (valueEl) { valueEl.textContent = map[valueId].v ?? "--"; }
        if (deltaEl) {
            const delta = map[valueId].d;
            if (delta === null || delta === undefined || isNaN(delta)) {
                deltaEl.textContent = "";
            } else {
                deltaEl.textContent = signed(delta, delta % 1 === 0 ? 0 : 1);
            }
        }
    });
}

// ----------------------------
// Scenario context / assumptions
// ----------------------------

function contextList(containerId, items) {
    const container = document.getElementById(containerId);
    if (!container) { return; }
    container.innerHTML = "";
    if (!items || !items.length) {
        const item = document.createElement("li");
        item.textContent = "No information supplied.";
        container.appendChild(item);
        return;
    }
    items.forEach(function (text) {
        const item = document.createElement("li");
        item.textContent = text;
        container.appendChild(item);
    });
}

function renderScenarioContext(data) {
    const profile = data.sectorProfileUsed;
    const decision = data.decisionProfileUsed;
    const dataset = data.datasetContext;

    // Sector profile
    const sectorLine = document.getElementById("sectorProfileLine");
    if (sectorLine && profile) {
        sectorLine.textContent =
            "Sector: " + profile.sector +
            " — baseline satisfaction " + Number(profile.baselineSatisfaction).toFixed(1) +
            " / 100 (" + (profile.baselineSatisfactionSource || "assumption") +
            "), baseline service pressure " + Number(profile.baselineServicePressure).toFixed(1) + " / 100.";
    }

    if (profile && profile.sensitivities) {
        const s = profile.sensitivities;
        contextList("sectorSensitivities", [
            "Social sensitivity: " + s.social,
            "Economic sensitivity: " + s.economic,
            "Service sensitivity: " + s.service,
            "Behavioral sensitivity: " + s.behavioral,
            "Business sensitivity: " + s.business
        ]);
    }

    // Decision profile
    const decisionLine = document.getElementById("decisionProfileLine");
    if (decisionLine && decision) {
        decisionLine.textContent =
            "Decision type: " + decision.decisionType +
            " — adoption rate ~" + decision.adoptionRateMonths + " month(s), " +
            "implementation friction " + decision.friction + " / 1.";
    }

    if (decision && decision.factors) {
        const f = decision.factors;
        contextList("decisionFactors", [
            "Social factor: " + f.social_factor,
            "Economic factor: " + f.economic_factor,
            "Service factor: " + f.service_factor,
            "Behavioral factor: " + f.behavioral_factor,
            "Business factor: " + f.business_factor,
            "Model note: " + (decision.summary || "")
        ]);
    }

    // Dataset context
    const datasetLine = document.getElementById("datasetContextLine");
    if (datasetLine && dataset) {
        if (dataset.used) {
            datasetLine.textContent =
                "Loaded — " + dataset.verifiedIndicatorCount + " verified indicators from " +
                dataset.sourceSectors.join(", ") +
                " (GASTAT 2024–2025). Basin satisfaction source: " +
                (dataset.baselineSatisfactionSource || "--");
        } else {
            datasetLine.textContent = dataset.note || "Dataset not used.";
        }
    }

    if (dataset && dataset.notableIndicators) {
        const items = dataset.notableIndicators.slice(0, 6).map(function (ind) {
            return ind.indicator + ": " + ind.value + " " + ind.unit + " (" + ind.year + ", " + ind.source + ")";
        });
        if (!items.length) {
            items.push("No percent-unit indicators for the mapped dataset sectors.");
        }
        contextList("datasetIndicators", items);
    }

    const methodology = document.getElementById("methodologyNote");
    if (methodology) {
        methodology.textContent = data.methodologyNote || "Simulated impact only.";
    }
}

// ----------------------------
// AI / ML Sector Intelligence
// ----------------------------

function formatNumber(value, digits) {
    if (value === null || value === undefined || isNaN(Number(value))) {
        return "--";
    }
    return Number(value).toFixed(digits != null ? digits : 4);
}

function renderMLInsights(data) {
    const section = document.getElementById("mlSection");
    if (!section) {
        return;
    }

    const ml = data.mlInsights;
    const hasInsights = Boolean(ml && typeof ml === "object");
    const enabled = Boolean(hasInsights && ml.enabled);

    // Always show the section. Old stored results (produced before the ML
    // layer existed) render a clear "not available" state instead of hiding
    // the section; a fresh run populates it from the backend's mlInsights.
    section.style.display = "block";

    const sensitivityNames = {
        social: "Social",
        economic: "Economic",
        service: "Service",
        behavioral: "Behavioral",
        business: "Business"
    };

    // Enabled / disabled status badge
    const badge = document.getElementById("mlStatusBadge");
    if (badge) {
        badge.className = enabled ? "tag-on" : "tag-off";
        badge.textContent = enabled ? "Enabled" : "Not available";
    }

    const statusText = document.getElementById("mlStatusText");
    if (statusText) {
        statusText.textContent = enabled
            ? "Applied to this run (" + (ml.method || "unsupervised clustering") + ")."
            : (hasInsights && ml.explanation) ||
                "ML sector intelligence is unavailable for this result. Run a simulation to include dataset-derived sector intelligence.";
    }

    // Cluster
    const hasCluster = enabled && ml.cluster !== null && ml.cluster !== undefined;
    contextList("mlClusterList", hasCluster
        ? [
            "Cluster number: " + ml.cluster,
            "Cluster label: " + (ml.clusterLabel || "Unlabelled")
        ]
        : ["No cluster was assigned (model not available)."]);

    // Similar sectors
    const similar = hasInsights && Array.isArray(ml.similarSectors) ? ml.similarSectors : [];
    contextList("mlSimilarSectors", similar.length
        ? similar.map(function (item) {
            return (item.sector || "--") + " — similarity " + formatNumber(item.similarity, 4);
        })
        : ["No similar sectors available."]);

    // Key features
    const features = hasInsights && Array.isArray(ml.keyFeatures) ? ml.keyFeatures : [];
    contextList("mlKeyFeatures", features.length
        ? features.map(function (item) {
            return item.feature + ": " + formatNumber(item.share, 4) +
                " (dataset average " + formatNumber(item.datasetAverage, 4) + ")";
        })
        : ["No key features available."]);

    // ML sensitivity multipliers
    const multipliers = enabled && ml.multipliers ? ml.multipliers : {};
    const multiplierItems = enabled
        ? Object.keys(sensitivityNames).map(function (key) {
            return sensitivityNames[key] + ": " + formatNumber(multipliers[key], 4);
        })
        : ["Not applied — the documented base sector profile was used."];
    contextList("mlMultipliers", multiplierItems);

    // Applied sensitivities
    const applied = enabled && ml.appliedSensitivities ? ml.appliedSensitivities : {};
    const appliedItems = enabled
        ? Object.keys(sensitivityNames).map(function (key) {
            return sensitivityNames[key] + ": " + formatNumber(applied[key], 4);
        })
        : ["Base sector profile was used for this run."];
    contextList("mlAppliedSensitivities", appliedItems);

    // Data quality
    const quality = hasInsights && ml.quality ? ml.quality : {};
    const qualityItems = [];
    if (enabled) {
        if (quality.silhouetteScore !== null && quality.silhouetteScore !== undefined) {
            qualityItems.push("Cluster quality (silhouette): " + formatNumber(quality.silhouetteScore, 4));
        }
        qualityItems.push("Cluster count: " + (quality.clusterCount != null ? quality.clusterCount : "--"));
        qualityItems.push("Model version: " + (quality.modelVersion || "--"));
        qualityItems.push("Preprocessing version: " + (quality.preprocessingVersion || "--"));
        qualityItems.push("Method: " + (quality.method || ml.method || "unsupervised clustering"));
        const profile = hasInsights && ml.sectorProfile ? ml.sectorProfile : {};
        if (profile.verifiability !== undefined) {
            qualityItems.push("Verified indicator coverage: " + formatNumber(profile.verifiability, 4));
        }
    } else {
        qualityItems.push("No model quality data available.");
    }
    contextList("mlQuality", qualityItems);

    // Scientific explanation
    const explanation = document.getElementById("mlExplanation");
    if (explanation) {
        explanation.textContent = (hasInsights && ml.explanation) ||
            "Unsupervised ML identifies patterns and similarities in the dataset. " +
            "It does not predict actual future policy outcomes.";
    }
}

// ----------------------------
// Scenario Comparison
// ----------------------------

function renderComparison(comparisonData) {
    const section = document.getElementById("comparisonSection");
    if (!section || !comparisonData) { return; }

    section.style.display = "block";

    const comp = comparisonData.comparison || {};

    const summary = document.getElementById("comparisonSummary");
    if (summary) { summary.textContent = comp.summary || "--"; }

    const a = comp.scenarioA || {};
    const b = comp.scenarioB || {};

    const aLabel = document.getElementById("compareALabel");
    if (aLabel) { aLabel.textContent = (a.label || "Scenario A") + " — " + (a.sector || ""); }
    const aRisk = document.getElementById("compareARisk");
    if (aRisk) { aRisk.textContent = (a.risk ?? "--") + " / 100"; }
    const aLevel = document.getElementById("compareARiskLevel");
    if (aLevel) { aLevel.textContent = "Risk level: " + (a.riskLevel || "--"); }

    const bLabel = document.getElementById("compareBLabel");
    if (bLabel) { bLabel.textContent = (b.label || "Scenario B") + " — " + (b.sector || ""); }
    const bRisk = document.getElementById("compareBRisk");
    if (bRisk) { bRisk.textContent = (b.risk ?? "--") + " / 100"; }
    const bLevel = document.getElementById("compareBRiskLevel");
    if (bLevel) { bLevel.textContent = "Risk level: " + (b.riskLevel || "--"); }

    const tbody = document.getElementById("comparisonTable");
    if (tbody) {
        tbody.innerHTML = "";
        (comp.items || []).forEach(function (item) {
            const row = document.createElement("tr");
            [
                item.metric,
                item.valueA,
                item.valueB,
                (item.delta > 0 ? "+" : "") + item.delta,
                item.better
            ].forEach(function (cellText) {
                const td = document.createElement("td");
                td.textContent = cellText;
                row.appendChild(td);
            });
            tbody.appendChild(row);
        });
    }

    const note = document.getElementById("comparisonNote");
    if (note) { note.textContent = comp.note || "Simulated outputs only."; }
}

// ----------------------------
// Monthly Chart
// ----------------------------

function createSimulationChart(monthlyResults, duration) {
    const chart = document.getElementById("simulationChart");
    const labels = document.getElementById("chartLabels");
    const durationFilter = document.getElementById("durationFilter");

    if (!chart || !labels) {
        return;
    }

    function drawChart() {
        chart.innerHTML = "";
        labels.innerHTML = "";

        if (!monthlyResults || monthlyResults.length === 0) {
            const message = document.createElement("p");
            message.className = "chart-empty";
            message.textContent = "No monthly simulation data available.";
            chart.appendChild(message);
            return;
        }

        let selectedDuration = durationFilter
            ? Number(durationFilter.value)
            : monthlyResults.length;

        if (!selectedDuration || selectedDuration <= 0) {
            selectedDuration = monthlyResults.length;
        }

        const selected = monthlyResults.slice(0, selectedDuration);

        selected.forEach(function (item) {
            const column = document.createElement("div");
            column.className = "chart-column";

            const bar = document.createElement("div");
            bar.className = "chart-bar";

            // Normalized simulated impact index for the month
            const components = [
                Math.abs(Number(item.behavior) || 0),
                Math.abs(Number(item.demand) || 0),
                Math.abs(Number(item.business) || 0),
                Math.abs(Number(item.service) || 0)
            ];
            const impactIndex = components.reduce(function (acc, c) {
                return acc + c;
            }, 0) / components.length;

            const height = Math.max(4, Math.min(100, impactIndex));
            bar.style.height = height + "%";

            bar.title =
                "Month " + item.month +
                " | Behaviour: " + (item.behavior ?? "--") +
                " | Demand: " + (item.demand ?? "--") +
                " | Business: " + (item.business ?? "--") +
                " | Service pressure: " + (item.service ?? "--") +
                " | Satisfaction: " + (item.satisfaction ?? "--") + "%";

            column.appendChild(bar);
            chart.appendChild(column);

            const label = document.createElement("span");
            label.textContent = "M" + item.month;
            labels.appendChild(label);
        });
    }

    drawChart();

    if (durationFilter) {
        durationFilter.addEventListener("change", drawChart);
        if (duration && [3, 6, 12].indexOf(Number(duration)) !== -1) {
            durationFilter.value = String(duration);
        }
    }
}

// ----------------------------
// Page bootstraps
// ----------------------------

if (window.location.pathname.includes("results.html")) {
    // Restore the last simulation result first, then overlay the comparison.
    renderSimulationResults();

    if (getQueryParam("comparison") === "1") {
        let comparisonData = null;
        try {
            comparisonData = JSON.parse(localStorage.getItem(STORAGE_COMPARISON) || "null");
        } catch (e) {
            comparisonData = null;
        }
        if (comparisonData) {
            // Keep scenario B's result in view and show the comparison table.
            renderComparison(comparisonData);
        }
    }
}

if (window.location.pathname.includes("reports.html")) {
    renderReportHistory();
}

// ----------------------------
// Reports history
// ----------------------------

function renderReportHistory() {
    let history = [];
    try {
        history = JSON.parse(localStorage.getItem(STORAGE_HISTORY) || "[]");
    } catch (e) {
        history = [];
    }

    const countLabel = document.querySelector(".reports-header p");
    if (countLabel) {
        countLabel.textContent =
            history.length + (history.length === 1 ? " report available" : " reports available");
    }

    const table = document.getElementById("historyRows");
    if (!table) { return; }

    table.innerHTML = "";

    if (!history.length) {
        const row = document.createElement("div");
        row.className = "table-row";
        row.innerHTML =
            '<strong>No reports yet</strong>' +
            '<span>--</span><span>--</span><span>--</span>' +
            '<span>Run a simulation to generate your first report.</span>';
        table.appendChild(row);
        return;
    }

    history.forEach(function (entry) {
        const row = document.createElement("div");
        row.className = "table-row";

        const levelClass = String(entry.riskLevel || "").toLowerCase();
        row.innerHTML =
            '<strong></strong>' +
            '<span></span>' +
            '<span class="' + levelClass + '"></span>' +
            '<span></span>' +
            '<a href="results.html">View Report</a>';

        row.children[0].textContent = entry.decisionType;
        row.children[1].textContent = entry.sector;
        row.children[2].textContent = entry.riskLevel || "--";
        row.children[3].textContent = formatDate(entry.simulationDate);

        table.appendChild(row);
    });
}

// ----------------------------
// Login Modal
// ----------------------------

function openLogin() {
    const modal = document.getElementById("loginModal");
    if (modal) {
        modal.style.display = "flex";
    }
}

function closeLogin() {
    const modal = document.getElementById("loginModal");
    if (modal) {
        modal.style.display = "none";
    }
}

function demoLogin(event) {
    event.preventDefault();
    alert("Login successful - Demo Mode");
    closeLogin();
}

// ----------------------------
// Privacy
// ----------------------------

function openPrivacy() {
    const modal = document.getElementById("privacyModal");
    if (modal) {
        modal.style.display = "flex";
    }
}

function closePrivacy() {
    const modal = document.getElementById("privacyModal");
    if (modal) {
        modal.style.display = "none";
    }
}