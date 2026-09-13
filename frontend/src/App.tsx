import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import { DashboardPage } from "./pages/dashboard";
import { KarnatakaGridPage } from "./pages/karnataka";
import { PredictionsPage } from "./pages/predictions";
import { AgentsPage } from "./pages/agents";
import { MarketPage } from "./pages/market";
import { SimulationPage } from "./pages/simulation";
import { ScenariosPage } from "./pages/scenarios";
import { AnalyticsPage } from "./pages/analytics";
import { SettingsPage } from "./pages/settings";
import { HopfieldLandscapePage } from "./pages/hopfield";
import { MarketNeuralGraphPage } from "./pages/marketgraph";
import { DigitalTwinPage } from "./pages/twin";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <Header />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/karnataka" element={<KarnatakaGridPage />} />
          <Route path="/predictions" element={<PredictionsPage />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/market" element={<MarketPage />} />
          <Route path="/simulation" element={<SimulationPage />} />
          <Route path="/scenarios" element={<ScenariosPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/hopfield" element={<HopfieldLandscapePage />} />
          <Route path="/marketgraph" element={<MarketNeuralGraphPage />} />
          <Route path="/twin" element={<DigitalTwinPage />} />
        </Routes>
      </main>
      <Footer />
    </BrowserRouter>
  );
}

function Header() {
  const location = useLocation();
  const isActive = (path: string) => location.pathname === path;

  return (
    <header className="app-header">
      <div className="app-header__brand">
        <Link to="/" className="app-header__logo-link">
          <span className="app-header__logo" aria-hidden="true">GM</span>
        </Link>
        <div className="app-header__brand-text">
          <h1 className="app-header__title">
            <Link to="/" className="app-header__title-link">GridMind</Link>
          </h1>
          <p className="app-header__subtitle">
            Autonomous Multi-Agent AI for Resilient Microgrid Coordination
          </p>
        </div>
      </div>
      <nav className="app-nav" aria-label="Main navigation">
        <NavLink to="/" label="Dashboard" active={isActive("/")} />
        <NavLink to="/karnataka" label="Karnataka Grid" active={isActive("/karnataka")} />
        <NavLink to="/predictions" label="Predictions" active={isActive("/predictions")} />
        <NavLink to="/agents" label="AI Agents" active={isActive("/agents")} />
        <NavLink to="/market" label="Market" active={isActive("/market")} />
        <NavLink to="/simulation" label="Simulation" active={isActive("/simulation")} />
        <NavLink to="/scenarios" label="Scenarios" active={isActive("/scenarios")} />
        <NavLink to="/analytics" label="Analytics" active={isActive("/analytics")} />
        <NavLink to="/hopfield" label="Energy 3D" active={isActive("/hopfield")} />
        <NavLink to="/marketgraph" label="Neural Graph" active={isActive("/marketgraph")} />
        <NavLink to="/twin" label="Digital Twin" active={isActive("/twin")} />
        <NavLink to="/settings" label="Settings" active={isActive("/settings")} />
      </nav>
    </header>
  );
}

function NavLink({ to, label, active }: { to: string; label: string; active: boolean }) {
  return (
    <Link
      to={to}
      className={`app-nav__item ${active ? "app-nav__item--active" : ""}`}
    >
      {label}
    </Link>
  );
}

function Footer() {
  return (
    <footer className="app-footer">
      <p>GridMind v1.0.0 — Backend: FastAPI + React</p>
    </footer>
  );
}

export default App;
