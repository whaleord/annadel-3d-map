import json

with open("data/annadel_osm_raw.json", "r", encoding="utf-8") as f:
    osm = json.load(f)

nodes = {}
for el in osm.get("elements", []):
    if el.get("type") == "node":
        nodes[el["id"]] = (el["lat"], el["lon"])

# Find outer boundary way 38197939
boundary_nodes = []
for el in osm.get("elements", []):
    if el.get("type") == "way" and el.get("id") == 38197939:
        boundary_nodes = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]

print(f"Boundary nodes count: {len(boundary_nodes)}")
if boundary_nodes:
    lats = [pt[0] for pt in boundary_nodes]
    lons = [pt[1] for pt in boundary_nodes]
    print(f"Park Bounds:")
    print(f"  Lat Min: {min(lats):.6f}, Max: {max(lats):.6f}")
    print(f"  Lon Min: {min(lons):.6f}, Max: {max(lons):.6f}")
