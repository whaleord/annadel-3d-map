import json

with open("data/annadel_osm_raw.json", "r", encoding="utf-8") as f:
    osm = json.load(f)

elements = osm.get("elements", [])
print(f"Total elements: {len(elements)}")

named_ways = {}
named_peaks = []
water_features = []
boundaries = []

for el in elements:
    tags = el.get("tags", {})
    name = tags.get("name")
    
    if el.get("type") == "way":
        if "highway" in tags and name:
            if name not in named_ways:
                named_ways[name] = {
                    "count": 0,
                    "highway": tags.get("highway"),
                    "surface": tags.get("surface"),
                    "bicycle": tags.get("bicycle"),
                    "foot": tags.get("foot"),
                    "tags": tags
                }
            named_ways[name]["count"] += 1
            
        if tags.get("natural") == "water" or "water" in tags:
            water_features.append({"id": el.get("id"), "name": name, "tags": tags})
            
    elif el.get("type") == "node":
        if tags.get("natural") == "peak" or tags.get("tourism") in ["viewpoint", "information"]:
            named_peaks.append({"name": name, "lat": el.get("lat"), "lon": el.get("lon"), "tags": tags})

print("\n--- NAMED TRAILS FOUND ---")
for name in sorted(named_ways.keys()):
    print(f"- {name} (segments: {named_ways[name]['count']}, type: {named_ways[name]['highway']})")

print("\n--- WATER FEATURES ---")
for wf in water_features:
    if wf.get("name"):
        print(f"- {wf.get('name')}")

print("\n--- PEAKS & POIS ---")
for p in named_peaks:
    print(f"- {p.get('name')} at ({p.get('lat')}, {p.get('lon')}) [{p.get('tags', {}).get('natural') or p.get('tags', {}).get('tourism')}]")
