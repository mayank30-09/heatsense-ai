import { useEffect, useState } from "react";
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
            {views.map((view, index) => (
              <button
                className={index === 0 ? "nav-item active" : "nav-item"}
                key={view}
                type="button"
                disabled={index !== 0}
              >
                {view}
              </button>
            ))}
          </nav>

          <p className="scope-note">
            Day 1 contains infrastructure and a Leaflet map shell only. Real
            Surat raster products are added in the later GIS pipeline.
          </p>
        </aside>

        <section className="workspace">
          <div className="workspace-heading">
            <div>
              <p className="eyebrow">MAP WORKSPACE</p>
              <h2>GIS foundation</h2>
            </div>

            <p className="muted">
              React + Vite + TypeScript + Leaflet
            </p>
          </div>

          <MapShell />

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