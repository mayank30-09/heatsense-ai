import psycopg
import json

conn = psycopg.connect('host=127.0.0.1 port=5433 dbname=heatsense user=heatsense password=mAyanklb07')
cur = conn.cursor()

# Get top 10 hotspots from Summer 2026
cur.execute('''
SELECT o.pixel_id, c.latitude, c.longitude, o.observed_lst_c, o.ndbi, o.ndvi
FROM stage_c_grid_observations o
JOIN stage_c_grid_cells c ON o.pixel_id = c.pixel_id
WHERE o.year = 2026 AND o.season = 'summer'
ORDER BY o.observed_lst_c DESC
LIMIT 10
''')
top10 = cur.fetchall()

results = []
query_str = '''
SELECT name, place_type, candidate_class,
       ST_Distance(geometry::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) as dist_m
FROM osm_places
ORDER BY dist_m ASC
LIMIT 3
'''

for r in top10:
    pid, lat, lon, lst, ndbi, ndvi = r
    cur.execute(query_str, (lon, lat))
    places = cur.fetchall()
    results.append({
        'pixel_id': pid,
        'latitude': round(lat, 4),
        'longitude': round(lon, 4),
        'lst_c': round(lst, 2),
        'ndbi': round(ndbi, 3),
        'ndvi': round(ndvi, 3),
        'nearest_osm_places': [
            {'name': p[0], 'place_type': p[1], 'candidate_class': p[2], 'distance_m': round(p[3], 1)}
            for p in places
        ]
    })

output = {
    'database_table_queried': 'osm_places',
    'query_sql': "SELECT name, place_type, candidate_class, ST_Distance(geometry::geography, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography) as dist_m FROM osm_places ORDER BY dist_m ASC LIMIT 3;",
    'data_source': 'OpenStreetMap (OSM) administrative and locality nodes/polygons loaded into PostGIS osm_places',
    'description': 'Nearest named OSM features to top 10 thermal hotspots in Surat (Summer 2026)',
    'top_10_hotspots': results
}

with open('docs/validation/osm_query_log.json', 'w') as f:
    json.dump(output, f, indent=2)

print('Saved docs/validation/osm_query_log.json')
for res in results:
    p = res['nearest_osm_places'][0]
    print(f"{res['pixel_id']}: LST={res['lst_c']}C, Nearest: {p['name']} ({p['place_type']}, dist={p['distance_m']}m)")
