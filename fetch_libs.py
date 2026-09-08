import requests
import os

os.makedirs("libs", exist_ok=True)

urls = {
    "libs/three.min.js": "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js",
    "libs/OrbitControls.js": "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"
}

headers = {"User-Agent": "Annadel3DMapBuilder/1.0"}

for dest, url in urls.items():
    if not os.path.exists(dest):
        print(f"Downloading {url} to {dest}...")
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(r.text)
                print(f"Saved {dest} ({len(r.text)} bytes)")
            else:
                print(f"Failed {url}: {r.status_code}")
        except Exception as e:
            print(f"Error downloading {url}: {e}")
