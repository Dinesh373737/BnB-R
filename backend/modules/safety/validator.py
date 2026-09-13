import math
from typing import Any

from backend.common.schemas.messages import AgentDecision
from backend.common.schemas.microgrid_state import MicrogridState
from backend.modules.safety.policy import SafetyPolicy


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def is_valid_number(value: Any) -> bool:
    return _as_float(value) is not None


def validate_state(state: MicrogridState | None) -> tuple[bool, str | None]:
    if state is None:
        return False, "Missing microgrid state."

    battery = getattr(state, "battery", None)
    if battery is not None:
        soc = _as_float(getattr(battery, "current_soc", None))
        if soc is None or not (0.0 <= soc <= 1.0):
            return False, "Battery SOC is missing or outside the valid range of 0 to 1."
        capacity = _as_float(getattr(battery, "capacity_kwh", None))
        if capacity is not None and capacity < 0:
            return False, "Battery capacity cannot be negative."

    grid = getattr(state, "grid_connection", None)
    if grid is not None:
        import_limit = _as_float(getattr(grid, "import_limit_kw", None))
        export_limit = _as_float(getattr(grid, "export_limit_kw", None))
        if import_limit is not None and import_limit < 0:
            return False, "Grid import limit cannot be negative."
        if export_limit is not None and export_limit < 0:
            return False, "Grid export limit cannot be negative."

    return True, None


def decision_quantity_kw(decision: AgentDecision) -> float | None:
    value = None
    if decision.quantity_kw is not None:
        value = decision.quantity_kw
    elif decision.quantity_kwh is not None:
        value = decision.quantity_kwh
    return _as_float(value)


def decision_resource_kind(resource: str) -> str:
    name = (resource or "").lower()
    if "battery" in name:
        return "battery"
    if "ev" in name:
        return "ev"
    if "grid" in name:
        return "grid"
    if "house" in name or "demand" in name or "load" in name:
        return "load"
    if "market" in name:
        return "market"
    return "unknown"


def apply_policy_limit(value: float, limit: float, *, allow_clamp: bool) -> tuple[float, bool, str | None, float | None]:
    if value < 0:
        return value, False, "Negative power is not allowed.", limit
    if limit <= 0:
        return value, False, "Safety limit is unavailable or zero.", limit
    if value <= limit:
        return value, False, None, limit
    if allow_clamp:
        return limit, True, "Requested value exceeded configured limit and was clamped.", limit
    return value, False, "Requested value exceeds configured limit.", limit


def battery_safe_limits(policy: SafetyPolicy, state: MicrogridState) -> tuple[float, float, float]:
    battery = getattr(state, "battery", None)
    if battery is None:
        raise ValueError("Battery state is missing.")

    soc = _as_float(getattr(battery, "current_soc", 0.0))
    capacity = _as_float(getattr(battery, "capacity_kwh", 0.0)) or 0.0
    min_soc = _as_float(getattr(battery, "min_soc", policy.min_battery_soc)) or policy.min_battery_soc
    max_soc = _as_float(getattr(battery, "max_soc", policy.max_battery_soc)) or policy.max_battery_soc
    min_allowed_kw = max(0.0, (soc - min_soc) * capacity * 60.0)
    max_allowed_kw = max(0.0, (max_soc - soc) * capacity * 60.0)
    return min_allowed_kw, max_allowed_kw, float(getattr(battery, "charge_rate_kw", policy.max_battery_charge_kw) or policy.max_battery_charge_kw)


def calculate_risk_level(status: str) -> str:
    if status == "approved":
        return "low"
    if status == "modified":
        return "medium"
    return "high"
