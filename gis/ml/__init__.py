"""Machine learning and spatial validation package for HEATSENSE AI.

Provides analysis dataset building, deterministic spatial blocking,
spatial cross-validation, baseline Random Forest, XGBoost regression,
and SHAP model attribution.
"""

from gis.ml.dataset import (
    load_seasonal_cog_df,
    build_analysis_dataset,
    assign_spatial_blocks,
)
from gis.ml.spatial_validation import (
    spatial_block_folds,
    validate_fold_separation,
)

__all__ = [
    "load_seasonal_cog_df",
    "build_analysis_dataset",
    "assign_spatial_blocks",
    "spatial_block_folds",
    "validate_fold_separation",
]
