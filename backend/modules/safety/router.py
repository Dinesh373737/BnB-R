from fastapi import APIRouter

from backend.common.logger import get_module_logger
from backend.common.schemas.enums import RiskLevel, SafetyStatus
from backend.modules.safety.schemas import SafetyValidationRequest, SafetyValidationResult
from backend.modules.safety.service import SafetyService

log = get_module_logger("safety.router")
router = APIRouter(prefix="/safety", tags=["Safety"])
safety_service = SafetyService()


@router.get("/status")
def get_safety_status():
    return {"status": "available", "service": "safety-layer", "risk_levels": [level.value for level in RiskLevel]}


@router.post("/validate", response_model=SafetyValidationResult)
def validate_agent_decisions(request: SafetyValidationRequest):
    try:
        result = safety_service.validate(request.state, request.decisions)
        log.info("Safety validation complete: %s", result.overall_status.value)
        return result
    except Exception as exc:  # fail closed
        log.exception("Unexpected safety validation failure")
        return SafetyValidationResult(
            overall_status=SafetyStatus.REJECTED,
            risk_level=RiskLevel.CRITICAL,
            reasons=[f"Unexpected validation failure: {exc}"],
            violations=["VALIDATION_EXCEPTION"],
        )
