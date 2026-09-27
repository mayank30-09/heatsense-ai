from logging.config import fileConfig
from sqlalchemy import inspect
from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db import models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()

database_url = settings.database_url

config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)

target_metadata = Base.metadata


def include_object(
    object,
    name,
    type_,
    reflected,
    compare_to,
):
    # Never filter objects coming from our SQLAlchemy metadata.
    if not reflected:
        return True

    # Ignore PostGIS system table.
    if type_ == "table" and name == "spatial_ref_sys":
        return False

    # Ignore known PostGIS/TIGER/Topology managed objects.
    ignored_tables = {
        "geocode_settings_default",
        "county_lookup",
        "countysub_lookup",
        "loader_variables",
        "place_lookup",
        "bg",
        "zip_lookup_base",
        "faces",
        "loader_lookuptables",
        "loader_platform",
        "geocode_settings",
        "pagc_gaz",
        "state_lookup",
        "tabblock",
        "cousub",
        "addrfeat",
        "addr",
        "zip_lookup_all",
        "topology",
        "pagc_rules",
        "direction_lookup",
        "tabblock20",
        "edges",
        "zip_lookup",
        "pagc_lex",
        "zip_state",
        "street_type_lookup",
        "county",
        "zip_state_loc",
        "tract",
        "secondary_unit_lookup",
        "place",
        "featnames",
        "state",
        "zcta5",
        "layer",
    }

    if type_ == "table" and name in ignored_tables:
        return False

    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
    url=url,
    target_metadata=target_metadata,
    literal_binds=True,
    include_object=include_object,
    include_schemas=False,
)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
    connection=connection,
    target_metadata=target_metadata,
    include_object=include_object,
    include_schemas=False,
)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()