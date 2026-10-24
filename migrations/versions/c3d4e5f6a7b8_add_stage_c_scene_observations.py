"""Add stage_c_scenes and stage_c_scene_observations for near-real-time Landsat monitoring.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-23 12:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Processing Ledger and Scene Catalog Table
    op.create_table(
        "stage_c_scenes",
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("acquisition_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sensor", sa.String(length=32), nullable=False),
        sa.Column("path", sa.Integer(), nullable=False, server_default="148"),
        sa.Column("row", sa.Integer(), nullable=False, server_default="45"),
        sa.Column("cloud_cover", sa.Float(precision=24), nullable=True),
        sa.Column("valid_pixel_fraction", sa.Float(precision=24), nullable=False),
        sa.Column("mean_lst_c", sa.Float(precision=24), nullable=True),
        sa.Column("max_lst_c", sa.Float(precision=24), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PROCESSED"),
        sa.Column("cog_path", sa.String(length=256), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "status IN ('PROCESSED', 'REJECTED_CLOUDY', 'FAILED', 'PENDING', 'SYNTHETIC_EXCLUDED')",
            name="ck_scene_status",
        ),
        sa.CheckConstraint(
            "valid_pixel_fraction >= 0.0 AND valid_pixel_fraction <= 1.0",
            name="ck_scene_valid_pixel_fraction",
        ),
        sa.PrimaryKeyConstraint("scene_id"),
    )
    op.create_index("idx_stage_c_scenes_date", "stage_c_scenes", ["acquisition_date"])
    op.create_index("idx_stage_c_scenes_time", "stage_c_scenes", ["acquisition_time"])
    op.create_index("idx_stage_c_scenes_status", "stage_c_scenes", ["status"])

    # 2. Per-Pixel Single-Scene Observation Table
    op.create_table(
        "stage_c_scene_observations",
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("pixel_id", sa.String(length=16), nullable=False),
        sa.Column("observed_lst_c", sa.Float(precision=24), nullable=True),
        sa.Column("st_qa_k", sa.Float(precision=24), nullable=True),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["scene_id"], ["stage_c_scenes.scene_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pixel_id"], ["stage_c_grid_cells.pixel_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scene_id", "pixel_id"),
    )
    op.create_index("idx_scene_obs_pixel_id", "stage_c_scene_observations", ["pixel_id"])
    op.create_index("idx_scene_obs_scene_id", "stage_c_scene_observations", ["scene_id"])


def downgrade() -> None:
    op.drop_index("idx_scene_obs_scene_id", table_name="stage_c_scene_observations")
    op.drop_index("idx_scene_obs_pixel_id", table_name="stage_c_scene_observations")
    op.drop_table("stage_c_scene_observations")

    op.drop_index("idx_stage_c_scenes_status", table_name="stage_c_scenes")
    op.drop_index("idx_stage_c_scenes_time", table_name="stage_c_scenes")
    op.drop_index("idx_stage_c_scenes_date", table_name="stage_c_scenes")
    op.drop_table("stage_c_scenes")
