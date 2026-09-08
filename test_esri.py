import requests

url = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/13/3147/1305"
r = requests.get(url, headers={"User-Agent": "AnnadelMap/1.0"})
print("ESRI Tile status:", r.status_code, "Length:", len(r.content))
