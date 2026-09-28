"""Step 3: detect individual trees in the canopy height model (inside the park only).

Method (the usual lidR-style recipe, done with numpy/scipy/scikit-image):
  1. Smooth the 1 m CHM slightly so single-branch spikes don't become trees.
  2. Tree tops = local maxima inside a window that grows with height
     (taller trees have wider crowns, so they suppress more neighbours).
  3. Marker-controlled watershed on the CHM grows each top into its crown;
     crown radius comes from the segment's area.
  4. Species group from the Sonoma County Veg Map alliance layer, with a height
     fallback where the map has no forest alliance.

Output: work/trees.npz with arrays lon, lat, height_m, crown_r_m, kind (0 conifer, 1 broadleaf)
"""
import json
import os

import numpy as np
from matplotlib.path import Path
from scipy import ndimage
from skimage.segmentation import watershed

from config import CELL_X_M, LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, NX, NY, REPO, WORK

MIN_TREE_HEIGHT_M = 5.0   # below this it's shrub / chaparral
CROWN_FLOOR_M = 2.0       # crowns stop where the canopy drops below this
MIN_CROWN_AREA_M2 = 5.0
MAX_ELONGATION = 4.0      # major/minor axis ratio of the crown footprint
# Taller "trees" are high-voltage wires spanning the canyons on the park's east side
# (all 60 m+ detections line up along that corridor); real crowns here top out in the 50s.
MAX_TREE_HEIGHT_M = 62.0
# Anything detected on the wires themselves (the corridor is kept clear of trees)
POWERLINE_CLEARANCE_M = 15.0
TILE = 2048
MARGIN = 48


def distance_to_powerline_m(lon, lat):
    """Distance from each point to the traced transmission line (step 3), in metres."""
    route = np.array(json.load(open(os.path.join(WORK, "powerline.json")))["route"])
    mx = 8720.0 / (LON_MAX - LON_MIN)
    my = 7774.0 / (LAT_MAX - LAT_MIN)
    p = np.stack([lon * mx, lat * my], axis=1)
    r = np.stack([route[:, 0] * mx, route[:, 1] * my], axis=1)
    best = np.full(len(p), np.inf)
    for a, b in zip(r[:-1], r[1:]):
        ab = b - a
        t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
        best = np.minimum(best, np.linalg.norm(p - (a + t[:, None] * ab), axis=1))
    return best


def window_diameter(h):
    """Search window (m) for a tree of height h; standard lidR example function."""
    return 2.6 * (-(np.exp(-0.08 * (h - 2.0)) - 1.0)) + 3.0


def disk(d):
    r = d / 2.0
    n = int(np.ceil(r))
    yy, xx = np.mgrid[-n:n + 1, -n:n + 1]
    return (xx * xx + yy * yy) <= r * r


def detect_tile(chm):
    smooth = ndimage.gaussian_filter(chm, 0.7)
    tops = np.zeros(chm.shape, dtype=bool)
    candidate = smooth >= MIN_TREE_HEIGHT_M
    # Bucket pixels by their required window size and test each bucket with one max filter
    diam = np.clip(np.round(window_diameter(smooth) / CELL_X_M), 3, 9)
    for d in np.unique(diam[candidate]):
        sel = candidate & (diam == d)
        mx = ndimage.maximum_filter(smooth, footprint=disk(d), mode="nearest")
        tops |= sel & (smooth >= mx)
    # Plateaus give several equal maxima; keep one per connected blob
    lab, n = ndimage.label(tops, structure=np.ones((3, 3)))
    if n == 0:
        return np.empty((0, 2), int), np.empty(0), np.empty(0)
    centers = np.array(ndimage.center_of_mass(tops, lab, range(1, n + 1)))
    ys = np.clip(np.round(centers[:, 0]).astype(int), 0, chm.shape[0] - 1)
    xs = np.clip(np.round(centers[:, 1]).astype(int), 0, chm.shape[1] - 1)
    markers = np.zeros(chm.shape, dtype=np.int32)
    markers[ys, xs] = np.arange(1, n + 1)
    crowns = watershed(-smooth, markers, mask=smooth >= CROWN_FLOOR_M)
    labels = np.arange(1, n + 1)
    area = ndimage.sum_labels(np.ones_like(crowns), crowns, index=labels)
    height = np.asarray(ndimage.maximum(chm, crowns, index=labels))
    radius = np.sqrt(np.maximum(area, 1.0) * CELL_X_M * CELL_X_M / np.pi)

    # Reject power-line spans and other non-trees: real crowns are compact blobs,
    # wires show up as thin elongated streaks in the canopy model
    yy, xx = np.indices(crowns.shape)
    a = np.maximum(area, 1.0)
    mx = ndimage.sum_labels(xx, crowns, labels) / a
    my = ndimage.sum_labels(yy, crowns, labels) / a
    sxx = ndimage.sum_labels(xx * xx, crowns, labels) / a - mx * mx
    syy = ndimage.sum_labels(yy * yy, crowns, labels) / a - my * my
    sxy = ndimage.sum_labels(xx * yy, crowns, labels) / a - mx * my
    tr, det = sxx + syy, sxx * syy - sxy * sxy
    disc = np.sqrt(np.maximum(tr * tr / 4 - det, 0))
    elongation = np.sqrt((tr / 2 + disc) / np.maximum(tr / 2 - disc, 0.05))
    ok = (area >= MIN_CROWN_AREA_M2) & (elongation <= MAX_ELONGATION)
    return np.stack([ys, xs], axis=1)[ok], height[ok], radius[ok]


def main():
    chm = np.load(os.path.join(WORK, "chm_1m.npy"))
    features = json.load(open(os.path.join(REPO, "data", "annadel_features.json")))
    boundary = Path([(p["lon"], p["lat"]) for p in features["boundary"]])
    lons = [p["lon"] for p in features["boundary"]]
    lats = [p["lat"] for p in features["boundary"]]
    c0 = max(0, int((min(lons) - LON_MIN) / (LON_MAX - LON_MIN) * NX) - MARGIN)
    c1 = min(NX, int((max(lons) - LON_MIN) / (LON_MAX - LON_MIN) * NX) + MARGIN)
    r0 = max(0, int((LAT_MAX - max(lats)) / (LAT_MAX - LAT_MIN) * NY) - MARGIN)
    r1 = min(NY, int((LAT_MAX - min(lats)) / (LAT_MAX - LAT_MIN) * NY) + MARGIN)

    all_rc, all_h, all_r = [], [], []
    for ty in range(r0, r1, TILE):
        for tx in range(c0, c1, TILE):
            y0, x0 = max(0, ty - MARGIN), max(0, tx - MARGIN)
            y1, x1 = min(NY, ty + TILE + MARGIN), min(NX, tx + TILE + MARGIN)
            rc, h, r = detect_tile(chm[y0:y1, x0:x1])
            rc = rc + [y0, x0]
            core = (rc[:, 0] >= ty) & (rc[:, 0] < min(ty + TILE, r1)) & (rc[:, 1] >= tx) & (rc[:, 1] < min(tx + TILE, c1))
            all_rc.append(rc[core]); all_h.append(h[core]); all_r.append(r[core])
            print(f"tile {ty},{tx}: {core.sum()} trees", flush=True)
    rc = np.concatenate(all_rc); height = np.concatenate(all_h); radius = np.concatenate(all_r)

    lon = LON_MIN + (rc[:, 1] + 0.5) / NX * (LON_MAX - LON_MIN)
    lat = LAT_MAX - (rc[:, 0] + 0.5) / NY * (LAT_MAX - LAT_MIN)
    inside = boundary.contains_points(np.stack([lon, lat], axis=1)) & (height <= MAX_TREE_HEIGHT_M)
    inside &= distance_to_powerline_m(lon, lat) > POWERLINE_CLEARANCE_M
    lon, lat, height, radius = lon[inside], lat[inside], height[inside], radius[inside]

    # Species group from the Veg Map alliance raster (1024^2 over the same bounds):
    # 1 conifer (Douglas-fir / redwood), 2 hardwood (oaks, bay, madrone), 3 shrub, 4 water, 0 other
    veg = np.load(os.path.join(REPO, "data", "annadel_vegmap_alliances.npy"))
    vs = veg.shape[0]
    vi = np.clip(((LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * (vs - 1)).round().astype(int), 0, vs - 1)
    vj = np.clip(((lon - LON_MIN) / (LON_MAX - LON_MIN) * (vs - 1)).round().astype(int), 0, vs - 1)
    alliance = veg[vi, vj]
    kind = np.where(alliance == 1, 0, 1)
    # Outside mapped forest alliances, only very tall trees are likely conifers
    kind = np.where((alliance != 1) & (alliance != 2) & (height >= 35.0), 0, kind).astype(np.uint8)

    np.savez(os.path.join(WORK, "trees.npz"), lon=lon, lat=lat, height_m=height.astype(np.float32),
             crown_r_m=radius.astype(np.float32), kind=kind)
    print(f"Trees inside park: {len(lon):,}  (conifer {np.count_nonzero(kind == 0):,}, broadleaf {np.count_nonzero(kind == 1):,})")
    print(f"Height m: median {np.median(height):.1f}, p95 {np.percentile(height, 95):.1f}, max {height.max():.1f}")
    print(f"Crown radius m: median {np.median(radius):.1f}, p95 {np.percentile(radius, 95):.1f}")


if __name__ == "__main__":
    main()
