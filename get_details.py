import requests
import json

q = """
[out:json];
(
  node["name"~"Ledson"];
  way["name"~"Ledson"];
  relation["name"~"Ledson"];
  relation["name"~"Trione-Annadel"];
);
out center;
"""
r = requests.post('https://overpass-api.de/api/interpreter', data={'data': q}, headers={'User-Agent': 'Test/1.0'})
print(json.dumps(r.json(), indent=2))
