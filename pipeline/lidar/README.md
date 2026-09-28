# LiDAR pipeline

Builds the terrain, textures and per-tree forest in `annadel_data.js` from the free
USGS 3DEP point cloud (`CA_NorthernCA_1_B22`, flown 2022) hosted on AWS.
No PDAL/GDAL needed: tiles are read straight from the public Entwine (EPT) bucket with `laspy`.

```bash
pip install -r requirements.txt
python 01_grid_lidar.py   # ~1.5 billion points streamed into 1 m rasters (~15-20 min, ~9 GB downloaded, nothing kept)
python 02_dem_chm.py      # bare-earth DEM + canopy height model
python 03_trees.py        # individual tree detection inside the park boundary
python 04_package.py      # writes ../../annadel_data.js
python ../../build_single_file.py   # optional: refresh annadel_standalone.html (run from repo root)
```

Large intermediates go in `work/` (gitignored, ~3 GB). Step 1 is resumable.

## Method

- **Rasters** (step 1-2): highest non-noise return per 1 m cell = surface; mean of ground-classified
  returns = bare earth. Ground gaps (under dense canopy, the lake) are filled from coarser averages.
  Canopy height = surface − ground, small laser pits filled.
- **Trees** (step 3): local maxima of the lightly smoothed canopy model, with a search window that grows
  with tree height (3–9 m), minimum height 5 m. Each top is grown into its crown with a watershed;
  crown radius comes from crown area. Only trees inside the OSM park boundary are kept.
- **Species** (step 3): conifer vs broadleaf from the Sonoma County Veg Map alliance polygons
  (`data/annadel_vegmap_alliances.npy`), falling back to height where no forest alliance is mapped.

## Known limits

- Dense oak/bay woodland with merged crowns is under-segmented (several trees become one wide crown);
  isolated trees and conifers come out well.
- A high-voltage line crosses the east side of the park. Its wires are unclassified in the source
  data; spans high over canyons are removed by a 62 m height cap, but lower spans can still leave a
  few false "trees" along the corridor.
- Species is the stand's alliance, not a per-tree identification.
