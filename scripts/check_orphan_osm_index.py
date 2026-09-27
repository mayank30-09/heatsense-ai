from sqlalchemy import create_engine, text
from backend.app.config import get_settings

engine = create_engine(get_settings().database_url)

with engine.connect() as conn:
    result = conn.execute(
        text("""
            SELECT
                n.nspname AS schema_name,
                c.relname AS relation_name,
                c.relkind AS relation_kind,
                pg_get_indexdef(c.oid) AS definition
            FROM pg_class c
            JOIN pg_namespace n
              ON n.oid = c.relnamespace
            WHERE c.relname = 'idx_osm_places_geometry'
        """)
    ).fetchall()

    for row in result:
        print("SCHEMA     =", row.schema_name)
        print("RELATION   =", row.relation_name)
        print("RELKIND    =", row.relation_kind)
        print("DEFINITION =", row.definition)
