import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import "@geoman-io/leaflet-geoman-free";
import type { AnalysisResult } from "../types/analysis";
import type { SeasonName } from "../types/heatPriority";
import { API_BASE_URL } from "../services/api";

const ZONAL_STATS_URL = `${API_BASE_URL}/analysis/zonal-stats`;
const AREA_NAME_URL = `${API_BASE_URL}/analysis/resolve-area-name-postgis`;

type GeomanControls = {
  addControls: (options: {
    position: string;
    drawPolygon: boolean;
    drawPolyline: boolean;
    drawCircle: boolean;
    drawCircleMarker: boolean;
    drawRectangle: boolean;
    drawMarker: boolean;
    drawText: boolean;
    editMode: boolean;
    removalMode: boolean;
    cutPolygon: boolean;
    rotateMode: boolean;
    dragMode: boolean;
  }) => void;

  removeControls: () => void;
};

type GeomanMap = ReturnType<typeof useMap> & {
  pm: GeomanControls;
};

type Props = {
  season?: SeasonName;
  year?: number;
  onAreaCreated: (
    areaId: string,
    name: string,
    result: AnalysisResult
  ) => void;

  onAreaUpdated: (
    areaId: string,
    result: AnalysisResult,
    name?: string
  ) => void;

  onAreaRemoved: (
    areaId: string
  ) => void;

  onAnalysisError: (
    message: string
  ) => void;
};

type AreaLayer = L.Layer & {
  __heatsenseAreaId?: string;
  __heatsenseAreaName?: string;
  __heatsenseAnalysisCode?: string;
};

type AreaNameResult = {
  resolved?: boolean;
  name?: string | null;
  name_type?: string | null;
  method?: string | null;
  source?: string | null;
  latitude?: number;
  longitude?: number;
};

export default function AreaDrawing({
  season = "summer",
  year = 2026,
  onAreaCreated,
  onAreaUpdated,
  onAreaRemoved,
  onAnalysisError,
}: Props) {
  const map = useMap() as GeomanMap;

  const initialized = useRef(false);
  const areaCounter = useRef(0);
  const seasonRef = useRef(season);
  const yearRef = useRef(year);

  useEffect(() => {
    seasonRef.current = season;
    yearRef.current = year;
  }, [season, year]);

  useEffect(() => {
    if (initialized.current) {
      return;
    }

    initialized.current = true;

    map.pm.addControls({
      position: "topleft",

      drawPolygon: true,
      drawPolyline: false,
      drawCircle: false,
      drawCircleMarker: false,
      drawRectangle: false,
      drawMarker: false,
      drawText: false,

      editMode: true,
      removalMode: true,

      cutPolygon: false,
      rotateMode: false,
      dragMode: false,
    });

    const calculateStatistics = async (
      layer: AreaLayer
    ): Promise<AnalysisResult | null> => {
      if (
        !layer ||
        typeof (layer as any).toGeoJSON !== "function"
      ) {
        onAnalysisError("Unable to read the selected area.");
        return null;
      }

      const geojson = (layer as any).toGeoJSON();
      const geometry = geojson.geometry;

      if (!geometry || geometry.type !== "Polygon") {
        onAnalysisError("Please select a valid polygon area.");
        return null;
      }

      if (
        !geometry.coordinates ||
        !Array.isArray(geometry.coordinates) ||
        geometry.coordinates.length === 0 ||
        !Array.isArray(geometry.coordinates[0]) ||
        geometry.coordinates[0].length < 4
      ) {
        onAnalysisError("Incomplete or empty polygon geometry. Please enclose a valid area.");
        return null;
      }

      try {
        const response = await fetch(ZONAL_STATS_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            geometry,
            season: seasonRef.current,
            year: yearRef.current,
          }),
        });

        const result = await response.json();

        if (!response.ok) {
          throw new Error(
            result?.detail || "Zonal statistics request failed."
          );
        }

        if (result && typeof result === "object") {
          result.geojson_geometry = geometry;
        }

        return result;
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Unable to calculate area statistics.";

        onAnalysisError(message);
        return null;
      }
    };

    const resolveAreaName = async (
      layer: AreaLayer
    ): Promise<AreaNameResult | null> => {
      if (
        !layer ||
        typeof (layer as any).toGeoJSON !== "function"
      ) {
        return null;
      }

      const geojson = (layer as any).toGeoJSON();
      const geometry = geojson.geometry;

      if (!geometry || geometry.type !== "Polygon") {
        return null;
      }

      try {
        const response = await fetch(AREA_NAME_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            geometry,
          }),
        });

        const result = await response.json();

        if (!response.ok) {
          throw new Error(
            result?.detail || "Area name resolution failed."
          );
        }

        return result;
      } catch (error) {
        console.warn("Unable to resolve area name:", error);
        return null;
      }
    };

    const handleLayerEdit = async (layer: AreaLayer) => {
      const areaId = layer.__heatsenseAreaId;
      if (!areaId) {
        return;
      }

      const result = await calculateStatistics(layer);
      if (!result) {
        return;
      }
      if (typeof (layer as any).toGeoJSON === "function") {
        result.geojson_geometry = (layer as any).toGeoJSON().geometry;
      }

      const place = await resolveAreaName(layer);
      const analysisCode =
        layer.__heatsenseAnalysisCode ||
        layer.__heatsenseAreaName?.match(/A\d+$/)?.[0] ||
        "A01";

      const localityName =
        place?.name?.trim() ||
        layer.__heatsenseAreaName?.replace(/ · A\d+$/, "") ||
        "Unnamed Locality";

      const updatedName = `${localityName} · ${analysisCode}`;
      layer.__heatsenseAreaName = updatedName;

      if (typeof (layer as any).unbindTooltip === "function") {
        (layer as any).unbindTooltip();
      }
      if (typeof (layer as any).bindTooltip === "function") {
        (layer as any).bindTooltip(updatedName, {
          permanent: false,
          direction: "center",
          className: "heatsense-area-tooltip",
        });
      }

      onAreaUpdated(areaId, result, updatedName);
    };

    const handleCreate = async (event: any) => {
      const layer = event.layer as AreaLayer;

      areaCounter.current += 1;
      const analysisCode = `A${String(areaCounter.current).padStart(2, "0")}`;
      const areaId = `area-${Date.now()}-${areaCounter.current}`;

      layer.__heatsenseAreaId = areaId;
      layer.__heatsenseAnalysisCode = analysisCode;

      // Attach direct edit listener so vertex edits are captured reliably
      if (typeof (layer as any).on === "function") {
        (layer as any).on("pm:edit", () => {
          handleLayerEdit(layer);
        });
      }

      const result = await calculateStatistics(layer);
      if (!result) {
        if (typeof (map as any).removeLayer === "function") {
          map.removeLayer(layer);
        }
        return;
      }
      if (typeof (layer as any).toGeoJSON === "function") {
        result.geojson_geometry = (layer as any).toGeoJSON().geometry;
      }

      const place = await resolveAreaName(layer);
      const localityName = place?.name?.trim() || "Unnamed Locality";
      const name = `${localityName} · ${analysisCode}`;

      layer.__heatsenseAreaName = name;
      if (typeof (layer as any).bindTooltip === "function") {
        (layer as any).bindTooltip(name, {
          permanent: false,
          direction: "center",
          className: "heatsense-area-tooltip",
        });
      }

      onAreaCreated(areaId, name, result);
    };

    const handleEdit = async (event: any) => {
      if (event.layer) {
        await handleLayerEdit(event.layer as AreaLayer);
      } else if (event.layers) {
        event.layers.eachLayer(async (layer: AreaLayer) => {
          await handleLayerEdit(layer);
        });
      }
    };

    const handleRemove = (
      event: any
    ) => {
      const layer =
        event.layer as AreaLayer;

      const areaId =
        layer?.__heatsenseAreaId;

      if (areaId) {
        onAreaRemoved(areaId);
      }
    };

    map.on(
      "pm:create",
      handleCreate
    );

    map.on(
      "pm:edit",
      handleEdit
    );

    map.on(
      "pm:remove",
      handleRemove
    );

    return () => {
      map.off(
        "pm:create",
        handleCreate
      );

      map.off(
        "pm:edit",
        handleEdit
      );

      map.off(
        "pm:remove",
        handleRemove
      );

      if (map.pm) {
        if (typeof (map.pm as any).disableDraw === "function") {
          (map.pm as any).disableDraw();
        }
        if (typeof map.pm.removeControls === "function") {
          map.pm.removeControls();
        }
      }

      initialized.current = false;
    };
  }, [
    map,
    onAreaCreated,
    onAreaUpdated,
    onAreaRemoved,
    onAnalysisError,
  ]);

  return null;
}
