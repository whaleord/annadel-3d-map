import json

with open("data/annadel_osm_raw.json", "r", encoding="utf-8") as f:
    osm = json.load(f)

print(f"Total elements in osm_raw: {len(osm.get('elements', []))}")

# Check for all relations and their names
for el in osm.get("elements", []):
    tags = el.get("tags", {})
    if el.get("type") == "relation":
        print("RELATION:", el.get("id"), tags.get("name"), tags.get("boundary"), tags.get("leisure"), tags.get("natural"))
    if "marsh" in str(tags).lower() or "ledson" in str(tags).lower():
        print("MATCH MARSH/LEDSON:", el.get("type"), el.get("id"), tags)
