from dataclasses import dataclass

from backend.common.schemas.microgrid_state import MicrogridState


@dataclass(frozen=True)
class SafetyPolicy:
    """Deterministic operational limits for the microgrid safety layer."""

    min_battery_soc: float = 0.10
    max_battery_soc: float = 0.95
    max_battery_charge_kw: float = 100.0
    max_battery_discharge_kw: float = 100.0
    max_ev_charge_kw: float = 7.0
    max_ev_discharge_kw: float = 0.0
    max_grid_import_kw: float = 5000.0
    max_grid_export_kw: float = 2000.0
    max_demand_reduction_kw: float = 0.0

    @classmethod
    def from_state(cls, state: MicrogridState | None) -> "SafetyPolicy":
        if state is None:
            return cls()

        battery = getattr(state, "battery", None)
        grid = getattr(state, "grid_connection", None)
        ev = getattr(state, "ev", None)

        policy = cls(
            min_battery_soc=float(getattr(battery, "min_soc", 0.10) or 0.10),
            max_battery_soc=float(getattr(battery, "max_soc", 0.95) or 0.95),
            max_battery_charge_kw=float(getattr(battery, "charge_rate_kw", 100.0) or 100.0),
            max_battery_discharge_kw=float(getattr(battery, "discharge_rate_kw", 100.0) or 100.0),
            max_grid_import_kw=float(getattr(grid, "import_limit_kw", 5000.0) or 5000.0),
            max_grid_export_kw=float(getattr(grid, "export_limit_kw", 2000.0) or 2000.0),
        )

        if ev is not None:
            connected = max(int(getattr(ev, "connected_count", 0) or 0), 1)
            policy = dataclass_replace(policy, max_ev_charge_kw=float(getattr(ev, "connected_count", connected) or connected) * 7.0)

        return policy


def dataclass_replace(value: SafetyPolicy, **updates) -> SafetyPolicy:
    return SafetyPolicy(**{**value.__dict__, **updates})
