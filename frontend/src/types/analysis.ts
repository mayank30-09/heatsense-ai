export type AnalysisResult = {
  status: "ok" | "no_data";

  area_km2: number;

  valid_pixel_count: number;

  total_intersecting_pixel_count?: number;

  data_coverage_percentage?: number;

  geometry?: {
    geometry_type: string;
    crs: string;

    area_km2: number;

    perimeter_km: number;

    centroid: {
      longitude: number;
      latitude: number;
    };

    bounding_box: {
      min_longitude: number;
      min_latitude: number;
      max_longitude: number;
      max_latitude: number;
    };
  };

  statistics: {
    min_c: number;
    max_c: number;
    mean_c: number;
    median_c: number;
    std_c: number;
    p10_c: number;
    p25_c: number;
    p75_c: number;
    p90_c: number;
  } | null;

  raster?: {
    source: string;
    crs: string;
    nodata: number;
    units: string;
  };
};