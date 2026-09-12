from flask import Flask, request, jsonify, send_from_directory
import os
import random

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================
# Person Agent
# ============================

class Person:

    def __init__(self):
        self.sensitivity = random.uniform(0.5, 1.5)
        self.spending = 100

    def react_to_decision(self, change, affected_ratio, target_factor):

        effect = (
            change
            * affected_ratio
            * self.sensitivity
            * target_factor
            / 100
        )

        self.spending *= max(
            0.5,
            1 - effect / 100
        )

        return effect


# ============================
# Business Agent
# ============================

class Business:

    def __init__(self):
        self.sensitivity = random.uniform(0.5, 1.5)
        self.sales = 100

    def react_to_demand(self, demand_change):

        effect = demand_change * self.sensitivity

        self.sales *= max(
            0.5,
            1 + effect / 100
        )

        return effect


# ============================
# Government Service Agent
# ============================

class GovernmentService:

    def __init__(self):
        self.sensitivity = random.uniform(0.5, 1.5)
        self.pressure = 20

    def react_to_demand(self, demand_change):

        increase = (
            abs(demand_change)
            * self.sensitivity
        )

        self.pressure += increase

        self.pressure = min(
            100,
            self.pressure
        )

        return increase


# ============================
# Agent Simulation
# ============================

def run_agent_simulation(
    change,
    affected,
    duration,
    target_group
):

    random.seed(
        100
        + int(change)
        + int(affected)
        + int(duration)
    )

    # Create agents

    people = [
        Person()
        for _ in range(1000)
    ]

    businesses = [
        Business()
        for _ in range(200)
    ]

    services = [
        GovernmentService()
        for _ in range(10)
    ]

    affected_ratio = affected / 100

    if target_group == "all":

        target_factor = 1.0

    else:

        target_factor = 0.75


    # ============================
    # Total Results
    # ============================

    total_behavior_change = 0

    total_demand_change = 0

    total_business_effect = 0

    total_service_pressure = 0


    # Monthly results for chart

    monthly_results = []


    # ============================
    # Monthly Simulation
    # ============================

    for month in range(duration):

        # ----------------------------
        # People
        # ----------------------------

        person_effects = []

        for person in people:

            effect = person.react_to_decision(
                change,
                affected_ratio,
                target_factor
            )

            person_effects.append(effect)


        average_behavior = (
            sum(person_effects)
            / len(person_effects)
        )


        demand_change = average_behavior


        total_behavior_change += (
            average_behavior
        )

        total_demand_change += (
            demand_change
        )


        # ----------------------------
        # Businesses
        # ----------------------------

        business_effects = []

        for business in businesses:

            effect = business.react_to_demand(
                -demand_change
            )

            business_effects.append(
                abs(effect)
            )


        average_business_effect = (
            sum(business_effects)
            / len(business_effects)
        )


        total_business_effect += (
            average_business_effect
        )


        # ----------------------------
        # Government Services
        # ----------------------------

        service_effects = []

        for service in services:

            effect = service.react_to_demand(
                demand_change
            )

            service_effects.append(
                effect
            )


        average_service_pressure = (
            sum(service_effects)
            / len(service_effects)
        )


        total_service_pressure += (
            average_service_pressure
        )


        # ----------------------------
        # Monthly Chart Data
        # ----------------------------

        monthly_results.append({

            "month":
                month + 1,

            "behavior":
                round(
                    average_behavior,
                    2
                ),

            "demand":
                round(
                    demand_change,
                    2
                ),

            "business":
                round(
                    average_business_effect,
                    2
                ),

            "service":
                round(
                    average_service_pressure,
                    2
                )
        })


    # ============================
    # Average Results
    # ============================

    behavior_change = (
        total_behavior_change
        / duration
    )

    demand_change = (
        total_demand_change
        / duration
    )

    business_impact = (
        total_business_effect
        / duration
    )

    service_pressure = (
        total_service_pressure
        / duration
    )


    # ============================
    # Social Impact
    # ============================

    social = min(
        100,
        abs(behavior_change) * 8
    )


    # ============================
    # Economic Impact
    # ============================

    economic = min(
        100,
        (
            business_impact * 5
            + abs(demand_change) * 3
        )
    )


    # ============================
    # Government Service Impact
    # ============================

    service = min(
        100,
        service_pressure * 5
    )


    # ============================
    # Decision Impact
    # ============================

    decision_impact = (
        abs(change)
        * affected
        / 100
    )


    # ============================
    # Duration Impact
    # ============================

    duration_impact = min(
        100,
        duration * 5
    )


    # ============================
    # Risk Calculation
    # ============================

    risk = 100 - (
        (change * 0.50)
        + (affected * 0.50)
    )

    risk = round(
        min(
            100,
            max(
                0,
                risk
            )
        )
    )


    # ============================
    # Risk Level
    # ============================

    if risk < 35:

        risk_level = "Low"

    elif risk < 65:

        risk_level = "Medium"

    else:

        risk_level = "High"


    # ============================
    # Satisfaction
    # ============================

    satisfaction = round(
        max(
            40,
            100
            - social * 0.25
            - service * 0.20
            - economic * 0.15
        )
    )


    # ============================
    # Recommendation
    # ============================

    if risk >= 65:

        recommendation = {

            "title":
                "Decision Review Recommended",

            "text":
                "The simulation indicates a high level of risk. The decision should be reviewed to assess its impact on beneficiaries, government services, and the economic sector."
        }

    elif risk >= 35:

        recommendation = {

            "title":
                "Decision Modification Recommended",

            "text":
                "The simulation indicates a moderate level of impact. Risks can be reduced by adjusting the scale of change or the target group."
        }

    else:

        recommendation = {

            "title":
                "Decision Can Be Implemented",

            "text":
                "The simulation indicates a low level of risk. The decision can be implemented while monitoring its expected impacts."
        }


    # ============================
    # Return Simulation Results
    # ============================

    return {

        "risk":
            risk,

        "riskLevel":
            risk_level,

        "social":
            round(social),

        "economic":
            round(economic),

        "service":
            round(service),

        "satisfaction":
            satisfaction,

        "behaviorChange":
            round(
                behavior_change,
                2
            ),

        "demandChange":
            round(
                demand_change,
                2
            ),

        "businessImpact":
            round(
                business_impact,
                2
            ),

        "servicePressure":
            round(
                service_pressure,
                2
            ),

        "agentsSimulated":
            len(people)
            + len(businesses)
            + len(services),

        "peopleAgents":
            len(people),

        "businessAgents":
            len(businesses),

        "governmentAgents":
            len(services),

        "monthsSimulated":
            duration,

        "monthlyResults":
            monthly_results,

        "recommendation":
            recommendation
    }


# ============================
# Home Page
# ============================

@app.route("/")
def home():

    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


# ============================
# Serve Other Files
# ============================

@app.route("/<path:filename>")
def serve_file(filename):

    return send_from_directory(
        BASE_DIR,
        filename
    )


# ============================
# Simulation API
# ============================

@app.route(
    "/simulate",
    methods=["POST"]
)
def simulate():

    data = request.json


    decision_type = data.get(
        "decisionType"
    )


    sector = data.get(
        "sector"
    )


    target_group = data.get(
        "targetGroup"
    )


    duration = int(
        data.get(
            "duration",
            12
        )
    )


    change = float(
        data.get(
            "change",
            0
        )
    )


    affected = float(
        data.get(
            "affected",
            0
        )
    )


    # Run Agent Simulation

    simulation = run_agent_simulation(

        change,

        affected,

        duration,

        target_group
    )


    # ============================
    # Return JSON
    # ============================

    return jsonify({

        "decisionType":
            decision_type,

        "sector":
            sector,

        "targetGroup":
            target_group,

        "duration":
            duration,

        "risk":
            simulation["risk"],

        "riskLevel":
            simulation["riskLevel"],

        "social":
            simulation["social"],

        "economic":
            simulation["economic"],

        "service":
            simulation["service"],

        "satisfaction":
            simulation["satisfaction"],

        "behaviorChange":
            simulation["behaviorChange"],

        "demandChange":
            simulation["demandChange"],

        "businessImpact":
            simulation["businessImpact"],

        "servicePressure":
            simulation["servicePressure"],

        "agentsSimulated":
            simulation["agentsSimulated"],

        "peopleAgents":
            simulation["peopleAgents"],

        "businessAgents":
            simulation["businessAgents"],

        "governmentAgents":
            simulation["governmentAgents"],

        "monthsSimulated":
            simulation["monthsSimulated"],

        # Data used by the chart

        "monthlyResults":
            simulation["monthlyResults"],

        # Recommendation

        "recommendation":
            simulation["recommendation"]
    })


# ============================
# Run Flask
# ============================

if __name__ == "__main__":

    app.run(
        debug=True
    )