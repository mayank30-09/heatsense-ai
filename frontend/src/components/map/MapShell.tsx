import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  MapContainer,
  TileLayer,
} from "react-leaflet";

import type { AnalysisResult } from "../../types/analysis";
import type {
  ActiveLayerMode,
  GridCellScoreItem,
  SeasonName,
} from "../../types/heatPriority";
import { fetchScenes, type SceneItem } from "../../services/scenesApi";

import AreaDrawing from "../AreaDrawing";
import CellInspector from "./CellInspector";
import HPILegend from "./HPILegend";
import HPIViewportGrid from "./HPIViewportGrid";
import LayerControls from "./LayerControls";
import { API_BASE_URL } from "../../services/api";

const SURAT_CENTER: [number, number] = [
  21.1702,
  72.8311,
];

type AnalysisArea = {
  id: string;
  name: string;
  result: AnalysisResult;
};

interface MapShellProps {
  initialTool?: "grid" | "drawing";
  initialLayer?: ActiveLayerMode;
}

export function MapShell({
  initialTool = "grid",
  initialLayer = "hpi",
}: MapShellProps) {
  const [activeTool, setActiveTool] = useState<"grid" | "drawing">(initialTool);
  const [layerMode, setLayerMode] = useState<ActiveLayerMode>(initialLayer);
  const [season, setSeason] = useState<SeasonName>("summer");
  const [year, setYear] = useState<number>(2026);
  const [showRasterTile, setShowRasterTile] = useState(true);
  const [minHpiFilter, setMinHpiFilter] = useState<number | undefined>(undefined);
  const [selectedCell, setSelectedCell] = useState<GridCellScoreItem | null>(null);

  const [scenes, setScenes] = useState<SceneItem[]>([]);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [scenesLoading, setScenesLoading] = useState(false);
  const [recentDayThreshold] = useState<number>(30);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();
    setScenesLoading(true);

    fetchScenes(controller.signal)
      .then((data) => {
        if (mounted) {
          setScenes(data);
          if (data.length > 0) {
            setSelectedSceneId((prev) => prev ?? data[0].scene_id);
          }
          setScenesLoading(false);
        }
      })
      .catch(() => {
        if (mounted) {
          setScenesLoading(false);
        }
      });

    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  const selectedScene = useMemo(() => {
    if (!scenes.length) return null;
    return scenes.find((s) => s.scene_id === selectedSceneId) ?? scenes[0];
  }, [scenes, selectedSceneId]);

  const hasRecentScene = useMemo(() => {
    if (!selectedScene) return false;
    const acqTime = new Date(selectedScene.acquisition_date).getTime();
    const now = new Date().getTime();
    const diffDays = Math.max(0, (now - acqTime) / (1000 * 60 * 60 * 24));
    return diffDays <= recentDayThreshold;
  }, [selectedScene, recentDayThreshold]);

  const effectiveYear = season === "post_monsoon" && year === 2026 ? 2025 : year;

  const handleSeasonChange = useCallback((newSeason: SeasonName) => {
    setSeason(newSeason);
    // If user changes season and was on HPI layer, switch to LST mode so the seasonal temperature layer is immediately visual
    if (layerMode === "hpi") {
      setLayerMode("lst");
    }
  }, [layerMode]);

  const [
    analysisAreas,
    setAnalysisAreas,
  ] = useState<AnalysisArea[]>([]);

  const [
    analysisError,
    setAnalysisError,
  ] = useState<string | null>(null);

  const handleAreaCreated =
  useCallback(
    (
      areaId: string,
      name: string,
      result: AnalysisResult
    ) => {
      setAnalysisError(null);

      setAnalysisAreas(
        (current) => [
          ...current,
          {
            id: areaId,
            name,
            result,
          },
        ]
      );
    },
    []
  );

const handleAreaUpdated =
  useCallback(
    (
      areaId: string,
      result: AnalysisResult,
      name?: string
    ) => {
      setAnalysisAreas(
        (previousAreas) =>
          previousAreas.map((area) =>
            area.id === areaId
              ? {
                  ...area,
                  name:
                    name?.trim() ||
                    area.name,
                  result,
                }
              : area
          )
      );
    },
    []
  );

const handleAreaRemoved =
  useCallback(
    (areaId: string) => {
      setAnalysisAreas(
        (current) =>
          current.filter(
            (area) =>
              area.id !== areaId
          )
      );
    },
    []
  );

  const handleAnalysisError =
    useCallback(
      (message: string) => {
        setAnalysisError(message);
      },
      []
    );

  return (
    <div
      className="map-frame"
      aria-label="HEATSENSE AI map"
    >
      <MapContainer
        center={SURAT_CENTER}
        zoom={11}
        minZoom={10}
        maxZoom={16}
        maxBounds={[
          [20.95, 72.60],
          [21.40, 73.08],
        ]}
        scrollWheelZoom
        className="leaflet-map"
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
        />

        {showRasterTile && (
          <TileLayer
            key={
              layerMode === "latest_scene" && selectedScene
                ? `lst-scene-${selectedScene.scene_id}`
                : `lst-raster-${season}-${effectiveYear}`
            }
            url={
              layerMode === "latest_scene" && selectedScene
                ? `${API_BASE_URL}/rasters/lst/tiles/{z}/{x}/{y}.png?scene_id=${selectedScene.scene_id}`
                : `${API_BASE_URL}/rasters/lst/tiles/{z}/{x}/{y}.png?season=${season}&year=${effectiveYear}`
            }
            opacity={0.65}
            attribution={
              layerMode === "latest_scene"
                ? "HEATSENSE AI · Landsat NRT Single Scene"
                : "HEATSENSE AI · Landsat LST"
            }
          />
        )}

        <HPIViewportGrid
          layerMode={layerMode}
          selectedCell={selectedCell}
          onSelectCell={(cell) => setSelectedCell(cell)}
          minHpiFilter={minHpiFilter}
          season={season}
          year={effectiveYear}
        />

        <AreaDrawing
          season={season}
          year={effectiveYear}
          onAreaCreated={
            handleAreaCreated
          }
          onAreaUpdated={
            handleAreaUpdated
          }
          onAreaRemoved={
            handleAreaRemoved
          }
          onAnalysisError={
            handleAnalysisError
          }
        />

        <HPILegend
          layerMode={layerMode}
          season={season}
          year={effectiveYear}
          selectedScene={selectedScene}
          recentDayThreshold={recentDayThreshold}
          hasRecentScene={hasRecentScene}
        />
      </MapContainer>

      {/* Monsoon Cloud Contamination Banner */}
      {season === "monsoon" && (
        <div className="pointer-events-none absolute top-16 left-1/2 z-[1000] -translate-x-1/2">
          <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-amber-300 bg-amber-50/95 px-4 py-1.5 shadow-md backdrop-blur">
            <span className="text-amber-800 text-xs font-semibold">
              ⚠️ Monsoon Layer: Low reliability due to cloud contamination (QA filtering in progress)
            </span>
          </div>
        </div>
      )}

      {/* Latest Scene Notice Banner */}
      {layerMode === "latest_scene" && (
        <div className="pointer-events-none absolute top-16 left-1/2 z-[1000] -translate-x-1/2">
          {scenes.length === 0 ? (
            <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-slate-300 bg-white/95 px-4 py-1.5 shadow-md backdrop-blur">
              <span className="text-slate-700 text-xs font-semibold">
                ℹ️ No Landsat scenes have been ingested yet. Showing base map.
              </span>
            </div>
          ) : !hasRecentScene ? (
            <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-amber-300 bg-amber-50/95 px-4 py-1.5 shadow-md backdrop-blur">
              <span className="text-amber-900 text-xs font-semibold">
                ⚠️ No clear scene in the last {recentDayThreshold} days.
              </span>
            </div>
          ) : null}
        </div>
      )}

      <LayerControls
        layerMode={layerMode}
        onLayerModeChange={setLayerMode}
        showRasterTile={showRasterTile}
        onToggleRasterTile={() => setShowRasterTile((prev) => !prev)}
        minHpiFilter={minHpiFilter}
        onToggleMinHpi={() => setMinHpiFilter((prev) => (prev === undefined ? 50 : undefined))}
        season={season}
        onSeasonChange={handleSeasonChange}
        activeTool={activeTool}
        onSelectTool={setActiveTool}
        scenes={scenes}
        selectedSceneId={selectedSceneId ?? undefined}
        onSelectScene={setSelectedSceneId}
        recentDayThreshold={recentDayThreshold}
      />

      {/* Grid Cell Inspector */}
      {selectedCell && (
        <CellInspector
          cell={selectedCell}
          onClose={() => setSelectedCell(null)}
        />
      )}

      {/* Polygon Drawing Area Analysis Drawer */}
      {(activeTool === "drawing" || analysisAreas.length > 0) && !selectedCell && (
        <div className="pointer-events-none absolute bottom-3 right-3 z-[1000] w-96 max-h-[75%] overflow-y-auto">
          <div className="pointer-events-auto rounded-lg border border-slate-200 bg-white/95 p-4 shadow-lg backdrop-blur">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
                  Area Analysis
                </div>
                <div className="mt-1 text-sm font-semibold text-slate-900">
                  Selected Analysis Areas
                </div>
              </div>
              {activeTool === "drawing" && (
                <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-800">
                  Draw Tool Active
                </span>
              )}
            </div>

            {analysisError && (
              <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-700">
                {analysisError}
              </div>
            )}

            {analysisAreas.length === 0 && (
              <div className="text-sm leading-5 text-slate-500">
                Use the polygon drawing tool on the left toolbar to draw an area for Landsat zonal statistics.
              </div>
            )}

            <div className="space-y-3">
              {analysisAreas.map(
                (area) => (
                  <AnalysisAreaCard
                    key={area.id}
                    area={area}
                  />
                )
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AnalysisAreaCard({
  area,
}: {
  area: AnalysisArea;
}) {
  const result =
    area.result;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">
            Analysis area
          </div>

          <div className="mt-0.5 text-sm font-semibold text-slate-900">
            {area.name}
          </div>
        </div>

        <div className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-medium text-slate-600">
          Landsat LST
        </div>
      </div>

      {result.status === "outside_study_area" ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-800">
          <div className="font-bold">Outside Study Area</div>
          Selected area lies completely outside the official 461.63 km² SMC study boundary.
        </div>
      ) : result.status === "no_valid_observations" || result.status === "no_data" ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          <div className="font-bold">No Valid Observations</div>
          No cloud-free Landsat thermal pixels available in this area for {result.season ? result.season.replace("_", " ") : "selected season"}.
        </div>
      ) : (
        <>
          {/* Active Season / Source Badge */}
          <div className="mb-2 flex items-center justify-between">
            <span className="rounded bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-900">
              {result.season ? result.season.replace("_", " ") : "Season"} {result.effective_year ?? ""}
            </span>
            {result.source_file && (
              <span className="max-w-[170px] truncate font-mono text-[9px] text-slate-400" title={result.source_file}>
                {result.source_file}
              </span>
            )}
          </div>

          {/* Partially Outside SMC Warning */}
          {result.status === "partially_outside" && (
            <div className="mb-2 rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-[10.5px] leading-snug text-amber-900">
              ⚠️ Partially outside SMC ({((result.inside_smc_fraction ?? 1) * 100).toFixed(0)}% inside boundary). Statistics reflect interior pixels only.
            </div>
          )}

          {/* Water Body Warning */}
          {result.water_warning && (
            <div className="mb-2 rounded border border-blue-200 bg-blue-50 px-2 py-1.5 text-[10.5px] leading-snug text-blue-900">
              🌊 Open water detected ({((result.ndwi_water_fraction ?? 0) * 100).toFixed(0)}% NDWI &gt; 0.05). LST reflects evaporative surface cooling rather than land heat risk.
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            <Metric
              label="Area"
              value={`${result.area_km2.toFixed(2)} km²`}
            />

            <Metric
              label="Coverage"
              value={
                result.data_coverage_percentage !== undefined
                  ? `${result.data_coverage_percentage.toFixed(1)}%`
                  : "N/A"
              }
            />

            <Metric
              label="Valid pixels"
              value={result.valid_pixel_count.toLocaleString()}
            />

            <Metric
              label="Intersecting pixels"
              value={
                result.total_intersecting_pixel_count?.toLocaleString() ??
                "N/A"
              }
            />
          </div>

          {result.statistics && (
            <div className="mt-3 border-t border-slate-100 pt-3">
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">
                LST Statistics ({result.season ? result.season.replace("_", " ") : "Selected"})
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Metric
                  label="Mean"
                  value={`${result.statistics.mean_c.toFixed(2)}°C`}
                />

                <Metric
                  label="Median"
                  value={`${result.statistics.median_c.toFixed(2)}°C`}
                />

                <Metric
                  label="Minimum"
                  value={`${result.statistics.min_c.toFixed(2)}°C`}
                />

                <Metric
                  label="Maximum"
                  value={`${result.statistics.max_c.toFixed(2)}°C`}
                />

                <Metric
                  label="P90"
                  value={`${result.statistics.p90_c.toFixed(2)}°C`}
                />

                <Metric
                  label="Std. deviation"
                  value={`${result.statistics.std_c.toFixed(2)}°C`}
                />
              </div>
            </div>
          )}

          {/* Multi-Season Comparison Table */}
          {result.seasons_table && result.seasons_table.length > 0 && (
            <div className="mt-3 border-t border-slate-100 pt-3">
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">
                Multi-Season Comparison
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500">
                      <th className="pb-1 font-medium">Season</th>
                      <th className="pb-1 font-medium">Year</th>
                      <th className="pb-1 text-right font-medium">Mean</th>
                      <th className="pb-1 text-right font-medium">Max</th>
                      <th className="pb-1 text-right font-medium">Cover</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {result.seasons_table.map((row) => (
                      <tr
                        key={`${row.season}-${row.year}`}
                        className={row.season === result.season ? "bg-amber-50/70 font-semibold" : ""}
                      >
                        <td className="py-1 capitalize">{row.season.replace("_", " ")}</td>
                        <td className="py-1 text-slate-500">{row.effective_year}</td>
                        <td className="py-1 text-right text-blue-700">
                          {row.mean_c !== null ? `${row.mean_c.toFixed(1)}°C` : "N/A"}
                        </td>
                        <td className="py-1 text-right text-red-700">
                          {row.max_c !== null ? `${row.max_c.toFixed(1)}°C` : "N/A"}
                        </td>
                        <td className="py-1 text-right text-slate-500">
                          {row.data_coverage_percentage.toFixed(0)}%
                          {row.is_partial && <span className="ml-0.5 text-amber-600" title="Partial coverage">⚠️</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result.geometry && (
            <div className="mt-3 border-t border-slate-100 pt-3">
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">
                Polygon Metadata
              </div>

              <div className="space-y-1 text-[11px] text-slate-600">
                <div className="flex justify-between">
                  <span>Perimeter</span>
                  <span className="font-medium text-slate-900">
                    {result.geometry.perimeter_km.toFixed(2)} km
                  </span>
                </div>

                <div className="flex justify-between">
                  <span>Centroid</span>
                  <span className="font-medium text-slate-900">
                    {result.geometry.centroid.latitude.toFixed(5)}, {result.geometry.centroid.longitude.toFixed(5)}
                  </span>
                </div>

                <div className="flex justify-between">
                  <span>CRS</span>
                  <span className="font-medium text-slate-900">
                    {result.geometry.crs}
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="mt-3 border-t border-slate-100 pt-2 text-[10px] leading-4 text-slate-500">
            Landsat radiant skin temperature (T<sub>skin</sub>) at ~10:30 local solar time (about 11:00 IST), distinct from ambient 2 m air temperature (T<sub>air</sub>).
          </div>
        </>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-md bg-slate-50 px-3 py-2">
      <div className="text-[9px] uppercase tracking-wide text-slate-400">
        {label}
      </div>

      <div className="mt-0.5 text-sm font-semibold text-slate-900">
        {value}
      </div>
    </div>
  );
}