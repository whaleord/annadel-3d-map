"""Step 4: package everything the web app needs into annadel_data.js.

  terrain   1024 x 1024 elevation grid from the 1 m LiDAR DEM (uint16 decimetres, base64)
  trees     one 8-byte record per detected tree (base64, layout below)
  textures  satellite (existing ESRI mosaic), plus topographic and shaded relief baked from the DEM
  features  trails / lake / boundary, with trail elevation stats recomputed on the LiDAR DEM

Tree record (little endian): u uint16, v uint16, height dm uint16, crown radius dm uint8, kind uint8
"""
import base64
import io
import json
import math
import os

import numpy as np
from PIL import Image
from scipy import ndimage

from config import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, NX, NY, REPO, WORK

GRID_RES = 1024
TEX_RES = 2048
M_TO_FT = 3.28084


def resample(grid, out_h, out_w):
    """Area-style downsample: blur by the reduction factor, then bilinear sample."""
    fy, fx = grid.shape[0] / out_h, grid.shape[1] / out_w
    blurred = ndimage.gaussian_filter(grid, (fy / 2.0, fx / 2.0))
    ys = np.linspace(0, grid.shape[0] - 1, out_h)
    xs = np.linspace(0, grid.shape[1] - 1, out_w)
    yy, xx = np.meshgrid(ys, xs, indexing="ij")
    return ndimage.map_coordinates(blurred, [yy, xx], order=1).astype(np.float32)


def hillshade(dem, cell_x, cell_y, azimuth_deg, altitude_deg):
    dzdy, dzdx = np.gradient(dem, cell_y, cell_x)
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(-dzdx, dzdy)
    az, alt = np.radians(azimuth_deg), np.radians(altitude_deg)
    return np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)


def multi_hillshade(dem, cx, cy):
    """Blend of four light directions: reads well without a single dominant shadow side."""
    return (0.4 * hillshade(dem, cx, cy, 315, 45) + 0.2 * hillshade(dem, cx, cy, 15, 45)
            + 0.2 * hillshade(dem, cx, cy, 255, 45) + 0.2 * hillshade(dem, cx, cy, 0, 90))


def jpeg_data_uri(rgb, quality=85):
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def topo_texture(dem_tex, shade):
    ft = dem_tex * M_TO_FT
    lo, hi = np.percentile(ft, 1), np.percentile(ft, 99.5)
    t = np.clip((ft - lo) / (hi - lo), 0, 1)
    stops = np.array([0.0, 0.3, 0.6, 0.85, 1.0])
    colors = np.array([[46, 117, 89], [118, 148, 86], [196, 163, 90], [176, 118, 81], [140, 130, 122]], float)
    rgb = np.stack([np.interp(t, stops, colors[:, i]) for i in range(3)], axis=-1)
    rgb *= (0.55 + 0.45 * shade)[..., None]
    # 40 ft contours, every fifth (200 ft) as an index contour; drawn where a contour crosses the pixel
    for interval, strength in ((40.0, 0.78), (200.0, 0.55)):
        level = np.floor(ft / interval)
        edge = np.zeros(ft.shape, bool)
        edge[:-1, :] |= level[:-1, :] != level[1:, :]
        edge[:, :-1] |= level[:, :-1] != level[:, 1:]
        rgb[edge] *= strength
    return np.clip(rgb, 0, 255).astype(np.uint8)


def trail_stats(trails, dem):
    """Min/max elevation and climb for each trail, sampled every ~5 m along the line."""
    def elev(lon, lat):
        col = (lon - LON_MIN) / (LON_MAX - LON_MIN) * NX - 0.5
        row = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * NY - 0.5
        return ndimage.map_coordinates(dem, [np.atleast_1d(row), np.atleast_1d(col)], order=1, mode="nearest")

    m_per_lon = 111320.0 * math.cos(math.radians((LAT_MIN + LAT_MAX) / 2))
    for tr in trails:
        lo, hi, climb = 1e9, -1e9, 0.0
        for seg in tr["lines"]:
            lon = np.array([p["lon"] for p in seg]); lat = np.array([p["lat"] for p in seg])
            d = np.hypot(np.diff(lon) * m_per_lon, np.diff(lat) * 110950.0)
            s = np.concatenate([[0], np.cumsum(d)])
            n = max(2, int(s[-1] / 5.0) + 1)
            si = np.linspace(0, s[-1], n)
            z = elev(np.interp(si, s, lon), np.interp(si, s, lat))
            dz = np.diff(z)
            up, down = dz[dz > 0].sum(), -dz[dz < 0].sum()
            # OSM draws segments in arbitrary directions; report the climb in the uphill direction
            climb += max(up, down)
            lo, hi = min(lo, z.min()), max(hi, z.max())
        tr["min_elev_ft"] = int(round(lo * M_TO_FT))
        tr["max_elev_ft"] = int(round(hi * M_TO_FT))
        tr["elev_gain_ft"] = int(round(climb * M_TO_FT))
        for seg in tr["lines"]:
            for p in seg:
                for k in ("ele_m", "ele_ft", "x", "z"):
                    p.pop(k, None)
        tr.pop("total_meters", None)


def main():
    dem = np.load(os.path.join(WORK, "dem_1m.npy"))
    cx, cy = 8720.0 / NX, 7774.0 / NY

    # Terrain grid for the mesh
    grid = resample(dem, GRID_RES, GRID_RES)
    dm = np.round(grid * 10).astype("<u2")
    terrain = {
        "bounds": {"lat_min": LAT_MIN, "lat_max": LAT_MAX, "lon_min": LON_MIN, "lon_max": LON_MAX},
        "grid_res": GRID_RES,
        "min_elevation_m": float(grid.min()),
        "max_elevation_m": float(grid.max()),
        "elev_dm_b64": base64.b64encode(dm.tobytes()).decode("ascii"),
    }

    # Baked textures
    dem_tex = resample(dem, TEX_RES, TEX_RES)
    tcx, tcy = 8720.0 / TEX_RES, 7774.0 / TEX_RES
    shade = multi_hillshade(dem_tex, tcx, tcy)
    relief = np.clip(70 + 185 * shade, 0, 255)
    relief_rgb = np.stack([relief * 0.97, relief * 0.98, relief], axis=-1).astype(np.uint8)
    sat = np.array(Image.open(os.path.join(REPO, "assets", "satellite.jpg")).convert("RGB").resize((TEX_RES, TEX_RES), Image.LANCZOS))
    textures = {
        "satellite": jpeg_data_uri(sat, 82),
        "topographic": jpeg_data_uri(topo_texture(dem_tex, shade), 85),
        "relief": jpeg_data_uri(relief_rgb, 85),
    }

    # Trees
    t = np.load(os.path.join(WORK, "trees.npz"))
    u = np.round((t["lon"] - LON_MIN) / (LON_MAX - LON_MIN) * 65535).astype("<u2")
    v = np.round((LAT_MAX - t["lat"]) / (LAT_MAX - LAT_MIN) * 65535).astype("<u2")
    h = np.round(t["height_m"] * 10).astype("<u2")
    r = np.clip(np.round(t["crown_r_m"] * 10), 1, 255).astype(np.uint8)
    rec = np.zeros(len(u), dtype=[("u", "<u2"), ("v", "<u2"), ("h", "<u2"), ("r", "u1"), ("k", "u1")])
    rec["u"], rec["v"], rec["h"], rec["r"], rec["k"] = u, v, h, r, t["kind"]
    trees = {"count": int(len(rec)), "b64": base64.b64encode(rec.tobytes()).decode("ascii")}

    # Vector features: keep trails, the real lake outline and the boundary
    features = json.load(open(os.path.join(REPO, "data", "annadel_features.json")))
    trail_stats(features["trails"], dem)
    lake = [w for w in features["water_bodies"] if w["type"] == "lake"]
    for w in lake:
        w["polygon"] = [{"u": p["u"], "v": p["v"]} for p in w["polygon"]]
        # Lake surface: lowest part of the shoreline on the LiDAR DEM
        us = np.array([p["u"] for p in w["polygon"]]); vs = np.array([p["v"] for p in w["polygon"]])
        z = ndimage.map_coordinates(dem, [vs * NY - 0.5, us * NX - 0.5], order=1, mode="nearest")
        w["surface_m"] = float(np.percentile(z, 10))
    bundle = {
        "meta": {
            "source": "USGS 3DEP lidar CA_NorthernCA_1_B22 (flown 2022), 1 m ground and canopy models",
            "tree_count": trees["count"],
        },
        "terrain": terrain,
        "trees": trees,
        "textures": textures,
        "features": {
            "trails": features["trails"],
            "water_bodies": lake,
            "boundary": [{"u": p["u"], "v": p["v"]} for p in features["boundary"]],
        },
    }
    out = os.path.join(REPO, "annadel_data.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write("window.ANNADEL_DATA = " + json.dumps(bundle, separators=(",", ":")) + ";\n")
    print(f"Wrote {out}: {os.path.getsize(out) / 1e6:.1f} MB, {trees['count']:,} trees")


if __name__ == "__main__":
    main()
