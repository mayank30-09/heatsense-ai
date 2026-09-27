from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry

from backend.app.db.base import Base


class OSMPlace(Base):
    __tablename__ = "osm_places"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    osm_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    osm_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    place_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    candidate_class: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    inside_smc: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    duplicate_name: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source_dataset: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    geometry = mapped_column(
        Geometry(
            geometry_type="POINT",
            srid=4326,
            spatial_index=True,
        ),
        nullable=False,
    )
