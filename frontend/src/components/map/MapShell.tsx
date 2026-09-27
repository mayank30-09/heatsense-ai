import {
  useCallback,
  useState,
} from "react";

import {
  MapContainer,
  TileLayer,
} from "react-leaflet";

import type { AnalysisResult } from "../../types/analysis";

import AreaDrawing from "../AreaDrawing";
import LSTLegend from "./LSTLegend";

const SURAT_CENTER: [number, number] = [
  21.1702,
  72.8311,
];


type AnalysisArea = {
  id: string;
  name: string;
  result: AnalysisResult;
};

export function MapShell() {
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
        scrollWheelZoom
        className="leaflet-map"
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
        />

        <TileLayer
          url="http://127.0.0.1:8000/api/v1/rasters/lst/tiles/{z}/{x}/{y}.png"
          opacity={0.65}
          attribution="HEATSENSE AI · Landsat LST"
        />

        <AreaDrawing
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

        <LSTLegend />
      </MapContainer>

      <div className="map-badge">
        LST layer active · Landsat
      </div>

      <div className="pointer-events-none absolute bottom-3 right-3 z-[1000] w-96 max-h-[75%] overflow-y-auto">
        <div className="pointer-events-auto rounded-lg border border-slate-200 bg-white/95 p-4 shadow-lg backdrop-blur">
          <div className="mb-3">
            <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
              Area Analysis
            </div>

            <div className="mt-1 text-sm font-semibold text-slate-900">
              Selected Analysis Areas
            </div>
          </div>

          {analysisError && (
            <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-700">
              {analysisError}
            </div>
          )}

          {analysisAreas.length === 0 && (
            <div className="text-sm leading-5 text-slate-500">
              Use the polygon drawing tool
              on the left side of the map to
              select an area for LST analysis.
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

      {result.status === "no_data" ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-800">
          No valid Landsat LST data
          available for this selected
          area.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <Metric
              label="Area"
              value={`${result.area_km2.toFixed(2)} km²`}
            />

            <Metric
              label="Coverage"
              value={
                result.data_coverage_percentage !==
                undefined
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
            <>
              <div className="mt-3 border-t border-slate-100 pt-3">
                <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">
                  LST Statistics
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
            </>
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
                    {result.geometry.perimeter_km.toFixed(
                      2
                    )}{" "}
                    km
                  </span>
                </div>

                <div className="flex justify-between">
                  <span>Centroid</span>
                  <span className="font-medium text-slate-900">
                    {result.geometry.centroid.latitude.toFixed(
                      5
                    )}
                    ,{" "}
                    {result.geometry.centroid.longitude.toFixed(
                      5
                    )}
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
            Land Surface Temperature derived
            from Landsat thermal observations.
            This represents surface temperature,
            not air temperature.
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