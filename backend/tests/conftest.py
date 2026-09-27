import os
import pyproj

# Ensure PROJ environment uses pyproj bundled data directory
if "PROJ_LIB" in os.environ and "PostgreSQL" in os.environ["PROJ_LIB"]:
    os.environ.pop("PROJ_LIB", None)

try:
    os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())
except Exception:
    pass
