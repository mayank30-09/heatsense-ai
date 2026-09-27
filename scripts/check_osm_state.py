from sqlalchemy import create_engine, text
from backend.app.config import get_settings

engine = create_engine(get_settings().database_url)

with engine.connect() as conn:
    result = conn.execute(
        text("""
            SELECT
                to_regclass('public.osm_places') AS table_name,
                to_regclass('public.idx_osm_places_geometry') AS index_name
        """)
    ).one()

    print("TABLE =", result.table_name)
    print("INDEX =", result.index_name)
