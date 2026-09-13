import copy
from typing import Dict, Any
from .schemas import ScenarioConfig, ScenarioResult
from .edge_cases import ALL_SCENARIOS

class ScenarioRunner:
    def __init__(self):
        self.scenarios: Dict[str, ScenarioConfig] = {
            s_id: ScenarioConfig(**config) for s_id, config in ALL_SCENARIOS.items()
        }

    def get_available_scenarios(self) -> Dict[str, ScenarioConfig]:
        """Returns all loaded predefined scenarios."""
        return self.scenarios

    def apply_scenario(self, base_state: Dict[str, Any], scenario_id: str) -> ScenarioResult:
        """
        Takes a base microgrid state and applies the requested scenario modifiers to it.
        Returns a ScenarioResult containing the original, modified state, and logs.
        """
        if scenario_id not in self.scenarios:
            raise ValueError(f"Scenario '{scenario_id}' not found.")
        
        scenario = self.scenarios[scenario_id]
        
        # Deepcopy to avoid mutating the original dictionary
        modified_state = copy.deepcopy(base_state)
        logs = []
        
        # Apply solar multiplier
        if "solar_generation" in modified_state and scenario.solar_multiplier != 1.0:
            old_val = modified_state["solar_generation"]
            new_val = old_val * scenario.solar_multiplier
            modified_state["solar_generation"] = new_val
            logs.append(f"Applied solar multiplier {scenario.solar_multiplier}: {old_val} -> {new_val}")
            
        # Apply wind multiplier
        if "wind_generation" in modified_state and scenario.wind_multiplier != 1.0:
            old_val = modified_state["wind_generation"]
            new_val = old_val * scenario.wind_multiplier
            modified_state["wind_generation"] = new_val
            logs.append(f"Applied wind multiplier {scenario.wind_multiplier}: {old_val} -> {new_val}")
            
        # Apply demand multiplier
        if "demand" in modified_state and scenario.demand_multiplier != 1.0:
            old_val = modified_state["demand"]
            new_val = old_val * scenario.demand_multiplier
            modified_state["demand"] = new_val
            logs.append(f"Applied demand multiplier {scenario.demand_multiplier}: {old_val} -> {new_val}")
            
        # Apply grid override
        if scenario.grid_available is not None:
            old_val = modified_state.get("grid_status", "UNKNOWN")
            new_val = "AVAILABLE" if scenario.grid_available else "OFFLINE"
            modified_state["grid_status"] = new_val
            logs.append(f"Overrode grid_status: {old_val} -> {new_val}")
            
        # Apply battery capacity multiplier
        if "battery_soc" in modified_state and scenario.battery_capacity_multiplier != 1.0:
            old_val = modified_state["battery_soc"]
            new_val = old_val * scenario.battery_capacity_multiplier
            modified_state["battery_soc"] = new_val
            logs.append(f"Applied battery multiplier {scenario.battery_capacity_multiplier}: {old_val} -> {new_val}")

        return ScenarioResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            original_state=base_state,
            modified_state=modified_state,
            logs=logs
        )
