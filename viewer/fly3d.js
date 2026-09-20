// The fly at the table. Real sizes: one unit is one centimeter. The fly is
// 3 mm long, the charts are a foot wide, the table is 113 by 71 cm. The body
// is NeuroMechFly (EPFL, Apache-2.0), 39 parts from a micro-CT scan, posed and
// walked here by rotating its joints. The table and the room light are Poly
// Haven scans (CC0).
//
// Frames. MuJoCo is z-up with x forward; here (x, y, z) becomes (y, z, x), so
// the fly faces +z, stands on y, and its left is +x. flygym's joint axes are
// pitch about MuJoCo y, roll about z, yaw about x, which become Three x, y, z.
// The right legs carry mirrored yaw and roll angles in rig.json, the way
// flygym mirrors them, so one axis set poses both sides.
window.Fly3D = function (opts) {
  const {canvas, stocks, order, candles, pick, col, caption, onSniff, onReady, base = ""} = opts;
  let held = [];   // what it owns; off duty it goes back to check on these
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const BODY = 0.3, WALK = 1.0, FLIGHT = 16, AIR = 5;
  // Six cards sit three across at a foot wide; a bigger board goes four across, a little smaller.
  const COLS = order.length > 6 ? 4 : 3;
  const CARD = COLS === 4 ? {w: 25, h: 15, dx: 27.5, dz: 23} : {w: 30, h: 18, dx: 36, dz: 25};
  const short = sym => sym.replace(/^X:/, "").replace(/USD$/, "");
  const TABLE = {x: 52, z: 31};

  const rnd = (a, b) => a + Math.random() * (b - a);
  const renderer = new THREE.WebGLRenderer({canvas, antialias: true});
  // Phones get a lighter scene: fewer pixels and no shadow pass.
  const lite = matchMedia("(max-width: 860px)").matches;
  renderer.setPixelRatio(Math.min(devicePixelRatio, lite ? 1.5 : 2));
  renderer.setClearColor(0x0b0b0e, 1);
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 0.78;
  renderer.shadowMap.enabled = !lite; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const scene = new THREE.Scene();
  scene.fog = null;   // the blurred backdrop gives the depth
  const camera = new THREE.PerspectiveCamera(32, 2, 0.12, 900);
  scene.add(new THREE.HemisphereLight(0xfff4e6, 0x2a201a, 0.18));
  const sun = new THREE.DirectionalLight(0xfff1dc, 0.72);
  sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048);
  const sc = sun.shadow.camera; sc.left = sc.bottom = -4; sc.right = sc.top = 4; sc.near = 1; sc.far = 80;
  sun.shadow.bias = -0.00015; sun.shadow.normalBias = 0.004;
  scene.add(sun); scene.add(sun.target);
  const fill = new THREE.DirectionalLight(0xdbe6ff, 0.35); fill.position.set(-40, 30, -20); scene.add(fill);

  // Room light from an HDRI, for reflections and the soft ambient a room has.
  if (THREE.RGBELoader) {
    const pmrem = new THREE.PMREMGenerator(renderer); pmrem.compileEquirectangularShader();
    new THREE.RGBELoader().setDataType(THREE.UnsignedByteType).load(base + "textures/lythwood_room_1k.hdr", tex => {
      scene.environment = pmrem.fromEquirectangular(tex).texture; tex.dispose(); pmrem.dispose();
    });
  }

  // ---- the table ----------------------------------------------------------
  const texLoader = new THREE.TextureLoader();
  const grain = texLoader.load(base + "textures/wood_nor_gl.jpg", t => { t.wrapS = t.wrapT = THREE.RepeatWrapping; });
  // A 1k scan of a whole table is a millimeter per texel. To a 3 mm fly that is
  // a blur, so the scan's own grain is tiled on top at a finer scale.
  function detail(mat, map, scale, strength) {
    mat.onBeforeCompile = sh => {
      sh.uniforms.detailMap = {value: map}; sh.uniforms.detailScale = {value: scale}; sh.uniforms.detailStrength = {value: strength};
      sh.fragmentShader = sh.fragmentShader
        .replace("void main() {", "uniform sampler2D detailMap; uniform float detailScale, detailStrength;\nvoid main() {")
        .replace("vec3 mapN = texture2D( normalMap, vUv ).xyz * 2.0 - 1.0;",
          "vec3 mapN = texture2D( normalMap, vUv ).xyz * 2.0 - 1.0; vec3 dn = texture2D( detailMap, vUv * detailScale ).xyz * 2.0 - 1.0; mapN = normalize( mapN + vec3( dn.xy * detailStrength, 0.0 ) );");
    };
    mat.customProgramCacheKey = () => "detail";
  }
  let tableTop = 0;
  if (THREE.GLTFLoader) {
    new THREE.GLTFLoader().load(base + "model/table/wooden_table_02.gltf", g => {
      const t = g.scene; t.scale.setScalar(100);
      t.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(t); t.position.y = -box.max.y; tableTop = 0;
      t.traverse(n => { if (n.isMesh) { n.receiveShadow = true; if (n.material.map) n.material.map.anisotropy = 8; if (n.material.normalMap) detail(n.material, grain, 36, 0.55); n.material.roughness = Math.min(0.75, n.material.roughness || 0.7); } });
      scene.add(t);
    }, undefined, e => console.warn("table not loaded", e));
  }

  // ---- the room. A lens focused on a 3 mm fly throws everything behind it far out of focus, so the
  // room is a photograph of one, blurred: Poly Haven's Lythwood room panorama (CC0), the same one that
  // lights the scene, wrapped on a large sphere. scripts/build_backdrop.py makes the image. The table
  // stands 80 cm high on a parquet floor that fades out at its edge into the backdrop.
  const ROOM = {floor: -80};
  {
    const backdrop = texLoader.load(base + "textures/room_backdrop.jpg", t => { t.encoding = THREE.sRGBEncoding; });
    const dome = new THREE.Mesh(new THREE.SphereGeometry(520, 48, 32),
      new THREE.MeshBasicMaterial({map: backdrop, side: THREE.BackSide, fog: false, toneMapped: false, color: 0xcfcac2, depthWrite: false}));
    dome.position.y = 30; dome.rotation.y = 0.9; dome.renderOrder = -1; scene.add(dome);
    const fade = (() => {
      const c = document.createElement("canvas"); c.width = c.height = 256; const x = c.getContext("2d");
      const g = x.createRadialGradient(128, 128, 40, 128, 128, 128); g.addColorStop(0, "#fff"); g.addColorStop(0.55, "#bbb"); g.addColorStop(1, "#000");
      x.fillStyle = g; x.fillRect(0, 0, 256, 256); return new THREE.CanvasTexture(c);
    })();
    const parquet = texLoader.load(base + "textures/diagonal_parquet_diff_1k.jpg", t => { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(3.4, 3.4); t.encoding = THREE.sRGBEncoding; t.anisotropy = 8; });
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(800, 800), new THREE.MeshStandardMaterial({map: parquet, alphaMap: fade, transparent: true, roughness: 0.8, depthWrite: false}));
    floor.rotation.x = -Math.PI / 2; floor.position.y = ROOM.floor; floor.receiveShadow = true; scene.add(floor);
  }
  // Dust in the light: a few hundred motes drifting slowly above the table.
  const motes = (() => {
    const n = 500, pos = new Float32Array(n * 3), vel = [];
    for (let i = 0; i < n; i++) { pos[i * 3] = rnd(-70, 70); pos[i * 3 + 1] = rnd(0.2, 40); pos[i * 3 + 2] = rnd(-45, 45); vel.push([rnd(-0.4, 0.4), rnd(-0.15, 0.25), rnd(-0.4, 0.4)]); }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    // A point is drawn as a square unless it has a texture. This one is a soft disc that fades to
    // nothing at the rim, so a mote near the lens reads as an out-of-focus blur, not a box.
    const soft = (() => {
      const c = document.createElement("canvas"); c.width = c.height = 64; const x = c.getContext("2d");
      const grad = x.createRadialGradient(32, 32, 0, 32, 32, 32);
      grad.addColorStop(0, "rgba(255,255,255,.9)"); grad.addColorStop(0.25, "rgba(255,255,255,.45)"); grad.addColorStop(0.6, "rgba(255,255,255,.12)"); grad.addColorStop(1, "rgba(255,255,255,0)");
      x.fillStyle = grad; x.fillRect(0, 0, 64, 64);
      return new THREE.CanvasTexture(c);
    })();
    const m = new THREE.Points(g, new THREE.PointsMaterial({color: 0xfff3dc, map: soft, size: 0.2, transparent: true, opacity: 0.5, depthWrite: false, sizeAttenuation: true, blending: THREE.AdditiveBlending}));
    scene.add(m);
    return {step(dt, t) { const a = g.attributes.position.array; for (let i = 0; i < n; i++) { const v = vel[i]; a[i * 3] += (v[0] + Math.sin(t * 0.7 + i) * 0.3) * dt; a[i * 3 + 1] += (v[1] + Math.cos(t * 0.5 + i * 1.3) * 0.2) * dt; a[i * 3 + 2] += (v[2] + Math.cos(t * 0.6 + i) * 0.3) * dt; if (a[i * 3 + 1] < 0.1 || a[i * 3 + 1] > 42) a[i * 3 + 1] = rnd(0.2, 40); if (Math.abs(a[i * 3]) > 72) a[i * 3] = -a[i * 3] * 0.98; if (Math.abs(a[i * 3 + 2]) > 46) a[i * 3 + 2] = -a[i * 3 + 2] * 0.98; } g.attributes.position.needsUpdate = true; }};
  })();

  // Water and sugar, the two things a fly on a table goes looking for.
  const SPOT = {water: new THREE.Vector3(-18, 0, -29), sugar: new THREE.Vector3(18, 0, -29)};
  {
    const drop = new THREE.Mesh(new THREE.SphereGeometry(0.9, 32, 20), new THREE.MeshPhysicalMaterial({color: 0xd6ecff, roughness: 0.03, metalness: 0, transparent: true, opacity: 0.5, clearcoat: 1}));
    drop.scale.set(1, 0.38, 1); drop.position.copy(SPOT.water); drop.position.y = 0.02; scene.add(drop);
    const crystal = new THREE.MeshStandardMaterial({color: 0xf6f3ec, roughness: 0.35});
    for (let i = 0; i < 26; i++) { const c = new THREE.Mesh(new THREE.BoxGeometry(0.11, 0.11, 0.11), crystal); c.position.set(SPOT.sugar.x + rnd(-0.6, 0.6), 0.055, SPOT.sugar.z + rnd(-0.6, 0.6)); c.rotation.set(rnd(0, 3), rnd(0, 3), rnd(0, 3)); c.castShadow = true; scene.add(c); }
  }

  // ---- the charts, printed on card --------------------------------------
  function drawChart(sym) {
    const c = document.createElement("canvas"); c.width = 1024; c.height = 614;
    const g = c.getContext("2d");
    g.fillStyle = col("--elev"); g.fillRect(0, 0, 1024, 614);
    g.strokeStyle = "rgba(255,255,255,.10)"; g.lineWidth = 3; g.strokeRect(1.5, 1.5, 1021, 611);
    const rows = candles[sym]; const lo = Math.min(...rows.map(r => r[2])), hi = Math.max(...rows.map(r => r[1]));
    const y = v => 580 - (v - lo) / (hi - lo) * 520, w = 1024 / rows.length;
    g.strokeStyle = "rgba(255,255,255,.07)"; g.lineWidth = 2;
    for (let k = 1; k < 5; k++) { g.beginPath(); g.moveTo(0, 60 + k * 104); g.lineTo(1024, 60 + k * 104); g.stroke(); }
    rows.forEach((r, i) => {
      const [o, h, l, cl] = r, x = i * w + w / 2, up = cl >= o;
      g.strokeStyle = g.fillStyle = up ? col("--brand") : col("--neg");
      g.lineWidth = 4; g.beginPath(); g.moveTo(x, y(h)); g.lineTo(x, y(l)); g.stroke();
      const top = y(Math.max(o, cl)), bot = y(Math.min(o, cl));
      g.fillRect(x - w * 0.28, top, w * 0.56, Math.max(4, bot - top));
    });
    return c;
  }
  function drawLabel(sym) {
    const c = document.createElement("canvas"); c.width = 1024; c.height = 154;
    const g = c.getContext("2d");
    g.fillStyle = col("--elev"); g.fillRect(0, 0, 1024, 154);
    g.fillStyle = col("--text"); g.font = "600 108px JetBrains Mono, monospace"; g.textBaseline = "middle"; g.fillText(short(sym), 36, 80);
    g.fillStyle = col("--muted"); g.font = "500 56px JetBrains Mono, monospace"; g.textAlign = "right"; { const px = stocks[sym].price; g.fillText("$" + (px >= 1000 ? Math.round(px).toLocaleString("en-US") : px >= 1 ? px.toFixed(2) : px.toPrecision(3)), 988, 84); }
    return c;
  }
  const paper = (canvasEl, w, h) => {
    const tex = new THREE.CanvasTexture(canvasEl); tex.encoding = THREE.sRGBEncoding; tex.anisotropy = 8;
    // Card stock is paper-thin, so it sits almost on the table; polygon offset keeps it from fighting the wood at a distance.
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshStandardMaterial({map: tex, roughness: 0.92, metalness: 0, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4}));
    m.rotation.x = -Math.PI / 2; m.receiveShadow = true; return m;
  };
  const dish = {};
  order.forEach((sym, k) => {
    const x = (k % COLS - (COLS - 1) / 2) * CARD.dx, z = (Math.floor(k / COLS) - 0.5) * CARD.dz;
    const card = paper(drawChart(sym), CARD.w, CARD.h); card.position.set(x, 0.02, z); scene.add(card);
    const label = paper(drawLabel(sym), CARD.w, CARD.h * 0.25); label.position.set(x, 0.02, z + CARD.h / 2 + CARD.h * 0.125 + 0.8); scene.add(label);
    dish[sym] = new THREE.Vector3(x, 0, z);
  });

  // ---- the fly -----------------------------------------------------------
  const fly = new THREE.Group(); scene.add(fly);
  const brainM = new THREE.MeshBasicMaterial({color: new THREE.Color(col("--brand")), transparent: true, opacity: 0, depthTest: false, blending: THREE.AdditiveBlending});
  const brain = new THREE.Mesh(new THREE.SphereGeometry(0.11, 14, 10), brainM); brain.renderOrder = 2;
  let R = null;   // the rig, once loaded

  function parseSTL(buf) {
    const dv = new DataView(buf); const n = dv.getUint32(80, true);
    const raw = new Float32Array(n * 9);
    for (let i = 0, o = 84; i < n; i++, o += 50) for (let k = 0; k < 3; k++) {
      const b = o + 12 + k * 12; const x = dv.getFloat32(b, true), y = dv.getFloat32(b + 4, true), z = dv.getFloat32(b + 8, true);
      raw[i * 9 + k * 3] = y * 1000; raw[i * 9 + k * 3 + 1] = z * 1000; raw[i * 9 + k * 3 + 2] = x * 1000;
    }
    // Merge shared vertices so the normals are smooth rather than faceted.
    const index = new Uint32Array(n * 3), pos = [], seen = new Map();
    for (let i = 0; i < n * 3; i++) {
      const x = raw[i * 3], y = raw[i * 3 + 1], z = raw[i * 3 + 2];
      const key = (x * 1e5 | 0) + "," + (y * 1e5 | 0) + "," + (z * 1e5 | 0);
      let j = seen.get(key); if (j === undefined) { j = pos.length / 3; seen.set(key, j); pos.push(x, y, z); }
      index[i] = j;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(new THREE.BufferAttribute(index, 1));
    g.computeVertexNormals(); return g;
  }
  const mirrored = g => {
    const m = g.clone(); m.scale(-1, 1, 1);
    const idx = m.index.array; for (let i = 0; i < idx.length; i += 3) { const t = idx[i + 1]; idx[i + 1] = idx[i + 2]; idx[i + 2] = t; }
    m.computeVertexNormals(); return m;
  };

  const X = new THREE.Vector3(1, 0, 0), Y = new THREE.Vector3(0, 1, 0), Z = new THREE.Vector3(0, 0, 1);
  const _q = new THREE.Quaternion(), _q2 = new THREE.Quaternion();
  // A joint: a node, its neutral pose, and the rotation between its parent's
  // frame and the body frame, so animation can speak in body axes.
  class Joint {
    constructor(node) {
      this.node = node; this.neutral = node.quaternion.clone();
      this.toBody = node.parent.getWorldQuaternion(new THREE.Quaternion()); this.fromBody = this.toBody.clone().invert();
    }
    reset() { this.node.quaternion.copy(this.neutral); }
    turn(axis, angle) {
      _q.setFromAxisAngle(axis, angle); _q2.copy(this.fromBody).multiply(_q).multiply(this.toBody);
      this.node.quaternion.premultiply(_q2);
    }
  }

  async function loadRig() {
    const rig = await fetch(base + "model/rig.json").then(r => r.json());
    // Cuticle colors of a male Drosophila melanogaster ("black belly"): honey-tan, a dark band along
    // the rear edge of each abdominal tergite, and the last two tergites dark all over, which is what
    // marks a male. The pigment is on the back; the underside stays pale. The brain here is a male's.
    // The body scan, NeuroMechFly, is from a female, so the shape is hers and the coloring is his.
    const matFor = n => n.includes("eye") ? new THREE.MeshStandardMaterial({color: 0xf01408, roughness: 0.38, envMapIntensity: 0.25})
      : n.includes("wing") ? new THREE.MeshPhysicalMaterial({color: 0xe9dcc4, transparent: true, opacity: 0.3, side: THREE.DoubleSide, roughness: 0.1, depthWrite: false})
      : n.includes("arista") ? new THREE.MeshStandardMaterial({color: 0x241a12, roughness: 0.6})
      : n.includes("haltere") ? new THREE.MeshStandardMaterial({color: 0x9e8052, roughness: 0.5})
      : /rostrum|haustellum/.test(n) ? new THREE.MeshStandardMaterial({color: 0x5c4021, roughness: 0.6})
      : /_(coxa|trochanterfemur|tibia|tarsus)/.test(n) ? new THREE.MeshStandardMaterial({color: 0x8e4a20, roughness: 0.6, envMapIntensity: 0.35})
      : new THREE.MeshStandardMaterial({color: 0xffffff, vertexColors: true, roughness: 0.6, side: THREE.DoubleSide, envMapIntensity: 0.35});
    // Matched against a photograph of a real male (A. Karwath, Wikimedia Commons): the thorax and head
    // are orange-amber, about #d09066 on screen; the abdomen is a paler cream between its dark bands;
    // the eye is scarlet, #e72605. Colors here are linear, so each is the screen color put through the
    // sRGB curve, and near-black has to be very low to read as black.
    const tan = new THREE.Color(0xa83c16), cream = new THREE.Color(0xa8602f), dark = new THREE.Color(0x0c0604);   // set a little more saturated than the target: the room light adds white
    function stripe(g, name) {
      const pos = g.attributes.position, n = pos.count, c = new Float32Array(n * 3);
      let lo = Infinity, hi = -Infinity, ylo = Infinity, yhi = -Infinity;
      for (let i = 0; i < n; i++) { const z = pos.getZ(i), y = pos.getY(i); lo = Math.min(lo, z); hi = Math.max(hi, z); ylo = Math.min(ylo, y); yhi = Math.max(yhi, y); }
      for (let i = 0; i < n; i++) {
        const f = (pos.getZ(i) - lo) / Math.max(1e-9, hi - lo);   // 0 at the rear of the part
        const up = (pos.getY(i) - ylo) / Math.max(1e-9, yhi - ylo);   // 0 at the belly, 1 on the back
        const dorsal = Math.max(0, Math.min(1, (up - 0.3) / 0.2));
        const band = f < 0.36 ? 1 : f < 0.46 ? (0.46 - f) / 0.1 : 0;
        let k = /abdomen[56]/.test(name) ? 1 : /abdomen[34]/.test(name) ? band : /abdomen12/.test(name) ? (f < 0.12 ? 1 : 0) : 0;
        k *= dorsal;
        if (name === "c_thorax") k = 0.18 * (1 - f);   // a little darker toward the scutellum
        const col = (/abdomen/.test(name) ? cream : tan).clone().lerp(dark, k); c[i * 3] = col.r; c[i * 3 + 1] = col.g; c[i * 3 + 2] = col.b;
      }
      g.setAttribute("color", new THREE.BufferAttribute(c, 3)); return g;
    }
    const geo = {};
    await Promise.all([...new Set(Object.values(rig.mesh))].map(async m => { geo[m] = parseSTL(await fetch(`${base}model/${m}.stl`).then(r => r.arrayBuffer())); }));
    const nodes = {}; const d = Math.PI / 180;
    for (const name of Object.keys(rig.bodies)) {
      const b = rig.bodies[name]; const node = new THREE.Group(); node.name = name;
      node.position.set(b.pos[1], b.pos[2], b.pos[0]);
      node.quaternion.set(b.quat[2], b.quat[3], b.quat[1], b.quat[0]);
      const pose = rig.pose[name];
      if (pose) {
        const q = new THREE.Quaternion();
        for (const ax of rig.axis_order) {
          const a = (pose[ax] || 0) * d; if (!a) continue;
          // rig.json already holds mirrored yaw and roll for the right legs.
          const axis = ax === "pitch" ? X : ax === "roll" ? Y : Z;
          q.multiply(new THREE.Quaternion().setFromAxisAngle(axis, a));
        }
        node.quaternion.multiply(q);
      }
      const meshName = rig.mesh[name];
      if (geo[meshName]) {
        let g = name[0] === "r" && meshName[0] === "l" ? mirrored(geo[meshName]) : geo[meshName];
        const mat = matFor(name); if (mat.vertexColors) g = stripe(g.clone(), name);
        const mesh = new THREE.Mesh(g, mat); mesh.castShadow = true; node.add(mesh);
      }
      nodes[name] = node;
      if (b.parent) nodes[b.parent].add(node);
    }
    const root = nodes["c_thorax"]; root.position.set(0, 0, 0);
    const holder = new THREE.Group(); holder.add(root); holder.updateMatrixWorld(true);
    const J = n => new Joint(nodes[n]);
    const legs = ["lf", "lm", "lh", "rf", "rm", "rh"].map(id => {
      const hip = nodes[`${id}_coxa`].getWorldPosition(new THREE.Vector3()), foot = nodes[`${id}_tarsus5`].getWorldPosition(new THREE.Vector3());
      const dir = foot.clone().sub(hip); dir.y = 0; dir.normalize();
      return {id, coxa: J(`${id}_coxa`), femur: J(`${id}_trochanterfemur`), tibia: J(`${id}_tibia`), tarsus: J(`${id}_tarsus1`),
              lift: dir.clone().cross(Y).normalize(), fwd: -Math.sign(dir.x) || 1, group: {lf: 0, rm: 0, lh: 0, rf: 1, lm: 1, rh: 1}[id]};
    });
    const wings = ["l_wing", "r_wing"].map(n => {
      const c = new THREE.Box3().setFromObject(nodes[n]).getCenter(new THREE.Vector3()), j = nodes[n].getWorldPosition(new THREE.Vector3());
      return {side: Math.sign(c.x - j.x) || (n[0] === "l" ? 1 : -1), joint: J(n)};
    });
    const halteres = ["l_haltere", "r_haltere"].map(n => ({side: n[0] === "l" ? 1 : -1, joint: J(n)}));
    const ants = ["l_pedicel", "r_pedicel"].map(n => ({side: n[0] === "l" ? 1 : -1, joint: J(n)}));
    const abdomen = ["c_abdomen12", "c_abdomen3", "c_abdomen4", "c_abdomen5", "c_abdomen6"].map(J);
    const rigObj = {holder, legs, wings, halteres, ants, abdomen, head: J("c_head"), rostrum: J("c_rostrum"), haustellum: J("c_haustellum"),
                    stride: 0, tuck: 0, spread: 0, sip: 0, groomH: 0, groomB: 0, twitch: 0};
    const box = new THREE.Box3().setFromObject(holder); const size = box.getSize(new THREE.Vector3());
    const k = BODY / size.z; holder.scale.setScalar(k); holder.updateMatrixWorld(true);
    const box2 = new THREE.Box3().setFromObject(holder); holder.position.y = -box2.min.y; holder.position.z = -(box2.min.z + box2.max.z) / 2;
    nodes["c_head"].add(brain); brain.position.set(0, 0.05, 0.08);
    fly.add(holder); R = rigObj;
  }
  loadRig().then(() => onReady && onReady()).catch(e => console.warn("rig not loaded", e));

  const ease = (a, b, dt, k) => a + (b - a) * Math.min(1, dt * k);
  // Speed in units per second. Airborne folds the legs and opens the wings.
  // act: {feeding, groom: "head"|"body", sniff}
  function animateRig(speed, dt, airborne, t, act) {
    R.stride += Math.abs(speed) * dt / (0.6 * BODY) * Math.PI * 2;   // one cycle per 0.6 body lengths
    const gait = airborne ? 0 : Math.min(1, Math.abs(speed) / (WALK * 0.5));
    R.tuck = ease(R.tuck, airborne ? 1 : 0, dt, 6);
    R.spread = ease(R.spread, airborne ? 1 : 0, dt, 8);
    R.sip = ease(R.sip, act.feeding && !airborne ? 1 : 0, dt, 3);
    R.groomH = ease(R.groomH, act.groom === "head" && !airborne ? 1 : 0, dt, 5);
    R.groomB = ease(R.groomB, act.groom === "body" && !airborne ? 1 : 0, dt, 5);
    R.twitch = ease(R.twitch, act.sniff && !airborne ? 1 : 0, dt, 4);
    // Four grooming motions, each as flies do it. Eyes: the front legs wipe up and over the head, one
    // side leading then the other, and the head tilts into the leg. Antennae: both front legs held low
    // in front, short fast strokes together. Abdomen: the hind legs rub along it while it curls down to
    // meet them. Wings: the hind legs reach up and draw back over one wing, then the other.
    const part = act.part, fast = part === "antennae" ? 40 : part === "wings" ? 16 : part === "abdomen" ? 24 : 26;
    const rub = Math.sin(t * fast);
    const lead = Math.sin(t * (part === "wings" ? 1.6 : 2.4));          // which side is working harder, for eyes and wings
    const reach = part === "antennae" ? 0.78 : part === "wings" ? 1.3 : 1;
    const oneSided = part === "eyes" || part === "wings";
    for (const L of R.legs) {
      const p = R.stride + (L.group ? Math.PI : 0);
      const swing = Math.sin(p) * 0.28 * gait, up = Math.max(0, Math.cos(p));
      const lift = up * 0.35 * gait, flex = up * 0.5 * gait;
      L.coxa.reset(); L.femur.reset(); L.tibia.reset(); L.tarsus.reset();
      L.coxa.turn(Y, L.fwd * (swing - 0.5 * R.tuck));
      L.coxa.turn(L.lift, lift + 0.45 * R.tuck);
      L.tibia.turn(L.lift, -(flex + 1.2 * R.tuck));
      L.tarsus.turn(L.lift, -0.4 * R.tuck);
      const front = L.id[1] === "f", hind = L.id[1] === "h", s = L.id[0] === "l" ? 1 : -1;
      const share = oneSided ? 0.55 + 0.45 * Math.max(-1, Math.min(1, lead * s * 2)) : 1;   // this leg's share of the work
      const stroke = part === "antennae" ? rub : rub * s;                                      // antennae: both legs together
      if (front && R.groomH > 0) { L.coxa.turn(Y, L.fwd * 0.55 * R.groomH); L.coxa.turn(L.lift, (0.75 * reach * share + 0.18 * stroke) * R.groomH); L.tibia.turn(L.lift, -(1.3 + 0.2 * stroke) * R.groomH); }
      if (hind && R.groomB > 0) { L.coxa.turn(Y, -L.fwd * (part === "wings" ? 0.75 : 0.5) * R.groomB); L.coxa.turn(L.lift, (0.7 * reach * share + 0.15 * stroke) * R.groomB); L.tibia.turn(L.lift, -(1.1 + 0.25 * stroke) * R.groomB); }
    }
    // Wings beat mostly above the body plane, drawn as a strobe.
    const flap = airborne ? 0.3 + Math.sin(t * 75) * 0.6 : 0;
    for (const W of R.wings) { W.joint.reset(); W.joint.turn(Y, -W.side * 1.15 * R.spread); W.joint.turn(Z, W.side * flap); }
    for (const H of R.halteres) { H.joint.reset(); H.joint.turn(Z, H.side * flap * 0.5); }
    for (const A of R.ants) { A.joint.reset(); A.joint.turn(Y, A.side * Math.sin(t * 9 + A.side) * 0.22 * R.twitch); A.joint.turn(X, Math.sin(t * 7) * 0.1 * R.twitch); }
    R.rostrum.reset(); R.haustellum.reset();
    R.rostrum.turn(X, -1.5 * R.sip); R.haustellum.turn(X, 2.8 * R.sip);
    R.head.reset(); R.head.turn(X, 0.03 * Math.sin(R.stride * 2) * gait + (R.groomH ? (part === "antennae" ? 0.16 : 0.05) * R.groomH : 0));
    if (R.groomH && part === "eyes") R.head.turn(Z, lead * 0.22 * R.groomH);                 // tilt the head into the working leg
    const curl = part === "abdomen" ? 0.13 + 0.03 * rub : 0;                                 // the abdomen bends down to the hind legs
    for (const A of R.abdomen) { A.reset(); if (R.groomB && curl) A.turn(X, curl * R.groomB); }
    if (R.groomB && part === "wings") for (const W of R.wings) W.joint.turn(Z, W.side * Math.max(0, lead * W.side) * 0.18 * R.groomB);   // the wing being cleaned lifts a little
  }

  // ---- behavior ---------------------------------------------------------
  // The fly flies to a card, lands, walks a little on it while its antennae
  // work, tastes it, and leaves. How long it stays is the verdict.
  let mode = "idle", waypoints = [], dwellMs = 0, dwellUntil = 0, onDone = null, current = pick || order[0];
  let flight = null, onArrive = null;   // flight: {from, to, s, len}
  const act = {feeding: false, groom: null, part: null, sniff: false};
  let heading = 0, speedNow = 0;
  let said = "";
  const say = s => { if (s !== said) { said = s; caption && caption(s); } };
  const onCard = (sym, spread = 0.8) => { const p = dish[sym]; return new THREE.Vector3(p.x + rnd(-1, 1) * CARD.w / 2 * spread, 0, p.z + rnd(-1, 1) * CARD.h / 2 * spread); };
  const nearby = (p, r) => new THREE.Vector3(p.x + rnd(-r, r), 0, p.z + rnd(-r, r));
  function takeOff(to) {
    flight = {from: fly.position.clone().setY(0), to: to.clone().setY(0), s: 0};
    flight.len = Math.max(1, flight.from.distanceTo(flight.to)); mode = "fly";
  }
  function visit(sym, verdict, done, arrive) {
    if (!dish[sym]) { done && done(); return; }
    current = sym; onDone = done || null; onArrive = arrive || null; act.groom = null;
    brainM.userData.level = Math.min(1, ((stocks[sym].cells ? stocks[sym].cells.length : stocks[sym].n) || 0) / 90);
    const land = onCard(sym, 0.7);
    waypoints = [nearby(land, 2.5), nearby(land, 2.5)];
    dwellMs = 1400 + Math.max(0, verdict) / 3 * 2600;
    takeOff(land); say(`Flying to ${short(sym)}`);
  }
  function settle(sym, done, arrive) {
    if (!dish[sym]) return;
    current = sym; onDone = done || null; onArrive = arrive || null; act.groom = null;
    waypoints = [nearby(dish[sym], 3)]; dwellMs = 7000; takeOff(onCard(sym, 0.4)); say(`Going back to ${short(sym)}`);
  }
  function goto(sym) { visit(sym, stocks[sym].verdict, null); }
  function abort() { onDone = null; onArrive = null; exploring = false; groomQueue = []; }

  // Off duty, the fly does what flies do: walks somewhere, flies somewhere,
  // stops to groom or rest.
  let exploring = false, dwellFeed = false;
  // Grooming runs front to rear, the fly's fixed priority (Seeds et al. 2014): eyes, antennae, abdomen,
  // wings. The front legs do the head, the hind legs do the body. A bout can stop after any part.
  const GROOM = [["eyes", "head", 2200, 4200], ["antennae", "head", 1600, 3200], ["abdomen", "body", 2200, 4200], ["wings", "body", 2400, 4600]];
  let groomQueue = [];
  // A bout starts at any part, the front of the body most often, and works toward the rear.
  const GROOM_START = [0.4, 0.25, 0.2, 0.15];
  function startGrooming(now, carryOn = 0.6) {
    groomQueue = []; let t = now;
    let first = 0; for (let r = Math.random(); first < GROOM.length - 1 && r >= GROOM_START[first]; first++) r -= GROOM_START[first];
    for (const [part, legs, lo, hi] of GROOM.slice(first)) { t += rnd(lo, hi); groomQueue.push({part, legs, until: t}); if (Math.random() > carryOn) break; }
    return t - now;
  }
  // How active a fly is at this hour. They are busiest around dawn and dusk, slow at midday and
  // nearly still at night (Drosophila's two daily activity peaks). The viewer's own clock sets it.
  function alertness(date = new Date()) {
    const h = date.getHours() + date.getMinutes() / 60, bump = (at, w) => { const d = ((h - at + 36) % 24 - 12) / w; return Math.exp(-d * d); };
    return Math.min(1, 0.18 + 0.85 * Math.max(bump(7.5, 2.2), bump(19, 2.4)) + 0.2 * bump(13, 3));
  }
  // Three needs, 0 to 1, that rise with time and effort and choose what the
  // fly does off duty. Ours, not the connectome's: the brain here only smells.
  const needs = {hunger: 0.35, thirst: 0.45, tired: 0.2};
  function goSpot(p, label, need, after) {
    const q = nearby(p, 0.5); dwellFeed = true; dwellMs = 3200; onDone = () => { needs[need] = 0.08; dwellFeed = false; after(); };
    if (fly.position.distanceTo(q) > 12) { waypoints = [q]; takeOff(nearby(p, 2)); } else { waypoints = [q]; mode = "walk"; }
    say(label);
  }
  const randomSpot = () => new THREE.Vector3(rnd(-TABLE.x, TABLE.x), 0, rnd(-TABLE.z, TABLE.z));
  // brief: the short warm-up before a replay, which should not make the viewer wait through a nap.
  function explore(steps, done, brief = false) {
    exploring = true; let left = steps;
    const step = () => {
      if (!exploring) return;
      if (left-- <= 0) { exploring = false; done && done(); return; }
      const r = Math.random(); onDone = step; act.groom = null; dwellFeed = false;
      if (needs.tired > 0.8) { waypoints = []; dwellMs = rnd(25000, 40000); mode = "walk"; say("Resting"); return; }
      if (needs.thirst > 0.75) { goSpot(SPOT.water, "Going for water", "thirst", step); return; }
      if (needs.hunger > 0.75) { goSpot(SPOT.sugar, "Going for sugar", "hunger", step); return; }
      if (held.length && r < 0.14) { const h = held[Math.floor(Math.random() * held.length)]; exploring = false; visit(h, stocks[h].verdict, () => { exploring = true; step(); }, () => onSniff && onSniff(h)); return; }
      // A fly is still about half the time, more when it is a quiet hour (Berman et al. 2014).
      // What is left goes to walking, then grooming, then the odd flight.
      const a = alertness(), rest = brief ? 0.1 : 0.82 - 0.35 * a, q = Math.random();
      if (r < rest) { waypoints = []; dwellMs = brief ? rnd(800, 1500) : rnd(8000, 22000) * (1.5 - a); mode = "walk"; say("Resting"); }
      else if (q < 0.5) { waypoints = [nearby(fly.position, 2.5), nearby(fly.position, 2.5)]; dwellMs = rnd(300, 800); mode = "walk"; say("Walking"); }
      else if (q < 0.85) { waypoints = []; mode = "walk"; dwellMs = startGrooming(performance.now(), brief ? 0.2 : 0.6); }
      else { const spot = randomSpot(); waypoints = [nearby(spot, 1.5)]; dwellMs = 300; takeOff(spot); say("Flying"); }
    };
    step();
  }
  function idle() { if (!exploring && mode === "idle") explore(1e9, null); }

  const tmp = new THREE.Vector3(), walkTmp = new THREE.Vector3();
  function step(dt, now) {
    let airborne = false; speedNow = 0;
    // Needs drift up; flying costs the most, resting pays it back.
    const still = mode === "dwell" && !act.groom && !act.feeding;
    // Minutes, not seconds: hungry in about a quarter of an hour, thirsty in ten minutes. A flight is
    // the expensive thing. Rest pays tiredness back over most of a minute.
    needs.hunger = Math.min(1, needs.hunger + dt * 0.0011);
    needs.thirst = Math.min(1, needs.thirst + dt * 0.0017);
    needs.tired = Math.max(0, Math.min(1, needs.tired + dt * (mode === "fly" ? 0.022 : mode === "walk" && waypoints.length ? 0.004 : still ? -0.018 : 0.0006)));
    // Flies clean themselves right after landing, most of the time.
    // A new instruction can arrive mid-flight (Replay pressed, a card clicked). The fly must come
    // down before it does anything on foot, or it walks on air.
    if (mode !== "fly" && fly.position.y > 0) { fly.position.y = Math.max(0, fly.position.y - dt * 14); fly.rotation.y = heading; return fly.position.y > 0; }
    if (mode !== "fly" && groomQueue.length) {
      while (groomQueue.length && now >= groomQueue[0].until) groomQueue.shift();
      if (groomQueue.length) { const g = groomQueue[0]; act.groom = g.legs; act.part = g.part; say(`Grooming its ${g.part}`); fly.rotation.y = heading; return false; }
      act.groom = null; act.part = null;
      // The bout is over: the caption goes back to what the fly is doing now.
      say(exploring ? (waypoints.length ? "Walking" : "Resting") : `Walking on ${short(current)}`);
    }
    if (mode === "fly") {
      airborne = true;
      flight.s = Math.min(1, flight.s + dt * FLIGHT / flight.len);
      const s = flight.s, e = s * s * (3 - 2 * s);
      tmp.lerpVectors(flight.from, flight.to, e);
      const h = Math.min(AIR, flight.len * 0.35) * Math.sin(Math.PI * s) + 0.03 * Math.sin(now * 0.02);
      const ahead = tmp.clone().sub(fly.position);
      fly.position.set(tmp.x, h, tmp.z); speedNow = FLIGHT;
      if (ahead.lengthSq() > 1e-6) heading = Math.atan2(ahead.x, ahead.z);
      if (s >= 1) { fly.position.y = 0; mode = "walk"; if (exploring ? Math.random() < 0.65 : Math.random() < 0.3) startGrooming(now, exploring ? 0.35 : 0); say(exploring ? "Walking" : `Walking on ${short(current)}`); }
    } else if (mode === "walk") {
      const w = waypoints[0];
      if (!w) { mode = "dwell"; dwellUntil = now + dwellMs; act.feeding = !exploring || dwellFeed; act.sniff = !exploring;
        if (!exploring && dish[current]) say(`Sniffing ${short(current)}`);
        if (onArrive) { const f = onArrive; onArrive = null; f(); } if (dwellFeed) say(needs.thirst > needs.hunger ? "Drinking" : "Feeding"); return false; }
      const d = walkTmp.copy(w).sub(fly.position); d.y = 0; const dist = d.length();
      if (dist < 0.12) { waypoints.shift(); return false; }
      const want = Math.atan2(d.x, d.z); let diff = want - heading; diff = Math.atan2(Math.sin(diff), Math.cos(diff));
      const turn = Math.sign(diff) * Math.min(Math.abs(diff), dt * 5); heading += turn;
      if (Math.abs(diff) < 0.6) { const v = Math.min(dist, WALK * dt); fly.position.x += Math.sin(heading) * v; fly.position.z += Math.cos(heading) * v; speedNow = WALK; }
      else speedNow = WALK * 0.5;
      act.sniff = !exploring;
    } else if (mode === "dwell") {
      if (now >= dwellUntil) {
        mode = "idle"; act.feeding = false; act.sniff = false;
        if (onDone) { const f = onDone; onDone = null; f(); } else say(`Staying on ${short(current)}`);
      }
    }
    fly.rotation.y = heading;
    return airborne;
  }

  // ---- camera --------------------------------------------------------------
  let slideNow = -1, flightFeel = 0;
  let view = "follow", orbit = 0.6, tilt = 0, dragging = null, dragUntil = 0, debugTop = false;
  canvas.addEventListener("pointerdown", e => { dragging = {x: e.clientX, y: e.clientY}; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener("pointermove", e => { if (!dragging) return; orbit += (e.clientX - dragging.x) * 0.006; tilt = Math.max(-0.6, Math.min(1.2, tilt - (e.clientY - dragging.y) * 0.004)); dragging = {x: e.clientX, y: e.clientY}; dragUntil = performance.now() + 4000; });
  canvas.addEventListener("pointerup", () => { dragging = null; });
  const camPos = new THREE.Vector3(0, 60, 90), look = new THREE.Vector3(), wantPos = new THREE.Vector3(), wantLook = new THREE.Vector3(), camOff = new THREE.Vector3(0, 60, 90);
  function setView(v) { view = v; }
  function updateCamera(dt, moving) {
    // The camera drifts round the fly all the time, faster when it travels.
    if (!reduce && performance.now() > dragUntil) orbit += dt * (moving ? 0.12 : 0.16);
    const aspect = camera.aspect || 1.6, fit = Math.max(1, 1.6 / aspect);
    if (view === "wide") { const d = 108 * fit; wantPos.set(Math.sin(orbit * 0.2) * d, (62 + tilt * 40) * fit, Math.cos(orbit * 0.2) * d); wantLook.set(0, 0, 0); }
    else {
      const dist = (view === "close" ? 0.9 : 2.4) * fit, height = (view === "close" ? 0.42 : 0.95) * (1 + tilt);
      wantLook.copy(fly.position); wantLook.y += view === "close" ? BODY * 0.4 : 0.2;
      wantPos.set(fly.position.x + Math.sin(orbit) * dist, fly.position.y + height, fly.position.z + Math.cos(orbit) * dist);
    }
    // The camera rides with the fly: its position is the fly's plus an offset
    // that eases, so a flight never leaves the frame and a view change glides.
    if (view === "wide") { camPos.lerp(wantPos, Math.min(1, dt * 2)); look.lerp(wantLook, Math.min(1, dt * 2)); }
    else { wantPos.sub(fly.position); camOff.lerp(wantPos, Math.min(1, dt * 4)); camPos.copy(fly.position).add(camOff); look.copy(wantLook); }
    // In the air the shot loosens: a wider lens, a little handheld shake, a slight bank.
    flightFeel += ((mode === "fly" && !reduce ? 1 : 0) - flightFeel) * Math.min(1, dt * 4);
    const ft = performance.now() / 1000, amp = 0.009 * flightFeel * (view === "wide" ? 0 : camOff.length());
    camera.position.copy(camPos).add(tmp.set(Math.sin(ft * 5.1) + 0.4 * Math.sin(ft * 9.3), Math.sin(ft * 6.7) + 0.4 * Math.sin(ft * 11.9), Math.sin(ft * 4.3)).multiplyScalar(amp));
    camera.lookAt(look);
    camera.rotateZ(Math.sin(ft * 1.4) * 0.02 * flightFeel);
    const fov = 32 + 6 * flightFeel; if (Math.abs(camera.fov - fov) > 0.01) { camera.fov = fov; camera.updateProjectionMatrix(); }
    if (debugTop) { camera.position.set(fly.position.x + 0.001, fly.position.y + 1.1, fly.position.z); camera.lookAt(fly.position); }
    // The brain panel covers the right of the frame, so the picture is slid
    // left: a little on a wide window, a lot on a narrow one.
    const cw = canvas.clientWidth, ch = canvas.clientHeight, slide = view === "wide" ? 0 : cw < 900 ? 0.27 : 0.12;
    if (slide !== slideNow) { slideNow = slide; if (slide) camera.setViewOffset(cw, ch, cw * slide, 0, cw, ch); else camera.clearViewOffset(); }
  }

  const t0 = performance.now(); let last = t0;
  function frame(now) {
    resize();
    const dt = Math.min(0.05, (now - last) / 1000); last = now; const t = (now - t0) / 1000;
    let airborne = false;
    if (reduce) { const q = dish[current]; if (q) fly.position.set(q.x, 0, q.z); }
    else airborne = step(dt, now);
    if (mode === "idle" && !exploring && !reduce) idle();
    const moving = mode === "fly" || (mode === "walk" && waypoints.length > 0);
    if (R) animateRig(reduce ? 0 : speedNow, dt, airborne, t, act);
    const level = brainM.userData.level || 0;
    brainM.opacity = act.sniff || act.feeding ? level * 0.45 * (0.55 + 0.45 * Math.abs(Math.sin(t * 6))) : 0;
    sun.position.copy(fly.position).add(tmp.set(18, 40, 12)); sun.target.position.copy(fly.position);
    if (!reduce) motes.step(dt, t);
    updateCamera(dt, moving);
    renderer.render(scene, camera);
  }
  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== Math.floor(w * renderer.getPixelRatio()) || canvas.height !== Math.floor(h * renderer.getPixelRatio())) { renderer.setSize(w, h, false); camera.aspect = w / h; slideNow = -1; camera.clearViewOffset(); camera.updateProjectionMatrix(); }
  }
  { const home = dish[pick] || dish[order[0]]; fly.position.set(home.x + 3, 0, home.z + 2); }
  window.__fly3d = {scene, camera, renderer, fly, portrait, snapshot, top: v => { debugTop = v; }, debug: () => ({mode, view, tilt, orbit, look: look.toArray(), wantLook: wantLook.toArray(), camPos: camPos.toArray(), waypoints: waypoints.length, act: {...act}, exploring, flight: flight && flight.s})};

  // Run the loop only while the canvas is on screen and the tab is visible. A 3D view that keeps
  // drawing after the reader has scrolled past it costs battery and GPU memory for nothing.
  let raf = 0, onScreen = true, alive = true;
  const tick = now => { raf = 0; if (!alive) return; frame(now); if (onScreen && !document.hidden) raf = requestAnimationFrame(tick); };
  const wake = () => { if (alive && !raf && onScreen && !document.hidden) { last = performance.now(); raf = requestAnimationFrame(tick); } };
  const watcher = new IntersectionObserver(es => { onScreen = es[0].isIntersecting; wake(); }, {rootMargin: "120px"});
  watcher.observe(canvas); document.addEventListener("visibilitychange", wake);
  // Free everything the GPU holds. A full page load does this anyway; a single-page app moving to
  // another route does not, and that is where a 3D view leaks.
  function dispose() {
    alive = false; cancelAnimationFrame(raf); watcher.disconnect(); document.removeEventListener("visibilitychange", wake);
    scene.traverse(o => {
      if (o.geometry) o.geometry.dispose();
      for (const m of [].concat(o.material || [])) { for (const k in m) if (m[k] && m[k].isTexture) m[k].dispose(); m.dispose(); }
    });
    if (scene.environment) scene.environment.dispose();
    renderer.dispose(); renderer.forceContextLoss();
  }
  addEventListener("pagehide", dispose, {once: true});
  wake();
  // A portrait of the fly alone on a transparent ground, for avatars. Same model,
  // same materials and light as the scene. yaw and pitch are in radians, measured
  // from the fly's own heading, so yaw 0 looks it in the face.
  function portrait({size = 512, yaw = 0.6, pitch = 0.35, dist = 0.5, aim = [0, 0.1, 0.09], pose = "stand", fov = 28} = {}) {
    if (!R) return null;
    const hidden = scene.children.filter(o => o !== fly && !o.isLight && o.visible);
    hidden.forEach(o => { o.visible = false; });
    const fog = scene.fog, was = {pos: fly.position.clone(), rot: fly.rotation.y, glow: brainM.opacity};
    // A render target skips the screen's tone mapping, so the same lights come out too bright. Turn them down for the shot.
    const lights = scene.children.filter(o => o.isLight), levels = lights.map(l => l.intensity);
    lights.forEach(l => { l.intensity *= 0.52; });
    scene.fog = null; brainM.opacity = 0; fly.position.set(0, pose === "fly" ? 1 : 0, 0); fly.rotation.y = 0;
    animateRig(0, 1, pose === "fly", 0.011, {feeding: pose === "feed", groom: pose === "groom" ? "head" : null, sniff: false});
    sun.position.set(18, 40, 12).add(fly.position); sun.target.position.copy(fly.position); sun.target.updateMatrixWorld();
    const cam = new THREE.PerspectiveCamera(fov, 1, 0.01, 50);
    const at = new THREE.Vector3(aim[0], aim[1], aim[2]).add(fly.position);
    cam.position.set(at.x + Math.sin(yaw) * Math.cos(pitch) * dist, at.y + Math.sin(pitch) * dist, at.z + Math.cos(yaw) * Math.cos(pitch) * dist);
    cam.lookAt(at);
    const target = new THREE.WebGLRenderTarget(size, size, {samples: 4}); target.texture.encoding = THREE.sRGBEncoding;
    const clear = new THREE.Color(); renderer.getClearColor(clear); const alpha = renderer.getClearAlpha();
    renderer.setClearColor(0x000000, 0); renderer.setRenderTarget(target); renderer.clear(); renderer.render(scene, cam);
    const px = new Uint8Array(size * size * 4); renderer.readRenderTargetPixels(target, 0, 0, size, size, px);
    renderer.setRenderTarget(null); renderer.setClearColor(clear, alpha); target.dispose();
    lights.forEach((l, k) => { l.intensity = levels[k]; });
    hidden.forEach(o => { o.visible = true; }); scene.fog = fog; fly.position.copy(was.pos); fly.rotation.y = was.rot; brainM.opacity = was.glow;
    const c = document.createElement("canvas"); c.width = c.height = size; const g = c.getContext("2d"), img = g.createImageData(size, size);
    for (let y = 0; y < size; y++) img.data.set(px.subarray((size - 1 - y) * size * 4, (size - y) * size * 4), y * size * 4);   // GL rows run bottom-up
    g.putImageData(img, 0, 0); return c;
  }

  // A staged still for figures: the fly tasting a card, the chart behind it. It does not wait for
  // the animation, so it works when the tab is in the background. Renders to a target, with the
  // lights turned down because a target skips the screen's tone mapping, and puts everything back.
  function snapshot({w = 1600, h = 900, sym = pick || order[0], yaw = 2.5, pitch = 0.32, dist = 1.15} = {}) {
    if (!R || !dish[sym]) return null;
    const was = {pos: fly.position.clone(), rot: fly.rotation.y, glow: brainM.opacity, fog: scene.fog};
    const lights = scene.children.filter(o => o.isLight), levels = lights.map(l => l.intensity);
    lights.forEach(l => { l.intensity *= 0.52; }); scene.fog = null; brainM.opacity = 0;
    fly.position.set(dish[sym].x - 2.2, 0, dish[sym].z + 1.4); fly.rotation.y = 0.5;
    animateRig(0, 1, false, 0.011, {feeding: true, groom: null, part: null, sniff: true});
    sun.position.set(18, 40, 12).add(fly.position); sun.target.position.copy(fly.position); sun.target.updateMatrixWorld(); scene.updateMatrixWorld(true);
    const cam = new THREE.PerspectiveCamera(30, w / h, 0.02, 600), at = fly.position.clone().add(new THREE.Vector3(0.12, 0.1, 0));
    cam.position.set(at.x + Math.sin(yaw) * Math.cos(pitch) * dist, at.y + Math.sin(pitch) * dist, at.z + Math.cos(yaw) * Math.cos(pitch) * dist); cam.lookAt(at);
    const target = new THREE.WebGLRenderTarget(w, h, {samples: 4}); target.texture.encoding = THREE.sRGBEncoding;
    renderer.setRenderTarget(target); renderer.clear(); renderer.render(scene, cam);
    const px = new Uint8Array(w * h * 4); renderer.readRenderTargetPixels(target, 0, 0, w, h, px);
    renderer.setRenderTarget(null); target.dispose();
    lights.forEach((l, k) => { l.intensity = levels[k]; }); scene.fog = was.fog; brainM.opacity = was.glow; fly.position.copy(was.pos); fly.rotation.y = was.rot;
    const c = document.createElement("canvas"); c.width = w; c.height = h; const g = c.getContext("2d"), img = g.createImageData(w, h);
    for (let y = 0; y < h; y++) img.data.set(px.subarray((h - 1 - y) * w * 4, (h - y) * w * 4), y * w * 4);
    g.putImageData(img, 0, 0); return c;
  }

  // How busy the body is, 0 to 1: resting, grooming, walking, flying. The
  // readout under the brain uses it for its baseline.
  function activity() {
    if (reduce) return 0.1;
    if (mode === "fly") return 0.9;
    if (mode === "walk" && waypoints.length) return 0.5;
    if (act.groom) return 0.3;
    if (act.sniff || act.feeding) return 0.35;
    return 0.08;
  }
  return {visit, settle, goto, abort, explore, setView, activity, dispose, needs: () => ({...needs}), setHeld: h => { held = h.slice(); }, get view() { return view; }};
};
