"""Step 3: trace the high-voltage transmission line that crosses the east side of the map.

The wires are unclassified in the source point cloud, so they show up in the canopy model as a
thin, continuous streak (and as a row of fake "trees"). Starting from rough bend points picked
off the canopy image, each straight run is snapped onto the streak, then the measured wire
height is sampled every metre along the route and towers are located.

Output: work/powerline.json
  route   [[lon, lat], ...] refined polyline (bend points = angle towers)
  profile [[lon, lat, ground_m, wire_m], ...] every ~5 m, wire_m absolute elevation of the top wire
  towers  [[lon, lat, ground_m, height_m], ...]
"""
import json
import os

import numpy as np
from scipy import ndimage

from config import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, NX, NY, WORK

M_PER_COL = 8720.0 / NX
M_PER_ROW = 7774.0 / NY

# Rough bend points (grid col, row at 1 m) read off the canopy image; refined below.
# The line enters at the north edge of the map and leaves at the south edge.
ROUGH = [(7010, 0), (7710, 1520), (6480, 3780), (7065, 4720), (6795, 6085), (6800, 7773)]


def sample(grid, cols, rows):
    return ndimage.map_coordinates(grid, [rows, cols], order=1, mode="nearest")


def to_m(p):
    return np.array([p[0] * M_PER_COL, p[1] * M_PER_ROW])


def to_px(m):
    return np.array([m[0] / M_PER_COL, m[1] / M_PER_ROW])


def thin_features(chm):
    """Cells that stand above their surroundings in a line 1-2 m wide: wires (and stray conifer tips)."""
    opened = ndimage.grey_opening(chm, size=(3, 3))
    thin = ((chm - opened) > 2.0) & (chm > 4.0)
    return ndimage.maximum_filter(thin.astype(np.float32), size=3)


def fit_run(thin, a, b):
    """Search angle and offset around the rough run a->b for the line best covered by thin features.

    Returns (point_on_centerline_m, direction, conductor_offsets_m, score)."""
    am, bm = to_m(a), to_m(b)
    L = np.linalg.norm(bm - am)
    base = np.arctan2(*(bm - am)[::-1])
    mid = (am + bm) / 2
    s = np.arange(-0.4 * L, 0.4 * L, 2.0)
    offsets = np.arange(-120, 120.01, 0.5)
    best = (-1, None, None)
    for dth in np.radians(np.arange(-4, 4.01, 0.1)):
        th = base + dth
        t = np.array([np.cos(th), np.sin(th)]); n = np.array([-t[1], t[0]])
        pts = mid[None, None, :] + s[None, :, None] * t + offsets[:, None, None] * n
        cols = pts[..., 0] / M_PER_COL; rows = pts[..., 1] / M_PER_ROW
        prof = ndimage.map_coordinates(thin, [rows.ravel(), cols.ravel()], order=0, mode="constant").reshape(pts.shape[:2]).mean(axis=1)
        if prof.max() > best[0]:
            best = (prof.max(), th, prof)
    score, th, prof = best
    t = np.array([np.cos(th), np.sin(th)]); n = np.array([-t[1], t[0]])
    peak = offsets[np.argmax(prof)]
    # Conductors: local maxima of the offset profile within 20 m of the strongest one
    cond = [o for i, o in enumerate(offsets)
            if abs(o - peak) <= 20 and prof[i] >= 0.35 * score
            and prof[i] == prof[max(0, i - 4):i + 5].max()]
    center = float(np.mean(cond))
    return mid + center * n, t, sorted(o - center for o in cond), float(score)


def intersect(p1, d1, p2, d2):
    A = np.array([d1, -d2]).T
    if abs(np.linalg.det(A)) < 1e-9:
        return (p1 + p2) / 2
    k = np.linalg.solve(A, p2 - p1)
    return p1 + k[0] * d1


def main():
    chm = np.load(os.path.join(WORK, "chm_1m.npy"))
    dem = np.load(os.path.join(WORK, "dem_1m.npy"))

    thin = thin_features(chm)
    # Snap each straight run onto the wires
    lines, conductor_sets = [], []
    for a, b in zip(ROUGH[:-1], ROUGH[1:]):
        p, d, cond, score = fit_run(thin, a, b)
        lines.append((p, d))
        conductor_sets.append(cond)
        print(f"run {a}->{b}: coverage {score:.2f}, conductors at {[round(c, 1) for c in cond]} m")

    # Bend points = intersections of consecutive runs; ends clipped to the map edge rows
    verts = []
    p, d = lines[0]
    verts.append(p + d * ((0 - p[1]) / d[1]))
    for (p1, d1), (p2, d2) in zip(lines[:-1], lines[1:]):
        verts.append(intersect(p1, d1, p2, d2))
    p, d = lines[-1]
    verts.append(p + d * (((NY - 1) * M_PER_ROW - p[1]) / d[1]))
    verts = np.array(verts)

    # Measure the wire along the route every metre: highest canopy-model value within 2 m of the line
    samples = []
    for v0, v1 in zip(verts[:-1], verts[1:]):
        L = np.linalg.norm(v1 - v0)
        t = (v1 - v0) / L
        n = np.array([-t[1], t[0]])
        for s in np.arange(0, L, 1.0):
            c = v0 + s * t
            best = 0.0
            for off in (-2, -1, 0, 1, 2):
                q = to_px(c + off * n)
                best = max(best, float(sample(chm, [q[0]], [q[1]])[0]))
            width = 0
            for off in range(-8, 9):
                q = to_px(c + off * n)
                width += float(sample(chm, [q[0]], [q[1]])[0]) > 8.0
            q = to_px(c)
            samples.append((c[0], c[1], float(sample(dem, [q[0]], [q[1]])[0]), best, width))
    S = np.array(samples)
    x, y, ground, h, width = S.T
    dist = np.concatenate([[0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])

    # Wire height: keep plausible returns, drop tree-crown contamination with a running median,
    # bridge gaps (deep canyons exceed the canopy model's range) by interpolation
    valid = (h > 6.0)
    hv = ndimage.median_filter(np.where(valid, h, np.nan), size=31, mode="nearest")
    ok = ~np.isnan(hv)
    wire_h = np.interp(dist, dist[ok], hv[ok])
    wire_h = ndimage.gaussian_filter1d(wire_h, 8)

    # Towers: bend points, plus peaks in footprint width (lattice towers are ~8-10 m wide,
    # wires only 1-2 cells) at least 150 m apart
    bend_d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(verts, axis=0), axis=1))])
    w = ndimage.uniform_filter1d(width, 9)
    peaks = [i for i in range(len(w)) if w[i] >= 9 and w[i] == w[max(0, i - 60):i + 61].max()]
    tower_d = list(bend_d[1:-1])
    for i in sorted(peaks, key=lambda i: -w[i]):
        if all(abs(dist[i] - td) > 150 for td in tower_d):
            tower_d.append(dist[i])
    tower_d = sorted(tower_d)
    # Fill any long span without a detected tower at the typical spacing
    filled = []
    for a, b in zip([0.0] + tower_d, tower_d + [dist[-1]]):
        n_extra = int((b - a) // 450)
        filled += [a + (b - a) * k / (n_extra + 1) for k in range(1, n_extra + 1)]
    tower_d = sorted(tower_d + filled)

    def lonlat(xm, ym):
        col, row = xm / M_PER_COL, ym / M_PER_ROW
        return LON_MIN + (col + 0.5) / NX * (LON_MAX - LON_MIN), LAT_MAX - (row + 0.5) / NY * (LAT_MAX - LAT_MIN)

    step = 5
    profile = []
    for i in range(0, len(dist), step):
        lo, la = lonlat(x[i], y[i])
        profile.append([round(lo, 6), round(la, 6), round(ground[i], 1), round(ground[i] + wire_h[i], 1)])
    towers = []
    for td in tower_d:
        i = int(np.searchsorted(dist, td))
        i = min(i, len(dist) - 1)
        lo, la = lonlat(x[i], y[i])
        towers.append([round(lo, 6), round(la, 6), round(ground[i], 1), round(float(np.clip(wire_h[i] + 4, 25, 60)), 1)])
    route = [list(map(lambda v: round(v, 6), lonlat(*v))) for v in verts]

    json.dump({"route": route, "profile": profile, "towers": towers},
              open(os.path.join(WORK, "powerline.json"), "w"))
    print(f"Route {dist[-1] / 1000:.2f} km, {len(route) - 2} bends, {len(towers)} towers "
          f"({len(peaks)} width peaks), wire height median {np.median(wire_h):.0f} m, max {wire_h.max():.0f} m")


if __name__ == "__main__":
    main()
