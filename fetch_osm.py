import requests
import json
import os

os.makedirs("data", exist_ok=True)

overpass_url = "https://overpass-api.de/api/interpreter"

# Bounding box roughly around Trione-Annadel State Park:
# South: 38.400, West: -122.685, North: 38.460, East: -122.585
bbox = "38.400,-122.685,38.460,-122.585"

query = f"""
[out:json][timeout:60];
(
  // Park boundary
  relation["boundary"="protected_area"]["name"~"Annadel"]({bbox});
  relation["leisure"="nature_reserve"]["name"~"Annadel"]({bbox});
  relation["boundary"="national_park"]["name"~"Annadel"]({bbox});
  way["leisure"="park"]["name"~"Annadel"]({bbox});

  // Official named trails/paths
  way["highway"~"path|track|footway"]["name"]({bbox});

  // Water features (Lake Ilsanjo, Ledson Marsh, etc)
  way["natural"="water"]({bbox});
  relation["natural"="water"]({bbox});
  way["water"]({bbox});
  relation["water"]({bbox});

  // Summits / Peaks
  node["natural"="peak"]({bbox});
  node["tourism"="viewpoint"]({bbox});
  node["tourism"="information"]({bbox});
);
out body;
>;
out skel qt;
"""

headers = {
    "User-Agent": "Annadel3DMapExplorer/1.0"
}
print("Sending Overpass query...")
resp = requests.post(overpass_url, data={"data": query}, headers=headers, timeout=90)
if resp.status_code == 200:
    data = resp.json()
    with open("data/annadel_osm_raw.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Success! Elements count: {len(data.get('elements', []))}")
else:
    print(f"Error {resp.status_code}: {resp.text[:200]}")
