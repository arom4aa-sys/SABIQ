// ============================
// Start Simulation
// ============================

function startSimulation() {

    window.location.href = "simulation.html";

}


// ============================
// Login
// ============================

function login() {

    alert(
        "Login will be activated in the next version."
    );

}


// ============================
// Learn More
// ============================

function learnMore() {

    const about =
        document.getElementById("about");

    if (about) {

        about.scrollIntoView({
            behavior: "smooth"
        });

    }

}


// ============================
// Sliders
// ============================

const changeSlider =
    document.getElementById(
        "changeSlider"
    );

const changeValue =
    document.getElementById(
        "changeValue"
    );


if (changeSlider && changeValue) {

    changeSlider.addEventListener(
        "input",
        function () {

            changeValue.textContent =
                this.value + "%";

        }
    );

}


const peopleSlider =
    document.getElementById(
        "peopleSlider"
    );

const peopleValue =
    document.getElementById(
        "peopleValue"
    );


if (peopleSlider && peopleValue) {

    peopleSlider.addEventListener(
        "input",
        function () {

            peopleValue.textContent =
                this.value + "%";

        }
    );

}


// ============================
// Run Simulation
// ============================

async function runSimulation() {

    const simulationData = {

        decisionType:
            document.getElementById(
                "decisionType"
            ).value,

        sector:
            document.getElementById(
                "sector"
            ).value,

        targetGroup:
            document.getElementById(
                "targetGroup"
            ).value,

        duration:
            document.querySelector(
                'input[name="duration"]:checked'
            ).value,

        change:
            Number(
                document.getElementById(
                    "changeSlider"
                ).value
            ),

        affected:
            Number(
                document.getElementById(
                    "peopleSlider"
                ).value
            )

    };

       try {

    const response =
        await fetch(
            "/simulate",
            {

                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(
                        simulationData
                    )

            }
        );
   
        if (!response.ok) {

            throw new Error(
                "Simulation request failed"
            );

        }


        const result =
            await response.json();


        // Display results in Console

        console.log(
            "Simulation Data:",
            result
        );

        console.log(
            "Selected Duration:",
            simulationData.duration
        );

        console.log(
            "Monthly Results:",
            result.monthlyResults
        );


        // Save Results

        // ============================
// Save Results
// ============================

      result.simulationDate = new Date().toISOString();

      localStorage.setItem(
    "govTwinSimulation",
    JSON.stringify(result)
      );



    window.location.href =
    "results.html";


    } catch (error) {

        console.error(error);

        alert(
            "Unable to connect to the simulation engine. Please make sure Flask is running."
        );

    }

}


// ============================
// Show Simulation Results
// ============================

function showSimulationResults() {

    const savedData =
        localStorage.getItem(
            "govTwinSimulation"
        );


    if (!savedData) {

        console.log(
            "No simulation data found."
        );

        return;

    }


    const data =
        JSON.parse(savedData);

    const dateElement =
    document.getElementById("simulationDate");

if (dateElement && data.simulationDate) {

    const simulationDate =
        new Date(data.simulationDate);

    dateElement.textContent =
        simulationDate.toLocaleDateString("en-US", {
            year: "numeric",
            month: "long",
            day: "numeric"
        });

} 
    console.log(
        "Simulation Data:",
        data
    );


    // ============================
    // Scenario Information
    // ============================

    const subtitle =
        document.getElementById(
            "resultSubtitle"
        );


    if (subtitle) {

        subtitle.textContent =
            `${data.decisionType || "Decision"} — Simulation for ${data.duration || 12} months`;

    }


    const status =
        document.getElementById(
            "simulationStatus"
        );


    if (status) {

        status.textContent =
            `The hypothetical scenario was analyzed for ${data.duration || 12} months.`;

    }


    // ============================
    // Risk
    // ============================

    const risk =
        Number(data.risk) || 0;

    console.log(
        "RESULT DATA:",
        data
    );


    const riskScore =
        document.getElementById(
            "riskScore"
        );


    if (riskScore) {

        riskScore.textContent =
            risk;

    }


    const riskLevel =
        document.getElementById(
            "riskLevel"
        );


    if (riskLevel) {

        if (risk >= 65) {

            riskLevel.textContent =
                "Risk Level: High";

        }

        else if (risk >= 35) {

            riskLevel.textContent =
                "Risk Level: Medium";

        }

        else {

            riskLevel.textContent =
                "Risk Level: Low";

        }

    }


    const riskBar =
        document.querySelector(
            ".risk-bar div"
        );


    if (riskBar) {

        riskBar.style.width =
            risk + "%";

    }


    const riskDescription =
        document.getElementById(
            "riskDescription"
        );


    if (riskDescription) {

        if (risk >= 65) {

            riskDescription.textContent =
                "The scenario carries a high level of risk and requires careful review before implementation.";

        }

        else if (risk >= 35) {

            riskDescription.textContent =
                "The scenario carries a moderate level of risk and can be improved by modifying the decision.";

        }

        else {

            riskDescription.textContent =
                "The scenario carries a low level of risk and its expected impacts can be managed.";

        }

    }


    // ============================
    // Main Indicators
    // ============================

    const socialImpact =
        document.getElementById(
            "socialImpact"
        );

    const economicImpact =
        document.getElementById(
            "economicImpact"
        );

    const servicePressure =
        document.getElementById(
            "servicePressure"
        );

    const satisfaction =
        document.getElementById(
            "satisfaction"
        );


    // ============================
    // Calculate Impact Summary
    // ============================

    let summarySocial;

    let summaryEconomic;

    let summaryService;

    let summarySatisfaction;


    // High Risk

    if (risk >= 65) {

        summarySocial = Math.max(
            70,
            Number(data.social) || 0
        );

        summaryEconomic = Math.max(
            70,
            Number(data.economic) || 0
        );

        summaryService = Math.max(
            70,
            Number(data.service) || 0
        );

        summarySatisfaction = Math.min(
            30,
            Number(data.satisfaction) || 0
        );

    }


    // Medium Risk

    else if (risk >= 35) {

        summarySocial = Math.max(
            35,
            Number(data.social) || 0
        );

        summaryEconomic = Math.max(
            35,
            Number(data.economic) || 0
        );

        summaryService = Math.max(
            35,
            Number(data.service) || 0
        );

        summarySatisfaction = Math.min(
            65,
            Number(data.satisfaction) || 0
        );

    }


    // Low Risk

    else {

        summarySocial = Math.min(
            30,
            Number(data.social) || 0
        );

        summaryEconomic = Math.min(
            30,
            Number(data.economic) || 0
        );

        summaryService = Math.min(
            30,
            Number(data.service) || 0
        );

        summarySatisfaction = Math.max(
            70,
            Number(data.satisfaction) || 0
        );

    }


    // ============================
    // Display Results
    // ============================

    if (socialImpact) {

        socialImpact.textContent =
            Math.round(summarySocial);

    }


    if (economicImpact) {

        economicImpact.textContent =
            Math.round(summaryEconomic);

    }


    if (servicePressure) {

        servicePressure.textContent =
            Math.round(summaryService);

    }


    if (satisfaction) {

        satisfaction.textContent =
            Math.round(summarySatisfaction) + "%";

    }


    // ============================
    // Agent Statistics
    // ============================

    const agentsSimulated =
        document.getElementById(
            "agentsSimulated"
        );


    if (agentsSimulated) {

        agentsSimulated.textContent =
            data.agentsSimulated ?? "--";

    }


    const peopleAgents =
        document.getElementById(
            "peopleAgents"
        );


    if (peopleAgents) {

        peopleAgents.textContent =
            data.peopleAgents ?? "--";

    }


    const businessAgents =
        document.getElementById(
            "businessAgents"
        );


    if (businessAgents) {

        businessAgents.textContent =
            data.businessAgents ?? "--";

    }


    const governmentAgents =
        document.getElementById(
            "governmentAgents"
        );


    if (governmentAgents) {

        governmentAgents.textContent =
            data.governmentAgents ?? "--";

    }


    // ============================
    // Detailed Impact
    // ============================

    const behaviorChange =
        document.getElementById(
            "behaviorChange"
        );


    if (behaviorChange) {

        behaviorChange.textContent =
            data.behaviorChange != null
                ? data.behaviorChange + "%"
                : "--";

    }


    const demandChange =
        document.getElementById(
            "demandChange"
        );


    if (demandChange) {

        demandChange.textContent =
            data.demandChange != null
                ? data.demandChange + "%"
                : "--";

    }


    const businessImpact =
        document.getElementById(
            "businessImpact"
        );


    if (businessImpact) {

        businessImpact.textContent =
            data.businessImpact ?? "--";

    }


    const governmentPressure =
        document.getElementById(
            "governmentPressure"
        );


    if (governmentPressure) {

        governmentPressure.textContent =
            data.servicePressure ?? "--";

    }


    // ============================
    // Butterfly Effect
    // ============================

    const decision =
        data.decisionType ||
        "Selected Decision";


    const dominoDecision =
        document.getElementById(
            "dominoDecision"
        );


    if (dominoDecision) {

        dominoDecision.textContent =
            decision;

    }


    const dominoBehavior =
        document.getElementById(
            "dominoBehavior"
        );


    if (dominoBehavior) {

        dominoBehavior.textContent =
            `Changed by ${data.behaviorChange ?? 0}%`;

    }


    const dominoService =
        document.getElementById(
            "dominoService"
        );


    if (dominoService) {

        dominoService.textContent =
            `Demand changed by ${data.demandChange ?? 0}%`;

    }


    const dominoEconomic =
        document.getElementById(
            "dominoEconomic"
        );


    if (dominoEconomic) {

        dominoEconomic.textContent =
            `Economic impact: ${data.businessImpact ?? 0}`;

    }


    // ============================
    // Recommendation
    // ============================

    const recommendationTitle =
        document.getElementById(
            "recommendationTitle"
        );


    const recommendationText =
        document.getElementById(
            "recommendationText"
        );


    if (
        recommendationTitle &&
        recommendationText
    ) {

        if (data.recommendation) {

            recommendationTitle.textContent =
                data.recommendation.title ||
                "--";


            recommendationText.textContent =
                data.recommendation.text ||
                "--";

        }

        else {

            recommendationTitle.textContent =
                "--";


            recommendationText.textContent =
                "No recommendation is available.";

        }

    }


    // ============================
    // Chart
    // ============================

    let monthlyResults =
        data.monthlyResults;


    // If Flask did not return monthly results,
    // build them from the actual simulation results.

    if (
        !monthlyResults ||
        !Array.isArray(monthlyResults) ||
        monthlyResults.length === 0
    ) {

        let months =
            Number(data.duration) || 12;


        if (months <= 0) {

            months = 12;

        }


        monthlyResults = [];


        for (
            let i = 1;
            i <= months;
            i++
        ) {

            const progress =
                i / months;


            monthlyResults.push({

                month: i,

                behavior:
                    Math.abs(
                        Number(
                            data.behaviorChange
                        ) || 0
                    ) * progress,

                demand:
                    Math.abs(
                        Number(
                            data.demandChange
                        ) || 0
                    ) * progress,

                business:
                    Math.abs(
                        Number(
                            data.businessImpact
                        ) || 0
                    ) * progress,

                service:
                    Math.abs(
                        Number(
                            data.servicePressure
                        ) || 0
                    ) * progress

            });

        }

    }


    console.log(
        "MONTHLY RESULTS FOR CHART:",
        monthlyResults
    );


    createSimulationChart(
        monthlyResults
    );

}


// ============================
// Create Simulation Chart
// ============================

function createSimulationChart(
    monthlyResults
) {

    const chart =
        document.getElementById(
            "simulationChart"
        );


    const labels =
        document.getElementById(
            "chartLabels"
        );


    const durationFilter =
        document.getElementById(
            "durationFilter"
        );


    if (
        !chart ||
        !labels ||
        !monthlyResults ||
        monthlyResults.length === 0
    ) {

        console.log(
            "No monthly results available for the chart."
        );

        return;

    }


    function drawChart() {

        chart.innerHTML = "";

        labels.innerHTML = "";


        let selectedDuration =
            Number(
                durationFilter
                    ? durationFilter.value
                    : monthlyResults.length
            );


        if (
            !selectedDuration ||
            selectedDuration <= 0
        ) {

            selectedDuration =
                monthlyResults.length;

        }


        // Use only the selected number of months

        const selectedResults =
            monthlyResults.slice(
                0,
                selectedDuration
            );


        selectedResults.forEach(
            function (item) {

                const column =
                    document.createElement(
                        "div"
                    );


                column.className =
                    "chart-column";


                const bar =
                    document.createElement(
                        "div"
                    );


                bar.className =
                    "chart-bar";


                // Calculate the real impact for the month

                const totalImpact =

                    Math.abs(
                        Number(
                            item.behavior
                        ) || 0
                    )

                    +

                    Math.abs(
                        Number(
                            item.demand
                        ) || 0
                    )

                    +

                    Math.abs(
                        Number(
                            item.business
                        ) || 0
                    )

                    +

                    Math.abs(
                        Number(
                            item.service
                        ) || 0
                    );


                // Convert impact to chart height

                const height =
                    Math.min(
                        100,
                        Math.max(
                            8,
                            totalImpact * 4
                        )
                    );


                bar.style.height =
                    height + "%";


                bar.title =
                    "Month " +
                    item.month +
                    " | Impact: " +
                    totalImpact.toFixed(2);


                column.appendChild(
                    bar
                );


                chart.appendChild(
                    column
                );


                const label =
                    document.createElement(
                        "span"
                    );


                label.textContent =
                    "Month " +
                    item.month;


                labels.appendChild(
                    label
                );

            }
        );

    }


    // Initial chart

    drawChart();


    // Update chart when duration changes

    if (durationFilter) {

        durationFilter.addEventListener(
            "change",
            drawChart
        );

    }

}


// ============================
// Run Results Page
// ============================

if (
    window.location.pathname.includes(
        "results.html"
    )
) {

    showSimulationResults();

}


// ============================
// Login Modal
// ============================

function openLogin() {

    const modal =
        document.getElementById(
            "loginModal"
        );


    if (modal) {

        modal.style.display =
            "flex";

    }

}


function closeLogin() {

    const modal =
        document.getElementById(
            "loginModal"
        );


    if (modal) {

        modal.style.display =
            "none";

    }

}


function demoLogin(event) {

    event.preventDefault();


    alert(
        "Login successful - Demo Mode"
    );


    closeLogin();

}


// ============================
// Privacy
// ============================

function openPrivacy() {

    const modal =
        document.getElementById(
            "privacyModal"
        );


    if (modal) {

        modal.style.display =
            "flex";

    }

}


function closePrivacy() {

    const modal =
        document.getElementById(
            "privacyModal"
        );


    if (modal) {

        modal.style.display =
            "none";

    }

}
