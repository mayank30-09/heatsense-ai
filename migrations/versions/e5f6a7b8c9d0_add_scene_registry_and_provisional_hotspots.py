"""Add stage_c_scene_registry and stage_c_provisional_hotspots.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-27 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Near-Real-Time Scene Lifecycle Registry Table
    op.create_table(
        "stage_c_scene_registry",
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("sensor", sa.String(length=32), nullable=False),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("acquisition_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("path", sa.Integer(), nullable=False, server_default="148"),
        sa.Column("row", sa.Integer(), nullable=False, server_default="45"),
        sa.Column("cloud_cover", sa.Float(precision=24), nullable=True),
        sa.Column("valid_pixel_fraction", sa.Float(precision=24), nullable=True),
        sa.Column("clear_threshold", sa.Float(precision=24), nullable=False, server_default="0.40"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="discovered"),
        sa.Column("rejection_reason", sa.String(length=256), nullable=True),
        sa.Column("mean_lst_c", sa.Float(precision=24), nullable=True),
        sa.Column("max_lst_c", sa.Float(precision=24), nullable=True),
        sa.Column("cog_path", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "status IN ('discovered', 'downloaded', 'qa_passed', 'scored', 'published', 'rejected')",
            name="ck_scene_registry_status",
        ),
        sa.CheckConstraint(
            "clear_threshold >= 0.0 AND clear_threshold <= 1.0",
            name="ck_scene_registry_threshold",
        ),
        sa.PrimaryKeyConstraint("scene_id"),
    )
    op.create_index("idx_scene_reg_status", "stage_c_scene_registry", ["status"])
    op.create_index("idx_scene_reg_date", "stage_c_scene_registry", ["acquisition_date"])
    op.create_index("idx_scene_reg_time", "stage_c_scene_registry", ["acquisition_time"])

    # 2. Provisional Single-Scene Hotspots (Isolated from Frozen HPI and 223 Chronic Set)
    op.create_table(
        "stage_c_provisional_hotspots",
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("pixel_id", sa.String(length=16), nullable=False),
        sa.Column("observed_lst_c", sa.Float(precision=24), nullable=False),
        sa.Column("climatology_lst_c", sa.Float(precision=24), nullable=True),
        sa.Column("thermal_anomaly_c", sa.Float(precision=24), nullable=True),
        sa.Column("percentile_rank", sa.Float(precision=24), nullable=True),
        sa.Column("is_provisional_hotspot", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("hotspot_type", sa.String(length=64), nullable=False, server_default="Provisional NRT hotspot, single scene"),
        sa.Column("flagged_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["pixel_id"], ["stage_c_grid_cells.pixel_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scene_id", "pixel_id"),
    )
    op.create_index("idx_prov_hotspots_pixel_id", "stage_c_provisional_hotspots", ["pixel_id"])
    op.create_index("idx_prov_hotspots_scene_id", "stage_c_provisional_hotspots", ["scene_id"])


def downgrade() -> None:
    op.drop_index("idx_prov_hotspots_scene_id", table_name="stage_c_provisional_hotspots")
    op.drop_index("idx_prov_hotspots_pixel_id", table_name="stage_c_provisional_hotspots")
    op.drop_table("stage_c_provisional_hotspots")

    op.drop_index("idx_scene_reg_time", table_name="stage_c_scene_registry")
    op.drop_index("idx_scene_reg_date", table_name="stage_c_scene_registry")
    op.drop_index("idx_scene_reg_status", table_name="stage_c_scene_registry")
    op.drop_table("stage_c_scene_registry")
