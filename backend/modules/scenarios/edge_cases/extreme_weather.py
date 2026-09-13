from ..schemas import ScenarioType

EXTREME_WEATHER_SCENARIO = {
    "id": "scn_ext_weather_001",
    "name": "Extreme Weather (Heavy Cloud & Calm Wind)",
    "description": "Simulates a severe weather event that drastically reduces renewable energy generation (50% drop in solar, 80% drop in wind).",
    "scenario_type": ScenarioType.EXTREME_WEATHER,
    "solar_multiplier": 0.5,
    "wind_multiplier": 0.2,
    "demand_multiplier": 1.1,  # People stay indoors, demand goes up slightly
    "grid_available": True,
    "battery_capacity_multiplier": 1.0,
    "custom_parameters": {}
}
