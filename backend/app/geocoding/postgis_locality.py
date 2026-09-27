from __future__ import annotations

from typing import Any

from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from sqlalchemy import text

from backend.app.db.session import SessionLocal


def resolve_polygon_locality(
    geometry: dict[str, Any],
) -> dict[str, Any]:
    """
    Resolve a drawn EPSG:4326 polygon to the most relevant
    OSM locality stored in PostGIS.

    Resolution priority:
    1. OSM locality point contained by polygon.
    2. Nearest OSM locality point inside the SMC boundary.
    """

    polygon = shape(geometry)

    if polygon.is_empty:
        raise ValueError("Polygon geometry is empty.")

    if polygon.geom_type != "Polygon":
        raise ValueError("Expected a GeoJSON Polygon geometry.")

    if not polygon.is_valid:
        polygon = polygon.buffer(0)

    if polygon.is_empty or not polygon.is_valid:
        raise ValueError("Polygon geometry is invalid.")

    polygon_wkb = from_shape(
        polygon,
        srid=4326,
    )

    db = SessionLocal()

    try:
        contained = db.execute(
            text(
                """
                SELECT
                    id,
                    name,
                    place_type,
                    candidate_class,
                    osm_id,
                    osm_type,
                    source,
                    ST_Distance(
                        geometry::geography,
                        ST_Centroid(
                            ST_SetSRID(ST_GeomFromWKB(:geometry), 4326)
                        )::geography
                    ) AS distance_m
                FROM public.osm_places
                WHERE inside_smc = TRUE
                  AND ST_Within(
                      geometry,
                      ST_SetSRID(ST_GeomFromWKB(:geometry), 4326)
                  )
                ORDER BY
                    CASE candidate_class
                        WHEN 'micro_locality' THEN 1
                        WHEN 'urban_locality' THEN 2
                        WHEN 'settlement' THEN 3
                        ELSE 4
                    END,
                    distance_m
                LIMIT 1
                """
            ),
            {"geometry": polygon_wkb.data},
        ).mappings().first()

        if contained:
            return {
                "resolved": True,
                "method": "contains",
                "name": contained["name"],
                "place_type": contained["place_type"],
                "candidate_class": contained["candidate_class"],
                "osm_id": contained["osm_id"],
                "osm_type": contained["osm_type"],
                "source": contained["source"],
                "distance_m": round(
                    float(contained["distance_m"]),
                    2,
                ),
            }

        nearest = db.execute(
            text(
                """
                SELECT
                    id,
                    name,
                    place_type,
                    candidate_class,
                    osm_id,
                    osm_type,
                    source,
                    ST_Distance(
                        geometry::geography,
                        ST_Centroid(
                            ST_SetSRID(ST_GeomFromWKB(:geometry), 4326)
                        )::geography
                    ) AS distance_m
                FROM public.osm_places
                WHERE inside_smc = TRUE
                ORDER BY
                    distance_m,
                    CASE candidate_class
                        WHEN 'micro_locality' THEN 1
                        WHEN 'urban_locality' THEN 2
                        WHEN 'settlement' THEN 3
                        ELSE 4
                    END
                LIMIT 1
                """
            ),
            {"geometry": polygon_wkb.data},
        ).mappings().first()

        if not nearest:
            return {
                "resolved": False,
                "method": None,
                "name": None,
                "reason": "No OSM locality candidates found.",
            }

        distance_m = float(nearest["distance_m"])

        if distance_m > 1000:
            return {
                "resolved": False,
                "method": "nearest",
                "name": None,
                "reason": (
                    "Nearest OSM locality is too far "
                    "to assign confidently."
                ),
                "nearest_name": nearest["name"],
                "nearest_distance_m": round(distance_m, 2),
            }

        return {
            "resolved": True,
            "method": "nearest",
            "name": nearest["name"],
            "place_type": nearest["place_type"],
            "candidate_class": nearest["candidate_class"],
            "osm_id": nearest["osm_id"],
            "osm_type": nearest["osm_type"],
            "source": nearest["source"],
            "distance_m": round(distance_m, 2),
        }

    finally:
        db.close()
