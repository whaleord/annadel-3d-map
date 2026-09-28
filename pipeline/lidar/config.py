"""Shared settings for the LiDAR pipeline. Map extent matches the web app's terrain bounds."""
import os

LAT_MIN, LAT_MAX = 38.390, 38.460
LON_MIN, LON_MAX = -122.670, -122.570

# ~1 m cells: 0.1 deg lon = 8,720 m and 0.07 deg lat = 7,774 m at this latitude
NX, NY = 8720, 7774
CELL_X_M = 8720.0 / NX
CELL_Y_M = 7774.0 / NY

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "work")          # large intermediates (gitignored)
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
