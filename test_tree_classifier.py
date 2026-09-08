import numpy as np
from PIL import Image

chm = np.load("data/lidar_chm_1024.npy")
intensity = np.load("data/lidar_intensity_1024.npy")
sat_img = Image.open("assets/satellite.jpg").convert("RGB").resize((1024, 1024))
sat_np = np.array(sat_img, dtype=np.float32)

r = sat_np[:, :, 0]
g = sat_np[:, :, 1]
b = sat_np[:, :, 2]
brightness = (r + g + b) / 3.0
exg = 2.0 * g - r - b

sh, sw = chm.shape

# Local maxima detection
pad = 2
padded_chm = np.pad(chm, pad, mode='constant', constant_values=0)
is_max = np.ones_like(chm, dtype=bool)

for dy in range(-pad, pad + 1):
    for dx in range(-pad, pad + 1):
        if dy == 0 and dx == 0:
            continue
        neighbor = padded_chm[pad + dy : pad + dy + sh, pad + dx : pad + dx + sw]
        is_max &= (chm >= neighbor)

candidate_mask = is_max & (chm >= 16.0)
y_indices, x_indices = np.where(candidate_mask)
print(f"Candidate tree peaks: {len(y_indices)}")

# Analyze variables for trees
h_list = []
sharp_list = []
inten_list = []
bright_list = []

for py, px in zip(y_indices, x_indices):
    h = chm[py, px]
    inten = intensity[py, px]
    br = brightness[py, px]
    
    # Measure crown steepness / sharpness in 3x3 window around peak:
    # Steep dropoff = conic spire (Fir); gentle dropoff = dome (Oak)
    y0 = max(0, py - 1)
    y1 = min(sh, py + 2)
    x0 = max(0, px - 1)
    x1 = min(sw, px + 2)
    window = chm[y0:y1, x0:x1]
    # Drop from peak to surrounding 8 neighbors
    drop = h - (np.sum(window) - h) / (window.size - 1)
    sharpness = drop / h # relative dropoff percentage (0.0 to 1.0)
    
    h_list.append(h)
    sharp_list.append(sharpness)
    inten_list.append(inten)
    bright_list.append(br)

h_arr = np.array(h_list)
sharp_arr = np.array(sharp_list)
inten_arr = np.array(inten_list)
bright_arr = np.array(bright_list)

print("--- Statistics ---")
print(f"Height: min={h_arr.min():.1f}, median={np.median(h_arr):.1f}, max={h_arr.max():.1f}")
print(f"Sharpness: min={sharp_arr.min():.2f}, median={np.median(sharp_arr):.2f}, max={sharp_arr.max():.2f}")
print(f"Intensity: min={inten_arr.min():.1f}, median={np.median(inten_arr):.1f}, max={inten_arr.max():.1f}")
print(f"Brightness: min={bright_arr.min():.1f}, median={np.median(bright_arr):.1f}, max={bright_arr.max():.1f}")

# Tall trees (>80 ft) vs Mid trees (25-50 ft)
tall_mask = h_arr >= 80.0
mid_mask = (h_arr >= 25.0) & (h_arr <= 50.0)

print("\n--- Comparison between Known Tall Conifers (>80 ft) vs Mid Canopy (25-50 ft) ---")
print(f"Tall Conifers (>80 ft) count: {np.count_nonzero(tall_mask)}")
print(f"  Sharpness mean: {sharp_arr[tall_mask].mean():.3f} (median: {np.median(sharp_arr[tall_mask]):.3f})")
print(f"  Intensity mean: {inten_arr[tall_mask].mean():.1f} (median: {np.median(inten_arr[tall_mask]):.1f})")
print(f"  Brightness mean: {bright_arr[tall_mask].mean():.1f} (median: {np.median(bright_arr[tall_mask]):.1f})")

print(f"\nMid Canopy (25-50 ft) count: {np.count_nonzero(mid_mask)}")
print(f"  Sharpness mean: {sharp_arr[mid_mask].mean():.3f} (median: {np.median(sharp_arr[mid_mask]):.3f})")
print(f"  Intensity mean: {inten_arr[mid_mask].mean():.1f} (median: {np.median(inten_arr[mid_mask]):.1f})")
print(f"  Brightness mean: {bright_arr[mid_mask].mean():.1f} (median: {np.median(bright_arr[mid_mask]):.1f})")
