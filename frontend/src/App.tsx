import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
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

interface NavItemDef {
  id: string;
  label: string;
  category: "Observation & Monitoring" | "Prescriptive Planning" | "Assurance & Trust";
  badge?: string;
  icon: (active: boolean) => ReactNode;
}

const NAV_ITEMS: NavItemDef[] = [
  {
    id: "Dashboard",
    label: "Dashboard",
    category: "Observation & Monitoring",
    icon: (active) => (
      <svg className={`h-4 w-4 ${active ? "text-teal-400" : "text-slate-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    id: "Heat Map",
    label: "Heat Map",
    category: "Observation & Monitoring",
    badge: "100m",
    icon: (active) => (
      <svg className={`h-4 w-4 ${active ? "text-teal-400" : "text-slate-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    id: "Area Analysis",
    label: "Area Analysis",
    category: "Observation & Monitoring",
    icon: (active) => (
      <svg className={`h-4 w-4 ${active ? "text-teal-400" : "text-slate-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z" />
      </svg>
    ),
  },
  {
    id: "Intervention Explorer",
    label: "Intervention Explorer",
    category: "Prescriptive Planning",
    icon: (active) => (
      <svg className={`h-4 w-4 ${active ? "text-teal-400" : "text-slate-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
      </svg>
    ),
  },
  {
    id: "Scenario Lab",
    label: "Scenario Lab",
    category: "Prescriptive Planning",
    badge: "UHAP",
    icon: (active) => (
      <svg className={`h-4 w-4 ${active ? "text-teal-400" : "text-slate-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
      </svg>
    ),
  },
  {
    id: "Optimization",
    label: "Optimization",
    category: "Prescriptive Planning",
    badge: "NSGA-II",
    icon: (active) => (
      <svg className={`h-4 w-4 ${active ? "text-teal-400" : "text-slate-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    id: "Validation / Trust",
    label: "Validation / Trust",
    category: "Assurance & Trust",
    icon: (active) => (
      <svg className={`h-4 w-4 ${active ? "text-teal-400" : "text-slate-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
  },
];

function ViewLoadingSkeleton({ viewName }: { viewName: string }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[440px] rounded-2xl border border-slate-200/90 bg-white p-12 text-slate-500 shadow-xs">
      <div className="relative mb-4 flex items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-3 border-teal-600 border-t-transparent" />
        <span className="absolute text-[11px] font-mono text-teal-800">🛰️</span>
      </div>
      <span className="text-sm font-semibold text-slate-800">Loading {viewName}…</span>
      <span className="text-xs text-slate-400 mt-1 max-w-sm text-center">
        Retrieving analytical grid layers, sensor metadata, and processing assets
      </span>
    </div>
  );
}

function AppContent() {
  const { user, role, isAuthenticated, logout } = useAuth();
  const [activeView, setActiveView] = useState(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const viewParam = params.get("view");
      const validViews = [
        "Dashboard",
        "Heat Map",
        "Area Analysis",
        "Intervention Explorer",
        "Optimization",
        "Optimization & ROIs",
        "Scenario Lab",
        "Validation / Trust",
      ];
      if (viewParam && validViews.includes(viewParam)) {
        return viewParam;
      }
      const hash = window.location.hash.replace("#", "");
      if (hash === "heat-map") return "Heat Map";
      if (hash === "area-analysis") return "Area Analysis";
    }
    return "Dashboard";
  });
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
      {/* Precision Geospatial Header */}
      <header className="app-header">
        <div className="flex items-center gap-3.5">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-teal-400 shadow-sm ring-1 ring-slate-800"
            aria-hidden="true"
          >
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="9" strokeOpacity="0.3" />
              <path d="M12 3v18M3 12h18" strokeOpacity="0.25" />
              <path d="M12 7a5 5 0 015 5 5 5 0 01-5 5 5 5 0 01-5-5 5 5 0 015-5z" stroke="#14b8a6" strokeWidth="2.2" />
              <circle cx="12" cy="12" r="2" fill="#2dd4bf" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="eyebrow tracking-wider text-slate-500 font-semibold">
                SURAT MUNICIPAL CORPORATION · URBAN OBSERVATORY
              </span>
            </div>
            <h1 className="text-xl font-extrabold tracking-tight text-slate-900">
              HEATSENSE AI
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Science Glossary Modal Trigger */}
          <button
            type="button"
            onClick={() => setShowGlossary(true)}
            aria-label="Open science and metric glossary"
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 hover:border-slate-300 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-1"
          >
            <span aria-hidden="true">📖</span>
            <span>Science Glossary</span>
          </button>

          {/* User Session Info Pill */}
          {isAuthenticated && user && (
            <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs shadow-2xs">
              <div className="h-5 w-5 rounded-full bg-slate-900 text-teal-400 flex items-center justify-center text-[10px] font-bold">
                {user.username.slice(0, 1).toUpperCase()}
              </div>
              <span className="font-semibold text-slate-800">{user.username}</span>
              <span className="rounded-md bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-800 font-mono">
                {role}
              </span>
              <button
                type="button"
                onClick={logout}
                aria-label="Sign out of account"
                className="ml-1 text-slate-400 hover:text-slate-700 text-xs font-medium cursor-pointer focus:outline-none focus:ring-1 focus:ring-slate-300 rounded px-1"
              >
                Logout
              </button>
            </div>
          )}

          {/* API Connectivity Status Pill */}
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
            <span className="font-medium text-slate-700">
              {backendConnected ? "API Connected" : "API Offline"}
            </span>
          </div>
        </div>
      </header>

      {/* Main Workspace Frame */}
      <main className="app-main">
        {/* Authoritative Navigation Sidebar */}
        <aside className="sidebar" aria-label="Application navigation">
          <h2>Workspace</h2>

          <nav role="tablist" aria-label="Workspace views">
            {NAV_ITEMS.map((item) => {
              const isActive = activeView === item.id;

              return (
                <button
                  role="tab"
                  aria-selected={isActive}
                  aria-label={`Switch to ${item.label} view`}
                  className={isActive ? "nav-item active" : "nav-item"}
                  key={item.id}
                  type="button"
                  onClick={() => setActiveView(item.id)}
                >
                  <div className="flex items-center justify-between w-full">
                    <div className="flex items-center gap-2.5">
                      <span className="nav-icon shrink-0">{item.icon(isActive)}</span>
                      <span>{item.label}</span>
                    </div>
                    {item.badge && (
                      <span
                        className={`text-[10px] font-bold font-mono px-1.5 py-0.5 rounded ${
                          isActive
                            ? "bg-slate-800 text-teal-300"
                            : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </nav>

          {/* Authoritative Domain Scope Specification Note */}
          <div className="scope-note">
            <div className="flex items-center gap-1.5 font-bold text-slate-800 text-[11px] uppercase tracking-wide">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-600"></span>
              <span>Stage C &amp; D Specification</span>
            </div>
            <p className="mt-1 text-slate-500 text-[11px] leading-relaxed">
              Authoritative 100m analytical grid, multi-temporal Landsat thermal observations, and linearized heat dissipation cooling optimization for SMC Surat.
            </p>
            <div className="mt-2 pt-2 border-t border-slate-200/80 text-[10px] font-mono text-slate-500 flex justify-between">
              <span>Domain: 461.63 km²</span>
              <span>49,747 Cells</span>
            </div>
          </div>
        </aside>

        {/* Workspace Region */}
        <section className="workspace" role="region" aria-label={`${activeView} content`}>
          <Suspense fallback={<ViewLoadingSkeleton viewName={activeView} />}>
            {activeView === "Dashboard" && (
              <>
                <div className="workspace-heading">
                  <div>
                    <p className="eyebrow">STAGE C EXECUTIVE DASHBOARD</p>
                    <h2>Heat Priority Index Analytics</h2>
                  </div>
                  <p className="muted font-mono text-xs">
                    Surat Municipal Corporation · 49,747 Cells · EPSG:32643
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
                    <h2>Stage C Analytical Grid &amp; Observations</h2>
                  </div>
                  <p className="muted font-mono text-xs">
                    Interactive 100m Viewport Grid &amp; Landsat LST · Surat WRS 148/45
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
                  <p className="muted font-mono text-xs">
                    Draw custom polygons &amp; compute Landsat zonal statistics
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
                  <p className="muted font-mono text-xs">
                    Linearized heat dissipation cooling interventions for Surat Municipal Corporation
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
                  <p className="muted font-mono text-xs">
                    Multi-tier capital budget benchmarks &amp; custom portfolio simulator for SMC Surat
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
                  <p className="muted font-mono text-xs">
                    NSGA-II Pareto genetic algorithm &amp; greedy knapsack budget allocation for SMC Surat
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
                    <p className="eyebrow">STAGE C &amp; D TRANSPARENCY</p>
                    <h2>Model Validation &amp; Trust Center</h2>
                  </div>
                  <p className="muted font-mono text-xs">
                    Spatial cross-validation, independent holdouts, error diagnostics &amp; sensor provenance
                  </p>
                </div>

                <ValidationTrust
                  onSwitchToMap={() => setActiveView("Heat Map")}
                />
              </>
            )}
          </Suspense>

          {/* Precision Connection & Observation Status Footer */}
          <footer className="connection-panel" aria-label="System connectivity status">
            <div className="connection-item">
              <span className="connection-label">Backend API:</span>
              <span className={backendConnected ? "connection-badge-connected" : "connection-badge-unavailable"}>
                <span className={`status-dot ${backendConnected ? "bg-emerald-600" : "bg-rose-600"}`} />
                <span>{backendConnected ? "Operational" : "Unavailable"}</span>
              </span>
            </div>

            <div className="connection-item">
              <span className="connection-label">PostGIS Database:</span>
              <span className={databaseConnected ? "connection-badge-connected" : "connection-badge-unavailable"}>
                <span className={`status-dot ${databaseConnected ? "bg-emerald-600" : "bg-rose-600"}`} />
                <span>{databaseConnected ? "Connected" : "Unavailable"}</span>
              </span>
            </div>

            {observationDates && (
              <div className="connection-item text-slate-600 text-xs flex-wrap max-w-full">
                <span className="connection-label font-bold text-slate-700 shrink-0">Latest observation date:</span>
                <span className="font-mono text-[11px] text-slate-800 break-words leading-tight bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">
                  {Object.entries(observationDates)
                    .map(([season, date]) => `${season}: ${date}`)
                    .join(" · ")}
                </span>
              </div>
            )}

            {apiError && (
              <div className="connection-item text-rose-700">
                <span className="connection-label text-rose-800">Error:</span>
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
