import { MapShell } from "./map/MapShell";
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
  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">URBAN HEAT ANALYSIS PLATFORM</p>
          <h1>HEATSENSE AI</h1>
        </div>
        <div className="status-pill">
          <span className="status-dot" /> Day 1 Skeleton
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
            <p className="muted">React + Vite + TypeScript + Leaflet</p>
          </div>
          <MapShell />
        </section>
      </main>
    </div>
  );
}
