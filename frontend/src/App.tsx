import { useEffect, useState } from "react";
import HPIDashboardView from "./components/dashboard/HPIDashboardView";
import InterventionExplorer from "./components/interventions/InterventionExplorer";
import Optimization from "./components/interventions/Optimization";
import ScenarioLab from "./components/interventions/ScenarioLab";
import { MapShell } from "./components/map/MapShell";
import { getHealth, type HealthResponse } from "./services/api";
import "./styles.css";

const views = [
  "Dashboard",
  "Heat Map",
  "Area Analysis",
  "Intervention Explorer",
  "Scenario Lab",
  "Optimization",
  "Validation / Trust",
];

export default function App() {
  const [activeView, setActiveView] = useState("Dashboard");
  const [scenarioBudget, setScenarioBudget] = useState<number | undefined>(undefined);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getHealth()
      .then((data) => {
        if (!cancelled) {
          setHealth(data);
          setApiError(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setApiError(
            error instanceof Error ? error.message : "Backend unavailable",
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const backendConnected = health?.status === "ok";
  const databaseConnected = health?.database === "connected";

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">URBAN HEAT ANALYSIS PLATFORM</p>
          <h1>HEATSENSE AI</h1>
        </div>

        <div className="status-pill">
          <span
            className={
              backendConnected ? "status-dot" : "status-dot offline"
            }
          />
          {backendConnected ? "API Connected" : "API Offline"}
        </div>
      </header>

      <main className="app-main">
        <aside className="sidebar" aria-label="Application navigation">
          <h2>Workspace</h2>

          <nav>
            {views.map((view) => {
              const isEnabled =
                view === "Dashboard" ||
                view === "Heat Map" ||
                view === "Area Analysis" ||
                view === "Intervention Explorer" ||
                view === "Scenario Lab" ||
                view === "Optimization";
              const isActive = activeView === view;

              return (
                <button
                  className={isActive ? "nav-item active" : "nav-item"}
                  key={view}
                  type="button"
                  disabled={!isEnabled}
                  onClick={() => isEnabled && setActiveView(view)}
                >
                  <div className="flex items-center justify-between">
                    <span>{view}</span>
                    {!isEnabled && (
                      <span className="text-[10px] text-slate-400 font-mono">Stage D</span>
                    )}
                  </div>
                </button>
              );
            })}
          </nav>

          <div className="scope-note">
            <div className="font-semibold text-slate-700">Stage C & D Verified</div>
            <p className="mt-1 text-slate-500">
              Authoritative 100m analytical grid, multi-temporal persistence (2021–2026), and physics-informed cooling recommendations for SMC Surat.
            </p>
          </div>
        </aside>

        <section className="workspace">
          {activeView === "Dashboard" && (
            <>
              <div className="workspace-heading">
                <div>
                  <p className="eyebrow">STAGE C EXECUTIVE DASHBOARD</p>
                  <h2>Heat Priority Index Analytics</h2>
                </div>
                <p className="muted">
                  Surat Municipal Corporation · 49,747 Cells
                </p>
              </div>

              <HPIDashboardView onSwitchToMap={() => setActiveView("Heat Map")} />
            </>
          )}

          {activeView === "Heat Map" && (
            <>
              <div className="workspace-heading">
                <div>
                  <p className="eyebrow">HEAT PRIORITY MAP</p>
                  <h2>Stage C Analytical Grid & Observations</h2>
                </div>
                <p className="muted">
                  Interactive 100m Viewport Grid & Landsat LST
                </p>
              </div>

              <MapShell initialTool="grid" />
            </>
          )}

          {activeView === "Area Analysis" && (
            <>
              <div className="workspace-heading">
                <div>
                  <p className="eyebrow">ZONAL ANALYSIS</p>
                  <h2>Custom Polygon Heat Analysis</h2>
                </div>
                <p className="muted">
                  Draw custom polygons & compute Landsat zonal statistics
                </p>
              </div>

              <MapShell initialTool="drawing" />
            </>
          )}

          {activeView === "Intervention Explorer" && (
            <>
              <div className="workspace-heading">
                <div>
                  <p className="eyebrow">STAGE D PRESCRIPTIVE CATALOG</p>
                  <h2>Intervention Candidate Explorer</h2>
                </div>
                <p className="muted">
                  Physics-calibrated cooling interventions for Surat Municipal Corporation
                </p>
              </div>

              <InterventionExplorer
                onSwitchToMap={() => setActiveView("Heat Map")}
              />
            </>
          )}

          {activeView === "Scenario Lab" && (
            <>
              <div className="workspace-heading">
                <div>
                  <p className="eyebrow">STAGE D SCENARIO PLANNING</p>
                  <h2>Urban Heat Mitigation Scenario Lab</h2>
                </div>
                <p className="muted">
                  Multi-tier capital budget benchmarks & custom portfolio simulator for SMC Surat
                </p>
              </div>

              <ScenarioLab
                onSwitchToMap={() => setActiveView("Heat Map")}
                onSwitchToOptimization={(budget) => {
                  setScenarioBudget(budget);
                  setActiveView("Optimization");
                }}
              />
            </>
          )}

          {activeView === "Optimization" && (
            <>
              <div className="workspace-heading">
                <div>
                  <p className="eyebrow">STAGE D CONSTRAINED OPTIMIZATION</p>
                  <h2>Multi-Objective Cooling Optimization</h2>
                </div>
                <p className="muted">
                  NSGA-II Pareto genetic algorithm & greedy knapsack budget allocation for SMC Surat
                </p>
              </div>

              <Optimization
                initialBudgetInr={scenarioBudget}
                onSwitchToMap={() => setActiveView("Heat Map")}
              />
            </>
          )}

          <div className="connection-panel">
            <div>
              <span className="connection-label">Backend</span>
              <strong>
                {backendConnected ? "Connected" : "Unavailable"}
              </strong>
            </div>

            <div>
              <span className="connection-label">Database</span>
              <strong>
                {databaseConnected ? "Connected" : "Unavailable"}
              </strong>
            </div>

            {apiError && (
              <div>
                <span className="connection-label">Error</span>
                <strong>{apiError}</strong>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}