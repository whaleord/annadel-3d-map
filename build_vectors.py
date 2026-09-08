import json
import math
import os

LAT_MIN = 38.390
LAT_MAX = 38.460
LON_MIN = -122.670
LON_MAX = -122.570

with open("data/annadel_osm_raw.json", "r", encoding="utf-8") as f:
    osm = json.load(f)

nodes = {}
for el in osm.get("elements", []):
    if el.get("type") == "node":
        nodes[el["id"]] = (el["lat"], el["lon"])

def coord_to_unit(lat, lon):
    # Normalized between -1 and 1
    # u in [0, 1] from west to east
    u = (lon - LON_MIN) / (LON_MAX - LON_MIN)
    # v in [0, 1] from north to south
    v = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN)
    # in 3D centered at 0, world size = 100
    x = (u - 0.5) * 100.0
    z = (v - 0.5) * 100.0
    return {"u": round(u, 5), "v": round(v, 5), "x": round(x, 2), "z": round(z, 2), "lat": round(lat, 6), "lon": round(lon, 6)}

# 1. Official Trails
OFFICIAL_TRAILS_DEF = {
    "Canyon Trail": {"type": "fire_road", "desc": "Wide central artery connecting Spring Lake to Lake Ilsanjo", "diff": "Moderate"},
    "Channel Trail": {"type": "singletrack", "desc": "Follows Channel Drive along the park's northern border", "diff": "Easy"},
    "Cobblestone Trail": {"type": "rocky_singletrack", "desc": "Iconic technical trail with ancient volcanic cobblestones", "diff": "Challenging"},
    "Cobblestone Bypass": {"type": "connector", "desc": "Smoother connector avoiding the roughest cobblestones", "diff": "Moderate"},
    "Lake Trail": {"type": "singletrack", "desc": "Picturesque path circling the perimeter of Lake Ilsanjo", "diff": "Easy to Moderate"},
    "Lawndale Trail": {"type": "fire_road", "desc": "Long steady climb from Lawndale Road up toward Ledson Marsh", "diff": "Moderate"},
    "Live Oak Trail": {"type": "singletrack", "desc": "Shaded oak woodland trail winding south of Lake Ilsanjo", "diff": "Moderate"},
    "Louis Trail": {"type": "singletrack", "desc": "Rolling singletrack through oak grassland and chaparral", "diff": "Moderate"},
    "Louis Connector": {"type": "connector", "desc": "Short connector linking Louis Trail to Warren Richardson", "diff": "Easy"},
    "Marsh Trail": {"type": "fire_road", "desc": "Panoramic high-elevation spine trail connecting Lake Ilsanjo to Ledson Marsh", "diff": "Moderate"},
    "North Burma Trail": {"type": "singletrack", "desc": "Thrilling technical descent/ascent through Douglas firs", "diff": "Challenging"},
    "South Burma Trail": {"type": "singletrack", "desc": "Flowing singletrack connecting Marsh Trail down to Richardson", "diff": "Challenging"},
    "Orchard Trail": {"type": "singletrack", "desc": "Passes through historical fruit orchards near Cobblestone", "diff": "Moderate"},
    "Orchard Loop": {"type": "singletrack", "desc": "Scenic loop branch of the Orchard Trail", "diff": "Moderate"},
    "Orchard Loop Connector": {"type": "connector", "desc": "Branch linking Orchard to Cobblestone", "diff": "Easy"},
    "Ridge Trail": {"type": "singletrack", "desc": "High ridgeline path along the southern park crest with expansive valley views", "diff": "Challenging"},
    "Ridge Marsh Connector": {"type": "connector", "desc": "Links the southern Ridge Trail to Marsh Trail", "diff": "Moderate"},
    "Rough Go Trail": {"type": "rocky_singletrack", "desc": "Famous technical trail loaded with volcanic rock gardens and slabs", "diff": "Expert / Strenuous"},
    "Schultz Trail": {"type": "singletrack", "desc": "Scenic singletrack through oak groves connecting south to Lawndale", "diff": "Moderate to Challenging"},
    "Spring Creek Trail": {"type": "singletrack", "desc": "Follows the riparian corridor of Spring Creek under redwood & bay canopies", "diff": "Moderate"},
    "Steve's \"S\" Trail": {"type": "singletrack", "desc": "Tight switchbacking trail climbing to the Richardson ridge", "diff": "Moderate"},
    "Two Quarry Trail": {"type": "fire_road", "desc": "Historic route passing stone quarries used for San Francisco paving stones", "diff": "Moderate"},
    "Warren Richardson Trail": {"type": "fire_road", "desc": "Main trunk fire road from Channel Drive to Lake Ilsanjo", "diff": "Moderate"},
    "Bennett Peak Trail": {"type": "singletrack", "desc": "Steep trail climbing up to the summit of Bennett Mountain (1,887 ft)", "diff": "Strenuous"},
    "Violetti Fire Road": {"type": "fire_road", "desc": "Access road leading from Violetti Road trailhead to park interior", "diff": "Moderate"},
    "Pig Flat Trail": {"type": "singletrack", "desc": "Scenic meadows and plateau trail north of Bennett Mountain", "diff": "Easy to Moderate"},
    "Cooper Ridge Trail": {"type": "singletrack", "desc": "Connecting ridge path with panoramic vistas over Sonoma Valley", "diff": "Moderate"},
}

NAME_ALIASES = {
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
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

processed_trails = {}

for el in osm.get("elements", []):
    if el.get("type") == "way":
        tags = el.get("tags", {})
        raw_name = tags.get("name", "").strip()
        if raw_name in NAME_ALIASES:
            canon = NAME_ALIASES[raw_name]
            way_nodes = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]
            if len(way_nodes) >= 2:
                if canon not in processed_trails:
                    info = OFFICIAL_TRAILS_DEF.get(canon, {})
                    processed_trails[canon] = {
                        "name": canon,
                        "type": info.get("type", "trail"),
                        "description": info.get("desc", ""),
                        "difficulty": info.get("diff", "Moderate"),
                        "total_meters": 0.0,
                        "lines": []
                    }
                coords = [coord_to_unit(pt[0], pt[1]) for pt in way_nodes]
                processed_trails[canon]["lines"].append(coords)
                for i in range(len(way_nodes) - 1):
                    processed_trails[canon]["total_meters"] += haversine(
                        way_nodes[i][0], way_nodes[i][1],
                        way_nodes[i+1][0], way_nodes[i+1][1]
                    )

trails_list = []
for name, tdata in sorted(processed_trails.items()):
    tdata["miles"] = round(tdata["total_meters"] / 1609.34, 2)
    tdata["km"] = round(tdata["total_meters"] / 1000.0, 2)
    # Compute midpoint / label position
    all_pts = [pt for line in tdata["lines"] for pt in line]
    if all_pts:
        mid_pt = all_pts[len(all_pts) // 2]
        tdata["label_pos"] = mid_pt
    trails_list.append(tdata)

# 2. Water Bodies
water_bodies = []

# Lake Ilsanjo
lake_ilsanjo_nodes = []
for el in osm.get("elements", []):
    if el.get("type") == "way" and el.get("id") == 28639795:
        lake_ilsanjo_nodes = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]

if lake_ilsanjo_nodes:
    coords = [coord_to_unit(pt[0], pt[1]) for pt in lake_ilsanjo_nodes]
    avg_lat = sum(pt[0] for pt in lake_ilsanjo_nodes) / len(lake_ilsanjo_nodes)
    avg_lon = sum(pt[1] for pt in lake_ilsanjo_nodes) / len(lake_ilsanjo_nodes)
    water_bodies.append({
        "name": "Lake Ilsanjo",
        "type": "lake",
        "elevation_ft": 650,
        "elevation_m": 198,
        "desc": "A 26-acre man-made lake constructed in the 1950s, the scenic heart of Annadel popular for fishing (bluegill, black bass) and trail junctions.",
        "polygon": coords,
        "center": coord_to_unit(avg_lat, avg_lon)
    })

# Ledson Marsh
ledson_node_ids = [314786982, 314786983, 314786984, 314786985, 314786987, 314786988, 314786989, 314786990, 314786991, 314786992, 314786993, 314786994, 314786995, 314786996, 314786997, 314786998, 314786982]
ledson_pts = [nodes[nid] for nid in ledson_node_ids if nid in nodes]
if not ledson_pts:
    # Approximate Ledson Marsh polygon if specific nodes not in raw extract
    # Center: 38.409006, -122.599360, roughly oval 300m x 150m
    center_lat, center_lon = 38.409006, -122.599360
    ledson_pts = []
    for deg in range(0, 360, 20):
        rad = math.radians(deg)
        d_lat = (150.0 / 111000.0) * math.cos(rad)
        d_lon = (250.0 / (111000.0 * math.cos(math.radians(center_lat)))) * math.sin(rad)
        ledson_pts.append((center_lat + d_lat, center_lon + d_lon))

coords = [coord_to_unit(pt[0], pt[1]) for pt in ledson_pts]
water_bodies.append({
    "name": "Ledson Marsh",
    "type": "marsh",
    "elevation_ft": 1180,
    "elevation_m": 360,
    "desc": "A 30-acre high-elevation seasonal freshwater marsh established in the late 1800s. Critical breeding habitat for the California red-legged frog and western pond turtle.",
    "polygon": coords,
    "center": coord_to_unit(38.409006, -122.599360)
})

# 3. Park Boundary
boundary_nodes = []
for el in osm.get("elements", []):
    if el.get("type") == "way" and el.get("id") == 38197939:
        boundary_nodes = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]

boundary_poly = [coord_to_unit(pt[0], pt[1]) for pt in boundary_nodes]

# 4. Landmarks & Summits
landmarks = [
    {
        "name": "Bennett Mountain Summit",
        "category": "summit",
        "elevation_ft": 1887,
        "elevation_m": 575,
        "desc": "The highest peak in Trione-Annadel State Park, offering commanding 360-degree views across Sonoma Valley, Santa Rosa, and Taylor Mountain.",
        "pos": coord_to_unit(38.412968, -122.623874),
        "icon": "mountain"
    },
    {
        "name": "Lake Ilsanjo",
        "category": "water",
        "elevation_ft": 650,
        "elevation_m": 198,
        "desc": "The centerpiece lake of Annadel, named by combining the names of its original landowners Ilse and Joe.",
        "pos": coord_to_unit(38.4285, -122.6280),
        "icon": "water"
    },
    {
        "name": "Ledson Marsh",
        "category": "wetland",
        "elevation_ft": 1180,
        "elevation_m": 360,
        "desc": "High mountain marshland surrounded by dense mixed evergreen forests.",
        "pos": coord_to_unit(38.4090, -122.5994),
        "icon": "leaf"
    },
    {
        "name": "Warren Richardson Trailhead / Visitor Center",
        "category": "trailhead",
        "elevation_ft": 360,
        "elevation_m": 110,
        "desc": "Main park entrance with parking kiosk, restrooms, and interpretive displays along Channel Drive.",
        "pos": coord_to_unit(38.4533, -122.6468),
        "icon": "parking"
    },
    {
        "name": "Cobblestone Trailhead",
        "category": "trailhead",
        "elevation_ft": 320,
        "elevation_m": 98,
        "desc": "Popular trailhead staging area off Channel Drive providing direct access to the rocky Cobblestone climb.",
        "pos": coord_to_unit(38.4532, -122.6675),
        "icon": "parking"
    },
    {
        "name": "Lawndale Trailhead",
        "category": "trailhead",
        "elevation_ft": 450,
        "elevation_m": 137,
        "desc": "Southeastern park staging area on Lawndale Road, ideal for climbs toward Ledson Marsh.",
        "pos": coord_to_unit(38.4089, -122.5967),
        "icon": "parking"
    },
    {
        "name": "Schultz Trailhead",
        "category": "trailhead",
        "elevation_ft": 490,
        "elevation_m": 149,
        "desc": "Eastern portal off Schultz Road accessing Ridge and Schultz trails.",
        "pos": coord_to_unit(38.4113, -122.5909),
        "icon": "parking"
    },
    {
        "name": "Spring Lake / Violet Horner Connector",
        "category": "park_connector",
        "elevation_ft": 330,
        "elevation_m": 100,
        "desc": "Pedestrian and equestrian bridge connection to adjacent Spring Lake Regional Park.",
        "pos": coord_to_unit(38.4485, -122.6585),
        "icon": "bridge"
    }
]

output_data = {
    "trails": trails_list,
    "water_bodies": water_bodies,
    "boundary": boundary_poly,
    "landmarks": landmarks
}

with open("data/annadel_features.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2)

print(f"Features saved to data/annadel_features.json:")
print(f"  Trails: {len(trails_list)}")
print(f"  Water Bodies: {len(water_bodies)}")
print(f"  Boundary points: {len(boundary_poly)}")
print(f"  Landmarks: {len(landmarks)}")
