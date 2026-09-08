import math
import numpy as np
from PIL import Image
import json
import os

with open("data/terrain.json", "r") as f:
    orig_terrain = json.load(f)

# Let's inspect cropped_elev before resize or re-decode directly from elev_canvas
# In build_dataset.py, let's load or re-stitch correctly
