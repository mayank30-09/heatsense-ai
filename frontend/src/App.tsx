import { lazy, Suspense, useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "./services/api";
import { fetchHeatPrioritySummary } from "./services/heatPriorityApi";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ScienceGlossaryModal from "./components/common/ScienceGlossaryModal";
import "./styles.css";

// Lazy-loaded route-level views for efficient code-splitting
const HPIDashboardView = lazy(() => import("./components/dashboard/HPIDashboardView"));
const ValidationTrust = lazy(() => import("./components/dashboard/ValidationTrust"));
const InterventionExplorer = lazy(() => import("./components/interventions/InterventionExplorer"));
const Optimization = lazy(() => import("./components/interventions/Optimization"));
const ScenarioLab = lazy(() => import("./components/interventions/ScenarioLab"));
const MapShell = lazy(() =>
  import("./components/map/MapShell").then((m) => ({ default: m.MapShell }))
);

const views = [
  "Dashboard",
  "Heat Map",
  "Area Analysis",
  "Intervention Explorer",
  "Scenario Lab",
  "Optimization",
  "Validation / Trust",
];

function ViewLoadingSkeleton({ viewName }: { viewName: string }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[420px] rounded-xl border border-slate-200 bg-white p-12 text-slate-500 shadow-xs">
      <div className="h-8 w-8 animate-spin rounded-full border-3 border-indigo-600 border-t-transparent mb-3" />
      <span className="text-sm font-semibold text-slate-700">Loading {viewName}…</span>
      <span className="text-xs text-slate-400 mt-1">Fetching component chunk and satellite datasets</span>
    </div>
  );
}

function AppContent() {
  const { user, role, isAuthenticated, logout } = useAuth();
  const [activeView, setActiveView] = useState("Dashboard");
  const [scenarioBudget, setScenarioBudget] = useState<number | undefined>(undefined);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [showGlossary, setShowGlossary] = useState<boolean>(false);
  const [observationDates, setObservationDates] = useState<Record<string, string> | null>(null);

  const checkHealth = () => {
    getHealth()
      .then((data) => {
        setHealth(data);
        setApiError(null);
      })
      .catch((error: unknown) => {
        setApiError(
          error instanceof Error ? error.message : "Backend unavailable"
        );
      });
  };

  useEffect(() => {
    checkHealth();
    fetchHeatPrioritySummary()
      .then((data) => {
        if (data.seasonal_observation_dates) {
          setObservationDates(data.seasonal_observation_dates);
        }
      })
      .catch(() => {
        // Fallback or offline state handled gracefully
      });
  }, []);

  const backendConnected = health?.status === "ok";
  const databaseConnected = health?.database === "connected";

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-700 text-white shadow-xs"
            aria-hidden="true"
          >
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="3" y="3" width="18" height="18" rx="4" />
              <path d="M3 9h18M3 15h18M9 3v18M15 3v18" strokeOpacity="0.4" />
              <circle cx="12" cy="12" r="3" fill="currentColor" fillOpacity="0.9" />
            </svg>
          </div>
          <div>
            <p className="eyebrow">URBAN HEAT ANALYSIS PLATFORM</p>
            <h1>HEATSENSE AI</h1>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowGlossary(true)}
            aria-label="Open science and metric glossary"
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 hover:border-slate-300 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-1"
          >
            <span aria-hidden="true">📖</span>
            <span>Science Glossary</span>
          </button>

          {isAuthenticated && user && (
            <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3.5 py-1 text-xs shadow-xs">
              <span className="font-semibold text-slate-800">{user.username}</span>
              <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-800">
                {role}
              </span>
              <button
                type="button"
                onClick={logout}
                aria-label="Sign out of account"
                className="ml-1 text-slate-400 hover:text-slate-700 text-xs font-semibold cursor-pointer focus:outline-none focus:ring-1 focus:ring-slate-300 rounded px-1 py-0.5"
              >
                Logout
              </button>
            </div>
          )}

          <div
            className="status-pill"
            role="status"
            aria-label={`API status: ${backendConnected ? "Connected" : "Offline"}`}
          >
            <span
              className={
                backendConnected ? "status-dot" : "status-dot offline"
              }
            />
            <span>{backendConnected ? "API Connected" : "API Offline"}</span>
          </div>
        </div>
      </header>

      <main className="app-main">
        <aside className="sidebar" aria-label="Application navigation">
          <h2>Workspace</h2>

          <nav role="tablist" aria-label="Workspace views">
            {views.map((view) => {
              const isActive = activeView === view;

              return (
                <button
                  role="tab"
                  aria-selected={isActive}
                  aria-label={`Switch to ${view} view`}
                  className={isActive ? "nav-item active" : "nav-item"}
                  key={view}
                  type="button"
                  onClick={() => setActiveView(view)}
                >
                  <div className="flex items-center justify-between">
                    <span>{view}</span>
                  </div>
                </button>
              );
            })}
          </nav>

          <div className="scope-note">
            <div className="font-semibold text-slate-700">Stage C & D Specification</div>
            <p className="mt-1 text-slate-500 text-xs leading-relaxed">
              Authoritative 100m analytical grid, multi-temporal Landsat thermal observations, and surface energy balance cooling optimization for SMC Surat.
            </p>
          </div>
        </aside>

        <section className="workspace" role="region" aria-label={`${activeView} content`}>
          <Suspense fallback={<ViewLoadingSkeleton viewName={activeView} />}>
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

                <MapShell initialTool="grid" mode="heat_map" />
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

                <MapShell initialTool="drawing" mode="area_analysis" />
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
                    Surface energy balance cooling interventions for Surat Municipal Corporation
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

            {activeView === "Validation / Trust" && (
              <>
                <div className="workspace-heading">
                  <div>
                    <p className="eyebrow">STAGE C & D TRANSPARENCY</p>
                    <h2>Model Validation & Trust Center</h2>
                  </div>
                  <p className="muted">
                    Spatial cross-validation, independent holdouts, error diagnostics & sensor provenance
                  </p>
                </div>

                <ValidationTrust
                  onSwitchToMap={() => setActiveView("Heat Map")}
                />
              </>
            )}
          </Suspense>

          <footer className="connection-panel" aria-label="System connectivity status">
            <div className="connection-item">
              <span className="connection-label">Backend API:</span>
              <span className={backendConnected ? "connection-badge-connected" : "connection-badge-unavailable"}>
                <span className={`status-dot ${backendConnected ? "bg-emerald-600" : "bg-rose-600"}`} />
                <span>{backendConnected ? "Connected (127.0.0.1:8000)" : "Unavailable"}</span>
              </span>
            </div>

            <div className="connection-item">
              <span className="connection-label">PostGIS Database:</span>
              <span className={databaseConnected ? "connection-badge-connected" : "connection-badge-unavailable"}>
                <span className={`status-dot ${databaseConnected ? "bg-emerald-600" : "bg-rose-600"}`} />
                <span>{databaseConnected ? "Connected (127.0.0.1:5433)" : "Unavailable"}</span>
              </span>
            </div>

            {observationDates && (
              <div className="connection-item text-slate-600 text-xs flex-wrap">
                <span className="connection-label font-bold text-slate-700">Latest observation date:</span>
                <span className="font-mono text-[11px] text-slate-800">
                  {Object.entries(observationDates)
                    .map(([season, date]) => `${season}: ${date}`)
                    .join(" · ")}
                </span>
              </div>
            )}

            {apiError && (
              <div className="connection-item text-rose-700">
                <span className="connection-label">Error:</span>
                <span className="font-medium text-xs">{apiError}</span>
                <button
                  type="button"
                  onClick={checkHealth}
                  className="rounded bg-rose-100 hover:bg-rose-200 text-rose-800 px-2 py-0.5 text-xs font-semibold cursor-pointer transition-colors"
                >
                  Retry
                </button>
              </div>
            )}
          </footer>
        </section>
      </main>

      {/* Persistent Science & Metric Glossary Modal */}
      <ScienceGlossaryModal
        isOpen={showGlossary}
        onClose={() => setShowGlossary(false)}
      />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}