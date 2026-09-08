import json
import math
import numpy as np
from PIL import Image

# Load satellite image
sat_img = Image.open("assets/satellite.jpg").convert("RGB")
sw, sh = sat_img.size
sat_np = np.array(sat_img, dtype=np.float32)

# Load terrain and features
with open("data/terrain.json", "r") as f:
    terrain = json.load(f)
with open("data/annadel_features.json", "r") as f:
    features = json.load(f)

# Compute Greenness Index: Excess Green (2*G - R - B)
r = sat_np[:, :, 0]
g = sat_np[:, :, 1]
b = sat_np[:, :, 2]
exg = 2 * g - r - b
brightness = (r + g + b) / 3.0

print(f"Satellite size: {sw}x{sh}")
print(f"ExG min: {exg.min():.1f}, max: {exg.max():.1f}, mean: {exg.mean():.1f}")

# Water bodies mask
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

# Precompute trail line segments to enforce trail clearance
trail_segs = []
for tr in features["trails"]:
    for line in tr["lines"]:
        for i in range(len(line) - 1):
            trail_segs.append((line[i]["u"], line[i]["v"], line[i+1]["u"], line[i+1]["v"]))

print(f"Trail segments for clearance check: {len(trail_segs)}")

def dist_to_segment(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)

# Sample candidate trees
np.random.seed(42)
N_CANDIDATES = 60000
trees = []

MAP_WIDTH = 100.0
MAP_DEPTH = 89.1

# Clearance in UV units (approx 20 meters ground distance)
TRAIL_CLEARANCE_UV = 0.0035

for _ in range(N_CANDIDATES):
    u = np.random.uniform(0.02, 0.98)
    v = np.random.uniform(0.02, 0.98)
    
    px = int(u * (sw - 1))
    py_img = int(v * (sh - 1))
    
    val_exg = exg[py_img, px]
    val_bright = brightness[py_img, px]
    
    # Trees grow where foliage is green (ExG > -5 and not super bright bleached rock or dark water)
    if val_exg < -8.0 or val_bright > 220 or val_bright < 20:
        continue
        
    # Check water bodies
    in_water = False
    for poly in water_polys:
        if point_in_poly(u, v, poly):
            in_water = True
            break
    if in_water:
        continue
        
    # Quick trail clearance check
    near_trail = False
    for seg in trail_segs:
        # Bounding box check first for speed
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

    # Tree type based on shade and location
    # Darker greens & sheltered north-facing slopes (lower v) -> Fir (type 0)
    # Lighter olive greens & open hills -> Oak (type 1)
    is_fir = (val_bright < 110 and val_exg > 0) or (v < 0.45 and val_exg > 5)
    tree_type = 0 if is_fir else 1
    
    # Height scale
    scale = round(float(np.random.uniform(0.8, 1.35)), 2)
    
    # 3D X and Z
    x = round(float((u - 0.5) * MAP_WIDTH), 2)
    z = round(float((v - 0.5) * MAP_DEPTH), 2)
    
    trees.append({
        "x": x,
        "z": z,
        "u": round(float(u), 4),
        "v": round(float(v), 4),
        "t": tree_type,
        "s": scale
    })
    
    if len(trees) >= 16000:
        break

print(f"Total valid trees generated: {len(trees)}")
fir_count = sum(1 for t in trees if t["t"] == 0)
oak_count = sum(1 for t in trees if t["t"] == 1)
print(f"  Douglas Firs / Conifers : {fir_count}")
print(f"  Coast Live Oaks / Madrone: {oak_count}")

with open("data/annadel_trees.json", "w", encoding="utf-8") as f:
    json.dump(trees, f)
print("Saved data/annadel_trees.json!")
