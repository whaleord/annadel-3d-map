import math
import requests
from PIL import Image
import io

# Test tile 13 / 1305 / 3147 (central tile containing Lake Ilsanjo)
url = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/13/1305/3147.png"
r = requests.get(url)
img = Image.open(io.BytesIO(r.content)).convert("RGB")
w, h = img.size
print(f"Tile size: {w}x{h}")

# Check min, max, avg elevation
elevs = []
for y in range(0, h, 10):
    for x in range(0, w, 10):
        r_val, g_val, b_val = img.getpixel((x, y))
        ele_m = (r_val * 256.0 + g_val + b_val / 256.0) - 32768.0
        elevs.append(ele_m)

print(f"Sampled min: {min(elevs):.1f}m ({min(elevs)*3.28084:.1f}ft)")
print(f"Sampled max: {max(elevs):.1f}m ({max(elevs)*3.28084:.1f}ft)")
print(f"Sampled avg: {sum(elevs)/len(elevs):.1f}m ({sum(elevs)/len(elevs)*3.28084:.1f}ft)")
