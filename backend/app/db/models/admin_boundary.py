from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry

from backend.app.db.base import Base


class AdminBoundary(Base):
    __tablename__ = "admin_boundaries"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    boundary_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    geometry = mapped_column(
        Geometry(
            geometry_type="POLYGON",
            srid=4326,
            spatial_index=True,
        ),
        nullable=False,
    )