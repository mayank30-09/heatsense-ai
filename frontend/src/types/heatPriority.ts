export interface NormalizationConstants {
  t_min_c: number;
  t_max_c: number;
  ndvi_min: number;
  ndvi_target: number;
  ndbi_min: number;
  ndbi_max: number;
  w_thermal: number;
  w_persistence: number;
  w_vegetation: number;
  w_builtup: number;
  formula: string;
  data_observation_years: string;
  overpass_solar_time: string;
}

export interface HeatPrioritySummary {
  scoring_period: string;
  spec_version: string;
  total_grid_cells: number;
  scored_cells: number;
  mean_hpi: number | null;
  min_hpi: number | null;
  max_hpi: number | null;
  chronic_hotspots_count: number;
  confidence_tier_counts: Record<string, number>;
  persistence_tier_counts: Record<string, number>;
  normalization_constants?: NormalizationConstants;
}

export interface GridCellScoreItem {
  pixel_id: string;
  row_idx: number;
  col_idx: number;
  latitude: number;
  longitude: number;
  nearest_osm_place_name: string | null;
  nearest_osm_distance_m: number | null;
  heat_priority_score: number | null;
  thermal_severity_component: number | null;
  persistence_component: number | null;
  vegetation_deficit_component: number | null;
  built_density_component: number | null;
  confidence_index: number | null;
  confidence_tier: string | null;
  persistence_tier: string | null;
  is_chronic_hotspot: boolean;
  hotspot_frequency: number | null;
  eligibility_status: string | null;
  observed_lst_c: number | null;
  optical_imputation_flag: string | null;
}

export interface GridCellsPaginatedResponse {
  total: number;
  offset: number;
  limit: number;
  items: GridCellScoreItem[];
}

export interface ViewportBBox {
  min_lon: number;
  min_lat: number;
  max_lon: number;
  max_lat: number;
}

export type ActiveLayerMode = "hpi" | "lst" | "confidence" | "chronic" | "latest_scene";

export type SeasonName = "summer" | "winter" | "monsoon" | "post_monsoon";

export interface CellQueryFilters {
  bbox?: ViewportBBox;
  min_hpi?: number;
  is_chronic_hotspot?: boolean;
  confidence_tier?: string;
  persistence_tier?: string;
  locality?: string;
  season?: SeasonName;
  year?: number;
  limit?: number;
  offset?: number;
}

export interface LSTStats {
  season: SeasonName;
  year: number;
  effective_year: number;
  n_cells: number;
  n_valid: number;
  valid_fraction?: number;
  mean_c: number | null;
  min_c: number | null;
  max_c: number | null;
  p90_c: number | null;
  source: string;
  is_partial: boolean;
  n_scenes?: number;
  first_acquisition_date?: string;
  last_acquisition_date?: string;
  date_window?: string;
}

export interface ModelValidationSummary {
  qc_summary: {
    status: string;
    dataset_integrity: {
      dataset_path: string;
      row_count: number;
      spatial_blocks: number;
      target: string;
      policy: string;
    };
    spatial_split_integrity: {
      total_blocks: number;
      development_blocks: number;
      test_blocks: number;
      test_ratio: number;
      disjointness_verified: boolean;
      coverage_verified: boolean;
      deterministic: boolean;
    };
    leakage_controls: Record<string, boolean>;
    feature_schema: {
      target: string;
      features: string[];
      coordinates_excluded: boolean;
    };
    holdout_evaluation: {
      evaluation_count: number;
      test_blocks: number;
      test_rows: number;
      mae: number;
      rmse: number;
      r2: number;
      inference_latency_seconds: number;
    };
    seasonal_performance: Record<
      string,
      { n: number; mae: number; rmse: number; r2: number; bias: number }
    >;
    hotspot_performance: Record<
      string,
      { n: number; mae: number; rmse: number; r2: number; bias: number }
    >;
    residual_diagnostics: {
      cold_bias_in_chronic_hotspots: number;
      spatial_clustering_of_residuals: string;
      primary_evidence_retained: string;
    };
    known_limitations: string[];
  };
  model_metadata: {
    model_id: string;
    git_commit?: string;
    timestamp_utc?: string;
    best_development_cv_rmse?: number;
    best_parameters?: Record<string, any>;
    environment?: Record<string, string>;
  };
  model_comparison?: Array<{
    model: string;
    mean_mae: number;
    std_mae: number;
    mean_rmse: number;
    std_rmse: number;
    mean_r2: number;
    std_r2: number;
  }>;
}


