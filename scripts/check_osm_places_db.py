from sqlalchemy import create_engine, text
from backend.app.config import get_settings

engine = create_engine(get_settings().database_url)

with engine.connect() as conn:
    table = conn.execute(
        text("SELECT to_regclass('public.osm_places')")
    ).scalar()

    indexes = conn.execute(
        text("""
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'osm_places'
            ORDER BY indexname
        """)
    ).fetchall()

    print("TABLE  =", table)
    print("INDEXES =", indexes)
