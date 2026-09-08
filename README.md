# Trione-Annadel State Park • 3D Topographical Map

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live%20Map-brightgreen?style=for-the-badge&logo=github)](https://whaleord.github.io/annadel-3d-map/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)

> An interactive 3D topographical map and trail guide for Trione-Annadel State Park in Santa Rosa, California. Built with Three.js, real USGS 3DEP LiDAR elevation data, and Sonoma County Veg Map canopy models.

### [Explore Live 3D Map](https://whaleord.github.io/annadel-3d-map/)

![Annadel 3D Map Preview](og-preview.png)

---

## Highlights & Features

- **Real USGS 3DEP LiDAR Terrain**: 256x256 sampled elevation mesh derived directly from 1-meter USGS 3D Elevation Program data, covering Lake Ilsanjo, Bennett Mountain, Spring Lake, and the full park boundary.
- **27 Official Trails**: Complete vector trail networks extracted from OpenStreetMap, filtered to official California State Park routes, tagged by difficulty (Easy, Moderate, Challenging, Expert).
- **Interactive Trail Cards**: Select any trail to view distance (miles), elevation gain (feet), min/max elevation, and a description.
- **Real-Time Terrain Inspector**: Hover over any point on the terrain to inspect real-world elevation and GPS coordinates.
- **Dynamic Lighting & Sun Position**: Adjust time of day to simulate realistic solar hillshade angles across canyon valleys.
- **Multiple Basemap Styles**:
  - **Satellite Imagery**: True-color aerial photography.
  - **Topographic**: Contour line styling.
  - **Shaded Relief**: Monochrome physical terrain rendering.
  - **Slope Heatmap**: Gradient visualization identifying steep climbs versus flats.
- **Offline / Field Ready PWA**: Service Worker caching enables offline usage directly inside the park without cellular reception.
- **Mobile Responsive**: Full touch controls (orbit, pinch-to-zoom, two-finger pan) and collapsible menus optimized for phones and tablets.

---

## Project Structure

`
annadel-3d-map/
+-- index.html                 # Main web application entry point
+-- app.js                     # Three.js 3D scene, controls, trail rendering & HUD
+-- style.css                  # Dark glassmorphism UI & responsive mobile styles
+-- annadel_data.js            # Packaged bundle (terrain grid, vector trails, textures)
+-- annadel_standalone.html    # Single-file distribution (HTML + CSS + Three.js + data)
+-- manifest.json              # Web App Manifest for PWA installation
+-- sw.js                      # Offline service worker cache
+-- favicon.ico                # App icon
+-- og-preview.png             # Social share & Open Graph preview image
+-- libs/                      # Three.js r128 & OrbitControls
+-- assets/                    # Aerial & topographic texture source maps
+-- data/                      # Raw elevation, canopy & vector GeoJSON sources
+-- build_dataset.py           # Data pipeline & vector processing scripts
`

---

## Local Development

To run locally:

`ash
# Using Python
python server.py
# or
python -m http.server 8089
`

Then navigate to http://localhost:8089/ in your browser.
