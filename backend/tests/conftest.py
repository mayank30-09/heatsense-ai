import os
import pyproj

# Ensure PROJ environment uses pyproj bundled data directory
if "PROJ_LIB" in os.environ and "PostgreSQL" in os.environ["PROJ_LIB"]:
    os.environ.pop("PROJ_LIB", None)

try:
    os.environ.setdefault("PROJ_DATA", pyproj.datadir.get_data_dir())
except Exception:
    pass

os.environ.setdefault("DEV_USER_PASSWORD", "test_throwaway_mock_password_2026")

import pytest
from backend.app.main import app
from backend.app.core.auth import DEV_USERS_DB, User, require_planner_or_admin


@pytest.fixture(autouse=True)
def _stage_d_test_auth_override(request):
    """Preserve Stage D test compatibility through explicit test dependency overrides.

    Stage D tests verify optimization mathematics, candidate selection, budget constraints,
    and cooling metrics. In runtime production/deployment configurations, optimization
    fails closed requiring Planner or Admin role.
    This override is scoped strictly to test_stage_d_* test files.
    """
    node_name = request.node.fspath.basename if hasattr(request.node, "fspath") else str(request.node.path)
    if "test_stage_d" in node_name:
        planner = DEV_USERS_DB["planner_officer"]
        app.dependency_overrides[require_planner_or_admin] = lambda: User(**planner.model_dump())
        try:
            yield
        finally:
            app.dependency_overrides.pop(require_planner_or_admin, None)
    else:
        yield
