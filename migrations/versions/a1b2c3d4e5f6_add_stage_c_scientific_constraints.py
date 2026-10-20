"""Add Stage C scientific constraints and persistence tier index.

Revision ID: a1b2c3d4e5f6
Revises: f4a8b1c2d3e4
Create Date: 2026-10-04 14:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f4a8b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Observation imputation flag constraint
    op.create_check_constraint(
        "ck_obs_imputation_flag",
        "stage_c_grid_observations",
        "optical_imputation_flag IN ('NONE', 'OPTICAL_IMPUTED_MEDIAN', 'OPTICAL_IMPUTED_BOUNDARY', 'OPTICAL_FALLBACK_NEUTRAL')",
    )

    # 2. Stage C Score component range and finite score constraints
    op.create_check_constraint(
        "ck_hpi_thermal_severity",
        "stage_c_heat_priority_scores",
        "thermal_severity_component >= 0.0 AND thermal_severity_component <= 1.0",
    )
    op.create_check_constraint(
        "ck_hpi_persistence",
        "stage_c_heat_priority_scores",
        "persistence_component >= 0.0 AND persistence_component <= 1.0",
    )
    op.create_check_constraint(
        "ck_hpi_vegetation_deficit",
        "stage_c_heat_priority_scores",
        "vegetation_deficit_component >= 0.0 AND vegetation_deficit_component <= 1.0",
    )
    op.create_check_constraint(
        "ck_hpi_built_density",
        "stage_c_heat_priority_scores",
        "built_density_component >= 0.0 AND built_density_component <= 1.0",
    )
    op.create_check_constraint(
        "ck_hpi_confidence_index",
        "stage_c_heat_priority_scores",
        "confidence_index >= 0.0 AND confidence_index <= 1.0",
    )
    op.create_check_constraint(
        "ck_hpi_hotspot_frequency",
        "stage_c_heat_priority_scores",
        "hotspot_frequency >= 0.0 AND hotspot_frequency <= 1.0",
    )
    op.create_check_constraint(
        "ck_hpi_persistence_tier",
        "stage_c_heat_priority_scores",
        "persistence_tier IN ('chronic_hotspot', 'frequent_hotspot', 'occasional_hotspot', 'transient_extreme', 'non_hotspot')",
    )
    op.create_check_constraint(
        "ck_hpi_eligibility",
        "stage_c_heat_priority_scores",
        "eligibility_status IN ('ACCEPT', 'FLAG', 'EXCLUDE', 'INSUFFICIENT_THERMAL_EVIDENCE')",
    )

    # 3. Persistence tier index for fast spatial-temporal hotspot queries
    op.create_index(
        "idx_stage_c_hpi_persistence_tier",
        "stage_c_heat_priority_scores",
        ["persistence_tier"],
    )


def downgrade() -> None:
    op.drop_index("idx_stage_c_hpi_persistence_tier", table_name="stage_c_heat_priority_scores")
    op.drop_constraint("ck_hpi_eligibility", "stage_c_heat_priority_scores", type_="check")
    op.drop_constraint("ck_hpi_persistence_tier", "stage_c_heat_priority_scores", type_="check")
    op.drop_constraint("ck_hpi_hotspot_frequency", "stage_c_heat_priority_scores", type_="check")
    op.drop_constraint("ck_hpi_confidence_index", "stage_c_heat_priority_scores", type_="check")
    op.drop_constraint("ck_hpi_built_density", "stage_c_heat_priority_scores", type_="check")
    op.drop_constraint("ck_hpi_vegetation_deficit", "stage_c_heat_priority_scores", type_="check")
    op.drop_constraint("ck_hpi_persistence", "stage_c_heat_priority_scores", type_="check")
    op.drop_constraint("ck_hpi_thermal_severity", "stage_c_heat_priority_scores", type_="check")
    op.drop_constraint("ck_obs_imputation_flag", "stage_c_grid_observations", type_="check")
