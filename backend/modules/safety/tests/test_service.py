from backend.common.schemas.enums import AgentType, SafetyStatus
from backend.common.schemas.messages import AgentDecision
from backend.common.schemas.microgrid_state import MicrogridState
from backend.modules.safety.service import SafetyService


def test_service_validates_multiple_decisions_and_sets_overall_risk():
    state = MicrogridState(
        battery={
            "capacity_kwh": 50.0,
            "current_soc": 0.60,
            "soc_percentage": 60.0,
            "min_soc": 0.20,
            "max_soc": 0.95,
            "charge_rate_kw": 10.0,
            "discharge_rate_kw": 10.0,
            "energy_available_kwh": 20.0,
        },
        grid_connection={
            "import_limit_kw": 20.0,
            "export_limit_kw": 20.0,
        },
    )
    decisions = [
        AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="charge", resource="battery", quantity_kw=5.0),
        AgentDecision(agent=AgentType.ENERGY_RESOURCE, action="discharge", resource="battery", quantity_kw=3.0),
    ]

    result = SafetyService().validate(state, decisions)

    assert result.overall_status == SafetyStatus.REJECTED
    assert result.risk_level.value in {"high", "critical"}
