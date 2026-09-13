from ..schemas import ScenarioType

GRID_OUTAGE_SCENARIO = {
    "id": "scn_grid_outage_001",
    "name": "Total Grid Outage (Blackout)",
    "description": "Simulates a complete failure of the main utility grid. The microgrid must survive on its own generation and battery storage.",
    "scenario_type": ScenarioType.GRID_OUTAGE,
    "solar_multiplier": 1.0,
    "wind_multiplier": 1.0,
    "demand_multiplier": 1.0,
    "grid_available": False,
    "battery_capacity_multiplier": 1.0,
    "custom_parameters": {}
}
