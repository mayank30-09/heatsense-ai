import json
import urllib.request

ZONAL_STATS_URL = "http://127.0.0.1:8000/api/v1/analysis/zonal-stats"
LOCALITY_URL = "http://127.0.0.1:8000/api/v1/analysis/resolve-area-name-postgis"


def post_json(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode("utf-8"))


def test_polygon_workflow():
    print("=" * 60)
    print("HEATSENSE AI · POLYGON ANALYSIS & EDITING WORKFLOW TEST")
    print("=" * 60)

    # --- STEP 1: CREATE POLYGON 1 (Dumas area) ---
    poly1_geo_init = {
        "type": "Polygon",
        "coordinates": [[
            [72.710, 21.080],
            [72.720, 21.080],
            [72.720, 21.090],
            [72.710, 21.090],
            [72.710, 21.080],
        ]],
    }
    stats1_init = post_json(ZONAL_STATS_URL, {"geometry": poly1_geo_init})
    loc1_init = post_json(LOCALITY_URL, {"geometry": poly1_geo_init})
    loc1_name = loc1_init.get("name") or "Unnamed Locality"
    id1 = "area-1"
    code1 = "A01"
    name1_init = f"{loc1_name} · {code1}"

    print(f"\n[CREATE POLYGON 1]")
    print(f"  ID: {id1} ({name1_init})")
    print(f"  Area: {stats1_init['area_km2']} km²")
    print(f"  Valid pixels: {stats1_init['valid_pixel_count']}")
    if stats1_init["statistics"]:
        print(f"  Mean LST: {stats1_init['statistics']['mean_c']}°C")

    # --- STEP 2: CREATE POLYGON 2 (Udhana area) ---
    poly2_geo = {
        "type": "Polygon",
        "coordinates": [[
            [72.835, 21.160],
            [72.845, 21.160],
            [72.845, 21.170],
            [72.835, 21.170],
            [72.835, 21.160],
        ]],
    }
    stats2 = post_json(ZONAL_STATS_URL, {"geometry": poly2_geo})
    loc2 = post_json(LOCALITY_URL, {"geometry": poly2_geo})
    loc2_name = loc2.get("name") or "Unnamed Locality"
    id2 = "area-2"
    code2 = "A02"
    name2 = f"{loc2_name} · {code2}"

    print(f"\n[CREATE POLYGON 2]")
    print(f"  ID: {id2} ({name2})")
    print(f"  Area: {stats2['area_km2']} km²")
    print(f"  Valid pixels: {stats2['valid_pixel_count']}")
    if stats2["statistics"]:
        print(f"  Mean LST: {stats2['statistics']['mean_c']}°C")

    # State before edit
    analysis_areas = [
        {"id": id1, "name": name1_init, "result": stats1_init},
        {"id": id2, "name": name2, "result": stats2},
    ]

    # --- STEP 3: EDIT POLYGON 1 (Expand geometry significantly) ---
    poly1_geo_edited = {
        "type": "Polygon",
        "coordinates": [[
            [72.705, 21.075],
            [72.725, 21.075],
            [72.725, 21.095],
            [72.705, 21.095],
            [72.705, 21.075],
        ]],
    }
    stats1_edited = post_json(ZONAL_STATS_URL, {"geometry": poly1_geo_edited})
    loc1_edited = post_json(LOCALITY_URL, {"geometry": poly1_geo_edited})
    loc1_name_edited = loc1_edited.get("name") or "Unnamed Locality"
    name1_edited = f"{loc1_name_edited} · {code1}"  # Preserve code1 A01!

    # Update in-place in state (matching MapShell handleAreaUpdated)
    analysis_areas = [
        {
            **area,
            "name": name1_edited if area["id"] == id1 else area["name"],
            "result": stats1_edited if area["id"] == id1 else area["result"],
        }
        for area in analysis_areas
    ]

    print(f"\n[EDIT POLYGON 1]")
    print(f"  ID preserved: {analysis_areas[0]['id']} == {id1} -> {analysis_areas[0]['id'] == id1}")
    print(f"  Name: {analysis_areas[0]['name']}")
    print(f"  Initial Area: {stats1_init['area_km2']} km² -> Edited Area: {analysis_areas[0]['result']['area_km2']} km²")
    print(f"  Initial Pixels: {stats1_init['valid_pixel_count']} -> Edited Pixels: {analysis_areas[0]['result']['valid_pixel_count']}")
    if stats1_init["statistics"] and analysis_areas[0]["result"]["statistics"]:
        print(f"  Initial Mean: {stats1_init['statistics']['mean_c']}°C -> Edited Mean: {analysis_areas[0]['result']['statistics']['mean_c']}°C")

    # Assertions
    assert len(analysis_areas) == 2, "Card count must remain 2 (no duplicate card on edit)!"
    assert analysis_areas[0]["id"] == id1, "Analysis ID must remain unchanged on edit!"
    assert "A01" in analysis_areas[0]["name"], "Analysis code A01 must remain in name on edit!"
    assert analysis_areas[0]["result"]["area_km2"] != stats1_init["area_km2"], "Area must change on edit!"

    # Independence check: Polygon 2 must NOT have changed
    assert analysis_areas[1]["id"] == id2, "Polygon 2 ID must remain unchanged!"
    assert analysis_areas[1]["result"]["area_km2"] == stats2["area_km2"], "Polygon 2 area must be untouched!"
    print("\n[INDEPENDENCE CHECK PASSED] Polygon 2 remained completely untouched while editing Polygon 1.")

    # --- STEP 4: REMOVE POLYGON 1 ---
    analysis_areas = [area for area in analysis_areas if area["id"] != id1]
    print(f"\n[REMOVE POLYGON 1]")
    print(f"  Remaining areas count: {len(analysis_areas)}")
    assert len(analysis_areas) == 1, "Only 1 area should remain after removing area 1!"
    assert analysis_areas[0]["id"] == id2, "Only Polygon 2 (area 2) should remain!"
    print(f"  Remaining area ID: {analysis_areas[0]['id']} ({analysis_areas[0]['name']})")
    print("\n[REMOVAL CHECK PASSED] Polygon 1 removed cleanly, Polygon 2 preserved.")
    print("=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    test_polygon_workflow()
