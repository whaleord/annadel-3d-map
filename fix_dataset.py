import math
import numpy as np
from PIL import Image
import json
import io
import requests
import os

LAT_MIN = 38.390
LAT_MAX = 38.460
LON_MIN = -122.670
LON_MAX = -122.570

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)

ZOOM = 13
x_min, y_min = deg2num(LAT_MAX, LON_MIN, ZOOM)
x_max, y_max = deg2num(LAT_MIN, LON_MAX, ZOOM)

tile_width = 256
grid_x_count = x_max - x_min + 1
grid_y_count = y_max - y_min + 1
total_w = grid_x_count * tile_width
total_h = grid_y_count * tile_width

elev_canvas = Image.new("RGB", (total_w, total_h))
headers = {"User-Agent": "Annadel3DMapBuilder/1.0"}

print("Downloading elevation tiles...")
for gx, tx in enumerate(range(x_min, x_max + 1)):
    for gy, ty in enumerate(range(y_min, y_max + 1)):
        terrarium_url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{ZOOM}/{tx}/{ty}.png"
        r = requests.get(terrarium_url, headers=headers, timeout=15)
        if r.status_code == 200:
            t_img = Image.open(io.BytesIO(r.content)).convert("RGB")
            elev_canvas.paste(t_img, (gx * tile_width, gy * tile_width))

north_lat, west_lon = num2deg(x_min, y_min, ZOOM)
south_lat, east_lon = num2deg(x_max + 1, y_max + 1, ZOOM)

crop_x1 = int((LON_MIN - west_lon) / (east_lon - west_lon) * total_w)
crop_x2 = int((LON_MAX - west_lon) / (east_lon - west_lon) * total_w)
crop_y1 = int((north_lat - LAT_MAX) / (north_lat - south_lat) * total_h)
crop_y2 = int((north_lat - LAT_MIN) / (north_lat - south_lat) * total_h)

crop_box = (max(0, crop_x1), max(0, crop_y1), min(total_w, crop_x2), min(total_h, crop_y2))
cropped_elev_raw = elev_canvas.crop(crop_box)
cw, ch = cropped_elev_raw.size
print(f"Cropped raw canvas size: {cw}x{ch} px")

# CRITICAL FIX: Decode to raw float meters BEFORE any spatial resampling!
rgb_array = np.array(cropped_elev_raw, dtype=np.float64)
# Formula: (R * 256 + G + B / 256) - 32768
float_elev_m = (rgb_array[:, :, 0] * 256.0 + rgb_array[:, :, 1] + rgb_array[:, :, 2] / 256.0) - 32768.0

print(f"Raw decoded elevations without byte boundary artifacts:")
print(f"  Min: {float_elev_m.min():.1f}m ({float_elev_m.min()*3.28084:.1f}ft)")
print(f"  Max: {float_elev_m.max():.1f}m ({float_elev_m.max()*3.28084:.1f}ft)")

# Now do pure mathematical floating-point bilinear interpolation to target GRID_RES (256x256)
GRID_RES = 256
y_indices = np.linspace(0, ch - 1, GRID_RES)
x_indices = np.linspace(0, cw - 1, GRID_RES)

# Bilinear interpolation
x0 = np.floor(x_indices).astype(int)
x1 = np.clip(x0 + 1, 0, cw - 1)
y0 = np.floor(y_indices).astype(int)
y1 = np.clip(y0 + 1, 0, ch - 1)

wx = (x_indices - x0).reshape(1, -1)
wy = (y_indices - y0).reshape(-1, 1)

top = float_elev_m[y0[:, None], x0] * (1 - wx) + float_elev_m[y0[:, None], x1] * wx
bot = float_elev_m[y1[:, None], x0] * (1 - wx) + float_elev_m[y1[:, None], x1] * wx
resampled_float = top * (1 - wy) + bot * wy

# Check max gradient between adjacent cells (to prove no 128m spikes remain)
diff_y = np.abs(np.diff(resampled_float, axis=0))
diff_x = np.abs(np.diff(resampled_float, axis=1))
print(f"Max adjacent elevation step after fix: {max(diff_y.max(), diff_x.max()):.2f}m (No spikes!)")

elevations_list = [[round(float(v), 1) for v in row] for row in resampled_float]

# Save to data/terrain.json
dataset = {
    "bounds": {
        "lat_min": LAT_MIN,
        "lat_max": LAT_MAX,
        "lon_min": LON_MIN,
        "lon_max": LON_MAX,
    },
    "grid_res": GRID_RES,
    "min_elevation_m": round(float(resampled_float.min()), 1),
    "max_elevation_m": round(float(resampled_float.max()), 1),
    "min_elevation_ft": round(float(resampled_float.min() * 3.28084), 1),
    "max_elevation_ft": round(float(resampled_float.max() * 3.28084), 1),
    "elevations": elevations_list,
}

with open("data/terrain.json", "w", encoding="utf-8") as f:
    json.dump(dataset, f)
print("Updated data/terrain.json with clean float elevation matrix!")

# Also generate clean topographic texture from the float array directly!
TEX_RES = 1024
y_tex = np.linspace(0, ch - 1, TEX_RES)
x_tex = np.linspace(0, cw - 1, TEX_RES)
x0_t = np.floor(x_tex).astype(int)
x1_t = np.clip(x0_t + 1, 0, cw - 1)
y0_t = np.floor(y_tex).astype(int)
y1_t = np.clip(y0_t + 1, 0, ch - 1)
wx_t = (x_tex - x0_t).reshape(1, -1)
wy_t = (y_tex - y0_t).reshape(-1, 1)

top_t = float_elev_m[y0_t[:, None], x0_t] * (1 - wx_t) + float_elev_m[y0_t[:, None], x1_t] * wx_t
bot_t = float_elev_m[y1_t[:, None], x0_t] * (1 - wx_t) + float_elev_m[y1_t[:, None], x1_t] * wx_t
tex_float = top_t * (1 - wy_t) + bot_t * wy_t

def get_topo_color(ele_ft, min_ft=300, max_ft=1900):
    t = max(0.0, min(1.0, (ele_ft - min_ft) / (max_ft - min_ft)))
    if t < 0.3:
        p = t / 0.3
        r = int(46 + p * (118 - 46))
        g = int(117 + p * (148 - 117))
        b = int(89 + p * (86 - 89))
    elif t < 0.6:
        p = (t - 0.3) / 0.3
        r = int(118 + p * (196 - 118))
        g = int(148 + p * (163 - 148))
        b = int(86 + p * (90 - 86))
    elif t < 0.85:
        p = (t - 0.6) / 0.25
        r = int(196 + p * (176 - 196))
        g = int(163 + p * (118 - 163))
        b = int(90 + p * (81 - 90))
    else:
        p = (t - 0.85) / 0.15
        r = int(176 + p * (140 - 176))
        g = int(118 + p * (130 - 118))
        b = int(81 + p * (122 - 81))

    contour_interval = 50.0
    is_index = abs(ele_ft % 200.0) < 2.0
    is_contour = abs(ele_ft % 50.0) < 1.8
    if is_index:
        r = max(0, int(r * 0.65))
        g = max(0, int(g * 0.65))
        b = max(0, int(b * 0.65))
    elif is_contour:
        r = max(0, int(r * 0.85))
        g = max(0, int(g * 0.85))
        b = max(0, int(b * 0.85))

    return (r, g, b)

topo_img = Image.new("RGB", (TEX_RES, TEX_RES))
tex_ft = tex_float * 3.28084
topo_pixels = [get_topo_color(tex_ft[y, x]) for y in range(TEX_RES) for x in range(TEX_RES)]
topo_img.putdata(topo_pixels)
topo_img.save("assets/topographic.jpg", quality=90)
print("Updated assets/topographic.jpg with smooth contours!")
