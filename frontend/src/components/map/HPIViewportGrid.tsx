import { useCallback, useEffect, useRef, useState } from "react";
import { CircleMarker, Tooltip, useMap, useMapEvents } from "react-leaflet";
import type {
  ActiveLayerMode,
  GridCellScoreItem,
  ViewportBBox,
} from "../../types/heatPriority";
import { fetchGridCells } from "../../services/heatPriorityApi";
import {
  getConfidenceColor,
  getHPIColor,
  getLSTColor,
} from "../../utils/hpiColorScales";

interface HPIViewportGridProps {
  layerMode: ActiveLayerMode;
  selectedCell: GridCellScoreItem | null;
  onSelectCell: (cell: GridCellScoreItem) => void;
  minHpiFilter?: number;
}

const MIN_ZOOM_FOR_CELLS = 12;

export default function HPIViewportGrid({
  layerMode,
  selectedCell,
  onSelectCell,
  minHpiFilter,
}: HPIViewportGridProps) {
  const map = useMap();
  const [cells, setCells] = useState<GridCellScoreItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState(map.getZoom());
  const [totalInView, setTotalInView] = useState(0);

  const debounceTimer = useRef<number | null>(null);
  const abortController = useRef<AbortController | null>(null);

  const loadViewportCells = useCallback(() => {
    const currentZoom = map.getZoom();
    setZoomLevel(currentZoom);

    // Guardrail: Do not download thousands of cells at low zoom!
    if (currentZoom < MIN_ZOOM_FOR_CELLS && layerMode !== "chronic") {
      setCells([]);
      setTotalInView(0);
      setIsLoading(false);
      setError(null);
      return;
    }

    if (debounceTimer.current) {
      window.clearTimeout(debounceTimer.current);
    }

    debounceTimer.current = window.setTimeout(async () => {
      if (abortController.current) {
        abortController.current.abort();
      }
      abortController.current = new AbortController();

      setIsLoading(true);
      setError(null);

      const bounds = map.getBounds();
      const bbox: ViewportBBox = {
        min_lon: bounds.getWest(),
        min_lat: bounds.getSouth(),
        max_lon: bounds.getEast(),
        max_lat: bounds.getNorth(),
      };

      try {
        const res = await fetchGridCells(
          {
            bbox: layerMode === "chronic" && currentZoom < MIN_ZOOM_FOR_CELLS ? undefined : bbox,
            is_chronic_hotspot: layerMode === "chronic" ? true : undefined,
            min_hpi: minHpiFilter,
            limit: 350,
          },
          abortController.current.signal
        );

        setCells(res.items);
        setTotalInView(res.total);
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return; // Ignore aborted requests
        }
        const message = err instanceof Error ? err.message : "Failed to load grid cells";
        setError(message);
      } finally {
        setIsLoading(false);
      }
    }, 250);
  }, [map, layerMode, minHpiFilter]);

  // Hook into Leaflet map events for bounded viewport loading
  useMapEvents({
    moveend: () => loadViewportCells(),
    zoomend: () => loadViewportCells(),
  });

  useEffect(() => {
    loadViewportCells();
    return () => {
      if (debounceTimer.current) {
        window.clearTimeout(debounceTimer.current);
      }
      if (abortController.current) {
        abortController.current.abort();
      }
    };
  }, [loadViewportCells]);

  // Marker style calculation based on active layer
  const getMarkerStyle = (cell: GridCellScoreItem) => {
    const isSelected = selectedCell?.pixel_id === cell.pixel_id;
    let fillColor = "#94a3b8";

    if (layerMode === "hpi") {
      fillColor = getHPIColor(cell.heat_priority_score, cell.is_chronic_hotspot);
    } else if (layerMode === "lst") {
      fillColor = getLSTColor(cell.observed_lst_c);
    } else if (layerMode === "confidence") {
      fillColor = getConfidenceColor(cell.confidence_tier);
    } else if (layerMode === "chronic") {
      fillColor = "#b91c1c";
    }

    const radius = isSelected ? 8 : zoomLevel >= 15 ? 7 : zoomLevel >= 14 ? 6 : 5;

    return {
      radius,
      fillColor,
      fillOpacity: isSelected ? 0.95 : 0.82,
      color: isSelected
        ? "#0f172a"
        : cell.is_chronic_hotspot
        ? "#7f1d1d"
        : "#ffffff",
      weight: isSelected ? 3 : cell.is_chronic_hotspot ? 2.5 : 1,
    };
  };

  return (
    <>
      {/* Zoom level warning / banner when zoomed out */}
      {zoomLevel < MIN_ZOOM_FOR_CELLS && layerMode !== "chronic" && (
        <div className="pointer-events-none absolute top-3 left-1/2 z-[1000] -translate-x-1/2">
          <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-blue-200 bg-white/95 px-4 py-1.5 shadow-md backdrop-blur">
            <svg className="h-4 w-4 text-blue-600 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
            </svg>
            <span className="text-xs font-semibold text-slate-700">
              Zoom in (Level 12+) to inspect individual 100m analytical cells
            </span>
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-mono text-slate-500">
              Zoom: {zoomLevel}
            </span>
          </div>
        </div>
      )}

      {/* Loading Indicator Status Pill */}
      {isLoading && (
        <div className="pointer-events-none absolute top-3 left-14 z-[1000]">
          <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-white/95 px-3 py-1.5 shadow-sm backdrop-blur">
            <div className="h-3 w-3 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
            <span className="text-xs font-medium text-slate-700">Fetching viewport cells…</span>
          </div>
        </div>
      )}

      {/* Error & Retry Banner */}
      {error && (
        <div className="pointer-events-none absolute top-3 left-14 z-[1000]">
          <div className="pointer-events-auto flex items-center gap-2 rounded-md border border-red-200 bg-red-50/95 px-3 py-1.5 shadow-sm backdrop-blur">
            <span className="text-xs font-medium text-red-800">{error}</span>
            <button
              type="button"
              onClick={loadViewportCells}
              className="rounded bg-red-600 px-2 py-0.5 text-[11px] font-bold text-white hover:bg-red-700 focus:outline-none"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Cell count pill in viewport */}
      {zoomLevel >= MIN_ZOOM_FOR_CELLS && !isLoading && (
        <div className="pointer-events-none absolute bottom-3 left-1/2 z-[1000] -translate-x-1/2">
          <div className="rounded-full border border-slate-200/90 bg-white/90 px-3 py-1 text-[11px] font-medium text-slate-600 shadow-sm backdrop-blur">
            Viewing <strong>{cells.length}</strong> cells in viewport (total in bounds: {totalInView.toLocaleString()})
          </div>
        </div>
      )}

      {/* Render grid cell markers */}
      {cells.map((cell) => {
        const style = getMarkerStyle(cell);
        return (
          <CircleMarker
            key={cell.pixel_id}
            center={[cell.latitude, cell.longitude]}
            radius={style.radius}
            pathOptions={{
              fillColor: style.fillColor,
              fillOpacity: style.fillOpacity,
              color: style.color,
              weight: style.weight,
            }}
            eventHandlers={{
              click: () => onSelectCell(cell),
            }}
          >
            <Tooltip direction="top" offset={[0, -6]} opacity={0.95}>
              <div className="font-sans text-xs">
                <div className="font-bold text-slate-900 font-mono">{cell.pixel_id}</div>
                {layerMode === "hpi" && (
                  <div>
                    HPI: <strong>{cell.heat_priority_score !== null ? cell.heat_priority_score.toFixed(1) : "Unavailable"}</strong>
                  </div>
                )}
                {layerMode === "lst" && (
                  <div>
                    LST: <strong>{cell.observed_lst_c !== null ? `${cell.observed_lst_c.toFixed(1)}°C` : "N/A"}</strong>
                  </div>
                )}
                {layerMode === "confidence" && (
                  <div>
                    Tier: <strong>{cell.confidence_tier || "N/A"}</strong> ({cell.confidence_index?.toFixed(2)})
                  </div>
                )}
                {cell.is_chronic_hotspot && (
                  <div className="text-[10px] font-bold text-red-600 uppercase">Chronic Hotspot</div>
                )}
                <div className="text-[10px] text-slate-500">Click to inspect full details</div>
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </>
  );
}
