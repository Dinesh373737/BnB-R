/**
 * GridMind API client
 *
 * Matches the backend REST surface:
 *   GET  /api/data/weather
 *   GET  /api/data/grid
 *   GET  /api/data/grid/history
 *   GET  /api/data/weather/history
 *   GET  /api/health
 *   GET  /api/status
 *   GET  /api/agents/status
 *   POST /api/agents/run
 *   GET  /api/forecast/demand
 *   GET  /api/forecast/solar
 *   GET  /api/forecast/wind
 *   GET  /api/predictions
 *   GET  /api/simulation/state
 *   POST /api/simulation/initialize
 *   POST /api/simulation/step
 *   POST /api/simulation/run
 *   POST /api/simulation/scenarios/primary
 *   GET  /api/market/orders/pending
 *   POST /api/market/orders
 *   POST /api/market/match
 *   GET  /api/market/trades
 *   GET  /api/scenarios
 *   POST /api/scenarios/run
 *   GET  /api/analytics/:runId
 *   GET  /api/analytics/:runId/comparison
 */

const BASE = ""; // relative to the dev server proxy or same-origin deployment

interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

async function request<T>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { params, ...fetchOpts } = options;

  let url = BASE + path;
  if (params) {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        search.set(key, String(value));
      }
    }
    const qs = search.toString();
    if (qs) {
      url += (url.includes("?") ? "&" : "?") + qs;
    }
  }

  const res = await fetch(url, {
    ...fetchOpts,
    headers: {
      "Content-Type": "application/json",
      ...(fetchOpts.headers || {}),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(JSON.stringify(body));
  }

  return res.json();
}

// ── Data Connectors ──────────────────────────────────────────────────────

export const dataApi = {
  weather: (asOf?: string) =>
    request<WeatherSnapshot>("/api/data/weather", {
      params: asOf ? { as_of: asOf } : undefined,
    }),

  grid: (asOf?: string) =>
    request<GridSnapshot>("/api/data/grid", {
      params: asOf ? { as_of: asOf } : undefined,
    }),

  gridHistory: (limit = 50, before?: string) =>
    request<GridSnapshot[]>("/api/data/grid/history", {
      params: { limit, before },
    }),

  weatherHistory: (limit = 50, before?: string) =>
    request<WeatherSnapshot[]>("/api/data/weather/history", {
      params: { limit, before },
    }),
};

// ── Health / Status ──────────────────────────────────────────────────────

export const systemApi = {
  health: () => request<HealthResponse>("/api/health"),
  status: () => request<StatusResponse>("/api/status"),
};

// ── Agents ───────────────────────────────────────────────────────────────

export const agentsApi = {
  status: () => request<AgentStatusResponse>("/api/agents/status"),
  run: (body: RunAgentsRequest) =>
    request<RunAgentsResponse>("/api/agents/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  explain: (agentType: string) =>
    request<AgentExplanationResponse>(`/api/agents/${agentType}/explain`),
  decisions: (agentType: string) =>
    request<AgentDecisionsResponse>(`/api/agents/${agentType}/decisions`),
};

// ── Forecasting ──────────────────────────────────────────────────────────

export const forecastApi = {
  demand: (params?: Partial<ForecastParams>) =>
    request<ForecastResult>("/api/forecast/demand", { params }),
  solar: (params?: Partial<ForecastParams>) =>
    request<ForecastResult>("/api/forecast/solar", { params }),
  wind: (params?: Partial<ForecastParams>) =>
    request<ForecastResult>("/api/forecast/wind", { params }),
  predictions: () => request<PredictionsSummary>("/api/predictions"),
};

// ── Simulation ───────────────────────────────────────────────────────────

export const simulationApi = {
  initialize: (config?: SimulationConfig) =>
    request<MicrogridState>("/api/simulation/initialize", {
      method: "POST",
      body: config ? JSON.stringify(config) : undefined,
    }),

  state: () => request<MicrogridState>("/api/simulation/state"),

  lastResult: () =>
    request<SimulationStepResult>("/api/simulation/last-result").catch(() => null),

  step: (controls?: ControlInputs, conditions?: EnvironmentalConditions) =>
    request<MicrogridState>("/api/simulation/step", {
      method: "POST",
      body: JSON.stringify({ controls, conditions }),
    }),

  run: () => request<MicrogridState[]>("/api/simulation/run", { method: "POST" }),

  activatePrimaryScenario: (startTimestep?: number, durationSteps?: number) =>
    request<ScenarioActivationResponse>("/api/simulation/scenarios/primary", {
      method: "POST",
      body: JSON.stringify({ start_timestep: startTimestep, duration_steps: durationSteps }),
    }),
};

// ── Market ───────────────────────────────────────────────────────────────

export const marketApi = {
  pendingOrders: () => request<MarketOrder[]>("/api/market/orders/pending"),
  placeOrder: (order: OrderCreate) =>
    request<MarketOrder>("/api/market/orders", {
      method: "POST",
      body: JSON.stringify(order),
    }),
  cancelOrder: (orderId: number) =>
    request<MarketOrder>(`/api/market/orders/${orderId}`, {
      method: "DELETE",
    }),
  match: () => request<MarketMatchResult>("/api/market/match", { method: "POST" }),
  trades: () => request<MarketTrade[]>("/api/market/trades"),
};

// ── Scenarios ────────────────────────────────────────────────────────────

export const scenariosApi = {
  list: () => request<Record<string, ScenarioConfig>>("/api/scenarios/"),
  run: (scenarioId: string, baseState: Record<string, unknown>) =>
    request<ScenarioRunResult>("/api/scenarios/run", {
      method: "POST",
      body: JSON.stringify({ scenario_id: scenarioId, base_state: baseState }),
    }),
};

// ── Analytics ────────────────────────────────────────────────────────────

export const analyticsApi = {
  get: (runId: number) => request<AnalyticsResponse>(`/api/analytics/${runId}`),
  comparison: (runId: number) =>
    request<ComparisonResponse>(`/api/analytics/${runId}/comparison`),
  calculate: (runId: number) =>
    request<AnalyticsResponse>(`/api/analytics/${runId}/calculate`, {
      method: "POST",
    }),
  latestRun: () =>
    request<{ latest_run_id: number | null }>("/api/analytics/latest/run"),
};

export const safetyApi = {
  status: () => request<SafetyStatusResponse>("/api/safety/status"),
};

export interface SafetyStatusResponse {
  status: string;
  service: string;
  risk_levels: string[];
}

// ── Shared types (mirror the backend-derived frontend shapes) ────────────

export interface WeatherSnapshot {
  timestamp: string;
  temperature_c: number;
  cloud_cover_percent: number;
  wind_speed_kmh: number;
  solar_radiation_wm2: number;
  is_forecast: boolean;
  weather_condition: string;
  source: string;
  source_confidence?: number | null;
}

export interface GridSnapshot {
  timestamp: string;
  total_demand_mw: number;
  total_generation_mw: number;
  solar_generation_mw: number;
  wind_generation_mw: number;
  grid_frequency_hz: number;
  status: string;
  is_simulated: boolean;
  source: string;
  source_confidence?: number | null;
}

export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  uptime_seconds: number;
  database: string;
  timestamp: string;
}

export interface StatusResponse {
  health: HealthResponse;
  feature_flags: Record<string, unknown>;
  apis: Record<string, unknown>;
  enabled_agents: string[];
  enabled_forecasts: string[];
}

export interface AgentStatusResponse {
  agents: AgentStatusItem[];
  total_agents: number;
  timestamp?: string;
}

export interface AgentStatusItem {
  agent_type: string;
  name: string;
  status: string;
  description?: string;
  last_decisions_count?: number;
  llm_available?: boolean;
}

export interface RunAgentsRequest {
  state: MicrogridState;
}

export interface RunAgentsResponse {
  success: boolean;
  agent_results: AgentResult[];
  coordination?: CoordinationResult | null;
  safety_result?: SafetyValidationResult | null;
  risk_level: string;
  risk_score: number;
  total_decisions: number;
  approved_decisions: number;
  rejected_decisions: number;
  timestamp?: string;
}

export interface AgentResult {
  agent_type: string;
  decisions: AgentDecision[];
  reasoning?: string;
  status?: string;
}

export interface AgentDecision {
  agent: string;
  action: string;
  resource: string;
  quantity_kw?: number | null;
  quantity_kwh?: number | null;
  duration_minutes?: number | null;
  reason?: string;
  expected_effect?: string;
  confidence?: number | null;
  priority?: number | null;
}

export interface CoordinationResult {
  approved_decisions: AgentDecision[];
  rejected_decisions: AgentDecision[];
  modified_decisions: AgentDecision[];
  resolution_reason?: string;
}

export interface SafetyValidationResult {
  overall_status: string;
  approved_decisions: AgentDecision[];
  modified_decisions: AgentDecision[];
  rejected_decisions: AgentDecision[];
  risk_level: string;
  reasons: string[];
  violations: string[];
  validation_details?: SafeDecisionOutcome[];
  timestamp: string;
}

export interface SafeDecisionOutcome {
  status: string;
  risk_level: string;
  original_decision?: AgentDecision;
  safe_decision?: AgentDecision;
  reason?: string;
  rule?: string;
  limit?: number | null;
  details?: Record<string, unknown>;
}

export interface AgentExplanationResponse {
  agent_type: string;
  inputs: Record<string, unknown>;
  decisions: AgentDecision[];
  reason: string;
  expected_effect: string;
}

export interface AgentDecisionsResponse {
  agent_type: string;
  decisions: AgentDecision[];
  total: number;
}

export interface ForecastResult {
  forecast_type: string;
  timestamp: string;
  current_value?: number | null;
  prediction: number;
  lower?: number | null;
  upper?: number | null;
  confidence: string;
  horizon_minutes: number;
  model_type: string;
  unit: string;
}

export interface ForecastParams {
  horizon_minutes?: number;
  current_value?: number;
  temperature_c?: number;
  cloud_cover_pct?: number;
  solar_radiation_wm2?: number;
  wind_speed_ms?: number;
}

export interface PredictionsSummary {
  timestamp: string;
  demand: ForecastResult;
  solar: ForecastResult;
  wind: ForecastResult;
  total_generation_forecast: number;
  net_position: number;
}

export interface MicrogridState {
  timestamp: string;
  simulation_run_id?: number | null;
  timestep: number;
  total_demand_kw: number;
  total_generation_kw: number;
  renewable_generation_kw: number;
  renewable_percentage: number;
  energy_balance_kw: number;
  grid_dependency_pct: number;
  solar: ResourceState;
  wind: ResourceState;
  battery: BatteryState;
  ev: EvState;
  households: DemandState;
  industry: DemandState;
  critical_facility: CriticalFacilityState;
  grid_connection: GridConnectionState;
  market: MarketState;
  forecast: ForecastState;
  risk: RiskState;
  weather: WeatherState;
  data_source: string;
}

export interface ResourceState {
  capacity_kw: number;
  current_output_kw: number;
  utilization_pct: number;
  forecast_output_kw?: number | null;
  status: string;
  data_source: string;
}

export interface BatteryState {
  capacity_kwh: number;
  current_soc: number;
  soc_percentage: number;
  current_power_kw: number;
  min_soc: number;
  max_soc: number;
  charge_rate_kw: number;
  discharge_rate_kw: number;
  energy_available_kwh: number;
  status: string;
}

export interface EvState {
  total_count: number;
  connected_count: number;
  charging_count: number;
  total_demand_kw: number;
  total_battery_kwh: number;
  average_soc: number;
  flexible_demand_kw: number;
}

export interface DemandState {
  count: number;
  total_demand_kw: number;
  flexible_demand_kw: number;
  fixed_demand_kw: number;
}

export interface CriticalFacilityState {
  required_power_kw: number;
  current_supply_kw: number;
  backup_energy_kwh: number;
  reserve_power_kw: number;
  status: string;
  is_protected: boolean;
}

export interface GridConnectionState {
  condition: string;
  import_power_kw: number;
  export_power_kw: number;
  import_limit_kw: number;
  export_limit_kw: number;
  is_connected: boolean;
  electricity_price_per_kwh: number;
}

export interface MarketState {
  is_active: boolean;
  total_energy_traded_kwh: number;
  active_bids: number;
  active_asks: number;
  last_clearing_price: number;
  total_transactions: number;
}

export interface ForecastState {
  demand_forecast_kw?: number | null;
  demand_lower_kw?: number | null;
  demand_upper_kw?: number | null;
  solar_forecast_kw?: number | null;
  solar_lower_kw?: number | null;
  solar_upper_kw?: number | null;
  wind_forecast_kw?: number | null;
  wind_lower_kw?: number | null;
  wind_upper_kw?: number | null;
  forecast_horizon_minutes: number;
  uncertainty_level: string;
}

export interface RiskState {
  risk_score: number;
  risk_level: string;
  drivers: string[];
  assessment_timestamp: string;
}

export interface WeatherState {
  temperature_c?: number | null;
  cloud_cover_pct?: number | null;
  solar_radiation_wm2?: number | null;
  wind_speed_ms?: number | null;
  weather_condition: string;
  data_source: string;
}

export interface SimulationConfig {
  timestep_seconds?: number;
  solar_capacity_kw?: number;
  wind_capacity_kw?: number;
  battery_capacity_kwh?: number;
  battery_initial_soc?: number;
  household_count?: number;
  ev_total_count?: number;
  critical_load_kw?: number;
  grid_import_limit_kw?: number;
  grid_export_limit_kw?: number;
}

export interface ControlInputs {
  battery_power_kw?: number;
  household_flexible_demand_kw?: number | null;
  industry_flexible_demand_kw?: number | null;
  ev_flexible_demand_kw?: number | null;
}

export interface EnvironmentalConditions {
  solar_capacity_factor?: number | null;
  wind_capacity_factor?: number | null;
  grid_connected?: boolean | null;
  grid_condition?: string | null;
  temperature_c?: number | null;
  cloud_cover_pct?: number | null;
  solar_radiation_wm2?: number | null;
  wind_speed_ms?: number | null;
  weather_condition?: string;
}

export interface ScenarioActivationResponse {
  scenario: string;
  start_timestep: number | null;
  duration_steps: number | null;
}

export interface SimulationStepResult {
  state: MicrogridState;
  requested_demand_kw: number;
  served_demand_kw: number;
  unserved_load_kw: number;
  curtailed_generation_kw: number;
  critical_load_supply_kw: number;
  active_scenario?: string | null;
  completed_at: string;
}

export interface MarketOrder {
  id: number;
  participant_id: string;
  participant_name?: string | null;
  order_type: string;
  energy_kwh: number;
  price_per_kwh: number;
  status: string;
  matched_with_id?: number | null;
  timestamp: string;
  simulation_run_id?: number | null;
  timestep: number;
}

export interface OrderCreate {
  participant_id: string;
  participant_name?: string;
  order_type: "bid" | "ask";
  energy_kwh: number;
  price_per_kwh: number;
}

export interface MarketMatchResult {
  matched_pairs: number;
  trades_executed: number;
  message: string;
}

export interface MarketTrade {
  id: number;
  seller_id: string;
  seller_name?: string | null;
  buyer_id: string;
  buyer_name?: string | null;
  energy_kwh: number;
  price_per_kwh: number;
  total_cost?: number | null;
  status: string;
  reason?: string | null;
  timestamp: string;
  simulation_run_id?: number | null;
  timestep: number;
}

export interface ScenarioConfig {
  id: string;
  name: string;
  description: string;
  scenario_type: string;
  solar_multiplier: number;
  wind_multiplier: number;
  demand_multiplier: number;
  grid_available?: boolean | null;
  battery_capacity_multiplier: number;
  custom_parameters?: Record<string, unknown>;
}

export interface ScenarioRunResult {
  scenario_id: string;
  scenario_name: string;
  original_state: Record<string, unknown>;
  modified_state: Record<string, unknown>;
  logs: string[];
}

export interface AnalyticsResponse {
  success: boolean;
  message: string;
  simulation_run_id: number;
  mode: string;
  metrics: FullMetricSet;
}

export interface ComparisonResponse {
  success: boolean;
  message: string;
  comparison: ComparisonResult;
}

export interface FullMetricSet {
  economic: EconomicMetrics;
  grid: GridMetrics;
  renewable: RenewableMetrics;
  storage: StorageMetrics;
  resilience: ResilienceMetrics;
  market: MarketMetrics;
}

export interface EconomicMetrics {
  total_cost: number;
  average_cost_per_kwh: number;
  cost_savings_percent: number;
}

export interface GridMetrics {
  peak_demand_kw: number;
  peak_reduction_percent: number;
}

export interface RenewableMetrics {
  renewable_utilization_percent: number;
  solar_utilization_percent: number;
  renewable_curtailment_kwh: number;
}

export interface StorageMetrics {
  battery_utilization_percent: number;
  battery_reserve_percent: number;
}

export interface ResilienceMetrics {
  unserved_energy_kwh: number;
  critical_load_protection_percent: number;
  recovery_time_minutes: number;
}

export interface MarketMetrics {
  total_energy_traded_kwh: number;
  transaction_count: number;
  average_trading_price: number;
}

export interface ComparisonResult {
  simulation_run_id: number | null;
  scenario?: string | null;
  timestamp?: string;
  baseline: FullMetricSet;
  gridmind: FullMetricSet;
  improvement: ImprovementMetrics;
}

export interface ImprovementMetrics {
  cost_savings_percent: number;
  peak_reduction_percent: number;
  renewable_improvement_percent: number;
  unserved_energy_reduction_percent: number;
  critical_load_improvement_percent: number;
  recovery_time_improvement_percent: number;
}
