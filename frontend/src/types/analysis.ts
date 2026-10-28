export interface SeasonSummary {
  season: string;
  year: number;
  effective_year: number;
  mean_c: number | null;
  min_c: number | null;
  max_c: number | null;
  valid_pixel_count: number;
  data_coverage_percentage: number;
  is_partial: boolean;
  delta_to_summer_c?: number | null;
}

export type AnalysisResult = {
  status: "ok" | "outside_study_area" | "partially_outside" | "no_valid_observations" | "no_data";

  season?: string;
  effective_year?: number;
  same_year_comparison?: boolean;
  season_note?: string;
  source_file?: string;

  area_km2: number;
  inside_smc_fraction?: number;
  valid_pixel_count: number;
  total_intersecting_pixel_count?: number;
  nodata_pixel_count?: number;
  data_coverage_percentage?: number;
  coverage_definition?: string;
  boundary_source?: string;
  geometry_repaired?: boolean;
  is_very_small_polygon?: boolean;
  ndwi_water_fraction?: number;
  water_warning?: boolean;
  geojson_geometry?: any;

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

  seasons_table?: SeasonSummary[];

  raster?: {
    source: string;
    crs: string;
    nodata: number;
    units: string;
  };
};