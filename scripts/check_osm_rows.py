from sqlalchemy import create_engine, text
from backend.app.config import get_settings

engine = create_engine(get_settings().database_url)

with engine.connect() as conn:
    print("ROWS =", conn.execute(
        text("SELECT COUNT(*) FROM public.osm_places")
    ).scalar())
