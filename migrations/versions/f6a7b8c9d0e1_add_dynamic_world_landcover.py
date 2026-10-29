"""Add stage_d_dynamic_world_landcover and stage_d_landcover_pipeline_runs tables.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-29 13:45:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Pipeline Runs Provenance Table
    op.create_table(
        "stage_d_landcover_pipeline_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("season", sa.String(length=20), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.String(length=10), nullable=False),
        sa.Column("end_date", sa.String(length=10), nullable=False),
        sa.Column("total_cells", sa.Integer(), nullable=False),
        sa.Column("cells_sufficient", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cells_insufficient", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cells_no_observations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_observations_threshold", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("source_dataset", sa.String(length=64), nullable=False, server_default="GOOGLE/DYNAMICWORLD/V1"),
        sa.Column("pipeline_version", sa.String(length=32), nullable=False, server_default="v1.0"),
        sa.Column("attribution", sa.String(length=256), nullable=False),
        sa.Column("citation", sa.String(length=256), nullable=False),
        sa.Column("license", sa.String(length=64), nullable=False, server_default="CC-BY-4.0"),
        sa.Column("parameters_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    # 2. Dynamic World Land Cover Table
    op.create_table(
        "stage_d_dynamic_world_landcover",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("cell_id", sa.String(length=16), nullable=False),
        sa.Column("season", sa.String(length=20), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.String(length=10), nullable=False),
        sa.Column("end_date", sa.String(length=10), nullable=False),
        # 9 Mean Probabilities
        sa.Column("mean_water", sa.Float(), nullable=True),
        sa.Column("mean_trees", sa.Float(), nullable=True),
        sa.Column("mean_grass", sa.Float(), nullable=True),
        sa.Column("mean_flooded_vegetation", sa.Float(), nullable=True),
        sa.Column("mean_crops", sa.Float(), nullable=True),
        sa.Column("mean_shrub_and_scrub", sa.Float(), nullable=True),
        sa.Column("mean_built", sa.Float(), nullable=True),
        sa.Column("mean_bare", sa.Float(), nullable=True),
        sa.Column("mean_snow_and_ice", sa.Float(), nullable=True),
        # 9 Hard-Label Proportions (computed separately from label band)
        sa.Column("prop_water", sa.Float(), nullable=True),
        sa.Column("prop_trees", sa.Float(), nullable=True),
        sa.Column("prop_grass", sa.Float(), nullable=True),
        sa.Column("prop_flooded_vegetation", sa.Float(), nullable=True),
        sa.Column("prop_crops", sa.Float(), nullable=True),
        sa.Column("prop_shrub_and_scrub", sa.Float(), nullable=True),
        sa.Column("prop_built", sa.Float(), nullable=True),
        sa.Column("prop_bare", sa.Float(), nullable=True),
        sa.Column("prop_snow_and_ice", sa.Float(), nullable=True),
        # Observation count and classification diagnostics
        sa.Column("valid_observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("top_class", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("margin", sa.Float(), nullable=True),
        sa.Column("entropy", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="SUFFICIENT"),
        # Provenance
        sa.Column("source_dataset", sa.String(length=64), nullable=False, server_default="GOOGLE/DYNAMICWORLD/V1"),
        sa.Column("class_schema", sa.String(length=64), nullable=False, server_default="dw_9class_v1"),
        sa.Column("pipeline_version", sa.String(length=32), nullable=False, server_default="v1.0"),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("cell_id", "season", "year", "pipeline_version", name="uq_dw_landcover_cell_season_year_ver"),
        sa.ForeignKeyConstraint(["cell_id"], ["stage_c_grid_cells.pixel_id"], ondelete="CASCADE"),
    )

    op.create_index("idx_dw_landcover_cell_id", "stage_d_dynamic_world_landcover", ["cell_id"])
    op.create_index("idx_dw_landcover_season_year", "stage_d_dynamic_world_landcover", ["season", "year"])
    op.create_index("idx_dw_landcover_status", "stage_d_dynamic_world_landcover", ["status"])
    op.create_index("idx_dw_landcover_top_class", "stage_d_dynamic_world_landcover", ["top_class"])
    op.create_index("idx_dw_landcover_run_id", "stage_d_dynamic_world_landcover", ["run_id"])


def downgrade() -> None:
    op.drop_table("stage_d_dynamic_world_landcover")
    op.drop_table("stage_d_landcover_pipeline_runs")

