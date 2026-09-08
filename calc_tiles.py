import math

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

for z in [12, 13, 14]:
    x1, y1 = deg2num(38.460, -122.665, z)
    x2, y2 = deg2num(38.390, -122.570, z)
    print(f"Zoom {z}: X range {x1} to {x2} (span {x2-x1+1}), Y range {y1} to {y2} (span {y2-y1+1}), total tiles: {(x2-x1+1)*(y2-y1+1)}")
