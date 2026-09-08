import json

with open('data/terrain.json', 'r', encoding='utf-8') as f:
    t = json.load(f)
with open('data/annadel_features.json', 'r', encoding='utf-8') as f:
    feat = json.load(f)

print('=== TERRAIN ELEVATION AUDIT ===')
print(f"Grid Resolution: {t['grid_res']} x {t['grid_res']} samples")
print(f"Elevation Min  : {t['min_elevation_ft']} ft ({t['min_elevation_m']} m)")
print(f"Elevation Max  : {t['max_elevation_ft']} ft ({t['max_elevation_m']} m)")

print('\n=== OFFICIAL TRAILS AUDIT (27 Named Routes) ===')
total_miles = sum(tr['miles'] for tr in feat['trails'])
for tr in sorted(feat['trails'], key=lambda x: x['miles'], reverse=True):
    print(f"- {tr['name']:26s} | {tr['miles']:4.2f} mi ({tr['km']:4.2f} km) | Gain: +{tr['elev_gain_ft']:4d} ft | Span: {tr['min_elev_ft']}'-{tr['max_elev_ft']}' | {tr['difficulty']}")
print(f"\nTotal Official Park Trail Mileage: {total_miles:.2f} miles")

print('\n=== WATER BODIES AUDIT ===')
for wb in feat['water_bodies']:
    print(f"- {wb['name']:20s} | {wb['type']:6s} | Elevation: {wb['elevation_ft']} ft | Vertices: {len(wb['polygon'])}")

print('\n=== LANDMARKS AUDIT ===')
for lm in feat['landmarks']:
    print(f"- {lm['name']:42s} | {lm['elevation_ft']:4d} ft | Category: {lm['category']}")
