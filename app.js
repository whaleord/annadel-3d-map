// Trione-Annadel State Park in 3D
// Terrain and every tree come from 2022 USGS 3DEP LiDAR (see pipeline/lidar).
// The map itself is look-only: nothing on it is clickable and the camera only moves when you
// drag it or press a button in the panel.

(function () {
  const data = window.ANNADEL_DATA;
  if (!data) {
    document.querySelector('.loading-sub').textContent = 'Map data failed to load.';
    return;
  }

  const features = data.features;
  const terrainData = data.terrain;
  const bounds = terrainData.bounds;
  const params = new URLSearchParams(window.location.search);
  const IS_TOUCH = window.matchMedia('(pointer: coarse)').matches;
  const M_TO_FT = 3.28084;

  function decodeBase64(b64) {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes.buffer;
  }

  // ---------------------------------------------------------------------------
  // World scale: the map is 100 units wide (8,720 m); +y is up, +z is south
  // ---------------------------------------------------------------------------
  const MAP_WIDTH = 100.0;
  const MAP_DEPTH = 89.1;
  const GROUND_WIDTH_M = 8720.0;
  const WORLD_PER_M = MAP_WIDTH / GROUND_WIDTH_M;
  const RES = terrainData.grid_res;
  const MIN_ELEV_M = terrainData.min_elevation_m;

  const elevDm = new Uint16Array(decodeBase64(terrainData.elev_dm_b64));
  const elevations = new Float32Array(elevDm.length);
  for (let i = 0; i < elevDm.length; i++) elevations[i] = elevDm[i] / 10.0;

  let exaggeration = 1.5;

  // Bilinear ground elevation (m) at map coordinates u (west->east), v (north->south) in [0, 1]
  function elevAt(u, v) {
    const gx = Math.max(0, Math.min(1, u)) * (RES - 1);
    const gy = Math.max(0, Math.min(1, v)) * (RES - 1);
    const x0 = Math.floor(gx), y0 = Math.floor(gy);
    const x1 = Math.min(RES - 1, x0 + 1), y1 = Math.min(RES - 1, y0 + 1);
    const dx = gx - x0, dy = gy - y0;
    const top = elevations[y0 * RES + x0] * (1 - dx) + elevations[y0 * RES + x1] * dx;
    const bot = elevations[y1 * RES + x0] * (1 - dx) + elevations[y1 * RES + x1] * dx;
    return top * (1 - dy) + bot * dy;
  }

  // World y of an elevation, before vertical exaggeration
  function baseY(elevM) {
    return (elevM - MIN_ELEV_M) * WORLD_PER_M;
  }

  const uToX = u => (u - 0.5) * MAP_WIDTH;
  const vToZ = v => (v - 0.5) * MAP_DEPTH;

  // ---------------------------------------------------------------------------
  // Renderer, camera, controls. Frames are only drawn when something changed.
  // ---------------------------------------------------------------------------
  const container = document.getElementById('canvas-container');
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  // Proper colour management: textures are decoded from sRGB, lit in linear space, re-encoded on output
  renderer.outputEncoding = THREE.sRGBEncoding;
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0d1117);
  scene.fog = new THREE.FogExp2(0x0d1117, 0.0028);

  const camera = new THREE.PerspectiveCamera(42, window.innerWidth / window.innerHeight, 0.05, 600);
  camera.position.set(8, 70, 88);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.15;
  controls.maxPolarAngle = Math.PI / 2 - 0.05;
  controls.minDistance = 1.5;
  controls.maxDistance = 320;
  controls.target.set(4, 4, 0);

  let needsRender = true;
  const requestRender = () => { needsRender = true; };
  controls.addEventListener('change', requestRender);

  // ---------------------------------------------------------------------------
  // Lighting: the real sun over Annadel for a chosen season and time of day
  // ---------------------------------------------------------------------------
  const linear = hex => new THREE.Color(hex).convertSRGBToLinear();
  const BG = new THREE.Color(0x0d1117);  // clear colour is written as-is
  const hemi = new THREE.HemisphereLight(0xffffff, 0xffffff, 0.5);
  const sun = new THREE.DirectionalLight(0xffffff, 2.0);
  sun.castShadow = true;
  const SHADOW_RES = IS_TOUCH ? 2048 : 4096;
  sun.shadow.mapSize.set(SHADOW_RES, SHADOW_RES);
  sun.shadow.bias = -0.0002;
  scene.add(hemi, sun, sun.target);
  const sunDir = new THREE.Vector3(0, 1, 0);

  const LAT = 38.425 * Math.PI / 180, LON = -122.62;
  // Day of year and UTC offset (clock time incl. daylight saving)
  const SEASONS = { winter: [355, -8], equinox: [80, -7], summer: [172, -7] };
  let season = 'summer';

  // NOAA solar position approximation. Returns elevation and azimuth (clockwise from north), radians.
  function solarPosition(doy, hours, tz) {
    const g = 2 * Math.PI / 365 * (doy - 1 + (hours - 12) / 24);
    const eqTime = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g)
      - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
    const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g)
      + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
    const trueSolarMin = hours * 60 + eqTime + 4 * LON - 60 * tz;
    const ha = (trueSolarMin / 4 - 180) * Math.PI / 180;
    const el = Math.asin(Math.sin(LAT) * Math.sin(decl) + Math.cos(LAT) * Math.cos(decl) * Math.cos(ha));
    const az = Math.atan2(Math.sin(ha), Math.cos(ha) * Math.sin(LAT) - Math.tan(decl) * Math.cos(LAT)) + Math.PI;
    return { el, az };
  }

  function daylight(doy, tz) {
    let rise = 12, set = 12;
    for (let h = 12; h > 3; h -= 1 / 60) if (solarPosition(doy, h, tz).el > 0) rise = h;
    for (let h = 12; h < 22; h += 1 / 60) if (solarPosition(doy, h, tz).el > 0) set = h;
    return [rise, set];
  }

  const SKY_DAY = linear(0xbcd4ee), SKY_LOW = linear(0xf4b98a);
  const GROUND_DAY = linear(0x4a4234), GROUND_LOW = linear(0x3a2c2a);
  const BG_LOW = new THREE.Color(0x19141c);
  const fogColor = new THREE.Color();

  // p: 0 = just after sunrise ... 100 = just before sunset
  function setSun(p) {
    const [doy, tz] = SEASONS[season];
    const [rise, set] = daylight(doy, tz);
    const hours = rise + 0.2 + (p / 100) * (set - rise - 0.4);
    const { el, az } = solarPosition(doy, hours, tz);
    sunDir.set(Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el));

    const elDeg = el * 180 / Math.PI;
    const low = THREE.MathUtils.clamp(1 - (elDeg - 3) / 27, 0, 1);  // 1 near the horizon, 0 above 30 deg
    sun.color.setRGB(1, 1 - 0.3 * low, 1 - 0.6 * low);
    sun.intensity = 1.0 + 0.8 * Math.min(1, elDeg / 35);
    hemi.color.copy(SKY_DAY).lerp(SKY_LOW, 0.55 * low);
    hemi.groundColor.copy(GROUND_DAY).lerp(GROUND_LOW, low);
    hemi.intensity = 0.55 + 0.15 * Math.min(1, elDeg / 30);
    scene.background.copy(BG).lerp(BG_LOW, 0.7 * low);
    scene.fog.color.copy(fogColor.copy(scene.background).convertSRGBToLinear());

    const clock = Math.round(hours * 60);
    const h = Math.floor(clock / 60), m = clock % 60;
    document.getElementById('sun-val').textContent =
      `${((h + 11) % 12) + 1}:${String(m).padStart(2, '0')} ${h < 12 ? 'am' : 'pm'}`;
    requestRender();
  }

  // ---------------------------------------------------------------------------
  // Terrain materials
  // ---------------------------------------------------------------------------
  const loader = new THREE.TextureLoader();
  function loadTexture(uri) {
    const t = loader.load(uri, requestRender);
    t.encoding = THREE.sRGBEncoding;
    t.anisotropy = renderer.capabilities.getMaxAnisotropy();
    return t;
  }

  function slopeTexture() {
    const N = 1024;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = N;
    const ctx = canvas.getContext('2d');
    const img = ctx.createImageData(N, N);
    const d = 1 / N;
    const stops = [[0, [34, 197, 94]], [12, [234, 179, 8]], [25, [249, 115, 22]], [35, [239, 68, 68]]];
    for (let y = 0; y < N; y++) {
      for (let x = 0; x < N; x++) {
        const u = x / N, v = y / N;
        const gx = (elevAt(u + d, v) - elevAt(u - d, v)) / (2 * d * GROUND_WIDTH_M);
        const gz = (elevAt(u, v + d) - elevAt(u, v - d)) / (2 * d * GROUND_WIDTH_M * MAP_DEPTH / MAP_WIDTH);
        const deg = Math.atan(Math.hypot(gx, gz)) * 180 / Math.PI;
        let k = 0;
        while (k < stops.length - 2 && deg > stops[k + 1][0]) k++;
        const [d0, c0] = stops[k], [d1, c1] = stops[k + 1];
        const t = Math.max(0, Math.min(1, (deg - d0) / (d1 - d0)));
        const i = (y * N + x) * 4;
        img.data[i] = c0[0] + t * (c1[0] - c0[0]);
        img.data[i + 1] = c0[1] + t * (c1[1] - c0[1]);
        img.data[i + 2] = c0[2] + t * (c1[2] - c0[2]);
        img.data[i + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    const tex = new THREE.CanvasTexture(canvas);
    tex.encoding = THREE.sRGBEncoding;
    tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
    return tex;
  }

  const materials = {
    satellite: new THREE.MeshStandardMaterial({ map: loadTexture(data.textures.satellite), roughness: 0.9, metalness: 0 }),
    relief: new THREE.MeshStandardMaterial({ map: loadTexture(data.textures.relief), roughness: 0.8, metalness: 0 }),
    topographic: new THREE.MeshStandardMaterial({ map: loadTexture(data.textures.topographic), roughness: 0.85, metalness: 0 }),
    slope: null  // built on first use
  };

  // ---------------------------------------------------------------------------
  // Everything draped on the terrain lives in one group; vertical exaggeration is its y scale
  // ---------------------------------------------------------------------------
  const draped = new THREE.Group();
  scene.add(draped);

  const MESH_RES = IS_TOUCH ? 512 : 768;
  const terrainGeo = new THREE.PlaneGeometry(MAP_WIDTH, MAP_DEPTH, MESH_RES - 1, MESH_RES - 1);
  terrainGeo.rotateX(-Math.PI / 2);
  {
    const pos = terrainGeo.attributes.position;
    for (let y = 0, i = 0; y < MESH_RES; y++) {
      for (let x = 0; x < MESH_RES; x++, i++) {
        pos.setY(i, baseY(elevAt(x / (MESH_RES - 1), y / (MESH_RES - 1))));
      }
    }
    terrainGeo.computeVertexNormals();
  }
  const terrain = new THREE.Mesh(terrainGeo, materials.satellite);
  terrain.receiveShadow = true;
  terrain.castShadow = true;
  draped.add(terrain);

  // Base block under the terrain
  {
    const mat = new THREE.MeshStandardMaterial({ color: linear(0x1a202b), roughness: 0.8, metalness: 0.2, side: THREE.DoubleSide });
    const BOTTOM = -3.5;
    const wall = (fixedU, fixedV) => {
      const verts = [], idx = [];
      for (let i = 0; i < MESH_RES; i++) {
        const t = i / (MESH_RES - 1);
        const u = fixedU === null ? t : fixedU;
        const v = fixedV === null ? t : fixedV;
        verts.push(uToX(u), baseY(elevAt(u, v)), vToZ(v), uToX(u), BOTTOM, vToZ(v));
        if (i < MESH_RES - 1) idx.push(2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 2, 2 * i + 1, 2 * i + 3);
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
      g.setIndex(idx);
      g.computeVertexNormals();
      return new THREE.Mesh(g, mat);
    };
    draped.add(wall(null, 0), wall(null, 1), wall(0, null), wall(1, null));
    const plate = new THREE.PlaneGeometry(MAP_WIDTH, MAP_DEPTH);
    plate.rotateX(Math.PI / 2);
    plate.translate(0, BOTTOM, 0);
    draped.add(new THREE.Mesh(plate, mat));
  }

  // Lake Ilsanjo
  const waterGroup = new THREE.Group();
  features.water_bodies.forEach(wb => {
    const shape = new THREE.Shape(wb.polygon.map(p => new THREE.Vector2(uToX(p.u), -vToZ(p.v))));
    const g = new THREE.ShapeGeometry(shape);
    g.rotateX(-Math.PI / 2);
    const mesh = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
      color: linear(0x1d6f95), roughness: 0.15, metalness: 0.2, transparent: true, opacity: 0.9
    }));
    mesh.position.y = baseY(wb.surface_m) + 0.01;
    mesh.receiveShadow = true;
    waterGroup.add(mesh);
  });
  draped.add(waterGroup);

  // Park boundary
  const boundaryGroup = new THREE.Group();
  {
    const pts = features.boundary.map(p => new THREE.Vector3(uToX(p.u), baseY(elevAt(p.u, p.v)) + 0.08, vToZ(p.v)));
    pts.push(pts[0].clone());
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineDashedMaterial({ color: linear(0xf5c451), dashSize: 0.6, gapSize: 0.4, transparent: true, opacity: 0.8 }));
    line.computeLineDistances();
    boundaryGroup.add(line);
  }
  draped.add(boundaryGroup);

  // Trails
  const DIFFICULTY = {
    'Easy': 0x4ade80, 'Easy to Moderate': 0x4ade80,
    'Moderate': 0x60a5fa, 'Moderate to Challenging': 0xfbbf24,
    'Challenging': 0xfbbf24, 'Strenuous': 0xf87171, 'Expert / Strenuous': 0xf87171
  };
  const trailColor = t => DIFFICULTY[t.difficulty] || 0x60a5fa;
  const cssColor = hex => '#' + hex.toString(16).padStart(6, '0');

  const trailsGroup = new THREE.Group();
  const trailLines = new Map();  // trail -> [THREE.Line]
  features.trails.forEach(tr => {
    const mat = new THREE.LineBasicMaterial({ color: linear(trailColor(tr)), transparent: true, opacity: 0.9 });
    const lines = tr.lines.map(seg => {
      const pts = seg.map(p => new THREE.Vector3(uToX(p.u), baseY(elevAt(p.u, p.v)) + 0.1, vToZ(p.v)));
      return new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat);
    });
    lines.forEach(l => trailsGroup.add(l));
    trailLines.set(tr, lines);
  });
  draped.add(trailsGroup);

  // A thick highlight for the selected trail
  let highlight = null;
  function setHighlight(trail) {
    if (highlight) {
      draped.remove(highlight);
      highlight.traverse(o => o.geometry && o.geometry.dispose());
      highlight = null;
    }
    if (!trail) return;
    highlight = new THREE.Group();
    const mat = new THREE.MeshBasicMaterial({ color: linear(0xfde047) });
    trail.lines.forEach(seg => {
      const pts = seg.map(p => new THREE.Vector3(uToX(p.u), baseY(elevAt(p.u, p.v)) + 0.12, vToZ(p.v)));
      if (pts.length < 2) return;
      const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
      highlight.add(new THREE.Mesh(new THREE.TubeGeometry(curve, pts.length * 3, 0.07, 5, false), mat));
    });
    draped.add(highlight);
  }

  // ---------------------------------------------------------------------------
  // Trees: every tree from the LiDAR canopy model, at true size (not exaggerated)
  // Record layout (8 bytes): u uint16, v uint16, height dm uint16, crown radius dm uint8, kind uint8
  // ---------------------------------------------------------------------------
  const treeBytes = new DataView(decodeBase64(data.trees.b64));
  const TREE_COUNT = data.trees.count;
  const treeU = new Float32Array(TREE_COUNT), treeV = new Float32Array(TREE_COUNT);
  const treeH = new Float32Array(TREE_COUNT), treeR = new Float32Array(TREE_COUNT);
  const treeKind = new Uint8Array(TREE_COUNT);  // 0 conifer, 1 broadleaf
  for (let i = 0; i < TREE_COUNT; i++) {
    const o = i * 8;
    treeU[i] = treeBytes.getUint16(o, true) / 65535;
    treeV[i] = treeBytes.getUint16(o + 2, true) / 65535;
    treeH[i] = treeBytes.getUint16(o + 4, true) / 10;
    treeR[i] = treeBytes.getUint8(o + 6) / 10;
    treeKind[i] = treeBytes.getUint8(o + 7);
  }

  const coniferGeo = new THREE.ConeGeometry(1, 0.85, 7, 1, true);
  coniferGeo.translate(0, 0.15 + 0.425, 0);
  const broadleafGeo = new THREE.IcosahedronGeometry(1, 0);
  broadleafGeo.scale(1, 0.4, 1);
  broadleafGeo.translate(0, 0.6, 0);
  // Crowns are darker underneath, like light filtering through foliage
  [coniferGeo, broadleafGeo].forEach(g => {
    const pos = g.attributes.position;
    g.computeBoundingBox();
    const { min, max } = g.boundingBox;
    const col = new Float32Array(pos.count * 3);
    for (let i = 0; i < pos.count; i++) {
      const k = 0.62 + 0.45 * (pos.getY(i) - min.y) / (max.y - min.y);
      col[3 * i] = col[3 * i + 1] = col[3 * i + 2] = k;
    }
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  });

  const treesGroup = new THREE.Group();
  const byKind = [[], []];
  for (let i = 0; i < TREE_COUNT; i++) byKind[treeKind[i]].push(i);
  const treeMeshes = [[coniferGeo, 0x33704a], [broadleafGeo, 0x6f8f38]].map(([geo, base], k) => {
    const mesh = new THREE.InstancedMesh(geo,
      new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.9, metalness: 0, flatShading: true, vertexColors: true }),
      Math.max(1, byKind[k].length));
    mesh.count = byKind[k].length;
    mesh.receiveShadow = true;
    // Trees cast shadows only when zoomed in (see updateShadowFrame)
    mesh.castShadow = false;
    const c = new THREE.Color();
    const baseColor = linear(base);
    byKind[k].forEach((t, j) => {
      c.copy(baseColor).multiplyScalar(0.82 + 0.3 * (((t * 2654435761) >>> 0) % 1000) / 1000);
      mesh.setColorAt(j, c);
    });
    treesGroup.add(mesh);
    return mesh;
  });
  scene.add(treesGroup);

  const dummy = new THREE.Object3D();
  function placeTrees() {
    treeMeshes.forEach((mesh, k) => {
      byKind[k].forEach((i, j) => {
        // Sunk 1 m so the base sits in the interpolated ground on slopes
        dummy.position.set(uToX(treeU[i]), baseY(elevAt(treeU[i], treeV[i])) * exaggeration - WORLD_PER_M, vToZ(treeV[i]));
        dummy.rotation.y = (i * 0.73) % (Math.PI * 2);
        const r = Math.max(treeR[i], 1.0) * WORLD_PER_M;
        dummy.scale.set(r, treeH[i] * WORLD_PER_M, r);
        dummy.updateMatrix();
        mesh.setMatrixAt(j, dummy.matrix);
      });
      mesh.instanceMatrix.needsUpdate = true;
    });
    requestRender();
  }

  // Spatial index for "what tree is under the cursor"
  const GRID = 200;
  const cellStart = new Uint32Array(GRID * GRID + 1);
  const cellItems = new Uint32Array(TREE_COUNT);
  const cellOf = (u, v) => Math.min(GRID - 1, Math.max(0, Math.floor(v * GRID))) * GRID + Math.min(GRID - 1, Math.max(0, Math.floor(u * GRID)));
  for (let i = 0; i < TREE_COUNT; i++) cellStart[cellOf(treeU[i], treeV[i]) + 1]++;
  for (let c = 0; c < GRID * GRID; c++) cellStart[c + 1] += cellStart[c];
  {
    const fill = cellStart.slice(0, GRID * GRID);
    for (let i = 0; i < TREE_COUNT; i++) cellItems[fill[cellOf(treeU[i], treeV[i])]++] = i;
  }
  function treeAt(u, v) {
    const col = Math.floor(u * GRID), row = Math.floor(v * GRID);
    let best = -1, bestScore = 1;
    for (let r = Math.max(0, row - 1); r <= Math.min(GRID - 1, row + 1); r++) {
      for (let c = Math.max(0, col - 1); c <= Math.min(GRID - 1, col + 1); c++) {
        const cell = r * GRID + c;
        for (let n = cellStart[cell]; n < cellStart[cell + 1]; n++) {
          const i = cellItems[n];
          const dxM = (treeU[i] - u) * GROUND_WIDTH_M;
          const dzM = (treeV[i] - v) * GROUND_WIDTH_M * MAP_DEPTH / MAP_WIDTH;
          const crown = Math.max(treeR[i], 2.0);
          const score = (dxM * dxM + dzM * dzM) / (crown * crown);
          if (score < bestScore) { bestScore = score; best = i; }
        }
      }
    }
    return best;
  }

  // ---------------------------------------------------------------------------
  // Transmission line: towers and three conductors following the measured wire height
  // ---------------------------------------------------------------------------
  const powerGroup = new THREE.Group();
  scene.add(powerGroup);
  const wireProfile = features.powerline ? features.powerline.wire : [];
  const towerSites = features.powerline ? features.powerline.towers : [];
  const CONDUCTOR_OFFSETS_M = [-6, 0, 6];

  // Unit lattice tower (metres): 4 legs tapering from 8 m to 2.4 m, braced, with a crossarm
  function towerGeometry(armHeight) {
    const top = armHeight + 5;
    const levels = [0, 0.2, 0.4, 0.6, 0.8, 1].map(f => f * armHeight);
    const half = y => 4 - (y / armHeight) * 2.8;
    const corners = y => { const h = half(y); return [[-h, -h], [h, -h], [h, h], [-h, h]]; };
    const seg = [];
    const push = (a, b) => seg.push(a[0], a[1], a[2], b[0], b[1], b[2]);
    for (let l = 0; l < levels.length - 1; l++) {
      const y0 = levels[l], y1 = levels[l + 1];
      const c0 = corners(y0), c1 = corners(y1);
      for (let k = 0; k < 4; k++) {
        const a0 = [c0[k][0], y0, c0[k][1]], b0 = [c0[(k + 1) % 4][0], y0, c0[(k + 1) % 4][1]];
        const a1 = [c1[k][0], y1, c1[k][1]], b1 = [c1[(k + 1) % 4][0], y1, c1[(k + 1) % 4][1]];
        push(a0, a1);          // leg
        push(a1, b1);          // ring
        push(a0, b1);          // cross brace
        push(b0, a1);
      }
    }
    const h = half(armHeight);
    // Crossarm (across the line = local x), peak and arm stays
    push([-7.5, armHeight, 0], [7.5, armHeight, 0]);
    push([-7.5, armHeight, 0], [0, top, 0]);
    push([7.5, armHeight, 0], [0, top, 0]);
    push([-h, armHeight, -h], [0, top, 0]);
    push([h, armHeight, h], [0, top, 0]);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(seg, 3));
    return g;
  }

  const towerMat = new THREE.LineBasicMaterial({ color: linear(0xaab2bd) });
  const wireMat = new THREE.LineBasicMaterial({ color: linear(0xd8dde4), transparent: true, opacity: 0.85 });

  function buildPowerLine() {
    powerGroup.children.forEach(o => o.geometry.dispose());
    powerGroup.clear();
    if (wireProfile.length < 2) return;

    // Per-sample position, height above ground (m) and across-line direction
    const n = wireProfile.length;
    const across = [];
    for (let i = 0; i < n; i++) {
      const a = wireProfile[Math.max(0, i - 2)], b = wireProfile[Math.min(n - 1, i + 2)];
      const dx = uToX(b[0]) - uToX(a[0]), dz = vToZ(b[1]) - vToZ(a[1]);
      const len = Math.hypot(dx, dz) || 1;
      across.push([-dz / len, dx / len]);
    }
    const heightAbove = wireProfile.map(p => p[3] - p[2]);
    const worldPoint = (i, offsetM, extraM = 0) => {
      const [u, v] = wireProfile[i];
      const y = baseY(elevAt(u, v)) * exaggeration + (heightAbove[i] + extraM) * WORLD_PER_M;
      return new THREE.Vector3(uToX(u) + across[i][0] * offsetM * WORLD_PER_M, y, vToZ(v) + across[i][1] * offsetM * WORLD_PER_M);
    };

    CONDUCTOR_OFFSETS_M.forEach(off => {
      const pts = [];
      for (let i = 0; i < n; i++) pts.push(worldPoint(i, off));
      powerGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), wireMat));
    });

    // Towers stand where the wires attach: crossarm at the measured wire height there
    towerSites.forEach(([u, v]) => {
      let nearest = 0, bestD = Infinity;
      for (let i = 0; i < n; i++) {
        const d = (wireProfile[i][0] - u) ** 2 + (wireProfile[i][1] - v) ** 2;
        if (d < bestD) { bestD = d; nearest = i; }
      }
      const armM = Math.max(12, heightAbove[nearest]);
      const tower = new THREE.LineSegments(towerGeometry(armM), towerMat);
      const [pu, pv] = wireProfile[nearest];
      tower.position.set(uToX(pu), baseY(elevAt(pu, pv)) * exaggeration, vToZ(pv));
      tower.scale.setScalar(WORLD_PER_M);
      tower.rotation.y = -Math.atan2(across[nearest][1], across[nearest][0]);
      powerGroup.add(tower);
    });
    requestRender();
  }

  // ---------------------------------------------------------------------------
  // Vertical exaggeration
  // ---------------------------------------------------------------------------
  let treeTimer = null;
  function setExaggeration(e, immediate) {
    exaggeration = e;
    draped.scale.y = e;
    buildPowerLine();
    document.getElementById('exag-val').textContent = `${e.toFixed(1)}×`;
    // Trees are true-scale, so they are re-seated on the ground rather than stretched.
    // While dragging they are hidden and re-placed once the slider settles.
    clearTimeout(treeTimer);
    if (immediate) {
      placeTrees();
    } else {
      treesGroup.visible = false;
      treeTimer = setTimeout(() => {
        placeTrees();
        treesGroup.visible = document.getElementById('layer-trees').checked;
        requestRender();
      }, 150);
    }
    requestRender();
  }

  // ---------------------------------------------------------------------------
  // Trail name labels (optional layer)
  // ---------------------------------------------------------------------------
  const labelsContainer = document.getElementById('labels-container');
  const trailLabels = features.trails.filter(t => t.label_pos).map(t => {
    const el = document.createElement('div');
    el.className = 'map-label';
    el.textContent = t.name;
    labelsContainer.appendChild(el);
    return { trail: t, el };
  });
  let showLabels = false;
  let selectedTrail = null;
  const tmpV = new THREE.Vector3();

  function updateLabels() {
    const w = window.innerWidth, h = window.innerHeight;
    trailLabels.forEach(({ trail, el }) => {
      const selected = trail === selectedTrail;
      if (!(showLabels && trailsGroup.visible) && !selected) { el.style.display = 'none'; return; }
      const p = trail.label_pos;
      tmpV.set(uToX(p.u), baseY(elevAt(p.u, p.v)) * exaggeration + 0.3, vToZ(p.v)).project(camera);
      if (tmpV.z > 1 || Math.abs(tmpV.x) > 1.05 || Math.abs(tmpV.y) > 1.05) { el.style.display = 'none'; return; }
      el.style.display = 'block';
      el.style.left = `${(tmpV.x * 0.5 + 0.5) * w}px`;
      el.style.top = `${(-tmpV.y * 0.5 + 0.5) * h}px`;
      el.classList.toggle('selected', selected);
    });
  }

  // ---------------------------------------------------------------------------
  // Readout: what's under the pointer (hover on desktop, tap on touch). Never moves the camera.
  // ---------------------------------------------------------------------------
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const readMain = document.getElementById('readout-main');
  const readSub = document.getElementById('readout-sub');
  let pendingPointer = null;

  function describeTree(i) {
    const kind = treeKind[i] === 0 ? 'Conifer (Douglas-fir / redwood)' : 'Broadleaf (oak / bay / madrone)';
    return `${kind} · ${Math.round(treeH[i] * M_TO_FT)} ft tall · ${Math.round(treeR[i] * 2 * M_TO_FT)} ft crown`;
  }

  function inspect(clientX, clientY) {
    pointer.set((clientX / window.innerWidth) * 2 - 1, -(clientY / window.innerHeight) * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObject(terrain)[0];
    if (!hit) {
      readMain.textContent = IS_TOUCH ? 'Tap the map' : 'Hover the map';
      readSub.textContent = '';
      return;
    }
    const u = hit.point.x / MAP_WIDTH + 0.5, v = hit.point.z / MAP_DEPTH + 0.5;
    const lat = bounds.lat_max - v * (bounds.lat_max - bounds.lat_min);
    const lon = bounds.lon_min + u * (bounds.lon_max - bounds.lon_min);
    const e = elevAt(u, v);
    readMain.textContent = `${Math.round(e * M_TO_FT).toLocaleString()} ft  ·  ${lat.toFixed(4)}° N, ${Math.abs(lon).toFixed(4)}° W`;
    const t = treesGroup.visible ? treeAt(u, v) : -1;
    readSub.textContent = t >= 0 ? describeTree(t) : '';
  }

  if (!IS_TOUCH) {
    renderer.domElement.addEventListener('pointermove', e => {
      if (e.buttons) return;  // dragging: the readout would just flicker
      pendingPointer = [e.clientX, e.clientY];
    });
    renderer.domElement.addEventListener('pointerleave', () => { pendingPointer = null; });
  } else {
    readMain.textContent = 'Tap the map';
    let down = null;
    renderer.domElement.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY, performance.now()]; });
    renderer.domElement.addEventListener('pointerup', e => {
      if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 8 && performance.now() - down[2] < 400) {
        inspect(e.clientX, e.clientY);
      }
      down = null;
    });
  }

  // ---------------------------------------------------------------------------
  // Camera moves: only from panel buttons, and cancelled the moment you touch the map
  // ---------------------------------------------------------------------------
  let flight = null;
  function flyTo(position, target, ms = 1100) {
    if (flight) cancelAnimationFrame(flight);
    if (ms <= 0) {
      camera.position.copy(position);
      controls.target.copy(target);
      controls.update();
      requestRender();
      return;
    }
    const p0 = camera.position.clone(), t0 = controls.target.clone(), start = performance.now();
    const step = now => {
      const k = Math.min(1, (now - start) / ms);
      const e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      camera.position.lerpVectors(p0, position, e);
      controls.target.lerpVectors(t0, target, e);
      controls.update();
      requestRender();
      flight = k < 1 ? requestAnimationFrame(step) : null;
    };
    flight = requestAnimationFrame(step);
  }
  controls.addEventListener('start', () => { if (flight) { cancelAnimationFrame(flight); flight = null; } });

  function groundPoint(u, v) {
    return new THREE.Vector3(uToX(u), baseY(elevAt(u, v)) * exaggeration, vToZ(v));
  }

  // [u, v, camera offset x, y, z] in world units relative to the ground point
  const VIEWS = {
    overview: [0.5, 0.5, 0, 72, 84],
    ilsanjo: [0.42, 0.45, -9, 11, 14],
    bennett: [0.46, 0.66, 9, 12, 12],
    canyon: [0.25, 0.35, -11, 11, 12],
    lawndale: [0.76, 0.6, 13, 10, 10]
  };
  function setView(name, ms) {
    const v = VIEWS[name];
    if (!v) return;
    const target = name === 'overview' ? new THREE.Vector3(0, 3, 0) : groundPoint(v[0], v[1]);
    // Portrait screens need to stand further back to fit the same ground in view
    const fit = name === 'overview' ? Math.max(1, 1.25 / camera.aspect) : 1;
    flyTo(target.clone().add(new THREE.Vector3(v[2], v[3], v[4]).multiplyScalar(fit)), target, ms);
  }

  function zoomToTrail(trail) {
    const box = new THREE.Box3();
    trail.lines.forEach(seg => seg.forEach(p => box.expandByPoint(groundPoint(p.u, p.v))));
    const center = box.getCenter(new THREE.Vector3());
    const size = Math.max(box.max.x - box.min.x, box.max.z - box.min.z, 4);
    const dir = camera.position.clone().sub(controls.target).setY(0);
    if (dir.lengthSq() < 1e-6) dir.set(0, 0, 1);
    dir.normalize().multiplyScalar(size * 0.9);
    flyTo(center.clone().add(new THREE.Vector3(dir.x, size * 0.9, dir.z)), center);
  }

  function faceNorth() {
    const offset = camera.position.clone().sub(controls.target);
    const flat = Math.hypot(offset.x, offset.z);
    flyTo(controls.target.clone().add(new THREE.Vector3(0, offset.y, flat)), controls.target.clone(), 600);
  }

  // ---------------------------------------------------------------------------
  // Panel wiring
  // ---------------------------------------------------------------------------
  const $ = id => document.getElementById(id);

  function setStyle(style) {
    if (!(style in materials)) style = 'satellite';
    if (style === 'slope' && !materials.slope) {
      materials.slope = new THREE.MeshStandardMaterial({ map: slopeTexture(), roughness: 0.85, metalness: 0 });
    }
    terrain.material = materials[style];
    document.querySelectorAll('#basemap button').forEach(b => b.classList.toggle('active', b.dataset.style === style));
    $('slope-legend').hidden = style !== 'slope';
    requestRender();
  }
  document.querySelectorAll('#basemap button').forEach(b => b.addEventListener('click', () => setStyle(b.dataset.style)));

  const layers = {
    'layer-trees': on => { treesGroup.visible = on; },
    'layer-trails': on => { trailsGroup.visible = on; },
    'layer-labels': on => { showLabels = on; },
    'layer-power': on => { powerGroup.visible = on; },
    'layer-boundary': on => { boundaryGroup.visible = on; },
    'layer-water': on => { waterGroup.visible = on; }
  };
  Object.entries(layers).forEach(([id, apply]) => {
    const box = $(id);
    apply(box.checked);
    box.addEventListener('change', () => { apply(box.checked); requestRender(); });
  });
  $('tree-count').textContent = TREE_COUNT.toLocaleString();

  $('exag').addEventListener('input', e => setExaggeration(parseFloat(e.target.value), false));
  $('sun').addEventListener('input', e => setSun(parseInt(e.target.value, 10)));
  document.querySelectorAll('#season button').forEach(b => b.addEventListener('click', () => {
    season = b.dataset.season;
    document.querySelectorAll('#season button').forEach(x => x.classList.toggle('active', x === b));
    setSun(parseInt($('sun').value, 10));
  }));

  document.querySelectorAll('.views button').forEach(b => b.addEventListener('click', () => setView(b.dataset.view)));

  const panel = $('panel');
  if (IS_TOUCH || window.innerWidth < 640) panel.classList.add('closed');
  $('btn-panel').addEventListener('click', () => panel.classList.toggle('closed'));

  function setUiHidden(hidden) {
    document.body.classList.toggle('ui-hidden', hidden);
    $('btn-show').hidden = !hidden;
  }
  $('btn-hide').addEventListener('click', () => setUiHidden(true));
  $('btn-show').addEventListener('click', () => setUiHidden(false));
  window.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT') return;
    if (e.key === 'h' || e.key === 'H') setUiHidden(!document.body.classList.contains('ui-hidden'));
    if (e.key === 'Escape') selectTrail(null);
  });
  $('btn-compass').addEventListener('click', faceNorth);

  // Trails list and card
  const list = $('trail-list');
  const DIFF_SHORT = t => t.difficulty.replace('Expert / ', '');
  function renderTrailList(filter = '') {
    const q = filter.trim().toLowerCase();
    const shown = features.trails.filter(t => t.name.toLowerCase().includes(q));
    $('trail-count').textContent = `${shown.length}`;
    list.replaceChildren(...shown.map(t => {
      const li = document.createElement('li');
      li.classList.toggle('selected', t === selectedTrail);
      const dot = document.createElement('span');
      dot.className = 'dot';
      dot.style.setProperty('--c', cssColor(trailColor(t)));
      const name = document.createElement('span');
      name.className = 'name';
      name.textContent = t.name;
      const miles = document.createElement('span');
      miles.className = 'miles';
      miles.textContent = `${t.miles.toFixed(1)} mi`;
      li.append(dot, name, miles);
      li.addEventListener('click', () => selectTrail(t === selectedTrail ? null : t));
      return li;
    }));
  }
  $('trail-search').addEventListener('input', e => renderTrailList(e.target.value));

  function selectTrail(trail) {
    selectedTrail = trail;
    setHighlight(trail);
    const card = $('trail-card');
    card.hidden = !trail;
    if (trail) {
      $('card-name').textContent = trail.name;
      const diff = $('card-diff');
      diff.innerHTML = '';
      const dot = document.createElement('span');
      dot.className = 'dot';
      dot.style.setProperty('--c', cssColor(trailColor(trail)));
      diff.append(dot, document.createTextNode(DIFF_SHORT(trail)));
      $('card-length').textContent = `${trail.miles.toFixed(2)} mi`;
      $('card-climb').textContent = `${trail.elev_gain_ft.toLocaleString()} ft`;
      $('card-low').textContent = `${trail.min_elev_ft.toLocaleString()} ft`;
      $('card-high').textContent = `${trail.max_elev_ft.toLocaleString()} ft`;
      $('card-desc').textContent = trail.description;
    }
    renderTrailList($('trail-search').value);
    requestRender();
  }
  $('card-close').addEventListener('click', () => selectTrail(null));
  $('card-zoom').addEventListener('click', () => selectedTrail && zoomToTrail(selectedTrail));

  // ---------------------------------------------------------------------------
  // Start
  // ---------------------------------------------------------------------------
  setStyle(params.get('style') || 'satellite');
  setSun(parseInt($('sun').value, 10));
  setExaggeration(parseFloat($('exag').value), true);
  renderTrailList();
  setView(params.get('view') || 'overview', 0);
  if (params.get('trail')) {
    const q = params.get('trail').toLowerCase();
    const t = features.trails.find(t => t.name.toLowerCase().includes(q));
    if (t) { selectTrail(t); zoomToTrail(t); }
  }

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    requestRender();
  });

  // The shadow map covers the area around what you're looking at, so shadows sharpen as you zoom in
  function updateShadowFrame() {
    const dist = camera.position.distanceTo(controls.target);
    const half = THREE.MathUtils.clamp(dist * 1.3, 5, 75);
    const cam = sun.shadow.camera;
    sun.target.position.copy(controls.target);
    sun.position.copy(controls.target).addScaledVector(sunDir, 150);
    cam.left = -half; cam.right = half; cam.top = half; cam.bottom = -half;
    cam.near = 1; cam.far = 320;
    cam.updateProjectionMatrix();
    sun.shadow.normalBias = (2 * half / SHADOW_RES) * 1.5;
    const treeShadows = dist < 30;
    treeMeshes.forEach(m => { m.castShadow = treeShadows; });
  }

  const compass = $('compass-needle');
  const dir = new THREE.Vector3();
  let firstFrame = true;
  function loop() {
    requestAnimationFrame(loop);
    if (controls.update()) needsRender = true;
    if (pendingPointer) {
      inspect(pendingPointer[0], pendingPointer[1]);
      pendingPointer = null;
    }
    if (!needsRender) return;
    needsRender = false;
    updateShadowFrame();
    renderer.render(scene, camera);
    updateLabels();
    camera.getWorldDirection(dir);
    compass.style.transform = `rotate(${-Math.atan2(dir.x, -dir.z) * 180 / Math.PI}deg)`;
    if (firstFrame) {
      firstFrame = false;
      document.getElementById('loading').classList.add('done');
    }
  }
  loop();

  // Small hook for scripted screenshots / debugging
  window.annadel = { setView, setStyle, selectTrail: name => selectTrail(features.trails.find(t => t.name === name) || null) };
})();
