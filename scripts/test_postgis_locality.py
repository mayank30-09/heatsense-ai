from backend.app.geocoding.postgis_locality import resolve_polygon_locality

geometry = {
    "type": "Polygon",
    "coordinates": [[
        [72.7800, 21.1200],
        [72.7900, 21.1200],
        [72.7900, 21.1300],
        [72.7800, 21.1300],
        [72.7800, 21.1200],
    ]],
}

result = resolve_polygon_locality(geometry)

print("LOCALITY RESOLUTION RESULT")
for key, value in result.items():
    print(f"{key}: {value}")
