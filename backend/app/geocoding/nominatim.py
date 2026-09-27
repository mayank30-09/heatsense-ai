from __future__ import annotations

import os
from typing import Any

import httpx


GOOGLE_GEOCODING_URL = (
    "https://maps.googleapis.com/maps/api/geocode/json"
)


class GoogleGeocodingError(RuntimeError):
    """Raised when Google Geocoding cannot resolve a location."""


def _extract_component(
    components: list[dict[str, Any]],
    component_type: str,
) -> str | None:
    """
    Return the long_name of the first address component
    containing the requested Google address type.
    """

    for component in components:
        types = component.get("types", [])

        if component_type in types:
            return component.get("long_name")

    return None


def _extract_area_name(
    components: list[dict[str, Any]],
) -> tuple[str | None, str | None]:
    """
    Select a human-readable local area.

    Priority:
        neighborhood
        sublocality_level_5
        sublocality_level_4
        sublocality_level_3
        sublocality_level_2
        sublocality_level_1
        sublocality
        locality

    Administrative district/state values are intentionally
    NOT used as the primary analysis-area name.
    """

    priority = [
        "neighborhood",
        "sublocality_level_5",
        "sublocality_level_4",
        "sublocality_level_3",
        "sublocality_level_2",
        "sublocality_level_1",
        "sublocality",
        "locality",
    ]

    for component_type in priority:
        value = _extract_component(
            components,
            component_type,
        )

        if value:
            return value, component_type

    return None, None


def reverse_geocode(
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    """
    Reverse geocode a coordinate using Google Geocoding API.
    """

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    if not api_key:
        raise GoogleGeocodingError(
            "GOOGLE_MAPS_API_KEY is not configured."
        )

    params = {
        "latlng": f"{latitude},{longitude}",
        "key": api_key,
        "language": "en",
        "region": "in",
    }

    try:
        with httpx.Client(
            timeout=10.0
        ) as client:
            response = client.get(
                GOOGLE_GEOCODING_URL,
                params=params,
            )
            response.raise_for_status()

    except httpx.HTTPError as exc:
        raise GoogleGeocodingError(
            f"Google Geocoding request failed: {exc}"
        ) from exc

    payload = response.json()

    status = payload.get("status")

    if status != "OK":
        error_message = payload.get(
            "error_message",
            "No additional error information.",
        )

        raise GoogleGeocodingError(
            f"Google Geocoding returned "
            f"{status}: {error_message}"
        )

    results = payload.get("results", [])

    if not results:
        return {
            "name": None,
            "type": None,
            "formatted_address": None,
            "place_id": None,
            "city": None,
            "district": None,
            "state": None,
            "country": None,
        }

    # Google generally returns the most exact result first,
    # but we inspect the address components rather than
    # blindly trusting the first formatted address.
    best_result = results[0]

    components = best_result.get(
        "address_components",
        [],
    )

    area_name, area_type = _extract_area_name(
        components
    )

    return {
        "name": area_name,
        "type": area_type,
        "formatted_address": best_result.get(
            "formatted_address"
        ),
        "place_id": best_result.get(
            "place_id"
        ),
        "city": _extract_component(
            components,
            "locality",
        ),
        "district": _extract_component(
            components,
            "administrative_area_level_2",
        ),
        "state": _extract_component(
            components,
            "administrative_area_level_1",
        ),
        "country": _extract_component(
            components,
            "country",
        ),
        "results_count": len(results),
    }
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

NOMINATIM_USER_AGENT = (
    "HEATSENSE-AI/1.0 "
    "(academic urban heat research)"
)

_NOMINATIM_LAST_REQUEST = 0.0
_NOMINATIM_MIN_INTERVAL = 1.0


def _nominatim_rate_limit() -> None:
    global _NOMINATIM_LAST_REQUEST

    import time

    elapsed = time.monotonic() - _NOMINATIM_LAST_REQUEST

    if elapsed < _NOMINATIM_MIN_INTERVAL:
        time.sleep(
            _NOMINATIM_MIN_INTERVAL - elapsed
        )

    _NOMINATIM_LAST_REQUEST = time.monotonic()


def _extract_nominatim_area_name(
    payload: dict[str, Any],
) -> tuple[str | None, str | None]:
    """
    Extract a human-readable locality suitable for
    displaying as an analysis-area name.

    Administrative units such as county, district,
    state_district, and state are deliberately excluded.

    The result is:
        (name, name_type)
    """

    address = payload.get("address", {})

    priority = [
        "neighbourhood",
        "suburb",
        "quarter",
        "village",
        "town",
        "city_district",
        "municipality",
        "locality",
        "city",
    ]

    for component_type in priority:
        value = address.get(component_type)

        if value:
            return str(value), component_type

    return None, None
def reverse_geocode_polygon(
    geometry: dict[str, Any],
) -> dict[str, Any]:
    """
    Reverse geocode the centroid of an EPSG:4326
    polygon using OpenStreetMap Nominatim.

    This is used as a fallback naming provider.
    PostGIS locality resolution should be preferred
    when a sufficiently close OSM locality candidate exists.
    """

    from shapely.geometry import shape

    polygon = shape(geometry)

    if polygon.is_empty:
        raise ValueError(
            "Polygon geometry is empty."
        )

    if polygon.geom_type != "Polygon":
        raise ValueError(
            "Expected a GeoJSON Polygon geometry."
        )

    if not polygon.is_valid:
        polygon = polygon.buffer(0)

    if polygon.is_empty or not polygon.is_valid:
        raise ValueError(
            "Polygon geometry is invalid."
        )

    centroid = polygon.centroid

    _nominatim_rate_limit()

    try:
        response = httpx.get(
    NOMINATIM_URL,
    params={
        "lat": centroid.y,
        "lon": centroid.x,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 14,
        "layer": "address",
    },
            headers={
                "User-Agent": NOMINATIM_USER_AGENT,
            },
            timeout=15.0,
        )

        response.raise_for_status()

    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Nominatim reverse geocoding failed: {exc}"
        ) from exc

    payload = response.json()

    name, name_type = _extract_nominatim_area_name(
    payload
)

    return {
    "resolved": bool(name),
    "method": "nominatim",
    "name": name,
    "name_type": name_type,
    "display_name": payload.get(
        "display_name"
    ),
    "place_type": payload.get(
        "type"
    ),
    "osm_type": payload.get(
        "osm_type"
    ),
    "osm_id": payload.get(
        "osm_id"
    ),
    "source": "OpenStreetMap Nominatim",
    "latitude": payload.get("lat"),
    "longitude": payload.get("lon"),
}