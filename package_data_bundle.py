import json
import base64
import os

with open("data/terrain.json", "r", encoding="utf-8") as f:
    terrain_data = json.load(f)

with open("data/annadel_features.json", "r", encoding="utf-8") as f:
    features_data = json.load(f)

with open("assets/satellite.jpg", "rb") as f:
    sat_b64 = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("ascii")

with open("assets/topographic.jpg", "rb") as f:
    topo_b64 = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("ascii")

with open("data/annadel_trees.json", "r", encoding="utf-8") as f:
    trees_data = json.load(f)

bundle = {
    "terrain": terrain_data,
    "features": features_data,
    "trees": trees_data,
    "textures": {
        "satellite": sat_b64,
        "topographic": topo_b64
    }
}

js_content = "window.ANNADEL_DATA = " + json.dumps(bundle) + ";\n"

with open("annadel_data.js", "w", encoding="utf-8") as f:
    f.write(js_content)

print(f"Successfully packaged annadel_data.js! File size: {os.path.getsize('annadel_data.js') / (1024*1024):.2f} MB")
