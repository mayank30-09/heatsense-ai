import os
import pyproj

# Prevent PostgreSQL/PostGIS PROJ_LIB conflict on Windows
if "PROJ_LIB" in os.environ and "PostgreSQL" in os.environ["PROJ_LIB"]:
    os.environ.pop("PROJ_LIB", None)

try:
    os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())
except Exception:
    pass
