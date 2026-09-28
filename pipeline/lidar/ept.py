"""Minimal reader for the USGS 3DEP Entwine Point Tile (EPT) datasets on AWS.

Walks the EPT octree hierarchy and lists the data nodes that intersect a
Web Mercator (EPSG:3857) bounding box, so we can fetch only what we need.
"""
import json
import math
import urllib.request

BASE = "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/"
DATASET = "CA_NorthernCA_1_B22"


def _get_json(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)


def lonlat_to_merc(lon, lat):
    x = lon * 20037508.342789244 / 180.0
    y = math.log(math.tan((90.0 + lat) * math.pi / 360.0)) * 6378137.0
    return x, y


def merc_to_lonlat(x, y):
    lon = x / 20037508.342789244 * 180.0
    lat = math.degrees(2.0 * math.atan(math.exp(y / 6378137.0)) - math.pi / 2.0)
    return lon, lat


class EPT:
    def __init__(self, dataset=DATASET):
        self.url = BASE + dataset + "/"
        self.meta = _get_json(self.url + "ept.json")
        self.bounds = self.meta["bounds"]  # cube: xmin, ymin, zmin, xmax, ymax, zmax
        self.hier = {}
        self._load_hier("0-0-0-0")

    def _load_hier(self, key):
        self.hier.update(_get_json(f"{self.url}ept-hierarchy/{key}.json"))

    def node_bounds(self, key):
        d, x, y, z = map(int, key.split("-"))
        b = self.bounds
        s = (b[3] - b[0]) / (2 ** d)
        return (b[0] + x * s, b[1] + y * s, b[0] + (x + 1) * s, b[1] + (y + 1) * s)

    def nodes_in_box(self, box, max_depth=99):
        """Return [(key, point_count)] for every node overlapping box (xmin, ymin, xmax, ymax)."""
        out = []

        def walk(d, x, y, z):
            key = f"{d}-{x}-{y}-{z}"
            if key not in self.hier:
                return
            if self.hier[key] == -1:
                self._load_hier(key)
            nb = self.node_bounds(key)
            if nb[2] < box[0] or nb[0] > box[2] or nb[3] < box[1] or nb[1] > box[3]:
                return
            if self.hier[key] > 0:
                out.append((key, self.hier[key]))
            if d < max_depth:
                for dx in (0, 1):
                    for dy in (0, 1):
                        for dz in (0, 1):
                            walk(d + 1, 2 * x + dx, 2 * y + dy, 2 * z + dz)

        walk(0, 0, 0, 0)
        return out

    def data_url(self, key):
        return f"{self.url}ept-data/{key}.laz"
