import json
import math
import numpy as np
from PIL import Image

print("Loading LiDAR Canopy Height Model & Official Sonoma VegMap Alliances...", flush=True)
chm = np.load("data/lidar_chm_1024.npy")
veg = np.load("data/annadel_vegmap_alliances.npy")
sh, sw = chm.shape

# Satellite orthoimagery for spectral brightness
sat_img = Image.open("assets/satellite.jpg").convert("RGB").resize((sw, sh))
sat_np = np.array(sat_img, dtype=np.float32)
brightness = (sat_np[:, :, 0] + sat_np[:, :, 1] + sat_np[:, :, 2]) / 3.0

# Load features for clearance and boundary
with open("data/annadel_features.json", "r", encoding="utf-8") as f:
    features = json.load(f)

# Water polygons (UV coordinates)
water_polys = []
for wb in features["water_bodies"]:
    pts = [(p["u"], p["v"]) for p in wb["polygon"]]
    water_polys.append(pts)

def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        p1x, p1y = poly[i]
        p2x, p2y = poly[(i + 1) % n]
        if min(p1y, p2y) < y <= max(p1y, p2y):
            if x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
    return inside

# Trail segments (UV coordinates)
trail_segs = []
for tr in features["trails"]:
    for line in tr["lines"]:
        for i in range(len(line) - 1):
            trail_segs.append((line[i]["u"], line[i]["v"], line[i+1]["u"], line[i+1]["v"]))

def dist_to_segment(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)

# Local maxima detection on CHM
print("Detecting individual tree crowns via local maxima...", flush=True)
pad = 2 # 5x5 window
padded = np.pad(chm, pad, mode='constant', constant_values=0)
is_max = np.ones_like(chm, dtype=bool)

for dy in range(-pad, pad + 1):
    for dx in range(-pad, pad + 1):
        if dy == 0 and dx == 0:
            continue
        neighbor = padded[pad + dy : pad + dy + sh, pad + dx : pad + dx + sw]
        is_max &= (chm >= neighbor)

# Min height filter: 16 feet (5 meters) to exclude small bushes and ground brush
candidate_mask = is_max & (chm >= 16.0)
y_indices, x_indices = np.where(candidate_mask)
print(f"Candidate tree crown peaks detected: {len(y_indices)}", flush=True)

MAP_WIDTH = 100.0
MAP_DEPTH = 89.1
TRAIL_CLEARANCE_UV = 0.0028 # approx 16m clearance from trail center

trees = []
alliance_counts = {"conifer_groundtruth": 0, "oak_groundtruth": 0, "model_conifer": 0, "model_oak": 0}

for idx in range(len(y_indices)):
    py = int(y_indices[idx])
    px = int(x_indices[idx])
    height_ft = float(chm[py, px])
    alliance_code = int(veg[py, px])
    br = float(brightness[py, px])
    
    u = px / (sw - 1.0)
    v = py / (sh - 1.0)
    
    # Check edges
    if u < 0.015 or u > 0.985 or v < 0.015 or v > 0.985:
        continue
        
    # Check water bodies
    in_water = False
    for poly in water_polys:
        if point_in_poly(u, v, poly):
            in_water = True
            break
    if in_water:
        continue
        
    # Check trail clearance
    near_trail = False
    for seg in trail_segs:
        min_u = min(seg[0], seg[2]) - TRAIL_CLEARANCE_UV
        max_u = max(seg[0], seg[2]) + TRAIL_CLEARANCE_UV
        min_v = min(seg[1], seg[3]) - TRAIL_CLEARANCE_UV
        max_v = max(seg[1], seg[3]) + TRAIL_CLEARANCE_UV
        if min_u <= u <= max_u and min_v <= v <= max_v:
            if dist_to_segment(u, v, seg[0], seg[1], seg[2], seg[3]) < TRAIL_CLEARANCE_UV:
                near_trail = True
                break
    if near_trail:
        continue

    # Multi-variable Ecological & Botanical Classification:
    # 1. Ground truth alliance if mapped
    if alliance_code == 1:
        # Verified Douglas Fir / Redwood Alliance
        tree_type = 0
        alliance_counts["conifer_groundtruth"] += 1
    elif alliance_code == 2:
        # Verified Coast Live Oak / Hardwood Alliance
        tree_type = 1
        alliance_counts["oak_groundtruth"] += 1
    else:
        # 2. Transition / unmapped edge: Fusion of LiDAR height & spectral darkness
        if height_ft >= 68.0:
            tree_type = 0
            alliance_counts["model_conifer"] += 1
        elif height_ft >= 38.0 and br < 65.0:
            # Dark evergreen needle canopy signature
            tree_type = 0
            alliance_counts["model_conifer"] += 1
        else:
            tree_type = 1
            alliance_counts["model_oak"] += 1
    
    # 3D scale proportional to surveyed LiDAR height
    if tree_type == 0:
        scale = round(float(np.clip(height_ft / 85.0, 0.75, 1.85)), 2)
    else:
        scale = round(float(np.clip(height_ft / 42.0, 0.60, 1.45)), 2)
        
    x = round(float((u - 0.5) * MAP_WIDTH), 2)
    z = round(float((v - 0.5) * MAP_DEPTH), 2)
    
    trees.append({
        "x": x,
        "z": z,
        "u": round(float(u), 4),
        "v": round(float(v), 4),
        "t": tree_type,
        "h": round(height_ft, 1), # Exact surveyed LiDAR height in feet!
        "s": scale
    })

print(f"Total LiDAR trees placed: {len(trees)}", flush=True)
fir_count = sum(1 for t in trees if t["t"] == 0)
oak_count = sum(1 for t in trees if t["t"] == 1)
print(f"  Douglas Firs / Conifers: {fir_count} ({(fir_count/len(trees))*100:.1f}%)")
print(f"    - Official VegMap Ground Truth: {alliance_counts['conifer_groundtruth']}")
print(f"    - Spectral + LiDAR Height Modeled: {alliance_counts['model_conifer']}")
print(f"  Coast Live Oaks / Hardwoods: {oak_count} ({(oak_count/len(trees))*100:.1f}%)")
print(f"    - Official VegMap Ground Truth: {alliance_counts['oak_groundtruth']}")
print(f"    - Spectral + LiDAR Height Modeled: {alliance_counts['model_oak']}")

h_vals = [t["h"] for t in trees]
print(f"  Height stats: min={min(h_vals):.1f} ft, median={np.median(h_vals):.1f} ft, max={max(h_vals):.1f} ft", flush=True)

with open("data/annadel_trees.json", "w", encoding="utf-8") as f:
    json.dump(trees, f)
print("Saved updated data/annadel_trees.json!", flush=True)
