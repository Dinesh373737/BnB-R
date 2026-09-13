import math
from typing import Any

from backend.common.logger import get_module_logger
from backend.common.schemas.enums import RiskLevel, SafetyStatus
from backend.common.schemas.messages import AgentDecision
from backend.common.schemas.microgrid_state import MicrogridState
from backend.modules.safety.policy import SafetyPolicy
from backend.modules.safety.schemas import SafetyDecisionOutcome, SafetyValidationResult
from backend.modules.safety.validator import (
    battery_safe_limits,
    calculate_risk_level,
    decision_quantity_kw,
    decision_resource_kind,
    validate_state,
)

log = get_module_logger("safety.service")


class SafetyService:
    """Deterministic safety gate for agent decisions."""

    def __init__(self, policy: SafetyPolicy | None = None):
        self.policy = policy or SafetyPolicy()

    def validate(
        self,
        state: MicrogridState | None,
        decisions: list[AgentDecision],
        strict_mode: bool = True,
    ) -> SafetyValidationResult:
        result = SafetyValidationResult()
        if state is None:
            for decision in decisions:
                safe_decision = decision.model_copy(deep=True) if hasattr(decision, "model_copy") else decision
                result.rejected_decisions.append(safe_decision)
                result.reasons.append("Missing microgrid state: decision rejected.")
                result.violations.append("STATE_MISSING")
                result.validation_details.append(
                    SafetyDecisionOutcome(
                        status=SafetyStatus.REJECTED,
                        risk_level=RiskLevel.CRITICAL,
                        original_decision=safe_decision,
                        safe_decision=safe_decision,
                        reason="Missing microgrid state.",
                        rule="STATE_MISSING",
                    )
                )
            result.overall_status = SafetyStatus.REJECTED
            result.risk_level = RiskLevel.CRITICAL
            return result

        valid_state, state_error = validate_state(state)
        if not valid_state:
            for decision in decisions:
                safe_decision = decision.model_copy(deep=True) if hasattr(decision, "model_copy") else decision
                result.rejected_decisions.append(safe_decision)
                result.reasons.append(state_error or "Invalid state.")
                result.violations.append("STATE_INVALID")
                result.validation_details.append(
                    SafetyDecisionOutcome(
                        status=SafetyStatus.REJECTED,
                        risk_level=RiskLevel.CRITICAL,
                        original_decision=safe_decision,
                        safe_decision=safe_decision,
                        reason=state_error or "Invalid state.",
                        rule="STATE_INVALID",
                    )
                )
            result.overall_status = SafetyStatus.REJECTED
            result.risk_level = RiskLevel.CRITICAL
            return result

        policy = SafetyPolicy.from_state(state)
        approved: list[AgentDecision] = []
        modified: list[AgentDecision] = []
        rejected: list[AgentDecision] = []

        for decision in decisions:
            try:
                safe_decision, status, reason, rule, limit, risk_level, detail = self._validate_decision(
                    decision, state, policy, strict_mode=strict_mode
                )
            except Exception as exc:
                log.exception("Safety validation failed unexpectedly for decision=%s", decision)
                safe_decision = decision.model_copy(deep=True) if hasattr(decision, "model_copy") else decision
                status = SafetyStatus.REJECTED
                reason = f"Unexpected validation failure: {exc}"
                rule = "VALIDATION_EXCEPTION"
                limit = None
                risk_level = RiskLevel.CRITICAL
                detail = {"exception": str(exc)}

            if status == SafetyStatus.APPROVED:
                approved.append(safe_decision)
            elif status == SafetyStatus.MODIFIED:
                modified.append(safe_decision)
            else:
                rejected.append(safe_decision)

            if reason:
                result.reasons.append(reason)
            if rule:
                result.violations.append(rule)
            result.validation_details.append(
                SafetyDecisionOutcome(
                    status=status,
                    risk_level=risk_level,
                    original_decision=decision.model_copy(deep=True) if hasattr(decision, "model_copy") else decision,
                    safe_decision=safe_decision,
                    reason=reason,
                    rule=rule,
                    limit=limit,
                    details=detail,
                )
            )

        approved, modified, rejected = self._apply_cross_decision_checks(state, policy, approved, modified, rejected)

        result.approved_decisions = approved
        result.modified_decisions = modified
        result.rejected_decisions = rejected
        result.risk_level = self._determine_overall_risk(approved, modified, rejected)
        result.overall_status = self._determine_overall_status(approved, modified, rejected)
        if not result.reasons:
            result.reasons = ["All decisions passed the safety checks."]
        if not result.violations:
            result.violations = ["NONE"]
        return result

    def _validate_decision(
        self,
        decision: AgentDecision,
        state: MicrogridState,
        policy: SafetyPolicy,
        *,
        strict_mode: bool,
    ) -> tuple[AgentDecision, SafetyStatus, str, str, float | None, RiskLevel, dict[str, Any]]:
        if decision is None:
            return decision, SafetyStatus.REJECTED, "Decision is missing.", "INVALID_DECISION", None, RiskLevel.CRITICAL, {}

        if not hasattr(decision, "agent") or not hasattr(decision, "action") or not hasattr(decision, "resource"):
            return decision, SafetyStatus.REJECTED, "Malformed decision structure.", "INVALID_DECISION", None, RiskLevel.CRITICAL, {}

        if decision.action is None or not str(decision.action):
            return decision, SafetyStatus.REJECTED, "Action is missing or invalid.", "INVALID_ACTION", None, RiskLevel.CRITICAL, {}

        amount = decision_quantity_kw(decision)
        if amount is None:
            return decision, SafetyStatus.REJECTED, "Decision quantity is missing, invalid, NaN, or infinite.", "INVALID_NUMBER", None, RiskLevel.CRITICAL, {}
        if amount < 0:
            return decision, SafetyStatus.REJECTED, "Negative power values are not allowed.", "NEGATIVE_POWER", None, RiskLevel.HIGH, {}

        action = str(decision.action).lower()
        resource = str(decision.resource or "").lower()
        resource_kind = decision_resource_kind(resource)

        if resource_kind == "unknown" and action not in {"hold", "run", "pause", "delay", "reserve", "use_local", "place_bid", "place_ask", "cancel_order", "execute_trade"}:
            return decision, SafetyStatus.REJECTED, f"Unknown resource '{decision.resource}'.", "UNKNOWN_RESOURCE", None, RiskLevel.CRITICAL, {}

        battery = getattr(state, "battery", None)
        if resource_kind == "battery":
            if battery is None:
                return decision, SafetyStatus.REJECTED, "Battery state is missing.", "BATTERY_STATE_MISSING", None, RiskLevel.CRITICAL, {}
            current_soc = float(getattr(battery, "current_soc", 0.0) or 0.0)
            min_soc = float(getattr(battery, "min_soc", policy.min_battery_soc) or policy.min_battery_soc)
            max_soc = float(getattr(battery, "max_soc", policy.max_battery_soc) or policy.max_battery_soc)
            capacity_kwh = float(getattr(battery, "capacity_kwh", 0.0) or 0.0)
            if not (0.0 <= current_soc <= 1.0):
                return decision, SafetyStatus.REJECTED, "Battery SOC is outside the valid range 0 to 1.", "BATTERY_SOC_RANGE", None, RiskLevel.CRITICAL, {}
            if current_soc < min_soc and action == "discharge":
                return decision, SafetyStatus.REJECTED, f"Requested battery discharge would violate minimum SOC of {min_soc:.2%}.", "BATTERY_MIN_SOC", min_soc, RiskLevel.CRITICAL, {}
            if current_soc > max_soc and action == "charge":
                return decision, SafetyStatus.REJECTED, f"Requested battery charge would violate maximum SOC of {max_soc:.2%}.", "BATTERY_MAX_SOC", max_soc, RiskLevel.CRITICAL, {}
            if capacity_kwh <= 0:
                return decision, SafetyStatus.REJECTED, "Battery capacity is zero or missing.", "BATTERY_CAPACITY", None, RiskLevel.CRITICAL, {}
            available_for_discharge_kwh = max(0.0, (current_soc - min_soc) * capacity_kwh)
            available_for_charge_kwh = max(0.0, (max_soc - current_soc) * capacity_kwh)

            if action == "charge":
                if amount > float(getattr(battery, "charge_rate_kw", policy.max_battery_charge_kw) or policy.max_battery_charge_kw):
                    safe_amount = min(amount, float(getattr(battery, "charge_rate_kw", policy.max_battery_charge_kw) or policy.max_battery_charge_kw))
                    if safe_amount <= 0:
                        return decision, SafetyStatus.REJECTED, "Charging rate limit is not available.", "BATTERY_CHARGE_RATE_LIMIT", None, RiskLevel.CRITICAL, {}
                    decision = decision.model_copy(deep=True)
                    decision.quantity_kw = round(safe_amount, 2)
                    return decision, SafetyStatus.MODIFIED, "Requested battery charge exceeds the configured maximum; value was clamped.", "BATTERY_CHARGE_RATE_LIMIT", safe_amount, RiskLevel.MEDIUM, {"safe_quantity_kw": safe_amount}
                if amount > available_for_charge_kwh:
                    return decision, SafetyStatus.REJECTED, "Requested battery charge exceeds the available headroom before max SOC.", "BATTERY_CHARGE_HEADROOM", available_for_charge_kwh, RiskLevel.CRITICAL, {}
                return decision, SafetyStatus.APPROVED, "Battery charge is within configured limits.", "BATTERY_OK", amount, RiskLevel.LOW, {"safe_quantity_kw": amount}

            if action == "discharge":
                if amount > float(getattr(battery, "discharge_rate_kw", policy.max_battery_discharge_kw) or policy.max_battery_discharge_kw):
                    safe_amount = min(amount, float(getattr(battery, "discharge_rate_kw", policy.max_battery_discharge_kw) or policy.max_battery_discharge_kw))
                    decision = decision.model_copy(deep=True)
                    decision.quantity_kw = round(safe_amount, 2)
                    return decision, SafetyStatus.MODIFIED, "Requested battery discharge exceeds the configured maximum; value was clamped.", "BATTERY_DISCHARGE_RATE_LIMIT", safe_amount, RiskLevel.MEDIUM, {"safe_quantity_kw": safe_amount}
                if amount > available_for_discharge_kwh:
                    return decision, SafetyStatus.REJECTED, "Requested battery discharge exceeds the available usable energy at minimum SOC.", "BATTERY_DISCHARGE_HEADROOM", available_for_discharge_kwh, RiskLevel.CRITICAL, {}
                return decision, SafetyStatus.APPROVED, "Battery discharge is within configured limits.", "BATTERY_OK", amount, RiskLevel.LOW, {"safe_quantity_kw": amount}

        if resource_kind == "ev":
            ev = getattr(state, "ev", None)
            if ev is None:
                return decision, SafetyStatus.REJECTED, "EV state is missing.", "EV_STATE_MISSING", None, RiskLevel.CRITICAL, {}
            ev_average_soc = float(getattr(ev, "average_soc", 0.0) or 0.0)
            if not (0.0 <= ev_average_soc <= 1.0):
                return decision, SafetyStatus.REJECTED, "EV SOC is outside the valid range 0 to 1.", "EV_SOC_RANGE", None, RiskLevel.CRITICAL, {}
            if action in {"charge", "discharge"}:
                limit = float(policy.max_ev_charge_kw or 7.0)
                if action == "discharge":
                    limit = float(policy.max_ev_discharge_kw or 0.0)
                if limit <= 0 and action == "discharge":
                    return decision, SafetyStatus.REJECTED, "Vehicle-to-grid discharge is not supported by the current model.", "EV_DISCHARGE_UNSUPPORTED", None, RiskLevel.CRITICAL, {}
                if amount > limit:
                    safe_amount = min(amount, limit)
                    decision = decision.model_copy(deep=True)
                    decision.quantity_kw = round(safe_amount, 2)
                    return decision, SafetyStatus.MODIFIED, "EV power request exceeds configured EV limit and was clamped.", "EV_POWER_LIMIT", safe_amount, RiskLevel.MEDIUM, {"safe_quantity_kw": safe_amount}
            return decision, SafetyStatus.APPROVED, "EV power request is within the configured limits.", "EV_OK", amount, RiskLevel.LOW, {"safe_quantity_kw": amount}

        if resource_kind == "grid":
            grid = getattr(state, "grid_connection", None)
            if grid is None:
                return decision, SafetyStatus.REJECTED, "Grid state is missing.", "GRID_STATE_MISSING", None, RiskLevel.CRITICAL, {}
            if action in {"import", "buy"}:
                limit = float(getattr(grid, "import_limit_kw", policy.max_grid_import_kw) or policy.max_grid_import_kw)
                if amount > limit:
                    safe_amount = min(amount, limit)
                    decision = decision.model_copy(deep=True)
                    decision.quantity_kw = round(safe_amount, 2)
                    return decision, SafetyStatus.MODIFIED, "Grid import exceeds the configured limit and was clamped.", "GRID_IMPORT_LIMIT", safe_amount, RiskLevel.MEDIUM, {"safe_quantity_kw": safe_amount}
                return decision, SafetyStatus.APPROVED, "Grid import is within the configured limit.", "GRID_IMPORT_OK", amount, RiskLevel.LOW, {"safe_quantity_kw": amount}
            if action in {"export", "sell"}:
                limit = float(getattr(grid, "export_limit_kw", policy.max_grid_export_kw) or policy.max_grid_export_kw)
                if amount > limit:
                    safe_amount = min(amount, limit)
                    decision = decision.model_copy(deep=True)
                    decision.quantity_kw = round(safe_amount, 2)
                    return decision, SafetyStatus.MODIFIED, "Grid export exceeds the configured limit and was clamped.", "GRID_EXPORT_LIMIT", safe_amount, RiskLevel.MEDIUM, {"safe_quantity_kw": safe_amount}
                return decision, SafetyStatus.APPROVED, "Grid export is within the configured limit.", "GRID_EXPORT_OK", amount, RiskLevel.LOW, {"safe_quantity_kw": amount}

        if resource_kind == "load":
            if amount < 0:
                return decision, SafetyStatus.REJECTED, "Load reduction or demand action cannot be negative.", "LOAD_NEGATIVE", None, RiskLevel.HIGH, {}
            if decision.quantity_kw is not None and not math.isfinite(float(decision.quantity_kw)):
                return decision, SafetyStatus.REJECTED, "Load value is not valid.", "LOAD_INVALID", None, RiskLevel.CRITICAL, {}
            return decision, SafetyStatus.APPROVED, "Load action is valid.", "LOAD_OK", amount, RiskLevel.LOW, {"safe_quantity_kw": amount}

        if action in {"hold", "reserve", "run", "pause", "delay", "cancel_order", "execute_trade", "place_bid", "place_ask", "use_local"}:
            return decision, SafetyStatus.APPROVED, "Action is valid for the current model.", "ACTION_OK", amount, RiskLevel.LOW, {"safe_quantity_kw": amount}

        return decision, SafetyStatus.REJECTED, f"Action '{decision.action}' is not supported by the safety layer.", "UNSUPPORTED_ACTION", None, RiskLevel.HIGH, {}

    def _apply_cross_decision_checks(
        self,
        state: MicrogridState,
        policy: SafetyPolicy,
        approved: list[AgentDecision],
        modified: list[AgentDecision],
        rejected: list[AgentDecision],
    ) -> tuple[list[AgentDecision], list[AgentDecision], list[AgentDecision]]:
        battery_decisions = [item for item in approved + modified if str(item.resource or "").lower().startswith("battery")]
        charge_total = sum(float(decision.quantity_kw or 0.0) for decision in battery_decisions if str(decision.action).lower() == "charge")
        discharge_total = sum(float(decision.quantity_kw or 0.0) for decision in battery_decisions if str(decision.action).lower() == "discharge")
        if charge_total > 0 and discharge_total > 0:
            for decision in battery_decisions:
                if str(decision.action).lower() in {"charge", "discharge"}:
                    rejected.append(decision)
                    if decision in approved:
                        approved.remove(decision)
                    if decision in modified:
                        modified.remove(decision)
            return approved, modified, rejected

        ev_decisions = [item for item in approved + modified if "ev" in str(item.resource or "").lower() and str(item.action).lower() == "charge"]
        ev_total = sum(float(decision.quantity_kw or 0.0) for decision in ev_decisions)
        ev_allowance = float(policy.max_ev_charge_kw or 7.0)
        if ev_total > ev_allowance and ev_decisions:
            scale = ev_allowance / ev_total if ev_total else 0
            for decision in ev_decisions:
                if decision in approved:
                    approved.remove(decision)
                if decision in modified:
                    modified.remove(decision)
                decision_copy = decision.model_copy(deep=True)
                decision_copy.quantity_kw = round(float(decision.quantity_kw or 0.0) * scale, 2)
                modified.append(decision_copy)
            return approved, modified, rejected

        grid_decisions = [item for item in approved + modified if "grid" in str(item.resource or "").lower() and str(item.action).lower() in {"import", "buy"}]
        grid_total = sum(float(decision.quantity_kw or 0.0) for decision in grid_decisions)
        grid_allowance = float(policy.max_grid_import_kw or 5000.0)
        if grid_total > grid_allowance and grid_decisions:
            scale = grid_allowance / grid_total if grid_total else 0
            for decision in grid_decisions:
                if decision in approved:
                    approved.remove(decision)
                if decision in modified:
                    modified.remove(decision)
                decision_copy = decision.model_copy(deep=True)
                decision_copy.quantity_kw = round(float(decision.quantity_kw or 0.0) * scale, 2)
                modified.append(decision_copy)
            return approved, modified, rejected

        return approved, modified, rejected

    def _determine_overall_status(
        self,
        approved: list[AgentDecision],
        modified: list[AgentDecision],
        rejected: list[AgentDecision],
    ) -> SafetyStatus:
        if rejected:
            return SafetyStatus.REJECTED
        if modified:
            return SafetyStatus.MODIFIED
        return SafetyStatus.APPROVED

    def _determine_overall_risk(
        self,
        approved: list[AgentDecision],
        modified: list[AgentDecision],
        rejected: list[AgentDecision],
    ) -> RiskLevel:
        if rejected:
            return RiskLevel.CRITICAL if len(rejected) > 1 else RiskLevel.HIGH
        if modified:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
