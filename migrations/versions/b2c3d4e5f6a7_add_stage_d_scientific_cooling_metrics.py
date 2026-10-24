"""Add Stage D scientific cooling metrics and scenario persistence tables.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-14 12:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    context = op.get_context()
    is_offline = getattr(context, "as_sql", False) or (context.bind and type(context.bind).__name__ == "MockConnection")
    if is_offline:
        existing_tables = set()
    else:
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        existing_tables = set(inspector.get_table_names())

    # 1. Candidates table
    if "stage_d_intervention_candidates" not in existing_tables:
        op.create_table(
            "stage_d_intervention_candidates",
            sa.Column("candidate_id", sa.String(length=64), primary_key=True),
            sa.Column("cell_id", sa.String(length=16), nullable=False),
            sa.Column("intervention_type", sa.String(length=32), nullable=False),
            sa.Column("usable_area_m2", sa.Float(), nullable=False),
            sa.Column("tree_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_inr", sa.Float(), nullable=False),
            sa.Column("cost_inr_min", sa.Float(), nullable=False),
            sa.Column("cost_inr_max", sa.Float(), nullable=False),
            sa.Column("expected_cooling_c", sa.Float(), nullable=False),
            sa.Column("expected_cooling_c_min", sa.Float(), nullable=False),
            sa.Column("expected_cooling_c_max", sa.Float(), nullable=False),
            sa.Column("feasibility_status", sa.String(length=20), nullable=False),
            sa.Column("rejection_reason", sa.String(length=40), nullable=False),
            sa.Column("baseline_hpi", sa.Float(), nullable=True),
            sa.Column("baseline_lst_c", sa.Float(), nullable=True),
            sa.Column("is_chronic_hotspot", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("administrative_zone", sa.String(length=64), nullable=False),
            sa.Column(
                "evidence_status",
                sa.String(length=64),
                nullable=False,
                server_default="CALIBRATED_EMPIRICAL_MICROCLIMATE",
            ),
            sa.Column(
                "geometry",
                geoalchemy2.types.Geometry(
                    geometry_type="POLYGON",
                    srid=4326,
                    spatial_index=True,
                ),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index("ix_stage_d_candidates_cell", "stage_d_intervention_candidates", ["cell_id"])
        op.create_index("ix_stage_d_candidates_type", "stage_d_intervention_candidates", ["intervention_type"])
        op.create_index(
            "ix_stage_d_candidates_zone_type",
            "stage_d_intervention_candidates",
            ["administrative_zone", "intervention_type"],
        )
        op.create_index(
            "ix_stage_d_candidates_feasibility",
            "stage_d_intervention_candidates",
            ["feasibility_status"],
        )

    # 2. Scenario results table
    if "stage_d_scenario_results" not in existing_tables:
        op.create_table(
            "stage_d_scenario_results",
            sa.Column("scenario_id", sa.String(length=64), primary_key=True),
            sa.Column("algorithm", sa.String(length=32), nullable=False),
            sa.Column("budget_inr", sa.Float(), nullable=False),
            sa.Column("total_cost_inr", sa.Float(), nullable=False),
            sa.Column("portfolio_thermal_benefit_c_m2", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("treated_area_m2", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("mean_local_cooling_c", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("citywide_cooling_c", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("domain_area_m2", sa.Float(), nullable=False, server_default="461630791.0"),
            sa.Column("heat_priority_weighted_benefit_c_m2", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("population_exposure_benefit", sa.Float(), nullable=True),
            sa.Column(
                "population_exposure_status",
                sa.String(length=64),
                nullable=False,
                server_default="POPULATION_DATA_UNAVAILABLE",
            ),
            sa.Column("total_cooling_c", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("heat_weighted_cooling", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("chronic_hotspots_count", sa.Integer(), nullable=False),
            sa.Column("interventions_count", sa.Integer(), nullable=False),
            sa.Column("is_feasible", sa.Boolean(), nullable=False),
            sa.Column("pareto_rank", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("selected_candidates_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index("ix_stage_d_scenarios_algo", "stage_d_scenario_results", ["algorithm"])
    else:
        # Table exists, inspect columns to add missing ones
        existing_cols = {col["name"] for col in inspector.get_columns("stage_d_scenario_results")}

        new_columns = [
            ("portfolio_thermal_benefit_c_m2", sa.Float(), "0.0", False),
            ("treated_area_m2", sa.Float(), "0.0", False),
            ("mean_local_cooling_c", sa.Float(), "0.0", False),
            ("citywide_cooling_c", sa.Float(), "0.0", False),
            ("domain_area_m2", sa.Float(), "461630791.0", False),
            ("heat_priority_weighted_benefit_c_m2", sa.Float(), "0.0", False),
            ("population_exposure_benefit", sa.Float(), None, True),
            ("population_exposure_status", sa.String(length=64), "'POPULATION_DATA_UNAVAILABLE'", False),
        ]

        for col_name, col_type, s_default, nullable in new_columns:
            if col_name not in existing_cols:
                op.add_column(
                    "stage_d_scenario_results",
                    sa.Column(col_name, col_type, nullable=nullable, server_default=s_default),
                )


def downgrade() -> None:
    context = op.get_context()
    is_offline = getattr(context, "as_sql", False) or (context.bind and type(context.bind).__name__ == "MockConnection")
    if is_offline:
        op.drop_index("ix_stage_d_scenarios_algo", table_name="stage_d_scenario_results")
        op.drop_table("stage_d_scenario_results")
        op.drop_index("ix_stage_d_candidates_feasibility", table_name="stage_d_intervention_candidates")
        op.drop_index("ix_stage_d_candidates_zone_type", table_name="stage_d_intervention_candidates")
        op.drop_index("ix_stage_d_candidates_type", table_name="stage_d_intervention_candidates")
        op.drop_index("ix_stage_d_candidates_cell", table_name="stage_d_intervention_candidates")
        op.drop_table("stage_d_intervention_candidates")
        return

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "stage_d_intervention_candidates" in existing_tables:
        op.drop_index("ix_stage_d_candidates_feasibility", table_name="stage_d_intervention_candidates")
        op.drop_index("ix_stage_d_candidates_zone_type", table_name="stage_d_intervention_candidates")
        op.drop_index("ix_stage_d_candidates_type", table_name="stage_d_intervention_candidates")
        op.drop_index("ix_stage_d_candidates_cell", table_name="stage_d_intervention_candidates")
        op.drop_table("stage_d_intervention_candidates")

    if "stage_d_scenario_results" in existing_tables:
        op.drop_index("ix_stage_d_scenarios_algo", table_name="stage_d_scenario_results")
        op.drop_table("stage_d_scenario_results")

