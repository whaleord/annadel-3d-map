import requests
import json
import time
import numpy as np
from PIL import Image, ImageDraw

BBOX = '-122.670,38.390,-122.570,38.460'
LAT_MIN = 38.390
LAT_MAX = 38.460
LON_MIN = -122.670
LON_MAX = -122.570

SIZE = 1024
url = 'https://socogis.sonomacounty.ca.gov/map/rest/services/OWTSPublic/Sonoma_Veg_Map_Vegetation_and_Habitat/FeatureServer/0/query'

print("1. Querying matching ObjectIDs for Annadel bounding box...", flush=True)
p1 = {
    'geometry': BBOX,
    'geometryType': 'esriGeometryEnvelope',
    'inSR': '4326',
    'spatialRel': 'esriSpatialRelIntersects',
    'returnIdsOnly': 'true',
    'f': 'json'
}
r1 = requests.get(url, params=p1, timeout=15)
object_ids = r1.json().get('objectIds', [])
print(f"Found {len(object_ids)} matching vegetation polygons!", flush=True)

print("2. Downloading polygons in chunks...", flush=True)
all_features = []
chunk_size = 400

for i in range(0, len(object_ids), chunk_size):
    chunk = object_ids[i : i + chunk_size]
    post_data = {
        'objectIds': ','.join(map(str, chunk)),
        'outFields': 'MAP_CLASS,LIFEFORM,ALLIANCE',
        'returnGeometry': 'true',
        'geometryPrecision': '5',
        'f': 'geojson'
    }
    t0 = time.time()
    r = requests.post(url, data=post_data, timeout=30)
    data = r.json()
    features = data.get('features', [])
    all_features.extend(features)
    print(f"  Chunk {i}..{i+len(chunk)}: fetched {len(features)} features ({time.time()-t0:.2f}s) - Total: {len(all_features)}", flush=True)

print(f"All {len(all_features)} polygons successfully downloaded!", flush=True)

# Alliance Classification:
# 1: Conifer (Pseudotsuga menziesii / Douglas Fir, Sequoia sempervirens / Redwood)
# 2: Oak / Hardwood (Quercus agrifolia, Q. kelloggii, Q. garryana, Q. lobata, Q. douglasii, Arbutus menziesii / Madrone, Umbellularia / Bay Laurel, Acer)
# 3: Chaparral / Shrub (Arctostaphylos / Manzanita, Adenostoma / Chamise, Baccharis)
# 4: Water / Wetland
# 0: Open Grassland / Meadow / Other

def classify_map_class(mc):
    if not mc:
        return 0
    mc_lower = mc.lower()
    if 'pseudotsuga' in mc_lower or 'sequoia' in mc_lower or 'conifer' in mc_lower or 'fir' in mc_lower or 'redwood' in mc_lower:
        return 1 # Conifer
    if any(k in mc_lower for k in ['quercus', 'oak', 'arbutus', 'madrone', 'umbellularia', 'bay', 'hardwood', 'aesculus', 'buckeye', 'acer', 'maple']):
        return 2 # Oak / Hardwood
    if any(k in mc_lower for k in ['arctostaphylos', 'manzanita', 'adenostoma', 'chamise', 'baccharis', 'shrub', 'scrub', 'chaparral']):
        return 3 # Shrub
    if any(k in mc_lower for k in ['water', 'marsh', 'wetland']):
        return 4 # Water
    return 0

# Sort by specificity: background (0) first, shrub (3), hardwood (2), conifer (1), water (4)
priority = {0: 0, 3: 1, 2: 2, 1: 3, 4: 4}
all_features.sort(key=lambda f: priority.get(classify_map_class(f['properties'].get('MAP_CLASS', '')), 0))

veg_canvas = Image.new("L", (SIZE, SIZE), 0)
draw = ImageDraw.Draw(veg_canvas)

def lonlat_to_pixel(lon, lat):
    px = int(((lon - LON_MIN) / (LON_MAX - LON_MIN)) * (SIZE - 1))
    py = int(((LAT_MAX - lat) / (LAT_MAX - LAT_MIN)) * (SIZE - 1))
    return (max(0, min(SIZE - 1, px)), max(0, min(SIZE - 1, py)))

for feat in all_features:
    mc = feat['properties'].get('MAP_CLASS', '')
    cat_id = classify_map_class(mc)
    if cat_id == 0:
        continue
        
    geom = feat.get('geometry', {})
    gtype = geom.get('type')
    coords = geom.get('coordinates', [])
    
    if gtype == 'Polygon':
        for ring in coords:
            pts = [lonlat_to_pixel(pt[0], pt[1]) for pt in ring]
            if len(pts) >= 3:
                draw.polygon(pts, fill=cat_id)
    elif gtype == 'MultiPolygon':
        for poly in coords:
            for ring in poly:
                pts = [lonlat_to_pixel(pt[0], pt[1]) for pt in ring]
                if len(pts) >= 3:
                    draw.polygon(pts, fill=cat_id)

veg_arr = np.array(veg_canvas, dtype=np.uint8)
np.save("data/annadel_vegmap_alliances.npy", veg_arr)
print("Saved data/annadel_vegmap_alliances.npy!", flush=True)

conifer_px = np.count_nonzero(veg_arr == 1)
hardwood_px = np.count_nonzero(veg_arr == 2)
shrub_px = np.count_nonzero(veg_arr == 3)
water_px = np.count_nonzero(veg_arr == 4)
open_px = np.count_nonzero(veg_arr == 0)

total_px = SIZE * SIZE
print("Official Sonoma VegMap Alliance Ground Truth:")
print(f"  Douglas Fir & Redwood Alliances: {conifer_px:,} px ({conifer_px/total_px*100:.1f}%)")
print(f"  Oak & Hardwood Alliances:        {hardwood_px:,} px ({hardwood_px/total_px*100:.1f}%)")
print(f"  Chaparral & Shrubland:           {shrub_px:,} px ({shrub_px/total_px*100:.1f}%)")
print(f"  Water & Wetlands:                {water_px:,} px ({water_px/total_px*100:.1f}%)")
print(f"  Grassland / Open Meadows:        {open_px:,} px ({open_px/total_px*100:.1f}%)")
