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

export type ActiveLayerMode = "hpi" | "lst" | "confidence" | "chronic";

export interface CellQueryFilters {
  bbox?: ViewportBBox;
  min_hpi?: number;
  is_chronic_hotspot?: boolean;
  confidence_tier?: string;
  persistence_tier?: string;
  locality?: string;
  limit?: number;
  offset?: number;
}
