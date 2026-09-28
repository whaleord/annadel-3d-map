"""Step 2: turn the gridded point cloud into a bare-earth DEM and a canopy height model.

  dem_1m.npy  ground elevation (m), gaps (under dense canopy, water) filled from coarser levels
  chm_1m.npy  canopy height above ground (m), 0 where no vegetation
"""
import os

import numpy as np
from scipy import ndimage

from config import NX, NY, WORK

MAX_TREE_HEIGHT_M = 85.0  # taller "canopy" is wires, birds or noise


def pyramid_fill(grid):
    """Fill NaNs by averaging valid cells at successively coarser resolutions."""
    levels = [grid]
    while min(levels[-1].shape) > 4 and np.isnan(levels[-1]).any():
        g = levels[-1]
        h, w = (g.shape[0] + 1) // 2 * 2, (g.shape[1] + 1) // 2 * 2
        p = np.full((h, w), np.nan, dtype=np.float32)
        p[:g.shape[0], :g.shape[1]] = g
        blocks = p.reshape(h // 2, 2, w // 2, 2)
        valid = ~np.isnan(blocks)
        s = np.where(valid, blocks, 0).sum(axis=(1, 3))
        c = valid.sum(axis=(1, 3))
        levels.append(np.where(c > 0, s / np.maximum(c, 1), np.nan).astype(np.float32))
    for i in range(len(levels) - 2, -1, -1):
        fine, coarse = levels[i], levels[i + 1]
        up = np.repeat(np.repeat(coarse, 2, axis=0), 2, axis=1)[:fine.shape[0], :fine.shape[1]]
        holes = np.isnan(fine)
        fine[holes] = up[holes]
    return levels[0]


def main():
    gsum = np.load(os.path.join(WORK, "ground_sum.npy")).reshape(NY, NX)
    gcnt = np.load(os.path.join(WORK, "ground_cnt.npy")).reshape(NY, NX)
    dsm = np.load(os.path.join(WORK, "dsm_max.npy")).reshape(NY, NX)

    dem = np.where(gcnt > 0, gsum / np.maximum(gcnt, 1), np.nan).astype(np.float32)
    del gsum
    print(f"Ground coverage: {np.count_nonzero(gcnt) / gcnt.size * 100:.1f}% of 1 m cells", flush=True)
    del gcnt
    dem = pyramid_fill(dem)
    # Light smoothing hides the seams between measured and filled cells
    dem = ndimage.gaussian_filter(dem, 0.8).astype(np.float32)
    np.save(os.path.join(WORK, "dem_1m.npy"), dem)
    print(f"DEM: {dem.min():.1f} .. {dem.max():.1f} m", flush=True)

    print(f"Surface coverage: {np.count_nonzero(~np.isnan(dsm)) / dsm.size * 100:.1f}% of 1 m cells", flush=True)
    chm = np.nan_to_num(dsm - dem, nan=0.0)
    del dsm
    chm[(chm < 0) | (chm > MAX_TREE_HEIGHT_M)] = 0.0
    # Pit filling: a single empty cell inside a crown is a laser gap, not a hole in the tree
    closed = ndimage.grey_closing(chm, size=(3, 3))
    pits = (closed - chm) > 2.0
    chm[pits] = closed[pits]
    np.save(os.path.join(WORK, "chm_1m.npy"), chm.astype(np.float32))
    print(f"CHM: {np.count_nonzero(chm > 2) / chm.size * 100:.1f}% of cells above 2 m, max {chm.max():.1f} m", flush=True)


if __name__ == "__main__":
    main()
