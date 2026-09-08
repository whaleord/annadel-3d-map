import json

with open("data/annadel_osm_raw.json", "r", encoding="utf-8") as f:
    osm = json.load(f)

way_ids = {el.get("id"): el for el in osm.get("elements", []) if el.get("type") == "way"}
print("Has Ledson Marsh 28640623?", 28640623 in way_ids)
print("Has Outer Boundary 38197939?", 38197939 in way_ids)
print("Has Lake Ilsanjo 28639795?", 28639795 in way_ids)
