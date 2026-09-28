// Trione-Annadel State Park 3D Topographical Map Application
// Uses Three.js & real USGS 3DEP LiDAR elevation data

(function() {
  if (!window.ANNADEL_DATA) {
    console.error("ANNADEL_DATA not loaded!");
    return;
  }

  const data = window.ANNADEL_DATA;
  const terrainData = data.terrain;
  const features = data.features;
  const texturesData = data.textures;
  const bounds = terrainData.bounds;

  function decodeBase64(b64) {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes.buffer;
  }

  // Ground dimensions (Aspect ratio matching real geographic distances)
  const MAP_WIDTH = 100.0;
  const MAP_DEPTH = 89.1;
  const RES = terrainData.grid_res;
  const MIN_ELEV_M = terrainData.min_elevation_m;
  const MAX_ELEV_M = terrainData.max_elevation_m;
  const GROUND_WIDTH_M = 8720.0; // Ground width in meters
  const WORLD_PER_M = MAP_WIDTH / GROUND_WIDTH_M;

  // LiDAR bare-earth grid, stored as uint16 decimetres, row-major from the north-west corner
  const elevDm = new Uint16Array(decodeBase64(terrainData.elev_dm_b64));
  const elevations = new Float32Array(elevDm.length);
  for (let i = 0; i < elevDm.length; i++) elevations[i] = elevDm[i] / 10.0;

  let currentExaggeration = 1.8;
  const urlParams = new URLSearchParams(window.location.search);
  let currentMapStyle = urlParams.get('style') || 'satellite';

  // Three.js Core
  const container = document.getElementById('canvas-container');
  const labelsContainer = document.getElementById('labels-container');

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0f14);
  scene.fog = new THREE.FogExp2(0x0b0f14, 0.0032);

  const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.5, 800);
  camera.position.set(10, 75, 95);

  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  container.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.maxPolarAngle = Math.PI / 2 - 0.04;
  controls.minDistance = 15;
  controls.maxDistance = 250;
  controls.target.set(8, 4, 0);

  // Lighting
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.45);
  scene.add(ambientLight);

  const hemiLight = new THREE.HemisphereLight(0xbae6fd, 0x1e293b, 0.4);
  scene.add(hemiLight);

  const sunLight = new THREE.DirectionalLight(0xfffaed, 1.25);
  sunLight.castShadow = true;
  sunLight.shadow.mapSize.width = 2048;
  sunLight.shadow.mapSize.height = 2048;
  sunLight.shadow.camera.near = 10;
  sunLight.shadow.camera.far = 300;
  sunLight.shadow.camera.left = -70;
  sunLight.shadow.camera.right = 70;
  sunLight.shadow.camera.top = 70;
  sunLight.shadow.camera.bottom = -70;
  sunLight.shadow.bias = -0.0005;
  scene.add(sunLight);

  function updateSunPosition(percent) {
    // percent: 0 (morning east) to 100 (sunset west)
    const angle = (percent / 100.0) * Math.PI;
    const radius = 120;
    const height = Math.sin(angle) * 80 + 25;
    const x = -Math.cos(angle) * radius;
    const z = 35;
    sunLight.position.set(x, height, z);
    
    // Light color shifts subtly with time of day
    if (percent < 25) {
      sunLight.color.setHex(0xffdfba); // Morning warm
      ambientLight.color.setHex(0xdbeafe);
    } else if (percent > 75) {
      sunLight.color.setHex(0xfeb272); // Golden sunset
      ambientLight.color.setHex(0xf3e8ff);
    } else {
      sunLight.color.setHex(0xfffaed); // Midday crisp
      ambientLight.color.setHex(0xffffff);
    }
  }
  updateSunPosition(65);

  // Helper: Get elevation in meters at normalized (u, v) [0 to 1]
  function getRawElevation(u, v) {
    u = Math.max(0.0, Math.min(1.0, u));
    v = Math.max(0.0, Math.min(1.0, v));
    const gx = u * (RES - 1);
    const gy = v * (RES - 1);
    const x0 = Math.floor(gx);
    const x1 = Math.min(RES - 1, x0 + 1);
    const y0 = Math.floor(gy);
    const y1 = Math.min(RES - 1, y0 + 1);
    const dx = gx - x0;
    const dy = gy - y0;
    const e00 = elevations[y0 * RES + x0];
    const e10 = elevations[y0 * RES + x1];
    const e01 = elevations[y1 * RES + x0];
    const e11 = elevations[y1 * RES + x1];
    const eTop = e00 * (1 - dx) + e10 * dx;
    const eBot = e01 * (1 - dx) + e11 * dx;
    return eTop * (1 - dy) + eBot * dy;
  }

  // Convert elevation in meters to 3D world Y
  function elevationToWorldY(elev_m, exaggeration) {
    const trueY = ((elev_m - MIN_ELEV_M) / GROUND_WIDTH_M) * MAP_WIDTH;
    return trueY * exaggeration;
  }

  // Convert (u, v) to 3D Vector3
  function uvToWorld(u, v, yOffset = 0.0) {
    const x = (u - 0.5) * MAP_WIDTH;
    const z = (v - 0.5) * MAP_DEPTH;
    const ele_m = getRawElevation(u, v);
    const y = elevationToWorldY(ele_m, currentExaggeration) + yOffset;
    return new THREE.Vector3(x, y, z);
  }

  // Textures
  const textureLoader = new THREE.TextureLoader();
  const satTexture = textureLoader.load(texturesData.satellite);
  satTexture.anisotropy = 8;

  const topoTexture = textureLoader.load(texturesData.topographic);
  topoTexture.anisotropy = 8;

  // Multi-directional hillshade baked from the 1 m LiDAR ground model
  const reliefTexture = textureLoader.load(texturesData.relief);
  reliefTexture.anisotropy = 8;

  // Generate Slope Heatmap Texture dynamically
  function generateSlopeTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 512;
    const ctx = canvas.getContext('2d');
    const imgData = ctx.createImageData(512, 512);
    const d = imgData.data;

    for (let y = 0; y < 512; y++) {
      for (let x = 0; x < 512; x++) {
        const u = x / 512.0;
        const v = y / 512.0;
        const delta = 1.0 / 512.0;
        const eL = getRawElevation(Math.max(0, u - delta), v);
        const eR = getRawElevation(Math.min(1, u + delta), v);
        const eT = getRawElevation(u, Math.max(0, v - delta));
        const eB = getRawElevation(u, Math.min(1, v + delta));

        const dx = (eR - eL) / (2 * delta * GROUND_WIDTH_M);
        const dz = (eB - eT) / (2 * delta * (GROUND_WIDTH_M * MAP_DEPTH / MAP_WIDTH));
        const slope = Math.sqrt(dx * dx + dz * dz); // rise over run
        const angleDeg = Math.atan(slope) * (180.0 / Math.PI);

        // Color ramp:
        // 0-10 deg: Gentle / Flat (Green: 34, 197, 94)
        // 10-22 deg: Moderate (Yellow: 234, 179, 8)
        // 22-35 deg: Steep (Orange: 249, 115, 22)
        // >35 deg: Very Steep Cliffs (Red: 239, 68, 68)
        let r, g, b;
        if (angleDeg < 12) {
          const t = angleDeg / 12;
          r = 34 + t * (234 - 34);
          g = 197 + t * (179 - 197);
          b = 94 + t * (8 - 94);
        } else if (angleDeg < 25) {
          const t = (angleDeg - 12) / 13;
          r = 234 + t * (249 - 234);
          g = 179 + t * (115 - 179);
          b = 8 + t * (22 - 8);
        } else {
          const t = Math.min(1.0, (angleDeg - 25) / 18);
          r = 249 + t * (239 - 249);
          g = 115 + t * (68 - 115);
          b = 22 + t * (68 - 22);
        }

        const idx = (y * 512 + x) * 4;
        d[idx] = r;
        d[idx+1] = g;
        d[idx+2] = b;
        d[idx+3] = 255;
      }
    }
    ctx.putImageData(imgData, 0, 0);
    const tex = new THREE.CanvasTexture(canvas);
    tex.anisotropy = 8;
    return tex;
  }
  const slopeTexture = generateSlopeTexture();

  // Terrain Materials
  const terrainMaterials = {
    satellite: new THREE.MeshStandardMaterial({
      map: satTexture,
      roughness: 0.85,
      metalness: 0.05,
      flatShading: false
    }),
    topographic: new THREE.MeshStandardMaterial({
      map: topoTexture,
      roughness: 0.75,
      metalness: 0.1,
      flatShading: false
    }),
    relief: new THREE.MeshStandardMaterial({
      map: reliefTexture,
      roughness: 0.65,
      metalness: 0.1,
      flatShading: false
    }),
    slope: new THREE.MeshStandardMaterial({
      map: slopeTexture,
      roughness: 0.8,
      metalness: 0.05,
      flatShading: false
    })
  };

  // Build Terrain Mesh
  const IS_TOUCH = window.matchMedia('(pointer: coarse)').matches;
  const MESH_RES = IS_TOUCH ? 512 : 768;
  const terrainGeo = new THREE.PlaneGeometry(MAP_WIDTH, MAP_DEPTH, MESH_RES - 1, MESH_RES - 1);
  terrainGeo.rotateX(-Math.PI / 2);

  function updateTerrainGeometry() {
    const pos = terrainGeo.attributes.position;
    let idx = 0;
    for (let y = 0; y < MESH_RES; y++) {
      const v = y / (MESH_RES - 1);
      for (let x = 0; x < MESH_RES; x++) {
        const u = x / (MESH_RES - 1);
        const ele_m = getRawElevation(u, v);
        const worldY = elevationToWorldY(ele_m, currentExaggeration);
        pos.setY(idx, worldY);
        idx++;
      }
    }
    pos.needsUpdate = true;
    terrainGeo.computeVertexNormals();
  }
  updateTerrainGeometry();

  const terrainMesh = new THREE.Mesh(terrainGeo, terrainMaterials[currentMapStyle]);
  terrainMesh.receiveShadow = true;
  terrainMesh.castShadow = true;
  scene.add(terrainMesh);

  // Museum-Grade 3D Base Pedestal (Skirt walls + Bottom plate)
  const skirtGroup = new THREE.Group();
  const skirtMat = new THREE.MeshStandardMaterial({
    color: 0x181e29,
    roughness: 0.7,
    metalness: 0.3
  });
  const BASE_Y = -5.0;

  function buildSkirtGeometry() {
    skirtGroup.clear();

    const createEdgeWall = (coordsA, coordsB, uFixed, vFixed, isHorizontal) => {
      const wallGeo = new THREE.BufferGeometry();
      const vertices = [];
      const indices = [];

      for (let i = 0; i < MESH_RES; i++) {
        const t = i / (MESH_RES - 1);
        const u = isHorizontal ? t : uFixed;
        const v = isHorizontal ? vFixed : t;
        const x = (u - 0.5) * MAP_WIDTH;
        const z = (v - 0.5) * MAP_DEPTH;
        const ele_m = getRawElevation(u, v);
        const topY = elevationToWorldY(ele_m, currentExaggeration);

        // Top vertex (2*i)
        vertices.push(x, topY, z);
        // Bottom vertex (2*i + 1)
        vertices.push(x, BASE_Y, z);

        if (i < MESH_RES - 1) {
          const v0 = 2 * i;
          const v1 = 2 * i + 1;
          const v2 = 2 * (i + 1);
          const v3 = 2 * (i + 1) + 1;
          indices.push(v0, v1, v2);
          indices.push(v2, v1, v3);
        }
      }

      wallGeo.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
      wallGeo.setIndex(indices);
      wallGeo.computeVertexNormals();
      const wallMesh = new THREE.Mesh(wallGeo, skirtMat);
      wallMesh.receiveShadow = true;
      return wallMesh;
    };

    // North wall (v = 0)
    skirtGroup.add(createEdgeWall(0, 1, null, 0, true));
    // South wall (v = 1)
    skirtGroup.add(createEdgeWall(0, 1, null, 1, true));
    // West wall (u = 0)
    skirtGroup.add(createEdgeWall(0, 1, 0, null, false));
    // East wall (u = 1)
    skirtGroup.add(createEdgeWall(0, 1, 1, null, false));

    // Bottom plate
    const basePlateGeo = new THREE.PlaneGeometry(MAP_WIDTH, MAP_DEPTH);
    basePlateGeo.rotateX(Math.PI / 2);
    basePlateGeo.translate(0, BASE_Y, 0);
    const basePlateMesh = new THREE.Mesh(basePlateGeo, skirtMat);
    skirtGroup.add(basePlateMesh);
  }
  buildSkirtGeometry();
  scene.add(skirtGroup);

  // Water Bodies (Lake Ilsanjo)
  const waterGroup = new THREE.Group();
  const waterMat = new THREE.MeshStandardMaterial({
    color: 0x0284c7,
    roughness: 0.12,
    metalness: 0.25,
    transparent: true,
    opacity: 0.88
  });

  function buildWaterBodies() {
    waterGroup.clear();

    features.water_bodies.forEach(wb => {
      const pts = wb.polygon.map(p => new THREE.Vector2((p.u - 0.5) * MAP_WIDTH, -(p.v - 0.5) * MAP_DEPTH));
      const waterGeo = new THREE.ShapeGeometry(new THREE.Shape(pts));
      waterGeo.rotateX(-Math.PI / 2);

      const mesh = new THREE.Mesh(waterGeo, waterMat);
      mesh.position.y = elevationToWorldY(wb.surface_m, currentExaggeration) + 0.02;
      mesh.receiveShadow = true;
      waterGroup.add(mesh);
    });
  }
  buildWaterBodies();
  scene.add(waterGroup);

  // LiDAR Forest: every tree detected in the 1 m canopy height model, drawn at true size.
  // Record layout (8 bytes): u uint16, v uint16, height dm uint16, crown radius dm uint8, kind uint8
  const treesGroup = new THREE.Group();
  const treeBytes = new DataView(decodeBase64(data.trees.b64));
  const TREE_COUNT = data.trees.count;
  const treeX = new Float32Array(TREE_COUNT);
  const treeZ = new Float32Array(TREE_COUNT);
  const treeU = new Float32Array(TREE_COUNT);
  const treeV = new Float32Array(TREE_COUNT);
  const treeH = new Float32Array(TREE_COUNT);   // meters
  const treeR = new Float32Array(TREE_COUNT);   // crown radius, meters
  const treeKind = new Uint8Array(TREE_COUNT);  // 0 conifer, 1 broadleaf
  for (let i = 0; i < TREE_COUNT; i++) {
    const o = i * 8;
    treeU[i] = treeBytes.getUint16(o, true) / 65535;
    treeV[i] = treeBytes.getUint16(o + 2, true) / 65535;
    treeH[i] = treeBytes.getUint16(o + 4, true) / 10;
    treeR[i] = treeBytes.getUint8(o + 6) / 10;
    treeKind[i] = treeBytes.getUint8(o + 7);
    treeX[i] = (treeU[i] - 0.5) * MAP_WIDTH;
    treeZ[i] = (treeV[i] - 0.5) * MAP_DEPTH;
  }

  // Unit-sized crowns, scaled per instance to (crown radius, height, crown radius)
  const coniferGeo = new THREE.ConeGeometry(1, 0.85, 7, 1, true);
  coniferGeo.translate(0, 0.15 + 0.425, 0);
  const broadleafGeo = new THREE.IcosahedronGeometry(1, 0);
  broadleafGeo.scale(1, 0.4, 1);
  broadleafGeo.translate(0, 0.6, 0);

  const coniferMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.9, metalness: 0.0, flatShading: true });
  const broadleafMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.85, metalness: 0.0, flatShading: true });
  const CONIFER_COLOR = new THREE.Color(0x1f5a36);
  const BROADLEAF_COLOR = new THREE.Color(0x5f7f2a);

  const kindIndex = [[], []];
  for (let i = 0; i < TREE_COUNT; i++) kindIndex[treeKind[i]].push(i);

  const treeMeshes = [
    new THREE.InstancedMesh(coniferGeo, coniferMat, Math.max(1, kindIndex[0].length)),
    new THREE.InstancedMesh(broadleafGeo, broadleafMat, Math.max(1, kindIndex[1].length))
  ];
  treeMeshes.forEach((mesh, k) => {
    mesh.count = kindIndex[k].length;
    // At whole-park scale a shadow-map texel is ~6 m, so per-tree shadows aren't worth a second geometry pass
    mesh.castShadow = false;
    mesh.receiveShadow = true;
    // Deterministic per-tree tint so the canopy doesn't read as one flat color
    const base = k === 0 ? CONIFER_COLOR : BROADLEAF_COLOR;
    const c = new THREE.Color();
    kindIndex[k].forEach((treeIdx, j) => {
      const jitter = 0.82 + 0.3 * (((treeIdx * 2654435761) >>> 0) % 1000) / 1000;
      c.copy(base).multiplyScalar(jitter);
      mesh.setColorAt(j, c);
    });
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    treesGroup.add(mesh);
  });

  const treeDummy = new THREE.Object3D();
  function updateTreePositions() {
    treeMeshes.forEach((mesh, k) => {
      kindIndex[k].forEach((i, j) => {
        // Sink the base slightly so trees sit in the (interpolated) ground on slopes
        const groundY = elevationToWorldY(getRawElevation(treeU[i], treeV[i]), currentExaggeration);
        treeDummy.position.set(treeX[i], groundY - 1.0 * WORLD_PER_M * currentExaggeration, treeZ[i]);
        treeDummy.rotation.y = (i * 0.73) % (Math.PI * 2);
        const r = Math.max(treeR[i], 1.0) * WORLD_PER_M;
        treeDummy.scale.set(r, treeH[i] * WORLD_PER_M, r);
        treeDummy.updateMatrix();
        mesh.setMatrixAt(j, treeDummy.matrix);
      });
      mesh.instanceMatrix.needsUpdate = true;
    });
  }
  updateTreePositions();
  scene.add(treesGroup);
  document.getElementById('trees-toggle-label').textContent = `LiDAR Forest (${TREE_COUNT.toLocaleString()} trees)`;

  // Spatial hash for the tree inspector (counting-sort into a 200x200 grid)
  const TREE_GRID = 200;
  const treeCellStart = new Uint32Array(TREE_GRID * TREE_GRID + 1);
  const treeCellItems = new Uint32Array(TREE_COUNT);
  function treeCell(u, v) {
    const c = Math.min(TREE_GRID - 1, Math.max(0, Math.floor(u * TREE_GRID)));
    const r = Math.min(TREE_GRID - 1, Math.max(0, Math.floor(v * TREE_GRID)));
    return r * TREE_GRID + c;
  }
  (function buildTreeGrid() {
    for (let i = 0; i < TREE_COUNT; i++) treeCellStart[treeCell(treeU[i], treeV[i]) + 1]++;
    for (let c = 0; c < TREE_GRID * TREE_GRID; c++) treeCellStart[c + 1] += treeCellStart[c];
    const fill = treeCellStart.slice(0, TREE_GRID * TREE_GRID);
    for (let i = 0; i < TREE_COUNT; i++) treeCellItems[fill[treeCell(treeU[i], treeV[i])]++] = i;
  })();

  // Nearest tree whose crown covers the point (x, z) in world units, or -1
  function findNearestTree(x, z) {
    const u = x / MAP_WIDTH + 0.5;
    const v = z / MAP_DEPTH + 0.5;
    const col = Math.min(TREE_GRID - 1, Math.max(0, Math.floor(u * TREE_GRID)));
    const row = Math.min(TREE_GRID - 1, Math.max(0, Math.floor(v * TREE_GRID)));
    let best = -1;
    let bestScore = Infinity;
    for (let r = Math.max(0, row - 1); r <= Math.min(TREE_GRID - 1, row + 1); r++) {
      for (let c = Math.max(0, col - 1); c <= Math.min(TREE_GRID - 1, col + 1); c++) {
        const cell = r * TREE_GRID + c;
        for (let n = treeCellStart[cell]; n < treeCellStart[cell + 1]; n++) {
          const i = treeCellItems[n];
          const dx = treeX[i] - x;
          const dz = treeZ[i] - z;
          const crown = Math.max(treeR[i], 2.0) * WORLD_PER_M;
          const score = (dx * dx + dz * dz) / (crown * crown);
          if (score < 1.0 && score < bestScore) {
            bestScore = score;
            best = i;
          }
        }
      }
    }
    return best;
  }

  function describeTree(i) {
    const species = treeKind[i] === 0 ? '🌲 Conifer (Douglas-fir / redwood)' : '🌳 Broadleaf (oak / bay / madrone)';
    const heightFt = Math.round(treeH[i] * 3.28084);
    const crownFt = Math.round(treeR[i] * 2 * 3.28084);
    return `${species} <span style="color:#94a3b8; font-size:11px; font-weight:normal;">${heightFt} ft tall · ${crownFt} ft crown</span>`;
  }

  // Official State Park Boundary Line
  const boundaryGroup = new THREE.Group();
  function buildBoundary() {
    boundaryGroup.clear();
    const pts = [];
    features.boundary.forEach(bp => {
      pts.push(uvToWorld(bp.u, bp.v, 0.12));
    });
    // Close polygon
    if (pts.length > 0) pts.push(pts[0].clone());

    const bGeo = new THREE.BufferGeometry().setFromPoints(pts);
    const bMat = new THREE.LineDashedMaterial({
      color: 0xf59e0b,
      dashSize: 1.5,
      gapSize: 0.8,
      linewidth: 2
    });
    const bLine = new THREE.Line(bGeo, bMat);
    bLine.computeLineDistances();
    boundaryGroup.add(bLine);
  }
  buildBoundary();
  scene.add(boundaryGroup);

  // Official Trails Network
  const trailsGroup = new THREE.Group();
  const trailMeshes = [];
  const trailLabels = [];
  let hoveredTrail = null;
  let selectedTrail = null;

  const DIFFICULTY_COLORS = {
    "Easy": 0x10b981,
    "Moderate": 0x38bdf8,
    "Challenging": 0xfbbf24,
    "Expert / Strenuous": 0xf87171,
    "Strenuous": 0xf87171
  };

  function buildTrails() {
    trailsGroup.clear();
    trailMeshes.length = 0;
    trailLabels.length = 0;
    labelsContainer.innerHTML = '';

    features.trails.forEach((tr, trIdx) => {
      const diffColor = DIFFICULTY_COLORS[tr.difficulty] || 0x38bdf8;
      
      const lineGroup = new THREE.Group();
      lineGroup.userData = { trail: tr, index: trIdx };

      tr.lines.forEach(seg => {
        const segPts = seg.map(pt => uvToWorld(pt.u, pt.v, 0.22));
        const lineGeo = new THREE.BufferGeometry().setFromPoints(segPts);
        
        // Base trail line
        const lineMat = new THREE.LineBasicMaterial({
          color: diffColor,
          linewidth: 2
        });
        const lineMesh = new THREE.Line(lineGeo, lineMat);
        lineMesh.userData = { trail: tr, index: trIdx };
        lineGroup.add(lineMesh);

        // Invisible wider tube or hit target for easier raycasting
        const cleanPts = [];
        for (let i = 0; i < segPts.length; i++) {
          if (i === 0 || segPts[i].distanceTo(cleanPts[cleanPts.length - 1]) > 0.08) {
            cleanPts.push(segPts[i]);
          }
        }
        if (cleanPts.length >= 2) {
          const tubeCurve = new THREE.CatmullRomCurve3(cleanPts);
          const hitGeo = new THREE.TubeGeometry(tubeCurve, Math.max(6, cleanPts.length * 2), 0.5, 4, false);
          const hitMat = new THREE.MeshBasicMaterial({ visible: false });
          const hitMesh = new THREE.Mesh(hitGeo, hitMat);
          hitMesh.userData = { trail: tr, index: trIdx, parentLine: lineMesh };
          lineGroup.add(hitMesh);
          trailMeshes.push(hitMesh);
        }
      });

      trailsGroup.add(lineGroup);

      // Create 2D Billboard label at midpoint
      if (tr.label_pos) {
        const labelDiv = document.createElement('div');
        labelDiv.className = 'map-label';
        labelDiv.textContent = tr.name;
        labelDiv.dataset.trail = tr.name;
        labelsContainer.appendChild(labelDiv);

        trailLabels.push({
          element: labelDiv,
          pos: tr.label_pos,
          trail: tr
        });
      }
    });
  }
  buildTrails();
  scene.add(trailsGroup);

  // Update Billboard Labels on Screen Projection
  function updateScreenLabels() {
    const showTrailLabels = document.getElementById('toggle-labels').checked;

    const tempV = new THREE.Vector3();

    // Trail Labels
    trailLabels.forEach(tl => {
      const isTarget = (hoveredTrail && hoveredTrail.name === tl.trail.name) ||
                       (selectedTrail && selectedTrail.name === tl.trail.name);

      if (!isTarget && (!showTrailLabels || !document.getElementById('toggle-trails').checked)) {
        tl.element.style.display = 'none';
        tl.element.classList.remove('active-trail-label');
        return;
      }

      const wPos = uvToWorld(tl.pos.u, tl.pos.v, 0.4);
      tempV.copy(wPos).project(camera);

      // Check if behind camera or outside viewport
      if (tempV.z > 1.0 || Math.abs(tempV.x) > 1.1 || Math.abs(tempV.y) > 1.1) {
        tl.element.style.display = 'none';
        return;
      }

      const x = (tempV.x * 0.5 + 0.5) * window.innerWidth;
      const y = (-(tempV.y * 0.5) + 0.5) * window.innerHeight;
      tl.element.style.display = 'block';
      tl.element.style.left = `${x}px`;
      tl.element.style.top = `${y}px`;

      if (isTarget) {
        tl.element.classList.add('active-trail-label');
      } else {
        tl.element.classList.remove('active-trail-label');
      }
    });
  }

  // Update Compass Indicator
  const compassNeedle = document.getElementById('compass-needle');
  const compassText = document.getElementById('compass-text');
  function updateCompass() {
    const dir = new THREE.Vector3();
    camera.getWorldDirection(dir);
    // Angle in XZ plane
    const angle = Math.atan2(dir.x, -dir.z);
    const deg = THREE.MathUtils.radToDeg(angle);
    compassNeedle.style.transform = `rotate(${-deg}deg)`;
    
    // Cardinal direction
    const cardinals = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const normDeg = (deg + 360) % 360;
    const cardIdx = Math.round(normDeg / 45) % 8;
    compassText.textContent = cardinals[cardIdx];
  }

  // Raycasting & Mouse Interaction
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2(-999, -999);

  const hudElev = document.getElementById('hud-elevation');
  const hudCoords = document.getElementById('hud-coords');
  const hudFeature = document.getElementById('hud-feature');

  window.addEventListener('mousemove', (e) => {
    mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;

    // Raycast on terrain
    raycaster.setFromCamera(mouse, camera);
    const intersectsTerrain = raycaster.intersectObject(terrainMesh);

    let nearTree = -1;
    if (intersectsTerrain.length > 0) {
      const hit = intersectsTerrain[0];
      const u = (hit.point.x / MAP_WIDTH) + 0.5;
      const v = (hit.point.z / MAP_DEPTH) + 0.5;
      
      const lat = bounds.lat_max - v * (bounds.lat_max - bounds.lat_min);
      const lon = bounds.lon_min + u * (bounds.lon_max - bounds.lon_min);
      const ele_m = getRawElevation(u, v);
      const ele_ft = Math.round(ele_m * 3.28084);

      hudElev.textContent = `${ele_ft.toLocaleString()} ft (${Math.round(ele_m)} m)`;
      hudCoords.textContent = `${lat.toFixed(4)}°N, ${Math.abs(lon).toFixed(4)}°W`;

      if (document.getElementById('toggle-trees').checked) {
        nearTree = findNearestTree(hit.point.x, hit.point.z);
      }
    }

    // Raycast on trails
    const intersectsTrails = raycaster.intersectObjects(trailMeshes);
    if (intersectsTrails.length > 0) {
      container.style.cursor = 'pointer';
      const hitTr = intersectsTrails[0].object.userData.trail;
      hudFeature.textContent = hitTr.name;
      hudFeature.style.color = '#fbbf24';
      highlightTrail(hitTr);
    } else if (nearTree >= 0) {
      container.style.cursor = 'default';
      hudFeature.innerHTML = describeTree(nearTree);
      hudFeature.style.color = treeKind[nearTree] === 0 ? '#4ade80' : '#a3e635';
      if (!selectedTrail) unhighlightTrail();
    } else {
      container.style.cursor = 'default';
      hudFeature.textContent = 'Ground';
      hudFeature.style.color = '#34d399';
      if (!selectedTrail) unhighlightTrail();
    }
  });

  window.addEventListener('click', (e) => {
    // If clicked on UI elements, ignore
    if (e.target.closest('#controls-panel') || e.target.closest('#header-bar') || e.target.closest('#trail-card')) {
      return;
    }

    mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersectsTrails = raycaster.intersectObjects(trailMeshes);
    if (intersectsTrails.length > 0) {
      const tr = intersectsTrails[0].object.userData.trail;
      selectTrail(tr);
      return;
    }

    // Touch tap or click on terrain/trees
    const intersectsTerrain = raycaster.intersectObject(terrainMesh);
    if (intersectsTerrain.length > 0) {
      const hit = intersectsTerrain[0];
      const u = (hit.point.x / MAP_WIDTH) + 0.5;
      const v = (hit.point.z / MAP_DEPTH) + 0.5;
      
      const lat = bounds.lat_max - v * (bounds.lat_max - bounds.lat_min);
      const lon = bounds.lon_min + u * (bounds.lon_max - bounds.lon_min);
      const ele_m = getRawElevation(u, v);
      const ele_ft = Math.round(ele_m * 3.28084);

      hudElev.textContent = `${ele_ft.toLocaleString()} ft (${Math.round(ele_m)} m)`;
      hudCoords.textContent = `${lat.toFixed(4)}°N, ${Math.abs(lon).toFixed(4)}°W`;

      let nearTree = -1;
      if (document.getElementById('toggle-trees').checked) {
        nearTree = findNearestTree(hit.point.x, hit.point.z);
      }

      if (nearTree >= 0) {
        hudFeature.innerHTML = describeTree(nearTree);
        hudFeature.style.color = treeKind[nearTree] === 0 ? '#4ade80' : '#a3e635';
      } else {
        hudFeature.textContent = 'Ground';
        hudFeature.style.color = '#34d399';
      }
    }
  });

  function highlightTrail(trail) {
    if (hoveredTrail === trail) return;
    hoveredTrail = trail;
    trailsGroup.children.forEach(grp => {
      const isTarget = grp.userData.trail && grp.userData.trail.name === trail.name;
      grp.children.forEach(ch => {
        if (ch.isLine) {
          if (isTarget) {
            ch.material.color.setHex(0xfacc15); // bright neon gold
            ch.scale.set(1.02, 1.05, 1.02);
          } else {
            const defColor = DIFFICULTY_COLORS[grp.userData.trail.difficulty] || 0x38bdf8;
            ch.material.color.setHex(defColor);
            ch.scale.set(1, 1, 1);
          }
        }
      });
    });
  }

  function unhighlightTrail() {
    hoveredTrail = null;
    trailsGroup.children.forEach(grp => {
      const isSelected = selectedTrail && grp.userData.trail && grp.userData.trail.name === selectedTrail.name;
      grp.children.forEach(ch => {
        if (ch.isLine) {
          if (isSelected) {
            ch.material.color.setHex(0x10b981); // Selected emerald
          } else {
            const defColor = DIFFICULTY_COLORS[grp.userData.trail.difficulty] || 0x38bdf8;
            ch.material.color.setHex(defColor);
          }
          ch.scale.set(1, 1, 1);
        }
      });
    });
  }

  function selectTrail(trail) {
    selectedTrail = trail;
    highlightTrail(trail);

    // Open Trail Card
    const card = document.getElementById('trail-card');
    document.getElementById('card-title').textContent = trail.name;
    document.getElementById('card-diff').textContent = trail.difficulty;
    document.getElementById('card-diff').className = `diff-badge diff-${trail.difficulty.toLowerCase().split(' ')[0]}`;
    document.getElementById('card-distance').textContent = `${trail.miles} mi (${trail.km} km)`;
    document.getElementById('card-gain').textContent = `+${trail.elev_gain_ft} ft`;
    document.getElementById('card-min-elev').textContent = `${trail.min_elev_ft} ft`;
    document.getElementById('card-max-elev').textContent = `${trail.max_elev_ft} ft`;
    document.getElementById('card-desc').textContent = trail.description;
    card.classList.add('visible');

    // Highlight in sidebar list
    document.querySelectorAll('.trail-item').forEach(el => {
      if (el.dataset.trail === trail.name) {
        el.classList.add('selected');
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } else {
        el.classList.remove('selected');
      }
    });

    // Smoothly fly camera to focus on trail midpoint
    if (trail.label_pos) {
      const targetPos = uvToWorld(trail.label_pos.u, trail.label_pos.v, 0);
      animateCameraTo(
        new THREE.Vector3(targetPos.x, targetPos.y + 25, targetPos.z + 30),
        targetPos,
        1200
      );
    }
  }

  window.closeTrailCard = function() {
    document.getElementById('trail-card').classList.remove('visible');
    selectedTrail = null;
    unhighlightTrail();
    document.querySelectorAll('.trail-item').forEach(el => el.classList.remove('selected'));
  };

  // Populate Trail Explorer List in Sidebar
  const trailListContainer = document.getElementById('trail-list');
  const trailSearch = document.getElementById('trail-search');

  function renderTrailList(filter = '') {
    trailListContainer.innerHTML = '';
    const filtered = features.trails.filter(t => t.name.toLowerCase().includes(filter.toLowerCase()));
    document.getElementById('trail-count-badge').textContent = `${filtered.length} Named`;

    filtered.forEach(t => {
      const item = document.createElement('div');
      item.className = `trail-item ${selectedTrail && selectedTrail.name === t.name ? 'selected' : ''}`;
      item.dataset.trail = t.name;

      const diffClass = `diff-${t.difficulty.toLowerCase().split(' ')[0]}`;
      item.innerHTML = `
        <span>${t.name}</span>
        <div style="display:flex; align-items:center; gap:6px;">
          <span style="font-size:10px; color:#94a3b8;">${t.miles} mi</span>
          <span class="diff-badge ${diffClass}">${t.difficulty}</span>
        </div>
      `;
      item.addEventListener('click', () => selectTrail(t));
      trailListContainer.appendChild(item);
    });
  }
  renderTrailList();

  const initialTrail = urlParams.get('trail');
  if (initialTrail) {
    const match = features.trails.find(t => t.name.toLowerCase() === initialTrail.toLowerCase() || t.name.toLowerCase().includes(initialTrail.toLowerCase()));
    if (match) setTimeout(() => selectTrail(match), 300);
  }

  const initialPreset = urlParams.get('preset');
  if (initialPreset) {
    setTimeout(() => flyToPreset(initialPreset, 0), 100);
  }

  trailSearch.addEventListener('input', (e) => {
    renderTrailList(e.target.value);
  });

  // UI Controls: Basemap Style Switcher
  window.setMapStyle = function(style) {
    currentMapStyle = style;
    document.querySelectorAll('.btn-group .pill-btn, .btn-group-3 .pill-btn').forEach(b => b.classList.remove('active'));
    if (style === 'satellite') document.getElementById('btn-sat').classList.add('active');
    else if (style === 'topographic') document.getElementById('btn-topo').classList.add('active');
    else if (style === 'relief') document.getElementById('btn-relief').classList.add('active');
    else if (style === 'slope') document.getElementById('btn-slope').classList.add('active');

    terrainMesh.material = terrainMaterials[style];
  };
  setMapStyle(currentMapStyle);

  // UI Controls: Vertical Exaggeration
  const sliderExaggeration = document.getElementById('slider-exaggeration');
  const valExaggeration = document.getElementById('val-exaggeration');
  sliderExaggeration.addEventListener('input', (e) => {
    currentExaggeration = parseFloat(e.target.value);
    valExaggeration.textContent = `${currentExaggeration.toFixed(1)}x`;
    
    // Update terrain mesh
    updateTerrainGeometry();
    // Update skirt base
    buildSkirtGeometry();
    // Update water meshes
    buildWaterBodies();
    // Update trails
    buildTrails();
    // Update boundary
    buildBoundary();
    // Update trees
    updateTreePositions();
  });

  // UI Controls: Sun Angle
  const sliderSun = document.getElementById('slider-sun');
  const valSun = document.getElementById('val-sun');
  sliderSun.addEventListener('input', (e) => {
    const val = parseInt(e.target.value);
    let label = "Afternoon (3:00 PM)";
    if (val < 20) label = "Early Morning (7:30 AM)";
    else if (val < 40) label = "Late Morning (10:30 AM)";
    else if (val < 60) label = "Midday (1:00 PM)";
    else if (val < 80) label = "Afternoon (3:30 PM)";
    else label = "Sunset Golden Hour (6:45 PM)";
    valSun.textContent = label;
    updateSunPosition(val);
  });

  // UI Controls: Layer Toggles
  document.getElementById('toggle-trails').addEventListener('change', (e) => {
    trailsGroup.visible = e.target.checked;
    updateScreenLabels();
  });
  document.getElementById('toggle-trees').addEventListener('change', (e) => {
    treesGroup.visible = e.target.checked;
  });
  document.getElementById('toggle-labels').addEventListener('change', () => {
    updateScreenLabels();
  });
  document.getElementById('toggle-boundary').addEventListener('change', (e) => {
    boundaryGroup.visible = e.target.checked;
  });
  document.getElementById('toggle-water').addEventListener('change', (e) => {
    waterGroup.visible = e.target.checked;
  });

  // Camera Presets & Animation
  let cameraTween = null;
  function animateCameraTo(targetCamPos, targetLookAt, duration = 1000) {
    if (duration <= 0) {
      camera.position.copy(targetCamPos);
      controls.target.copy(targetLookAt);
      controls.update();
      return;
    }

    const startCamPos = camera.position.clone();
    const startLookAt = controls.target.clone();
    const startTime = performance.now();

    if (cameraTween) cancelAnimationFrame(cameraTween);

    function step(now) {
      const elapsed = now - startTime;
      const progress = Math.min(1.0, elapsed / duration);
      // Ease in-out cubic
      const ease = progress < 0.5 
        ? 4 * progress * progress * progress 
        : 1 - Math.pow(-2 * progress + 2, 3) / 2;

      camera.position.lerpVectors(startCamPos, targetCamPos, ease);
      controls.target.lerpVectors(startLookAt, targetLookAt, ease);
      controls.update();

      if (progress < 1.0) {
        cameraTween = requestAnimationFrame(step);
      } else {
        cameraTween = null;
      }
    }
    cameraTween = requestAnimationFrame(step);
  }

  window.flyToPreset = function(preset, dur = 1400) {
    if (preset === 'overview') {
      animateCameraTo(new THREE.Vector3(0, 85, 95), new THREE.Vector3(0, 4, 0), dur);
    } else if (preset === 'ilsanjo') {
      // Lake Ilsanjo coords
      const ilsanjoCenter = uvToWorld(0.42, 0.45, 0);
      animateCameraTo(
        new THREE.Vector3(ilsanjoCenter.x - 12, ilsanjoCenter.y + 14, ilsanjoCenter.z + 18),
        ilsanjoCenter,
        dur
      );
    } else if (preset === 'bennett') {
      // Bennett Mountain Summit
      const bennettPos = uvToWorld(0.46, 0.67, 0);
      animateCameraTo(
        new THREE.Vector3(bennettPos.x + 10, bennettPos.y + 16, bennettPos.z + 15),
        bennettPos,
        dur
      );
    } else if (preset === 'canyon') {
      // Western entrance / Canyon Trail
      const canyonPos = uvToWorld(0.25, 0.35, 0);
      animateCameraTo(
        new THREE.Vector3(canyonPos.x - 15, canyonPos.y + 16, canyonPos.z + 16),
        canyonPos,
        dur
      );
    } else if (preset === 'lawndale') {
      // Southeastern Lawndale / Ledson
      const lawndalePos = uvToWorld(0.70, 0.72, 0);
      animateCameraTo(
        new THREE.Vector3(lawndalePos.x + 14, lawndalePos.y + 16, lawndalePos.z + 14),
        lawndalePos,
        dur
      );
    }
  };

  window.resetCamera = function() {
    window.flyToPreset('overview');
  };

  // Window Resize
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    updateScreenLabels();
  });

  // Main Render Loop
  function animate() {
    requestAnimationFrame(animate);
    controls.update();

    updateScreenLabels();
    updateCompass();

    renderer.render(scene, camera);
  }
  animate();

  window.toggleMenu = function() {
    const panel = document.getElementById('controls-panel');
    panel.classList.toggle('open');
  };

  console.log("Trione-Annadel 3D Topographical Map initialized successfully!");
})();
