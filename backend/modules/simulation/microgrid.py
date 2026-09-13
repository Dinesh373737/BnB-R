"""Deterministic physical models for microgrid components."""

from dataclasses import dataclass

from backend.common.schemas.enums import (
    CriticalLoadStatus,
    GridCondition,
    ResourceStatus,
)


@dataclass
class RenewableGenerator:
    """A capacity-limited renewable generator."""

    capacity_kw: float
    current_output_kw: float = 0.0

    def generate(self, capacity_factor: float, multiplier: float = 1.0) -> float:
        """Calculate output without exceeding rated capacity."""
        factor = max(0.0, min(1.0, capacity_factor))
        adjusted = max(0.0, multiplier)
        self.current_output_kw = min(self.capacity_kw, self.capacity_kw * factor * adjusted)
        return self.current_output_kw

    @property
    def utilization_pct(self) -> float:
        if self.capacity_kw <= 0:
            return 0.0
        return self.current_output_kw / self.capacity_kw * 100.0


class SolarGenerator(RenewableGenerator):
    """Solar generation component; output follows irradiance/capacity factor."""


class WindGenerator(RenewableGenerator):
    """Wind generation component; output follows wind/capacity factor."""


@dataclass
class Battery:
    """Battery model using the shared sign convention: charge positive."""

    capacity_kwh: float
    current_soc: float
    min_soc: float
    max_soc: float
    charge_rate_kw: float
    discharge_rate_kw: float
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    current_power_kw: float = 0.0

    @property
    def energy_kwh(self) -> float:
        return self.current_soc * self.capacity_kwh

    @property
    def energy_available_kwh(self) -> float:
        return max(0.0, (self.current_soc - self.min_soc) * self.capacity_kwh)

    @property
    def status(self) -> ResourceStatus:
        if self.current_power_kw > 1e-9:
            return ResourceStatus.CHARGING
        if self.current_power_kw < -1e-9:
            return ResourceStatus.DISCHARGING
        return ResourceStatus.IDLE

    def apply_power(self, requested_power_kw: float, timestep_hours: float) -> float:
        """Apply a feasible setpoint and return the actual AC-side power.

        Charging uses ``power * duration * charge_efficiency`` stored energy.
        Discharging removes ``power * duration / discharge_efficiency`` stored
        energy.  The method never violates SOC or rate bounds.
        """
        if self.capacity_kwh <= 0 or timestep_hours <= 0:
            self.current_power_kw = 0.0
            return 0.0

        if requested_power_kw >= 0:
            room_kwh = max(0.0, (self.max_soc - self.current_soc) * self.capacity_kwh)
            soc_limited_kw = room_kwh / (timestep_hours * self.charge_efficiency)
            actual = min(requested_power_kw, self.charge_rate_kw, soc_limited_kw)
            self.current_soc += actual * timestep_hours * self.charge_efficiency / self.capacity_kwh
        else:
            requested_discharge_kw = -requested_power_kw
            available_kwh = self.energy_available_kwh
            soc_limited_kw = available_kwh * self.discharge_efficiency / timestep_hours
            discharge_kw = min(requested_discharge_kw, self.discharge_rate_kw, soc_limited_kw)
            actual = -discharge_kw
            self.current_soc -= discharge_kw * timestep_hours / self.discharge_efficiency / self.capacity_kwh

        self.current_soc = min(self.max_soc, max(self.min_soc, self.current_soc))
        self.current_power_kw = actual
        return actual


@dataclass(frozen=True)
class HouseholdLoad:
    """Aggregated fixed and flexible household demand."""

    count: int
    fixed_demand_per_household_kw: float
    flexible_demand_per_household_kw: float

    def resolve_demand(
        self,
        flexible_multiplier: float = 1.0,
        requested_flexible_kw: float | None = None,
    ) -> tuple[float, float]:
        """Return non-negative fixed and flexible household demand in kW."""
        fixed_kw = max(0.0, self.count * self.fixed_demand_per_household_kw)
        if requested_flexible_kw is not None:
            flexible_kw = requested_flexible_kw
        else:
            flexible_kw = (
                self.count
                * self.flexible_demand_per_household_kw
                * max(0.0, flexible_multiplier)
            )
        return fixed_kw, max(0.0, flexible_kw)


@dataclass(frozen=True)
class IndustrialLoad:
    """Aggregated industrial fixed and flexible demand."""

    fixed_demand_kw: float
    flexible_demand_kw: float

    def resolve_demand(
        self,
        flexible_multiplier: float = 1.0,
        requested_flexible_kw: float | None = None,
    ) -> tuple[float, float]:
        """Return non-negative fixed and flexible industrial demand in kW."""
        flexible_kw = (
            requested_flexible_kw
            if requested_flexible_kw is not None
            else self.flexible_demand_kw * max(0.0, flexible_multiplier)
        )
        return max(0.0, self.fixed_demand_kw), max(0.0, flexible_kw)


@dataclass(frozen=True)
class EVFleet:
    """Flexible electric-vehicle demand for the current microgrid timestep."""

    total_count: int
    connected_count: int
    battery_kwh_per_vehicle: float
    average_soc: float
    flexible_demand_kw: float

    @property
    def total_battery_kwh(self) -> float:
        return max(0.0, self.total_count * self.battery_kwh_per_vehicle)

    def resolve_demand(
        self,
        flexible_multiplier: float = 1.0,
        requested_demand_kw: float | None = None,
    ) -> float:
        """Return non-negative EV charging demand without scheduling EVs."""
        if requested_demand_kw is not None:
            return max(0.0, requested_demand_kw)
        return max(0.0, self.flexible_demand_kw * max(0.0, flexible_multiplier))


@dataclass(frozen=True)
class CriticalFacility:
    """Non-flexible critical demand that receives physical supply priority."""

    required_power_kw: float
    backup_energy_kwh: float = 0.0

    def supply_status(self, available_power_kw: float) -> tuple[float, CriticalLoadStatus, bool]:
        """Allocate available physical supply to the facility before other loads."""
        required_kw = max(0.0, self.required_power_kw)
        supplied_kw = min(required_kw, max(0.0, available_power_kw))
        if supplied_kw >= required_kw - 1e-9:
            return supplied_kw, CriticalLoadStatus.PROTECTED, True
        if supplied_kw > 1e-9:
            return supplied_kw, CriticalLoadStatus.AT_RISK, False
        return supplied_kw, CriticalLoadStatus.UNPROTECTED, False


@dataclass(frozen=True)
class GridExchange:
    """Actual power exchanged with the upstream grid in one timestep."""

    import_power_kw: float = 0.0
    export_power_kw: float = 0.0


@dataclass
class GridConnection:
    """Physical upstream-grid connection with import/export limits."""

    import_limit_kw: float
    export_limit_kw: float
    is_connected: bool
    condition: GridCondition

    def exchange(self, local_balance_kw: float) -> GridExchange:
        """Balance local shortage/surplus as far as the grid permits."""
        if not self.is_connected or self.condition == GridCondition.OUTAGE:
            return GridExchange()
        if local_balance_kw < 0:
            return GridExchange(import_power_kw=min(-local_balance_kw, self.import_limit_kw))
        if local_balance_kw > 0:
            return GridExchange(export_power_kw=min(local_balance_kw, self.export_limit_kw))
        return GridExchange()
