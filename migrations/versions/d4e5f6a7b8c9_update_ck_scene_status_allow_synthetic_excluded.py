"""Update ck_scene_status constraint to allow SYNTHETIC_EXCLUDED.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-24 23:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_scene_status", "stage_c_scenes", type_="check")
    op.create_check_constraint(
        "ck_scene_status",
        "stage_c_scenes",
        "status IN ('PROCESSED', 'REJECTED_CLOUDY', 'FAILED', 'PENDING', 'SYNTHETIC_EXCLUDED')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_scene_status", "stage_c_scenes", type_="check")
    op.create_check_constraint(
        "ck_scene_status",
        "stage_c_scenes",
        "status IN ('PROCESSED', 'REJECTED_CLOUDY', 'FAILED', 'PENDING')",
    )
