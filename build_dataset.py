import os
import math
import json
import io
import requests
from PIL import Image, ImageDraw, ImageFont

os.makedirs("assets", exist_ok=True)
os.makedirs("data", exist_ok=True)

# 1. Coordinate Bounds for Trione-Annadel State Park
# Let's set a well-framed bounding box
# LAT: 38.390 to 38.460
# LON: -122.670 to -122.570
LAT_MIN = 38.390
LAT_MAX = 38.460
LON_MIN = -122.670
LON_MAX = -122.570

print(f"Annadel Map Bounding Box:")
print(f"  Lat: {LAT_MIN} to {LAT_MAX}")
print(f"  Lon: {LON_MIN} to {LON_MAX}")

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

# At Zoom 15:
ZOOM = 15
x_min, y_min = deg2num(LAT_MAX, LON_MIN, ZOOM)
x_max, y_max = deg2num(LAT_MIN, LON_MAX, ZOOM)

print(f"Zoom {ZOOM} Tile Range: X=[{x_min}, {x_max}], Y=[{y_min}, {y_max}]")

# Download Terrarium Elevation Tiles and ESRI Satellite Tiles
tile_width = 256
grid_x_count = x_max - x_min + 1
grid_y_count = y_max - y_min + 1
total_w = grid_x_count * tile_width
total_h = grid_y_count * tile_width

print(f"Grid: {grid_x_count}x{grid_y_count} tiles -> Canvas {total_w}x{total_h} px")

elev_canvas = Image.new("RGB", (total_w, total_h))
sat_canvas = Image.new("RGB", (total_w, total_h))

headers = {"User-Agent": "Annadel3DMapBuilder/1.0"}

for gx, tx in enumerate(range(x_min, x_max + 1)):
    for gy, ty in enumerate(range(y_min, y_max + 1)):
        # 1. Terrarium Tile
        terrarium_url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{ZOOM}/{tx}/{ty}.png"
        try:
            r = requests.get(terrarium_url, headers=headers, timeout=15)
            if r.status_code == 200:
                t_img = Image.open(io.BytesIO(r.content)).convert("RGB")
                elev_canvas.paste(t_img, (gx * tile_width, gy * tile_width))
        except Exception as e:
            print(f"Error fetching terrarium {tx},{ty}: {e}")

        # 2. ESRI Satellite Tile
        esri_url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{ZOOM}/{ty}/{tx}"
        try:
            r2 = requests.get(esri_url, headers=headers, timeout=15)
            if r2.status_code == 200:
                s_img = Image.open(io.BytesIO(r2.content)).convert("RGB")
                sat_canvas.paste(s_img, (gx * tile_width, gy * tile_width))
        except Exception as e:
            print(f"Error fetching ESRI {tx},{ty}: {e}")

# Calculate exact geographic bounds of the stitched canvas
north_lat, west_lon = num2deg(x_min, y_min, ZOOM)
south_lat, east_lon = num2deg(x_max + 1, y_max + 1, ZOOM)

print(f"Stitched Tile Canvas Geographic Bounds:")
print(f"  North: {north_lat:.6f}, South: {south_lat:.6f}")
print(f"  West:  {west_lon:.6f}, East:  {east_lon:.6f}")

# Crop to our exact Bounding Box: [LON_MIN, LAT_MIN, LON_MAX, LAT_MAX]
crop_x1 = int((LON_MIN - west_lon) / (east_lon - west_lon) * total_w)
crop_x2 = int((LON_MAX - west_lon) / (east_lon - west_lon) * total_w)

# Note: y goes from north to south
crop_y1 = int((north_lat - LAT_MAX) / (north_lat - south_lat) * total_h)
crop_y2 = int((north_lat - LAT_MIN) / (north_lat - south_lat) * total_h)

crop_box = (max(0, crop_x1), max(0, crop_y1), min(total_w, crop_x2), min(total_h, crop_y2))
print(f"Cropping to exact bounding box: {crop_box}")

cropped_elev = elev_canvas.crop(crop_box)
cropped_sat = sat_canvas.crop(crop_box)

# Target resolution for 3D terrain grid: 1024 x 1024 for smooth WebGL vertex grid
GRID_RES = 1024
cropped_elev = cropped_elev.resize((GRID_RES, GRID_RES), Image.Resampling.BILINEAR)

# Target resolution for satellite texture: 2048 x 2048 for crisp visual display
TEX_RES = 2048
cropped_sat_hq = sat_canvas.crop(crop_box).resize((TEX_RES, TEX_RES), Image.Resampling.LANCZOS)
cropped_sat_hq.save("assets/satellite.jpg", quality=90)
print("Saved assets/satellite.jpg")

# Extract elevations from cropped_elev
# Formula: (r * 256 + g + b / 256) - 32768
elevations_m = []
elevations_ft = []

min_e = 99999
max_e = -99999

for y in range(GRID_RES):
    row_m = []
    row_ft = []
    for x in range(GRID_RES):
        r, g, b = cropped_elev.getpixel((x, y))
        ele_m = (r * 256.0 + g + b / 256.0) - 32768.0
        ele_ft = ele_m * 3.28084
        row_m.append(round(ele_m, 1))
        row_ft.append(round(ele_ft, 1))
        if ele_m < min_e: min_e = ele_m
        if ele_m > max_e: max_e = ele_m
    elevations_m.append(row_m)
    elevations_ft.append(row_ft)

print(f"Elevation Grid generated: {GRID_RES}x{GRID_RES}")
print(f"  Min Elevation: {min_e:.1f} m ({min_e * 3.28084:.1f} ft)")
print(f"  Max Elevation: {max_e:.1f} m ({max_e * 3.28084:.1f} ft)")

# Generate Topographic Hypsometric Color Texture with Contour Lines
topo_img = Image.new("RGB", (TEX_RES, TEX_RES))
# Let's create an interpolated elevation map for texture
elev_for_tex = cropped_elev.resize((TEX_RES, TEX_RES), Image.Resampling.BICUBIC)

def get_topo_color(ele_ft, min_ft=300, max_ft=1900):
    t = max(0.0, min(1.0, (ele_ft - min_ft) / (max_ft - min_ft)))
    # Gradient:
    # 0.0: Lush valley green (46, 117, 89)
    # 0.3: Olive / Oak savannah (118, 148, 86)
    # 0.6: Warm amber / chaparral ridge (196, 163, 90)
    # 0.85: Sonoma volcanic stone / terra cotta (176, 118, 81)
    # 1.0: Bennett peak rocky crag (140, 130, 122)
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

    # Add subtle contour lines every 50 ft and index contours every 200 ft
    contour_interval = 50.0
    dist_to_contour = abs((ele_ft % contour_interval) - contour_interval/2)
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

topo_pixels = []
for y in range(TEX_RES):
    for x in range(TEX_RES):
        r, g, b = elev_for_tex.getpixel((x, y))
        ele_m = (r * 256.0 + g + b / 256.0) - 32768.0
        ele_ft = ele_m * 3.28084
        topo_pixels.append(get_topo_color(ele_ft))

topo_img.putdata(topo_pixels)
topo_img.save("assets/topographic.jpg", quality=90)
print("Saved assets/topographic.jpg")

# Export dataset JSON
dataset = {
    "bounds": {
        "lat_min": LAT_MIN,
        "lat_max": LAT_MAX,
        "lon_min": LON_MIN,
        "lon_max": LON_MAX,
    },
    "grid_res": GRID_RES,
    "min_elevation_m": min_e,
    "max_elevation_m": max_e,
    "min_elevation_ft": min_e * 3.28084,
    "max_elevation_ft": max_e * 3.28084,
    "elevations": elevations_m,
}

with open("data/terrain.json", "w", encoding="utf-8") as f:
    json.dump(dataset, f)
print("Saved data/terrain.json")
