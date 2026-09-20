// The real brain: MaleCNS v1.0 neuropil meshes (FlyEM at HHMI Janelia, Google
// Research, Cambridge Connectomics Group, CC BY 4.0), decimated for the page
// by scripts/build_brain_meshes.py. On both sides, the antennal lobe's 58
// glomeruli, the calyx, the pedunculus and the 15 lobe compartments light up
// from the same replay that drives the schematic. The lateral horns are drawn
// dim for orientation; the brain shell is a ghost around them.
window.Brain3D = function (opts) {
  const {canvas, col, channels, base = ""} = opts;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: true});
  renderer.setPixelRatio(Math.min(devicePixelRatio, matchMedia("(max-width: 860px)").matches ? 1.5 : 2)); renderer.setClearColor(0x000000, 0);
  renderer.outputEncoding = THREE.sRGBEncoding; renderer.toneMapping = THREE.ACESFilmicToneMapping;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 2, 1, 5000);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x202028, 1.1));
  const key = new THREE.DirectionalLight(0xffffff, 0.8); key.position.set(300, 500, 600); scene.add(key);
  const rim = new THREE.DirectionalLight(0x8fb8ff, 0.5); rim.position.set(-400, 100, -500); scene.add(rim);
  const group = new THREE.Group(); scene.add(group);
  // EM volumes put y down and z back. Flip so dorsal is up and the front faces the camera.
  group.rotation.x = Math.PI;

  const brand = new THREE.Color(col("--brand")), accent = new THREE.Color(col("--accent"));
  const parts = {};   // name -> {mesh, group, base}
  const glom = {}, comps = [];
  const calyces = [], peds = []; const focus = new THREE.Vector3(0, 0, 0);
  async function load() {
    const [meta, bin] = await Promise.all([fetch(base + "model/brain/brain.json").then(r => r.json()), fetch(base + "model/brain/brain.bin").then(r => r.arrayBuffer())]);
    for (const m of meta.meshes) {
      const pos = new Float32Array(bin, m.offset, m.vertices * 3), idx = new Uint32Array(bin, m.offset + m.vertices * 12, m.triangles * 3);
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(pos, 3)); g.setIndex(new THREE.BufferAttribute(idx, 1)); g.computeVertexNormals();
      let mat;
      if (m.group === "shell") mat = new THREE.MeshStandardMaterial({color: 0xb8c0d0, transparent: true, opacity: 0.075, depthWrite: false, roughness: 0.9, side: THREE.FrontSide});
      else if (m.group === "context") mat = new THREE.MeshStandardMaterial({color: 0x4a4a58, transparent: true, opacity: 0.22, roughness: 0.8});   // the other hemisphere and the lateral horn, dim: the circuit runs there too, the panel lights one side
      else if (m.group === "glomerulus") mat = new THREE.MeshStandardMaterial({color: 0x1a2a40, emissive: accent, emissiveIntensity: 0, roughness: 0.5});
      else mat = new THREE.MeshStandardMaterial({color: 0x1c3226, emissive: brand, emissiveIntensity: 0, roughness: 0.5});
      const mesh = new THREE.Mesh(g, mat); mesh.renderOrder = m.group === "shell" ? 3 : m.group === "context" ? 2 : 1;
      group.add(mesh);
      const part = {mesh, group: m.group, level: 0, target: 0, halo: null};
      if (mat.emissive) {
        // A cheap glow: the same shape, a little bigger, drawn additively.
        const c = new THREE.Vector3(...m.centre), hg = g.clone().translate(-c.x, -c.y, -c.z);
        const halo = new THREE.Mesh(hg, new THREE.MeshBasicMaterial({color: mat.emissive, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.BackSide}));
        halo.position.copy(c); halo.scale.setScalar(1.22); halo.renderOrder = 4; group.add(halo); part.halo = halo;
      }
      parts[m.name] = part;
      // Both hemispheres run in the simulation, so a channel lights its glomerulus on both sides.
      if (m.group === "glomerulus") { const k = m.name.replace(/^AL-|\([RL]\)$/g, ""); (glom[k] = glom[k] || []).push(part); }
      if (m.group === "compartment") comps.push(part);
      if (m.group === "calyx") calyces.push(part); if (m.group === "pedunculus") peds.push(part);
    }
    // Frame the olfactory circuit, not the whole brain.
    const mean = names => { const v = new THREE.Vector3(); const ms = meta.meshes.filter(m => names.includes(m.group)); ms.forEach(m => v.add(new THREE.Vector3(...m.centre))); return v.divideScalar(ms.length); };
    focus.copy(mean(["glomerulus"]).lerp(mean(["compartment", "calyx", "pedunculus"]), 0.5)); focus.y *= -1; focus.z *= -1;
  }
  load().then(() => { if (lastSmell) setSmell(...lastSmell); }).catch(e => console.warn("brain meshes not loaded", e));

  // What is lit right now. A sniff arrives at the glomeruli, then the calyx,
  // then runs down the pedunculus into the lobes, a few hundred milliseconds
  // apart, which is roughly the order the real circuit fires in.
  let wave = 0, cellsLevel = 0, lastSmell = null;
  function setSmell(activations, cells) {
    lastSmell = [activations, cells];
    for (const k in glom) glom[k].forEach(p => { p.target = 0; });
    for (const ch in activations) {
      const orn = channels[ch]; if (!orn) continue;
      const name = orn.replace(/^ORN_/, "").replace(/^(VM6)[lmv]$/, "$1");
      if (glom[name]) glom[name].forEach(p => { p.target = Math.max(p.target, activations[ch]); });
    }
    cellsLevel = Math.min(1, (cells || 0) / 90);
    wave = performance.now();
  }
  function pulse(part, sinceMs, delay, hold) {
    const x = sinceMs - delay; if (x < 0) return 0;
    return x < hold ? 1 : Math.max(0, 1 - (x - hold) / 900);
  }

  let drag = null, yaw = 0.35, pitch = 0.12, spin = true, zoom = 1;
  canvas.addEventListener("wheel", e => { e.preventDefault(); zoom = Math.max(0.35, Math.min(2.5, zoom * Math.exp(e.deltaY * 0.0015))); }, {passive: false});
  canvas.addEventListener("pointerdown", e => { drag = {x: e.clientX, y: e.clientY, yaw, pitch}; spin = false; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener("pointermove", e => { if (!drag) return; yaw = drag.yaw + (e.clientX - drag.x) * 0.008; pitch = Math.max(-1.2, Math.min(1.2, drag.pitch + (e.clientY - drag.y) * 0.008)); });
  let idleTimer = null;
  canvas.addEventListener("pointerup", () => { drag = null; clearTimeout(idleTimer); idleTimer = setTimeout(() => { spin = true; }, 6000); });

  let last = performance.now();
  function frame(now) {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== Math.floor(w * renderer.getPixelRatio()) || canvas.height !== Math.floor(h * renderer.getPixelRatio())) { renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (spin && !reduce) yaw += dt * 0.4;
    const dist = 980 * zoom * Math.max(1, 1.35 / (camera.aspect || 1.35));
    camera.position.set(focus.x + Math.sin(yaw) * Math.cos(pitch) * dist, focus.y + Math.sin(pitch) * dist, focus.z + Math.cos(yaw) * Math.cos(pitch) * dist);
    camera.lookAt(focus);
    const since = now - wave;
    const glow = reduce ? 1 : 0.7 + 0.3 * Math.abs(Math.sin(now / 160));
    const lit = (p, v) => { p.mesh.material.emissiveIntensity = v * 2.4; if (p.halo) p.halo.material.opacity = v * 0.45; };
    for (const k in glom) glom[k].forEach(p => { p.level += (p.target - p.level) * Math.min(1, dt * 8); lit(p, p.level * glow); });
    calyces.forEach(p => lit(p, cellsLevel * pulse(p, since, 180, 1400) * glow));
    peds.forEach(p => lit(p, cellsLevel * pulse(p, since, 380, 900) * 0.8 * glow));
    comps.forEach((p, i) => lit(p, cellsLevel * pulse(p, since, 520 + (i % 15) * 25, 700) * 0.6 * glow));
    renderer.render(scene, camera);
  }

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
  return {setSmell, dispose};
};
