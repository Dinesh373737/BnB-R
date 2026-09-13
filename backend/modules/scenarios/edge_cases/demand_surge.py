from ..schemas import ScenarioType

DEMAND_SURGE_SCENARIO = {
    "id": "scn_demand_surge_001",
    "name": "Sudden Demand Surge (EVs & HVAC)",
    "description": "Simulates a sudden 30% spike in total demand, testing the system's ability to handle peak loads.",
    "scenario_type": ScenarioType.DEMAND_SURGE,
    "solar_multiplier": 1.0,
    "wind_multiplier": 1.0,
    "demand_multiplier": 1.3,
    "grid_available": True,
    "battery_capacity_multiplier": 1.0,
    "custom_parameters": {}
}
