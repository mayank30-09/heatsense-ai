from sqlalchemy import create_engine, text
from backend.app.config import get_settings

engine = create_engine(get_settings().database_url)

with engine.connect() as conn:
    rows = conn.execute(
        text("""
            SELECT name, place_type, candidate_class
            FROM public.osm_places
            WHERE inside_smc = TRUE
            ORDER BY candidate_class, place_type, name
        """)
    ).fetchall()

    for row in rows:
        print(
            f"{row.name} | "
            f"{row.place_type} | "
            f"{row.candidate_class}"
        )
