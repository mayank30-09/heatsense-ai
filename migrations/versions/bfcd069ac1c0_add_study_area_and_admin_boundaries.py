"""add study area and admin boundaries

Revision ID: bfcd069ac1c0
Revises: 0001_enable_postgis
Create Date: 2026-09-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry


revision: str = "bfcd069ac1c0"
down_revision: Union[str, Sequence[str], None] = "0001_enable_postgis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "study_areas",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "code",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "area_km2",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "geometry",
            Geometry(
                geometry_type="POLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "code",
            name="uq_study_areas_code",
        ),
    )

    op.create_index(
        "idx_study_areas_geometry",
        "study_areas",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "admin_boundaries",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "boundary_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "geometry",
            Geometry(
                geometry_type="POLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
            ),
            nullable=False,
        ),
    )

    op.create_index(
        "idx_admin_boundaries_geometry",
        "admin_boundaries",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_admin_boundaries_geometry",
        table_name="admin_boundaries",
    )

    op.drop_table("admin_boundaries")

    op.drop_index(
        "idx_study_areas_geometry",
        table_name="study_areas",
    )

    op.drop_table("study_areas")