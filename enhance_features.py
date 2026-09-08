import json
import math

with open("data/terrain.json", "r", encoding="utf-8") as f:
    terrain = json.load(f)

with open("data/annadel_features.json", "r", encoding="utf-8") as f:
    features = json.load(f)

elev_grid = terrain["elevations"]
res = terrain["grid_res"]

def get_elevation_at_uv(u, v):
    u = max(0.0, min(1.0, u))
    v = max(0.0, min(1.0, v))
    gx = u * (res - 1)
    gy = v * (res - 1)
    x0 = int(math.floor(gx))
    x1 = min(res - 1, x0 + 1)
    y0 = int(math.floor(gy))
    y1 = min(res - 1, y0 + 1)
    dx = gx - x0
    dy = gy - y0
    e00 = elev_grid[y0][x0]
    e10 = elev_grid[y0][x1]
    e01 = elev_grid[y1][x0]
    e11 = elev_grid[y1][x1]
    e_top = e00 * (1 - dx) + e10 * dx
    e_bot = e01 * (1 - dx) + e11 * dx
    return e_top * (1 - dy) + e_bot * dy

# Enhance trails with 3D heights and elevation stats
for tr in features["trails"]:
    min_elev = 99999
    max_elev = -99999
    gain = 0.0
    loss = 0.0
    prev_ele = None

    for line in tr["lines"]:
        for pt in line:
            ele_m = get_elevation_at_uv(pt["u"], pt["v"])
            ele_ft = ele_m * 3.28084
            pt["ele_m"] = round(ele_m, 1)
            pt["ele_ft"] = round(ele_ft, 1)

            if ele_ft < min_elev: min_elev = ele_ft
            if ele_ft > max_elev: max_elev = ele_ft

            if prev_ele is not None:
                diff = ele_ft - prev_ele
                if diff > 0: gain += diff
                else: loss += abs(diff)
            prev_ele = ele_ft

    tr["min_elev_ft"] = round(min_elev)
    tr["max_elev_ft"] = round(max_elev)
    tr["elev_gain_ft"] = round(gain)

# Enhance landmarks
for lm in features["landmarks"]:
    ele_m = get_elevation_at_uv(lm["pos"]["u"], lm["pos"]["v"])
    lm["pos"]["ele_m"] = round(ele_m, 1)
    lm["pos"]["ele_ft"] = round(ele_m * 3.28084, 1)

# Enhance boundary
for pt in features["boundary"]:
    ele_m = get_elevation_at_uv(pt["u"], pt["v"])
    pt["ele_m"] = round(ele_m, 1)
    pt["ele_ft"] = round(ele_m * 3.28084, 1)

# Enhance water bodies
for wb in features["water_bodies"]:
    ele_m = get_elevation_at_uv(wb["center"]["u"], wb["center"]["v"])
    wb["center"]["ele_m"] = round(ele_m, 1)
    wb["center"]["ele_ft"] = round(ele_m * 3.28084, 1)
    for pt in wb["polygon"]:
        e_m = get_elevation_at_uv(pt["u"], pt["v"])
        pt["ele_m"] = round(e_m, 1)
        pt["ele_ft"] = round(e_m * 3.28084, 1)

with open("data/annadel_features.json", "w", encoding="utf-8") as f:
    json.dump(features, f, indent=2)

print("Enhanced features with 3D elevations!")
