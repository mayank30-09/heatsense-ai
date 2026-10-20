"""add stage c heat priority tables

Revision ID: f4a8b1c2d3e4
Revises: e39ad56b8ec7
Create Date: 2026-10-04 12:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2


revision: str = 'f4a8b1c2d3e4'
down_revision: Union[str, None] = 'e39ad56b8ec7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Master Grid Cells
    op.create_table(
        'stage_c_grid_cells',
        sa.Column('pixel_id', sa.String(length=16), nullable=False),
        sa.Column('row_idx', sa.Integer(), nullable=False),
        sa.Column('col_idx', sa.Integer(), nullable=False),
        sa.Column('latitude', sa.Float(precision=53), nullable=False),
        sa.Column('longitude', sa.Float(precision=53), nullable=False),
        sa.Column('x_utm', sa.Float(precision=53), nullable=False),
        sa.Column('y_utm', sa.Float(precision=53), nullable=False),
        sa.Column(
            'geometry',
            geoalchemy2.types.Geometry(
                geometry_type='POLYGON',
                srid=4326,
                dimension=2,
                from_text='ST_GeomFromEWKT',
                name='geometry',
                nullable=False
            ),
            nullable=False
        ),
        sa.Column('nominal_area_m2', sa.Float(precision=53), nullable=False),
        sa.Column('smc_clipped_area_m2', sa.Float(precision=53), nullable=False),
        sa.Column('smc_fractional_weight', sa.Float(precision=53), nullable=False),
        sa.Column('is_centroid_inside', sa.Boolean(), nullable=False),
        sa.Column('is_boundary_cell', sa.Boolean(), nullable=False),
        sa.Column('nearest_osm_place_id', sa.Integer(), nullable=True),
        sa.Column('nearest_osm_place_name', sa.String(length=64), nullable=True),
        sa.Column('nearest_osm_distance_m', sa.Float(precision=24), nullable=True),
        sa.CheckConstraint(
            'smc_fractional_weight >= 0.0 AND smc_fractional_weight <= 1.0',
            name='ck_cells_fractional_weight'
        ),
        sa.ForeignKeyConstraint(['nearest_osm_place_id'], ['osm_places.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('pixel_id')
    )
    op.create_index('idx_stage_c_cells_coords', 'stage_c_grid_cells', ['latitude', 'longitude'])

    # 2. Multi-Temporal Observations
    op.create_table(
        'stage_c_grid_observations',
        sa.Column('pixel_id', sa.String(length=16), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('season', sa.String(length=16), nullable=False),
        sa.Column('observed_lst_c', sa.Float(precision=24), nullable=True),
        sa.Column('obs_count', sa.Float(precision=24), nullable=False),
        sa.Column('st_qa_k', sa.Float(precision=24), nullable=True),
        sa.Column('ndvi', sa.Float(precision=24), nullable=True),
        sa.Column('ndbi', sa.Float(precision=24), nullable=True),
        sa.Column('ndwi', sa.Float(precision=24), nullable=True),
        sa.Column('optical_imputation_flag', sa.String(length=32), nullable=False, server_default='NONE'),
        sa.Column('eligibility_status', sa.String(length=16), nullable=False),
        sa.Column('quality_flag', sa.String(length=128), nullable=False),
        sa.Column('source_cog', sa.String(length=128), nullable=False),
        sa.CheckConstraint("season IN ('winter', 'summer', 'monsoon', 'post_monsoon')", name='ck_obs_season'),
        sa.CheckConstraint("eligibility_status IN ('ACCEPT', 'FLAG', 'EXCLUDE')", name='ck_obs_eligibility'),
        sa.ForeignKeyConstraint(['pixel_id'], ['stage_c_grid_cells.pixel_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('pixel_id', 'year', 'season')
    )
    op.create_index('idx_stage_c_obs_year_season', 'stage_c_grid_observations', ['year', 'season'])
    op.create_index('idx_stage_c_obs_eligibility', 'stage_c_grid_observations', ['eligibility_status'])

    # 3. Versioned Heat Priority Scores
    op.create_table(
        'stage_c_heat_priority_scores',
        sa.Column('pixel_id', sa.String(length=16), nullable=False),
        sa.Column('scoring_period', sa.String(length=32), nullable=False),
        sa.Column('spec_version', sa.String(length=16), nullable=False, server_default='v2.0'),
        sa.Column('heat_priority_score', sa.Float(precision=24), nullable=True),
        sa.Column('thermal_severity_component', sa.Float(precision=24), nullable=True),
        sa.Column('persistence_component', sa.Float(precision=24), nullable=True),
        sa.Column('vegetation_deficit_component', sa.Float(precision=24), nullable=True),
        sa.Column('built_density_component', sa.Float(precision=24), nullable=True),
        sa.Column('effective_weights', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('confidence_index', sa.Float(precision=24), nullable=False),
        sa.Column('confidence_tier', sa.String(length=32), nullable=False),
        sa.Column('persistence_tier', sa.String(length=32), nullable=False),
        sa.Column('is_chronic_hotspot', sa.Boolean(), nullable=False),
        sa.Column('valid_seasons_count', sa.Integer(), nullable=False),
        sa.Column('hot_seasons_count', sa.Integer(), nullable=False),
        sa.Column('hotspot_frequency', sa.Float(precision=24), nullable=False),
        sa.Column('distinct_years_count', sa.Integer(), nullable=False),
        sa.Column('eligibility_status', sa.String(length=32), nullable=False),
        sa.Column('provenance_hash', sa.String(length=64), nullable=False),
        sa.Column('calculated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint('heat_priority_score >= 0.0 AND heat_priority_score <= 100.0', name='ck_hpi_score_range'),
        sa.CheckConstraint("confidence_tier IN ('HIGH', 'MODERATE', 'LOW', 'INSUFFICIENT')", name='ck_hpi_confidence_tier'),
        sa.ForeignKeyConstraint(['pixel_id'], ['stage_c_grid_cells.pixel_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('pixel_id', 'scoring_period', 'spec_version')
    )
    op.create_index('idx_stage_c_hpi_score', 'stage_c_heat_priority_scores', ['heat_priority_score'])
    op.create_index('idx_stage_c_hpi_chronic', 'stage_c_heat_priority_scores', ['is_chronic_hotspot'])
    op.create_index('idx_stage_c_hpi_confidence', 'stage_c_heat_priority_scores', ['confidence_tier'])


def downgrade() -> None:
    op.drop_table('stage_c_heat_priority_scores')
    op.drop_table('stage_c_grid_observations')
    op.drop_table('stage_c_grid_cells')
