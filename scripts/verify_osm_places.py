from sqlalchemy import create_engine, text
from backend.app.config import get_settings

engine = create_engine(get_settings().database_url)

with engine.connect() as conn:
    total = conn.execute(
        text("SELECT COUNT(*) FROM public.osm_places")
    ).scalar()

    inside_smc = conn.execute(
        text("""
            SELECT COUNT(*)
            FROM public.osm_places
            WHERE inside_smc = TRUE
        """)
    ).scalar()

    print("TOTAL PLACES =", total)
    print("INSIDE SMC   =", inside_smc)
