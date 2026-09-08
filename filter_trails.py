import json
import math

with open("data/annadel_osm_raw.json", "r", encoding="utf-8") as f:
    osm = json.load(f)

# Build node dict
nodes = {}
for el in osm.get("elements", []):
    if el.get("type") == "node":
        nodes[el["id"]] = (el["lat"], el["lon"])

# Canonical list of official park trails on state park brochure
OFFICIAL_TRAIL_NAMES = {
    "Canyon Trail": "Canyon Trail",
    "Channel Trail": "Channel Trail",
    "Cobblestone Trail": "Cobblestone Trail",
    "Cobblestone Bypass": "Cobblestone Bypass",
    "Lake Trail": "Lake Trail",
    "Lawndale Trail": "Lawndale Trail",
    "Live Oak Trail": "Live Oak Trail",
    "Louis Trail": "Louis Trail",
    "Louis Connector": "Louis Connector",
    "Marsh Trail": "Marsh Trail",
    "North Burma Trail": "North Burma Trail",
    "South Burma": "South Burma Trail",
    "South Burma Trail": "South Burma Trail",
    "Orchard Trail": "Orchard Trail",
    "Orchard Loop": "Orchard Loop",
    "Orchard Loop Connector": "Orchard Loop Connector",
    "Ridge Trail": "Ridge Trail",
    "Ridge Marsh Connector": "Ridge Marsh Connector",
    "Rough-Go Trail": "Rough Go Trail",
    "Rough Go Trail": "Rough Go Trail",
    "Schultz Trail": "Schultz Trail",
    "Spring Creek Trail": "Spring Creek Trail",
    "Steve's \"S\" Trail": "Steve's \"S\" Trail",
    "Two Quarry Trail": "Two Quarry Trail",
    "Warren Richardson Trail": "Warren Richardson Trail",
    "Bennett Peak Trail": "Bennett Peak Trail",
    "Violetti Fire Road": "Violetti Fire Road",
    "Pig Flat Trail": "Pig Flat Trail",
    "Cooper Ridge Trail": "Cooper Ridge Trail",
}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

official_trails = {}

for el in osm.get("elements", []):
    if el.get("type") == "way":
        tags = el.get("tags", {})
        raw_name = tags.get("name", "").strip()
        if raw_name in OFFICIAL_TRAIL_NAMES:
            canon_name = OFFICIAL_TRAIL_NAMES[raw_name]
            way_nodes = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]
            if len(way_nodes) >= 2:
                if canon_name not in official_trails:
                    official_trails[canon_name] = {
                        "name": canon_name,
                        "segments": [],
                        "surface": tags.get("surface", "dirt"),
                        "bicycle": tags.get("bicycle", "yes"),
                        "total_meters": 0.0
                    }
                official_trails[canon_name]["segments"].append(way_nodes)
                for i in range(len(way_nodes) - 1):
                    official_trails[canon_name]["total_meters"] += haversine(
                        way_nodes[i][0], way_nodes[i][1],
                        way_nodes[i+1][0], way_nodes[i+1][1]
                    )

print(f"Total Official Trails Extracted: {len(official_trails)}")
for name, tr in sorted(official_trails.items()):
    miles = tr["total_meters"] / 1609.34
    print(f"- {name:26s}: {miles:4.2f} miles ({len(tr['segments'])} segments)")
