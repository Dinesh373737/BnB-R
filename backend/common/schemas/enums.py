"""
GridMind — Enumerations
=========================
ALL enums for the entire project live here.
Modules import from here — never define their own enums.

Usage:
    from backend.common.schemas.enums import RiskLevel, AgentType
    if risk_score > 75:
        level = RiskLevel.HIGH
"""

from enum import Enum


# ══════════════════════════════════════════════════════════════════════════
#  APPLICATION / SYSTEM
# ══════════════════════════════════════════════════════════════════════════


class AppMode(str, Enum):
    """Application deployment mode."""
    LOCAL = "local"
    CLOUD = "cloud"


class DatabaseMode(str, Enum):
    """Database backend type."""
    SQLITE = "sqlite"
    POSTGRES = "postgres"


class SimulationMode(str, Enum):
    """Simulation operating mode."""
    LIVE = "live"           # Uses real Karnataka + weather data
    SIMULATION = "simulation"  # User-controlled parameters


class SimulationStatus(str, Enum):
    """Status of a simulation run."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ══════════════════════════════════════════════════════════════════════════
#  DATA SOURCES
# ══════════════════════════════════════════════════════════════════════════


class DataSourceType(str, Enum):
    """
    Indicates where a data value came from.
    Per the doc: show LIVE / HISTORICAL / SIMULATED / DERIVED / UNAVAILABLE
    rather than pretending unavailable data is live.
    """
    LIVE = "live"
    HISTORICAL = "historical"
    SIMULATED = "simulated"
    DERIVED = "derived"
    UNAVAILABLE = "unavailable"


# ══════════════════════════════════════════════════════════════════════════
#  GRID
# ══════════════════════════════════════════════════════════════════════════


class GridCondition(str, Enum):
    """Karnataka grid operating condition."""
    STABLE = "stable"
    STRESSED = "stressed"
    OUTAGE = "outage"


# ══════════════════════════════════════════════════════════════════════════
#  RISK
# ══════════════════════════════════════════════════════════════════════════


class RiskLevel(str, Enum):
    """System risk level (from Risk & Forecast Agent)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskDriver(str, Enum):
    """Identifiable causes of risk."""
    ENERGY_SHORTAGE = "energy_shortage"
    SUPPLY_DEMAND_IMBALANCE = "supply_demand_imbalance"
    RENEWABLE_DROP = "renewable_generation_drop"
    BATTERY_SHORTAGE = "battery_shortage"
    GRID_OUTAGE = "grid_outage"
    PEAK_DEMAND_STRESS = "peak_demand_stress"
    CRITICAL_LOAD_THREAT = "critical_load_threat"
    HIGH_FORECAST_UNCERTAINTY = "high_forecast_uncertainty"
    SOLAR_DECLINE = "solar_decline"
    WIND_DECLINE = "wind_decline"
    DEMAND_INCREASE = "demand_increase"


# ══════════════════════════════════════════════════════════════════════════
#  AGENTS
# ══════════════════════════════════════════════════════════════════════════


class AgentType(str, Enum):
    """The six AI agents in GridMind."""
    COORDINATOR = "coordinator"
    RISK_FORECAST = "risk_forecast"
    MARKET_TRADING = "market_trading"
    ENERGY_RESOURCE = "energy_resource"
    DEMAND_MANAGEMENT = "demand_management"
    CRITICAL_FACILITY = "critical_facility"


class AgentStatus(str, Enum):
    """Current operational status of an agent."""
    IDLE = "idle"
    OBSERVING = "observing"
    DECIDING = "deciding"
    ACTING = "acting"
    WAITING = "waiting"
    ERROR = "error"
    DISABLED = "disabled"


# ══════════════════════════════════════════════════════════════════════════
#  AGENT ACTIONS (per agent type)
# ══════════════════════════════════════════════════════════════════════════


class CoordinatorAction(str, Enum):
    """Actions the Coordinator Agent can take."""
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    PRIORITIZE = "prioritize"
    COORDINATE = "coordinate"


class ResourceAction(str, Enum):
    """Actions the Energy Resource Agent can take."""
    CHARGE = "charge"
    DISCHARGE = "discharge"
    HOLD = "hold"
    RESERVE = "reserve"
    USE_LOCAL = "use_local"
    SELL = "sell"
    DELAY_EV = "delay_ev"


class DemandAction(str, Enum):
    """Actions the Demand Management Agent can take."""
    RUN = "run"
    DELAY = "delay"
    REDUCE = "reduce"
    SHIFT = "shift"
    PAUSE = "pause"


class MarketAction(str, Enum):
    """Actions the Market & Trading Agent can take."""
    PLACE_BID = "place_bid"
    PLACE_ASK = "place_ask"
    CANCEL_ORDER = "cancel_order"
    EXECUTE_TRADE = "execute_trade"
    HOLD = "hold"


class CriticalFacilityAction(str, Enum):
    """Actions the Critical Facility Agent can take."""
    PROTECT = "protect"
    RESERVE = "reserve"
    RELEASE = "release"
    EMERGENCY = "emergency"
    NORMAL = "normal"


# ══════════════════════════════════════════════════════════════════════════
#  RESOURCES
# ══════════════════════════════════════════════════════════════════════════


class ResourceType(str, Enum):
    """Types of energy resources in the microgrid."""
    SOLAR = "solar"
    WIND = "wind"
    BATTERY = "battery"
    EV = "ev"
    GRID = "grid"


class ResourceStatus(str, Enum):
    """Operational status of a resource."""
    ACTIVE = "active"
    IDLE = "idle"
    CHARGING = "charging"
    DISCHARGING = "discharging"
    OFFLINE = "offline"
    RESERVED = "reserved"
    MAINTENANCE = "maintenance"


# ══════════════════════════════════════════════════════════════════════════
#  MARKET
# ══════════════════════════════════════════════════════════════════════════


class MarketOrderType(str, Enum):
    """Type of market order."""
    BID = "bid"     # Buyer wants energy
    ASK = "ask"     # Seller has energy


class OrderStatus(str, Enum):
    """Status of a market order."""
    PENDING = "pending"
    MATCHED = "matched"
    EXECUTED = "executed"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class TradeStatus(str, Enum):
    """Status of a completed trade."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


# ══════════════════════════════════════════════════════════════════════════
#  SAFETY
# ══════════════════════════════════════════════════════════════════════════


class SafetyStatus(str, Enum):
    """Result of safety validation."""
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class SafetyConstraintType(str, Enum):
    """Types of safety constraints."""
    ENERGY_BALANCE = "energy_balance"
    BATTERY_SOC_LIMIT = "battery_soc_limit"
    CHARGE_RATE_LIMIT = "charge_rate_limit"
    DISCHARGE_RATE_LIMIT = "discharge_rate_limit"
    GRID_POWER_LIMIT = "grid_power_limit"
    ENERGY_AVAILABILITY = "energy_availability"
    MARKET_VALIDITY = "market_validity"
    CRITICAL_LOAD_PROTECTION = "critical_load_protection"


# ══════════════════════════════════════════════════════════════════════════
#  CRITICAL FACILITY
# ══════════════════════════════════════════════════════════════════════════


class CriticalLoadStatus(str, Enum):
    """Protection status of critical facility."""
    PROTECTED = "protected"
    AT_RISK = "at_risk"
    UNPROTECTED = "unprotected"


# ══════════════════════════════════════════════════════════════════════════
#  FORECASTING
# ══════════════════════════════════════════════════════════════════════════


class ForecastType(str, Enum):
    """Type of ML forecast."""
    DEMAND = "demand"
    SOLAR = "solar"
    WIND = "wind"


class ForecastConfidence(str, Enum):
    """Confidence level of a forecast."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MLModelType(str, Enum):
    """Supported ML model types."""
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    SKLEARN = "sklearn"


# ══════════════════════════════════════════════════════════════════════════
#  EVENTS / LOGGING
# ══════════════════════════════════════════════════════════════════════════


class EventType(str, Enum):
    """Types of system events stored in the events table."""
    RISK_UPDATE = "risk_update"
    AGENT_DECISION = "agent_decision"
    MARKET_TRADE = "market_trade"
    STATE_CHANGE = "state_change"
    SCENARIO_TRIGGER = "scenario_trigger"
    SAFETY_CHECK = "safety_check"
    SYSTEM_EVENT = "system_event"
    FORECAST_UPDATE = "forecast_update"
    DATA_UPDATE = "data_update"
    ERROR = "error"


class EventSeverity(str, Enum):
    """Severity of an event."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ══════════════════════════════════════════════════════════════════════════
#  SCENARIOS
# ══════════════════════════════════════════════════════════════════════════


class ScenarioType(str, Enum):
    """Pre-defined crisis scenario types."""
    SOLAR_DROP_DEMAND_SURGE = "solar_drop_demand_surge"  # Primary: Solar -50%, Demand +30%
    GRID_OUTAGE = "grid_outage"
    BATTERY_SHORTAGE = "battery_shortage"
    WIND_DROP = "wind_drop"
    EV_CHARGING_SURGE = "ev_charging_surge"
    EXTREME_WEATHER = "extreme_weather"
    RENEWABLE_FAILURE = "renewable_generation_failure"
    CUSTOM = "custom"


# ══════════════════════════════════════════════════════════════════════════
#  ANALYTICS
# ══════════════════════════════════════════════════════════════════════════


class MetricCategory(str, Enum):
    """Categories of analytics metrics."""
    ECONOMIC = "economic"
    GRID = "grid"
    RENEWABLE = "renewable"
    STORAGE = "storage"
    RESILIENCE = "resilience"
    MARKET = "market"


class AnalyticsMode(str, Enum):
    """Whether analytics are for GridMind or baseline."""
    GRIDMIND = "gridmind"
    BASELINE = "baseline"


# ══════════════════════════════════════════════════════════════════════════
#  WEATHER
# ══════════════════════════════════════════════════════════════════════════


class WeatherCondition(str, Enum):
    """Simplified weather condition categories."""
    CLEAR = "clear"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    RAIN = "rain"
    HEAVY_RAIN = "heavy_rain"
    THUNDERSTORM = "thunderstorm"
    FOG = "fog"
    UNKNOWN = "unknown"
