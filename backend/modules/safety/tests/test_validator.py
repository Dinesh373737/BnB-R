import math

from backend.common.schemas.enums import AgentType, SafetyStatus
from backend.common.schemas.messages import AgentDecision
from backend.common.schemas.microgrid_state import MicrogridState

from backend.modules.safety.service import SafetyService


def _state(**overrides):
    state = MicrogridState(
        battery={
            "capacity_kwh": 50.0,
            "current_soc": 0.60,
            "soc_percentage": 60.0,
            "current_power_kw": 0.0,
            "min_soc": 0.20,
            "max_soc": 0.95,
            "charge_rate_kw": 10.0,
            "discharge_rate_kw": 10.0,
            "energy_available_kwh": 20.0,
        },
        grid_connection={
            "import_limit_kw": 20.0,
            "export_limit_kw": 20.0,
            "import_power_kw": 0.0,
            "export_power_kw": 0.0,
        },
        ev={
            "total_count": 3,
            "connected_count": 3,
            "charging_count": 0,
            "total_demand_kw": 0.0,
            "total_battery_kwh": 180.0,
            "average_soc": 0.60,
            "flexible_demand_kw": 0.0,
        },
    )
    for key, value in overrides.items():
        if key == "battery":
            state.battery = state.battery.model_copy(update=value)
        elif key == "grid_connection":
            state.grid_connection = state.grid_connection.model_copy(update=value)
        elif key == "ev":
            state.ev = state.ev.model_copy(update=value)
        else:
            setattr(state, key, value)
    return state


def test_valid_battery_charge_is_approved():
    service = SafetyService()
    state = _state()
    decision = AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="charge", resource="battery", quantity_kw=5.0)

    result = service.validate(state, [decision])

    assert result.overall_status == SafetyStatus.APPROVED
    assert len(result.approved_decisions) == 1


def test_valid_battery_discharge_is_approved():
    service = SafetyService()
    state = _state()
    decision = AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="discharge", resource="battery", quantity_kw=3.0)

    result = service.validate(state, [decision])

    assert result.overall_status == SafetyStatus.APPROVED


def test_battery_soc_below_min_is_rejected():
    service = SafetyService()
    state = _state(battery={"current_soc": 0.15, "soc_percentage": 15.0, "energy_available_kwh": 0.0})
    decision = AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="discharge", resource="battery", quantity_kw=1.0)

    result = service.validate(state, [decision])

    assert result.overall_status == SafetyStatus.REJECTED
    assert any("minimum" in r.lower() for r in result.reasons)


def test_battery_charge_above_max_power_is_modified_or_rejected():
    service = SafetyService()
    state = _state(battery={"current_soc": 0.40, "soc_percentage": 40.0, "max_soc": 0.95, "charge_rate_kw": 5.0})
    decision = AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="charge", resource="battery", quantity_kw=10.0)

    result = service.validate(state, [decision])

    assert result.overall_status in {SafetyStatus.MODIFIED, SafetyStatus.REJECTED}


def test_battery_charge_and_discharge_simultaneously_is_rejected():
    service = SafetyService()
    state = _state()
    decisions = [
        AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="charge", resource="battery", quantity_kw=5.0),
        AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="discharge", resource="battery", quantity_kw=3.0),
    ]

    result = service.validate(state, decisions)

    assert result.overall_status == SafetyStatus.REJECTED


def test_discharge_beyond_available_energy_is_rejected():
    service = SafetyService()
    state = _state(battery={"current_soc": 0.25, "soc_percentage": 25.0, "min_soc": 0.20, "capacity_kwh": 20.0})
    decision = AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="discharge", resource="battery", quantity_kw=10.0)

    result = service.validate(state, [decision])

    assert result.overall_status == SafetyStatus.REJECTED


def test_negative_battery_power_is_rejected():
    service = SafetyService()
    state = _state()
    decision = AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="charge", resource="battery", quantity_kw=-2.0)

    result = service.validate(state, [decision])

    assert result.overall_status == SafetyStatus.REJECTED


def test_ev_charge_above_limit_is_modified_or_rejected():
    service = SafetyService()
    state = _state(ev={"total_count": 2, "connected_count": 2, "average_soc": 0.50, "total_battery_kwh": 120.0})
    decision = AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="charge", resource="ev_fleet", quantity_kw=20.0)

    result = service.validate(state, [decision])

    assert result.overall_status in {SafetyStatus.MODIFIED, SafetyStatus.REJECTED}


def test_grid_import_above_limit_is_modified_or_rejected():
    service = SafetyService()
    state = _state(grid_connection={"import_limit_kw": 20.0})
    decision = AgentDecision(agent=AgentType.MARKET_TRADING, action="import", resource="grid", quantity_kw=30.0)

    result = service.validate(state, [decision])

    assert result.overall_status in {SafetyStatus.MODIFIED, SafetyStatus.REJECTED}


def test_nan_or_infinity_values_are_rejected():
    service = SafetyService()
    state = _state()
    decision = AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="charge", resource="battery", quantity_kw=float("nan"))

    result = service.validate(state, [decision])

    assert result.overall_status == SafetyStatus.REJECTED


def test_unknown_resource_is_rejected():
    service = SafetyService()
    state = _state()
    decision = AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="charge", resource="unknown_resource", quantity_kw=3.0)

    result = service.validate(state, [decision])

    assert result.overall_status == SafetyStatus.REJECTED


def test_missing_state_is_rejected():
    service = SafetyService()
    decision = AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="charge", resource="battery", quantity_kw=2.0)

    result = service.validate(None, [decision])

    assert result.overall_status == SafetyStatus.REJECTED


def test_validation_exception_fails_closed():
    service = SafetyService()
    state = _state()
    decision = AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="charge", resource="battery", quantity_kw=1.0)

    result = service.validate(state, [decision], strict_mode=False)

    assert result.overall_status in {SafetyStatus.REJECTED, SafetyStatus.APPROVED}


def test_status_endpoint_is_available():
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.get("/api/safety/status")

    assert response.status_code == 200
    assert response.json()["status"] == "available"


def test_validation_endpoint_rejects_unsafe_decisions():
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/safety/validate",
        json={
            "state": {
                "battery": {
                    "capacity_kwh": 50.0,
                    "current_soc": 0.60,
                    "soc_percentage": 60.0,
                    "min_soc": 0.20,
                    "max_soc": 0.95,
                    "charge_rate_kw": 10.0,
                    "discharge_rate_kw": 10.0,
                    "energy_available_kwh": 20.0,
                },
                "grid_connection": {
                    "import_limit_kw": 20.0,
                    "export_limit_kw": 20.0,
                },
                "ev": {
                    "total_count": 3,
                    "connected_count": 3,
                    "total_battery_kwh": 180.0,
                    "average_soc": 0.60,
                },
            },
            "decisions": [
                {
                    "agent": "energy_resource",
                    "action": "discharge",
                    "resource": "battery",
                    "quantity_kw": 30.0,
                    "reason": "test",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["overall_status"] in {"rejected", "modified"}
