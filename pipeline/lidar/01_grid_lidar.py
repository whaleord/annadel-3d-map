"""Step 1: stream the USGS 3DEP point cloud over the map area into 1 m rasters.

Nothing is kept on disk except the rasters: each EPT tile is downloaded,
binned, and discarded. Outputs (in work/):
  dsm_max.npy     highest non-noise return per cell (surface incl. canopy), NaN = no data
  ground_sum.npy  sum of ground-classified (class 2) elevations per cell
  ground_cnt.npy  number of ground points per cell
Resumable: progress is checkpointed to work/done_keys.json.
"""
import io
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import laspy
import numpy as np

from config import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, NX, NY, WORK
from ept import EPT, lonlat_to_merc

NOISE_CLASSES = (7, 18)
CHECKPOINT_EVERY = 1500


def _fetch(url):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return r.read()
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def process_tile(url):
    """Download one tile and reduce it to per-cell (max surface, ground sum/count)."""
    las = laspy.read(io.BytesIO(_fetch(url)))
    keep = ~np.isin(np.asarray(las.classification), NOISE_CLASSES) & ~np.asarray(las.withheld, dtype=bool)
    x = np.asarray(las.x)[keep]
    y = np.asarray(las.y)[keep]
    z = np.asarray(las.z, dtype=np.float32)[keep]
    cls = np.asarray(las.classification)[keep]

    lon = x / 20037508.342789244 * 180.0
    lat = np.degrees(2.0 * np.arctan(np.exp(y / 6378137.0)) - np.pi / 2.0)
    col = np.floor((lon - LON_MIN) / (LON_MAX - LON_MIN) * NX).astype(np.int64)
    row = np.floor((LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * NY).astype(np.int64)
    inside = (col >= 0) & (col < NX) & (row >= 0) & (row < NY)
    if not inside.any():
        return None
    idx = row[inside] * NX + col[inside]
    z = z[inside]
    ground = cls[inside] == 2

    order = np.argsort(idx, kind="stable")
    idx_s, z_s = idx[order], z[order]
    uniq, starts = np.unique(idx_s, return_index=True)
    zmax = np.maximum.reduceat(z_s, starts)

    gidx = idx[ground]
    gz = z[ground].astype(np.float64)
    guniq, ginv = np.unique(gidx, return_inverse=True)
    gsum = np.bincount(ginv, weights=gz).astype(np.float32)
    gcnt = np.bincount(ginv).astype(np.uint16)
    return uniq, zmax, guniq, gsum, gcnt


def process_batch(urls):
    with ThreadPoolExecutor(12) as ex:
        return list(ex.map(process_tile, urls))


def main():
    os.makedirs(WORK, exist_ok=True)
    paths = {k: os.path.join(WORK, k + ".npy") for k in ("dsm_max", "ground_sum", "ground_cnt")}
    done_path = os.path.join(WORK, "done_keys.json")

    if os.path.exists(done_path):
        done = set(json.load(open(done_path)))
        dsm = np.load(paths["dsm_max"])
        gsum = np.load(paths["ground_sum"])
        gcnt = np.load(paths["ground_cnt"])
        print(f"Resuming: {len(done)} tiles already processed", flush=True)
    else:
        done = set()
        dsm = np.full(NX * NY, np.nan, dtype=np.float32)
        gsum = np.zeros(NX * NY, dtype=np.float32)
        gcnt = np.zeros(NX * NY, dtype=np.uint16)

    ept = EPT()
    x0, y0 = lonlat_to_merc(LON_MIN, LAT_MIN)
    x1, y1 = lonlat_to_merc(LON_MAX, LAT_MAX)
    nodes = [(k, c) for k, c in ept.nodes_in_box((x0, y0, x1, y1)) if k not in done]
    total_pts = sum(c for _, c in nodes)
    print(f"{len(nodes)} tiles / {total_pts:,} points to process", flush=True)

    def checkpoint():
        np.save(paths["dsm_max"], dsm)
        np.save(paths["ground_sum"], gsum)
        np.save(paths["ground_cnt"], gcnt)
        json.dump(sorted(done), open(done_path, "w"))

    t0 = time.time()
    pts_done = 0
    batches = [nodes[i:i + 24] for i in range(0, len(nodes), 24)]
    since_ckpt = 0
    with ProcessPoolExecutor(4) as pool:
        for batch, results in zip(batches, pool.map(process_batch, [[ept.data_url(k) for k, _ in b] for b in batches])):
            for (key, cnt), res in zip(batch, results):
                if res is not None:
                    uniq, zmax, guniq, gs, gc = res
                    dsm[uniq] = np.fmax(dsm[uniq], zmax)
                    gsum[guniq] += gs
                    gcnt[guniq] += gc
                done.add(key)
                pts_done += cnt
                since_ckpt += 1
            if since_ckpt >= CHECKPOINT_EVERY:
                checkpoint()
                since_ckpt = 0
            el = time.time() - t0
            rate = pts_done / max(el, 1e-6)
            print(f"{len(done)} tiles, {pts_done / 1e6:,.0f}M / {total_pts / 1e6:,.0f}M pts, "
                  f"{rate / 1e6:.2f} Mpts/s, ETA {(total_pts - pts_done) / max(rate, 1) / 60:.0f} min", flush=True)
    checkpoint()
    print("Done.", flush=True)


if __name__ == "__main__":
    sys.exit(main())
