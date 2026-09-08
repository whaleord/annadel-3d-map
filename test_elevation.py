import math
import requests
import io

# Let's test Nextzen / AWS terrarium tile
# For Lat: 38.43, Lon: -122.63, zoom 12 and 13
def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

z = 12
x, y = deg2num(38.43, -122.63, z)
print(f"Zoom {z}: tile ({x}, {y})")

url_terrarium = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
print("Testing Terrarium:", url_terrarium)
try:
    r = requests.get(url_terrarium, timeout=10)
    print("Terrarium status:", r.status_code, "Length:", len(r.content))
except Exception as e:
    print("Terrarium err:", e)

# Test USGS 3DEP EPQS (Elevation Point Query Service)
usgs_epqs = "https://epqs.nationalmap.gov/v1/json?x=-122.63&y=38.43&units=Feet&output=json"
print("Testing USGS EPQS:", usgs_epqs)
try:
    r2 = requests.get(usgs_epqs, timeout=10)
    print("USGS status:", r2.status_code, "Response:", r2.text)
except Exception as e:
    print("USGS err:", e)

# Test Open-Elevation
oe_url = "https://api.open-elevation.com/api/v1/lookup?locations=38.43,-122.63"
print("Testing Open-Elevation:", oe_url)
try:
    r3 = requests.get(oe_url, timeout=10)
    print("OE status:", r3.status_code, "Response:", r3.text[:200])
except Exception as e:
    print("OE err:", e)
