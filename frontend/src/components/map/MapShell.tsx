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
import {
  fetchPipelineStatus,
  fetchScenes,
  type PipelineStatus,
  type SceneItem,
} from "../../services/scenesApi";

import AreaDrawing from "../AreaDrawing";
import AreaRecommendationsPanel from "./AreaRecommendationsPanel";
import CellInspector from "./CellInspector";
import HPILegend from "./HPILegend";
import HPIViewportGrid from "./HPIViewportGrid";
import LayerControls from "./LayerControls";
import LatestSceneSidebar from "./LatestSceneSidebar";
import { API_BASE_URL } from "../../services/api";
import { fetchGridCellDetail } from "../../services/heatPriorityApi";

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
  mode?: "heat_map" | "area_analysis";
}

export function MapShell({
  initialTool = "grid",
  initialLayer = "hpi",
  mode = "heat_map",
}: MapShellProps) {
  const isAreaAnalysis = mode === "area_analysis";
  const [activeTool, setActiveTool] = useState<"grid" | "drawing">(
    isAreaAnalysis ? "drawing" : initialTool
  );
  const [layerMode, setLayerMode] = useState<ActiveLayerMode>(
    isAreaAnalysis ? "lst" : initialLayer
  );
  const [season, setSeason] = useState<SeasonName>("summer");
  const [year, setYear] = useState<number>(2026);
  const [showRasterTile, setShowRasterTile] = useState(true);
  const [minHpiFilter, setMinHpiFilter] = useState<number | undefined>(undefined);
  const [selectedCell, setSelectedCell] = useState<GridCellScoreItem | null>(null);

  const [scenes, setScenes] = useState<SceneItem[]>([]);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [scenesLoading, setScenesLoading] = useState(false);
  const [scenesError, setScenesError] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
  const [recentDayThreshold] = useState<number>(30);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();
    setScenesLoading(true);
    setScenesError(null);

    fetchScenes(controller.signal)
      .then((data) => {
        if (mounted) {
          setScenes(data);
          if (data.length > 0) {
            const firstProcessed = data.find((s) => s.status === "PROCESSED" || s.status === "published");
            setSelectedSceneId((prev) => prev ?? firstProcessed?.scene_id ?? data[0].scene_id);
          }
          setScenesLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setScenesError(err?.message ?? "Failed to fetch scenes");
          setScenesLoading(false);
        }
      });

    fetchPipelineStatus(controller.signal)
      .then((status) => {
        if (mounted) {
          setPipelineStatus(status);
        }
      })
      .catch(() => {});

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

  const handleSelectCell = useCallback(
    (cell: GridCellScoreItem) => {
      setSelectedCell(cell);
      fetchGridCellDetail(
        cell.pixel_id,
        season,
        effectiveYear,
        layerMode === "latest_scene" ? (selectedScene?.scene_id ?? undefined) : undefined
      )
        .then((detail) => setSelectedCell(detail))
        .catch(() => {});
    },
    [season, effectiveYear, layerMode, selectedScene?.scene_id]
  );

  // Synchronize selected cell whenever season, effectiveYear, layerMode, or scene changes
  useEffect(() => {
    if (!selectedCell?.pixel_id) return;
    let mounted = true;
    const controller = new AbortController();

    fetchGridCellDetail(
      selectedCell.pixel_id,
      season,
      effectiveYear,
      layerMode === "latest_scene" ? (selectedScene?.scene_id ?? undefined) : undefined,
      undefined,
      undefined,
      controller.signal
    )
      .then((updated) => {
        if (mounted) {
          setSelectedCell(updated);
        }
      })
      .catch(() => {});

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [season, effectiveYear, layerMode, selectedScene?.scene_id]);

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

        {!isAreaAnalysis && (
          <HPIViewportGrid
            layerMode={layerMode}
            selectedCell={selectedCell}
            onSelectCell={handleSelectCell}
            minHpiFilter={minHpiFilter}
            season={season}
            year={effectiveYear}
            sceneId={selectedScene?.scene_id}
          />
        )}

        {isAreaAnalysis && (
          <AreaDrawing
            season={season}
            year={effectiveYear}
            onAreaCreated={handleAreaCreated}
            onAreaUpdated={handleAreaUpdated}
            onAreaRemoved={handleAreaRemoved}
            onAnalysisError={handleAnalysisError}
          />
        )}

        {layerMode !== "latest_scene" && (
          <HPILegend
            layerMode={isAreaAnalysis ? "lst" : layerMode}
            season={season}
            year={effectiveYear}
            selectedScene={selectedScene}
            recentDayThreshold={recentDayThreshold}
            hasRecentScene={hasRecentScene}
          />
        )}
      </MapContainer>

      {/* Monsoon Cloud Contamination Banner (non-colliding) */}
      {season === "monsoon" && layerMode !== "latest_scene" && (
        <div className="pointer-events-none absolute bottom-12 left-1/2 z-[1000] -translate-x-1/2">
          <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-amber-300 bg-amber-50/95 px-4 py-1.5 shadow-md backdrop-blur">
            <span className="text-amber-800 text-xs font-semibold">
              ⚠️ Monsoon Layer: Low reliability due to cloud contamination (QA filtering in progress)
            </span>
          </div>
        </div>
      )}

      <LayerControls
        isAreaAnalysis={isAreaAnalysis}
        layerMode={layerMode}
        onLayerModeChange={setLayerMode}
        showRasterTile={showRasterTile}
        onToggleRasterTile={() => setShowRasterTile((prev) => !prev)}
        minHpiFilter={minHpiFilter}
        onToggleMinHpi={() => setMinHpiFilter((prev) => (prev === undefined ? 50 : undefined))}
        season={season}
        onSeasonChange={handleSeasonChange}
        activeTool={activeTool}
        scenes={scenes}
        selectedSceneId={selectedSceneId ?? undefined}
        onSelectScene={setSelectedSceneId}
        recentDayThreshold={recentDayThreshold}
        pipelineStatus={pipelineStatus}
        scenesLoading={scenesLoading}
        scenesError={scenesError}
      />

      {layerMode === "latest_scene" && !isAreaAnalysis && (
        <LatestSceneSidebar
          scenes={scenes}
          selectedSceneId={selectedSceneId ?? undefined}
          onSelectScene={setSelectedSceneId}
          showRasterTile={showRasterTile}
          onToggleRasterTile={() => setShowRasterTile((prev) => !prev)}
          pipelineStatus={pipelineStatus}
          scenesLoading={scenesLoading}
          scenesError={scenesError}
        />
      )}

      {/* Grid Cell Inspector */}
      {!isAreaAnalysis && selectedCell && (
        <CellInspector
          cell={selectedCell}
          onClose={() => setSelectedCell(null)}
          activeLayerMode={layerMode}
          activeSeason={season}
          activeYear={effectiveYear}
          selectedScene={selectedScene}
        />
      )}

      {/* Polygon Drawing Area Analysis Drawer */}
      {isAreaAnalysis && (activeTool === "drawing" || analysisAreas.length > 0) && (
        <div className="pointer-events-none absolute bottom-3 right-3 z-[1000] w-[calc(100vw-24px)] max-w-md sm:w-[420px] max-h-[75vh] overflow-y-auto">
          <div className="pointer-events-auto rounded-xl border border-slate-200 bg-white/95 p-4 shadow-lg backdrop-blur">
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
                    season={season}
                    year={effectiveYear}
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
  season,
  year,
}: {
  area: AnalysisArea;
  season?: string;
  year?: number;
}) {
  const result = area.result;
  const [showRecommendations, setShowRecommendations] = useState(true);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-xs">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
            Polygon statistics
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

          {/* Geometry Validity Warnings */}
          {result.geometry_repaired && (
            <div className="mb-2 rounded border border-amber-300 bg-amber-50 px-2 py-1.5 text-[10.5px] leading-snug text-amber-950">
              ⚠️ <strong>Geometry Repaired:</strong> Self-intersecting or non-simple polygon boundary was automatically normalized using buffer(0).
            </div>
          )}
          {result.area_km2 < 0.01 && (
            <div className="mb-2 rounded border border-amber-300 bg-amber-50 px-2 py-1.5 text-[10.5px] leading-snug text-amber-950">
              ⚠️ <strong>Very Small Polygon:</strong> Area ({result.area_km2 < 0.001 ? "<0.001" : result.area_km2.toFixed(4)} km²) is smaller than a single 100m grid cell (1.0 ha / 0.01 km²). Sub-pixel edge effects increase statistical uncertainty.
            </div>
          )}

          {/* SMC Boundary Containment & Source */}
          <div className="mb-2 rounded border border-slate-200 bg-slate-50 p-2 text-[10.5px] space-y-1">
            <div className="flex justify-between">
              <span className="text-slate-500">Boundary source:</span>
              <span className="font-medium text-slate-800">SMC study-area polygon in PostGIS</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Inside-SMC fraction:</span>
              <span className="font-semibold text-slate-800">
                {((result.inside_smc_fraction ?? 1.0) * 100).toFixed(1)}%
              </span>
            </div>
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

            <Metric
              label="NoData count"
              value={
                (result.nodata_pixel_count ??
                  Math.max(0, (result.total_intersecting_pixel_count ?? 0) - result.valid_pixel_count)
                ).toLocaleString()
              }
            />

            <Metric
              label="Coverage definition"
              value="valid / intersecting pixels"
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
                  value={`${result.statistics.mean_c.toFixed(1)}°C`}
                />

                <Metric
                  label="Median"
                  value={`${result.statistics.median_c.toFixed(1)}°C`}
                />

                <Metric
                  label="Minimum"
                  value={`${result.statistics.min_c.toFixed(1)}°C`}
                />

                <Metric
                  label="Maximum"
                  value={`${result.statistics.max_c.toFixed(1)}°C`}
                />

                <Metric
                  label="P90"
                  value={`${result.statistics.p90_c.toFixed(1)}°C`}
                />

                <Metric
                  label="Std. deviation"
                  value={`${result.statistics.std_c.toFixed(1)}°C`}
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
                        <td className="py-1 text-slate-700">
                          {row.effective_year}
                          {row.season === "post_monsoon" && row.effective_year !== 2026 && (
                            <span className="ml-1 text-[9px] font-bold text-amber-700" title="Mixed-year baseline: Post-Monsoon 2026 unobserved; evaluated on 2025 validated composite">*</span>
                          )}
                        </td>
                        <td className="py-1 text-right text-blue-700">
                          {row.mean_c !== null ? `${row.mean_c.toFixed(1)}°C` : "N/A"}
                        </td>
                        <td className="py-1 text-right text-red-700">
                          {row.max_c !== null ? `${row.max_c.toFixed(1)}°C` : "N/A"}
                        </td>
                        <td className="py-1 text-right text-slate-600">
                          {row.data_coverage_percentage.toFixed(0)}%
                          {(row.is_partial || row.data_coverage_percentage < 70) && (
                            <span className="ml-1 text-[10px] text-amber-700 font-bold" title="Low coverage: <70% valid clear pixels">⚠️ Low</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-1 space-y-0.5 text-[9.5px] text-slate-500">
                <div>* <strong>Mixed-year baseline:</strong> Post-Monsoon uses 2025 composite because 2026 data was unobserved.</div>
                <div>⚠️ <strong>Low coverage:</strong> Monsoon observations have high cloud masking (&lt;70% valid clear pixels).</div>
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
                    EPSG:32643 planar
                  </span>
                </div>

                <div className="flex justify-between">
                  <span>Area method</span>
                  <span className="font-medium text-slate-900">
                    Geodesic ellipsoidal area (WGS84) / planar EPSG:32643
                  </span>
                </div>

                <div className="flex justify-between">
                  <span>Pixel size</span>
                  <span className="font-medium text-slate-900">
                    100m × 100m (1 ha)
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="mt-3 border-t border-slate-100 pt-2 text-[10px] leading-4 text-slate-500">
            Landsat 30 m radiant skin temperature (T<sub>skin</sub>) at ~10:30 local solar time (about 11:00 IST), distinct from ambient 2 m air temperature (T<sub>air</sub>). Zonal statistics reflect pixel aggregates within the selected perimeter.
          </div>
        </>
      )}

      {/* Heat Interventions & Recommendations */}
      {result.geojson_geometry && (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">
              Interventions
            </span>
            <button
              type="button"
              onClick={() => setShowRecommendations((prev) => !prev)}
              className="text-[11px] font-medium text-blue-600 hover:text-blue-800"
            >
              {showRecommendations ? "Hide Recommendations" : "Show Recommendations"}
            </button>
          </div>

          {showRecommendations && (
            <AreaRecommendationsPanel
              areaId={area.id}
              areaName={area.name}
              geometry={result.geojson_geometry}
              season={result.season || season}
              year={result.effective_year || year}
            />
          )}
        </div>
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