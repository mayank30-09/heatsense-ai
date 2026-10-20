import os
from pathlib import Path
import sqlalchemy as sa
import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5433")
    dbname = os.environ.get("POSTGRES_DB", "heatsense")
    if not user or not password:
        raise ValueError("Database credentials not configured. Set DATABASE_URL or POSTGRES_PASSWORD in .env.")
    db_url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
else:
    db_url = db_url.replace("+psycopg", "")

engine = sa.create_engine(db_url)
with engine.connect() as conn:
    for t in ['study_areas', 'admin_boundaries', 'osm_places']:
        query = sa.text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = :t")
        cols = conn.execute(query, {"t": t}).fetchall()
        print(f"\n--- Table: {t} ---")
        for col, dtype in cols:
            print(f"  {col}: {dtype}")
        cnt = conn.execute(sa.text(f"SELECT count(*) FROM {t}")).scalar()
        print(f"  Total rows: {cnt}")
        
    print("\n--- Inspecting study_areas rows ---")
    df_sa = pd.read_sql("SELECT id, name, code, area_km2, ST_GeometryType(geometry) as geom_type FROM study_areas", conn)
    print(df_sa)

    print("\n--- Inspecting osm_places samples ---")
    df_osm = pd.read_sql("""SELECT id, name, place_type, candidate_class, inside_smc, 
                            ST_GeometryType(geometry) as geom_type, ST_SRID(geometry) as srid, 
                            ST_Area(ST_Transform(geometry, 32643))/1e6 as area_km2 
                            FROM osm_places""", conn)
    print(f"osm_places total: {len(df_osm)}, geom_types: {df_osm['geom_type'].value_counts().to_dict()}, sum area_km2: {df_osm['area_km2'].sum()}")
    print("All osm_places:")
    print(df_osm.sort_values(by='area_km2', ascending=False).to_string())
