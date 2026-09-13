"""
GridMind — Custom Exceptions
==============================
All custom exception classes for the entire project.
Modules raise these — the FastAPI error handlers catch them.

Usage:
    from backend.common.exceptions import AgentError, SafetyViolationError
    raise AgentError("risk_forecast", "Failed to compute risk score")
"""


class GridMindError(Exception):
    """Base exception for all GridMind errors."""

    def __init__(self, message: str = "An unexpected GridMind error occurred"):
        self.message = message
        super().__init__(self.message)


# ── Database ──────────────────────────────────────────────────────────────


class DatabaseError(GridMindError):
    """Raised for database connection, query, or migration errors."""

    def __init__(self, message: str = "Database error", operation: str = ""):
        self.operation = operation
        super().__init__(f"[DB:{operation}] {message}" if operation else message)


# ── Configuration ─────────────────────────────────────────────────────────


class ConfigurationError(GridMindError):
    """Raised when a required configuration value is missing or invalid."""

    def __init__(self, key: str, message: str = ""):
        self.key = key
        msg = f"Configuration error for '{key}'"
        if message:
            msg += f": {message}"
        super().__init__(msg)


# ── Validation ────────────────────────────────────────────────────────────


class ValidationError(GridMindError):
    """Raised when input data fails validation."""

    def __init__(self, field: str = "", message: str = "Validation failed"):
        self.field = field
        msg = f"[{field}] {message}" if field else message
        super().__init__(msg)


# ── Agent Errors ──────────────────────────────────────────────────────────


class AgentError(GridMindError):
    """Raised when an AI agent encounters an error during execution."""

    def __init__(self, agent_name: str, message: str = "Agent execution failed"):
        self.agent_name = agent_name
        super().__init__(f"[Agent:{agent_name}] {message}")


class AgentCommunicationError(AgentError):
    """Raised when agent-to-agent or agent-to-coordinator communication fails."""

    def __init__(
        self,
        sender: str,
        receiver: str = "coordinator",
        message: str = "Communication failed",
    ):
        self.sender = sender
        self.receiver = receiver
        super().__init__(sender, f"→ {receiver}: {message}")


# ── Safety ────────────────────────────────────────────────────────────────


class SafetyViolationError(GridMindError):
    """Raised when an agent decision violates a safety constraint."""

    def __init__(
        self,
        constraint: str,
        agent_name: str = "",
        message: str = "Safety constraint violated",
    ):
        self.constraint = constraint
        self.agent_name = agent_name
        prefix = f"[Safety:{constraint}]"
        if agent_name:
            prefix += f"[Agent:{agent_name}]"
        super().__init__(f"{prefix} {message}")


# ── Data Connectors ───────────────────────────────────────────────────────


class DataConnectorError(GridMindError):
    """Raised when an external data source (Karnataka API, Weather) fails."""

    def __init__(
        self,
        source: str,
        message: str = "Data connector error",
        status_code: int | None = None,
    ):
        self.source = source
        self.status_code = status_code
        msg = f"[DataSource:{source}] {message}"
        if status_code:
            msg += f" (HTTP {status_code})"
        super().__init__(msg)


# ── Forecasting ───────────────────────────────────────────────────────────


class ForecastError(GridMindError):
    """Raised when ML forecasting fails (model loading, prediction, training)."""

    def __init__(
        self,
        forecast_type: str = "",
        message: str = "Forecast error",
    ):
        self.forecast_type = forecast_type
        msg = f"[Forecast:{forecast_type}] {message}" if forecast_type else message
        super().__init__(msg)


class ModelNotFoundError(ForecastError):
    """Raised when a trained ML model file cannot be found."""

    def __init__(self, model_path: str, forecast_type: str = ""):
        self.model_path = model_path
        super().__init__(forecast_type, f"Model file not found: {model_path}")


# ── Market ────────────────────────────────────────────────────────────────


class MarketError(GridMindError):
    """Raised for P2P market engine errors (bidding, matching, clearing)."""

    def __init__(self, message: str = "Market engine error", operation: str = ""):
        self.operation = operation
        msg = f"[Market:{operation}] {message}" if operation else message
        super().__init__(msg)


class InsufficientEnergyError(MarketError):
    """Raised when a trade cannot be fulfilled due to insufficient energy."""

    def __init__(self, required_kwh: float, available_kwh: float):
        self.required_kwh = required_kwh
        self.available_kwh = available_kwh
        super().__init__(
            f"Insufficient energy: need {required_kwh} kWh, have {available_kwh} kWh",
            operation="trade",
        )


# ── Simulation ────────────────────────────────────────────────────────────


class SimulationError(GridMindError):
    """Raised when the simulation engine encounters an error."""

    def __init__(self, message: str = "Simulation error", step: int | None = None):
        self.step = step
        msg = f"[Sim:step={step}] {message}" if step is not None else message
        super().__init__(msg)


class ScenarioError(SimulationError):
    """Raised when a scenario configuration is invalid."""

    def __init__(self, scenario_name: str, message: str = "Invalid scenario"):
        self.scenario_name = scenario_name
        super().__init__(f"[Scenario:{scenario_name}] {message}")


# ── WebSocket ─────────────────────────────────────────────────────────────


class WebSocketError(GridMindError):
    """Raised for WebSocket connection or broadcast errors."""

    def __init__(self, channel: str = "", message: str = "WebSocket error"):
        self.channel = channel
        msg = f"[WS:{channel}] {message}" if channel else message
        super().__init__(msg)
