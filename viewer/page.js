// The page logic for "Can a fly trade stocks?": the smell encoding, the diagram, the readouts, the
// replay. It takes one session and wires it to the markup by id, so the same file runs the local
// concept page and the ClawStreet route. Whoever calls it supplies the session:
//   FlyPage({STOCKS, ORDER, PICK, CANDLES, META, base})
// base is the folder the 3D assets are served from, "" locally and "/fly/" on ClawStreet.
window.FlyPage = function ({STOCKS, ORDER, PICK, CANDLES, META, base = "", site = "https://www.clawstreet.io"}) {
  // dispose() stops everything this call started: listeners on the document, timers, both 3D scenes.
  const life = new AbortController(); let alive = true; const timers = [];
  const later = (fn, ms) => { const id = setTimeout(() => alive && fn(), ms); timers.push(id); return id; };
  const N_KC = 4064;
  const short = sym => sym.replace(/^X:/, "").replace(/USD$/, "");
  // Replays and agent names come from whoever runs a fly. They go into HTML as text, never as markup.
  // A ticker links to its symbol page on ClawStreet. Crypto symbols carry a colon, so the path is encoded.
  const symLink = sym => `<a class="sym" href="${site}/symbols/${encodeURIComponent(sym)}">${esc(short(sym))}</a>`;
  const esc = v => String(v).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const money = v => "$" + Math.round(v).toLocaleString("en-US");
  const statusText = () => esc(`${META.market ? META.market + " · " : ""}Session ${META.session} · ${META.date}${META.dry ? " · rehearsal" : ""} · `) +
    (META.holdsNow && META.holdsNow.length ? `holds ${META.holdsNow.map(symLink).join(", ")}` : "holds nothing yet");
  // ---- the smell, same rule as fly_smell.py ---------------------------
  const lin = (a,b,n)=>Array.from({length:n},(_,i)=>a+(b-a)*i/(n-1));
  const geo = (a,b,n)=>Array.from({length:n},(_,i)=>a*Math.pow(b/a,i/(n-1)));
  const FEATURES = [
    {k:"rsi", label:"RSI", c:lin(15,85,8), fmt:v=>v.toFixed(1)},
    {k:"bb_position", label:"Position in Bollinger band", c:lin(0,1,8), fmt:v=>v.toFixed(2)},
    {k:"distance_from_sma50", label:"Distance from 50-day average", c:lin(-.2,.2,8), fmt:v=>(v*100).toFixed(1)+"%"},
    {k:"volume_ratio", label:"Volume vs average", c:geo(.5,3,8), fmt:v=>v.toFixed(2)+"×"},
    {k:"price_change_5d", label:"5-day return", c:lin(-.15,.15,8), fmt:v=>(v*100).toFixed(1)+"%"},
    {k:"sentiment", label:"News sentiment", c:lin(-1,1,4), fmt:v=>v.toFixed(2)},
  ];
  const CATS = {rsi_trend:["rising","falling","flat"], earnings:["tomorrow","this week","later","none"]};
  const WIDTH = 0.75;
  function channels(){ const n=[]; for(const f of FEATURES) f.c.forEach((_,i)=>n.push(`${f.k}[${i}]`)); for(const k in CATS) CATS[k].forEach(v=>n.push(`${k}=${v}`)); return n; }
  const CH = channels();
  function smell(r){
    const out = {};
    for(const f of FEATURES){
      const v = r[f.k]; if(v==null) continue;
      const sp = (f.c[f.c.length-1]-f.c[0])/(f.c.length-1);
      const s = f.c.map(c=>Math.exp(-Math.pow((v-c)/(WIDTH*sp),2)));
      const pk = Math.max(...s);
      s.forEach((x,i)=>{ if(x/pk>0.02) out[`${f.k}[${i}]`]=x/pk; });
    }
    for(const k in CATS){ if(CATS[k].includes(r[k])) out[`${k}=${r[k]}`]=1; }
    return out;
  }
  const vec = a => CH.map(n=>a[n]||0);
  const cos = (a,b)=>{ let d=0,x=0,y=0; for(let i=0;i<a.length;i++){d+=a[i]*b[i];x+=a[i]*a[i];y+=b[i]*b[i];} return x&&y? d/Math.sqrt(x*y):0; };
  for(const s of ORDER){ STOCKS[s].smell = smell(STOCKS[s].r); STOCKS[s].vec = vec(STOCKS[s].smell); }

  // ---- the fly at the table, driven by the same replay --------------------
  const css = getComputedStyle(document.querySelector(".flypage") || document.documentElement); const col = n => css.getPropertyValue(n).trim();

  const fly3d = (typeof THREE !== "undefined" && window.Fly3D) ? Fly3D({base, canvas: document.getElementById("fly3d"), stocks: STOCKS, order: ORDER, candles: CANDLES, pick: PICK, col,
    caption: t => { document.getElementById("cap3d").textContent = t; },
    // A page with a still image over the canvas fades it out once the fly is on the table.
    onReady: () => { document.querySelector(".hero").classList.add("live"); },
    onSniff: sym => { show(sym, true); barSniff(sym); if (bought) barPick(); }}) : null;
  let bought = false;
  document.getElementById("status").innerHTML = statusText(false);
  if (META.botId) {
    // The profile carries ClawStreet's follow button; trades is the fly's full fill history.
    const profile = `${site}/agents/${META.botId}`;
    document.getElementById("follow").hidden = false;
    document.getElementById("followLink").textContent = `Follow ${META.name}`; document.getElementById("followLink").href = profile;
    document.getElementById("tradesLink").href = `${profile}/trades`;
  }
  {
    // Name in bold, balance in regular weight, return in green or red.
    const label = f => {
      const r = f.ret, tone = r > 0 ? "up" : r < 0 ? "down" : "flat";
      return `<span class="nm">${esc(f.name)}</span>` + (f.equity == null ? "" :
        `<span class="eq">$${Math.round(f.equity).toLocaleString("en-US")}</span><span class="rt ${tone}">${r > 0 ? "+" : r < 0 ? "\u2212" : ""}${Math.abs(r || 0).toFixed(2)}%</span>`);
    };
    const roster = META.roster || [{id: META.fly, name: META.name}];
    const btn = document.getElementById("flybtn"), menu = document.getElementById("flymenu");
    btn.innerHTML = label(roster.find(f => f.id === META.fly) || roster[0]) + (roster.length > 1 ? '<span class="caret"></span>' : "");
    // A plain path plus the query, so a "#how" left over from the jump link does not scroll the new page down.
    menu.innerHTML = roster.map(f => `<li><a href="${location.pathname}?fly=${encodeURIComponent(f.id)}"${f.id === META.fly ? ' aria-current="true"' : ""}>${label(f)}</a></li>`).join("");
    const open = on => { menu.hidden = !on; btn.setAttribute("aria-expanded", String(on)); };
    btn.addEventListener("click", () => { if (roster.length > 1) open(menu.hidden); });
    document.addEventListener("click", e => { if (!e.target.closest("#flypick")) open(false); }, {signal: life.signal});
    document.addEventListener("keydown", e => { if (e.key === "Escape") { open(false); btn.focus(); } }, {signal: life.signal});
  }
  if (fly3d) timers.push(setInterval(() => { const n = fly3d.needs(); document.querySelectorAll("[data-need]").forEach(b => { b.style.width = Math.round(n[b.dataset.need] * 100) + "%"; }); }, 500));
  // Count down to the next session. A daily fly decides at 15:30 New York time on weekdays, half an
  // hour before the close. A "4h" fly decides every four hours, weekends too.
  // New York's clock for a moment in time, as [year, month, day, weekday 0-6, UTC offset in ms].
  const newYork = at => {
    const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", {timeZone: "America/New_York", hourCycle: "h23",
      year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric", second: "numeric"}).formatToParts(at).map(x => [x.type, +x.value]));
    const wall = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
    return [p.year, p.month - 1, p.day, new Date(wall).getUTCDay(), wall - Math.floor(at.getTime() / 1000) * 1000];
  };
  (function tick() {
    const now = new Date(); let next;
    const hours = /^(\d+)h$/.exec(META.cadence);
    if (hours) { const h = +hours[1] * 3600e3; next = new Date(Math.ceil((now.getTime() + 1) / h) * h); }
    else {
      // A stock fly decides at listed New York times on weekdays. "daily" is 15:30.
      const times = META.cadence === "daily" ? ["15:30"] : META.cadence.split(",").sort();
      const [y, m, d] = newYork(now);
      search: for (let k = 0; k < 8; k++) {
        const noon = new Date(Date.UTC(y, m, d + k, 17)), [, , , weekday, offset] = newYork(noon);
        if (weekday === 0 || weekday === 6) continue;
        for (const t of times) {
          const [hh, mm] = t.split(":").map(Number);
          next = new Date(Date.UTC(y, m, d + k, hh, mm) - offset);
          if (next > now) break search;
        }
      }
    }
    const s = Math.floor((next - now) / 1000), hh = Math.floor(s / 3600), mm = Math.floor(s % 3600 / 60), ss = s % 60;
    document.getElementById("next").textContent = `Next pick in ${hh}h ${String(mm).padStart(2, "0")}m ${String(ss).padStart(2, "0")}s`;
    later(tick, 1000);
  })();
  document.querySelectorAll("[data-view]").forEach(b => b.addEventListener("click", () => {
    if (fly3d) fly3d.setView(b.dataset.view);
    document.querySelectorAll("[data-view]").forEach(x => x.classList.toggle("on", x === b));
  }));
  let brain3d = null;
  document.getElementById("brainbig").addEventListener("click", e => { const big = document.querySelector(".ov-brain").classList.toggle("big"); const b = document.getElementById("brainbig"); b.title = big ? "Smaller" : "Larger"; b.setAttribute("aria-label", big ? "Make the brain panel smaller" : "Make the brain panel larger"); });

  // ---- brain schematic --------------------------------------------------
  const svg = document.getElementById("brain");
  const NS = "http://www.w3.org/2000/svg";
  const el = (t,a={},parent=svg)=>{ const e=document.createElementNS(NS,t); for(const k in a) e.setAttribute(k,a[k]); parent.appendChild(e); return e; };
  const text = (x,y,s,cls,anchor="start")=>{ const t=el("text",{x,y,class:cls,"text-anchor":anchor}); t.textContent=s; return t; };

  // antennal lobe: 51 glomeruli on a phyllotaxis spiral inside a blob
  const AL = {cx:150, cy:190, r:118};
  el("circle",{cx:AL.cx,cy:AL.cy,r:AL.r,fill:"var(--panel)",stroke:"var(--grid)"});
  text(AL.cx, 52, "51 SMELL CHANNELS", "lbl", "middle");
  const gloms = CH.map((name,i)=>{
    const a = i*2.399963, rr = 12 + (AL.r-24)*Math.sqrt((i+.5)/CH.length);
    const g = el("circle",{cx:AL.cx+rr*Math.cos(a), cy:AL.cy+rr*Math.sin(a), r:9, class:"glom", fill:"var(--accent)","fill-opacity":0.06});
    const tt = el("title",{},g); tt.textContent = name; return g;
  });
  // tract
  el("path",{d:`M ${AL.cx+AL.r} ${AL.cy} C 330 190 330 190 ${420-96} 190`, fill:"none", stroke:"var(--grid)","stroke-width":2});
  text(300, 178, "relay neurons", "cap", "middle");

  // calyx: 4,064 Kenyon cells as a 64x64 dot field inside a rounded blob
  const CA = {x:420, y:96, w:192, h:192};
  el("rect",{x:CA.x-10,y:CA.y-10,width:CA.w+20,height:CA.h+20,rx:44,fill:"var(--panel)",stroke:"var(--grid)"});
  text(CA.x+CA.w/2, 52, "4,064 LEARNING CELLS", "lbl", "middle");
  const kcs = [];
  for(let i=0;i<N_KC;i++){ const gx=i%64, gy=(i-gx)/64; kcs.push(el("circle",{cx:CA.x+gx*3+1.5, cy:CA.y+gy*3+1.5, r:1.1, class:"kc"})); }
  text(CA.x+CA.w/2, CA.y+CA.h+38, "one neuron keeps about 4% active", "cap", "middle");

  // lobes: 15 dopamine compartments
  el("path",{d:`M ${CA.x+CA.w+10} 190 C 660 190 660 190 690 190`, fill:"none", stroke:"var(--grid)","stroke-width":2});
  text(700, 52, "APPROACH AND AVOID OUTPUTS", "lbl");
  const comps = [];
  const compAt = (name,x,y,w,h)=>{ const g=el("g",{class:"comp"}); el("rect",{x,y,width:w,height:h,rx:5,fill:"var(--panel)",stroke:"var(--grid)"},g); const t=text(x+w/2,y+h/2+3,name,"",'middle'); g.appendChild(t); comps.push({name,g}); };
  ["g1","g2","g3","g4","g5"].forEach((n,i)=>compAt(n,700+i*34,214,30,26));
  ["b1","b2"].forEach((n,i)=>compAt(n,700+i*34,248,30,26));
  ["b'1","b'2"].forEach((n,i)=>compAt(n,780+i*34,248,30,26));
  ["a3","a2","a1"].forEach((n,i)=>compAt(n,700,96+i*36,30,30));
  ["a'3","a'2","a'1"].forEach((n,i)=>compAt(n,738,96+i*36,30,30));
  text(700, 298, "learning happens at these connections,", "cap");
  text(700, 313, "each time a trade closes", "cap");

  // verdict readout lives under the diagram, in HTML, so it lays out at any width
  const vfill = document.getElementById("vfill"), vtext = document.getElementById("vtext");

  function show(sym, quiet){
    const s = STOCKS[sym];
    gloms.forEach((g,i)=>{ const v=s.smell[CH[i]]||0; g.setAttribute("fill-opacity", 0.06+0.94*v); g.setAttribute("r", 9+3*v); });
    kcs.forEach(k=>k.classList.remove("on"));
    if(s.cells){ s.cells.forEach(i=>kcs[i].classList.add("on")); }
    vfill.style.width = Math.max(0, Math.min(100, s.verdict / 6.0 * 100)) + "%";
    vtext.textContent = `${short(sym)} ${s.verdict.toFixed(3)}  ·  ${s.cells ? s.cells.length : s.n} cells fired`;
    document.querySelectorAll("#setups button").forEach(b => b.classList.toggle("on", b.dataset.sym === sym));
    if (!quiet) barSniff(sym);
    if (fly3d && !quiet) fly3d.goto(sym);
    if (brain3d) brain3d.setSmell(s.smell, s.cells ? s.cells.length : s.n);
    renderSmell(sym);
  }

  // ---- the bar under the brain: what it is sniffing right now -----------
  const bar = document.getElementById("brainbar");
  const FLYMARK = `<svg viewBox="0 0 32 24" aria-label="the fly picked this"><ellipse cx="16" cy="13" rx="6" ry="4.2" fill="var(--brand)"/><circle cx="21.5" cy="11" r="2.6" fill="var(--brand)"/><ellipse cx="8" cy="9" rx="7" ry="3.2" fill="var(--brand)" opacity=".45" transform="rotate(-18 8 9)"/><ellipse cx="8" cy="17" rx="7" ry="3.2" fill="var(--brand)" opacity=".45" transform="rotate(18 8 17)"/></svg>`;
  // The bar under the brain holds results only: the last thing it sniffed, then what it bought.
  // What the fly is doing right now is said once, in the caption at the bottom left.
  function barReset() { bought = false; document.getElementById("status").innerHTML = statusText(false); if (fly3d) fly3d.setHeld([]); trace.reset(); bar.classList.remove("pick"); bar.querySelector(".t").textContent = "Nothing sniffed yet"; bar.querySelector(".v").textContent = ""; }
  function barSniff(sym) { const st = STOCKS[sym]; bar.classList.remove("pick"); bar.querySelector(".t").innerHTML = `Last sniff: ${symLink(sym)}`; bar.querySelector(".v").textContent = `${st.verdict >= 0 ? "+" : ""}${st.verdict.toFixed(2)} · ${st.cells ? st.cells.length : st.n} cells · ${Object.values(st.smell).filter(v => v >= 0.5).length} channels`; trace.fire(sym); ekg.fire(st.cells ? st.cells.length : st.n); }
  // Activity over time. The spikes are the simulation: a burst of Kenyon cells
  // when a smell arrives, sized by how many fired, then the APL clamps it. The
  // baseline is the body: busier walking and flying than resting.
  const ekg = (() => {
    const c = document.getElementById("ekg"), g = c.getContext("2d");
    const hist = new Float32Array(300); let head = 0, burst = -1e9, level = 0, count = 0;
    function fire(cells) { burst = performance.now(); level = Math.min(1, cells / 90); count = cells; }
    function frame(now) {
      const w = c.clientWidth, h = c.clientHeight;
      if (c.width !== w * 2 || c.height !== h * 2) { c.width = w * 2; c.height = h * 2; }
      const since = (now - burst) / 1000;
      const busy = fly3d ? fly3d.activity() : 0.2, r = Math.random();
      hist[head] = (since >= 0 && since < 0.5 ? level * Math.exp(-since * 7) * (0.55 + 0.45 * r) : 0) + busy * (0.06 + 0.22 * r * r * r + (r > 0.97 ? 0.25 : 0));
      head = (head + 1) % hist.length;
      g.clearRect(0, 0, c.width, c.height);
      g.strokeStyle = col("--brand"); g.lineWidth = 2.5; g.beginPath();
      for (let k = 0; k < hist.length; k++) { const v = hist[(head + k) % hist.length]; const x = 14 + k / (hist.length - 1) * (c.width - 28), y = c.height - 10 - v * (c.height - 30); k ? g.lineTo(x, y) : g.moveTo(x, y); }
      g.stroke();
      g.fillStyle = col("--muted"); g.font = "500 15px JetBrains Mono, monospace"; g.textBaseline = "top"; g.textAlign = "left";
      g.fillText("BRAIN ACTIVITY", 14, 8); g.textAlign = "right"; g.fillText(count ? `${count} of 4,064 cells fired` : "", c.width - 14, 8); g.textAlign = "left";
      if (!alive) return;
      if (!document.hidden) requestAnimationFrame(frame); else document.addEventListener("visibilitychange", () => requestAnimationFrame(frame), {once: true, signal: life.signal});
    }
    requestAnimationFrame(frame);
    return {fire};
  })();
  // Two live readouts under the brain: the smell as 51 channel bars, and the
  // verdicts as the fly hands them in. Both are the session's real numbers.
  const trace = (() => {
    const c = document.getElementById("trace"), g = c.getContext("2d");
    const spec = new Float32Array(CH.length), want = new Float32Array(CH.length);
    const verd = {}; let flash = -1e9;
    function fire(sym) { const st = STOCKS[sym]; st.vec.forEach((v, k) => { want[k] = v; }); verd[sym] = st.verdict; flash = performance.now(); }
    function reset() { want.fill(0); for (const k in verd) delete verd[k]; }
    function frame(now) {
      const w = c.clientWidth, h = c.clientHeight;
      if (c.width !== w * 2 || c.height !== h * 2) { c.width = w * 2; c.height = h * 2; }
      for (let k = 0; k < spec.length; k++) spec[k] += (want[k] - spec[k]) * 0.12;
      g.clearRect(0, 0, c.width, c.height);
      const W = c.width, H = c.height, top = 34, base = H - 12, gap = 24, lw = Math.round(W * 0.56) - gap;
      g.fillStyle = col("--muted"); g.font = "500 17px JetBrains Mono, monospace"; g.textBaseline = "top"; g.textAlign = "left";
      g.fillText("SMELL · 51 CHANNELS", 14, 10); g.fillText("VERDICTS", lw + gap + 14, 10);
      const bw = (lw - 28) / spec.length;
      for (let k = 0; k < spec.length; k++) {
        const v = spec[k]; g.fillStyle = v > 0.03 ? `rgba(62,166,255,${0.25 + 0.75 * v})` : "rgba(255,255,255,.08)";
        const bh = Math.max(3, v * (base - top)); g.fillRect(14 + k * bw, base - bh, Math.max(1, bw - 1.5), bh);
      }
      const x0 = lw + gap + 14, cw = (W - x0 - 14) / ORDER.length, max = 3;
      ORDER.forEach((sym, k) => {
        const v = verd[sym]; const x = x0 + k * cw;
        g.fillStyle = "rgba(255,255,255,.08)"; g.fillRect(x, top, cw - 4, base - top);
        if (v !== undefined) { const bh = Math.max(3, Math.min(1, Math.max(0, v) / max) * (base - top)); g.fillStyle = sym === PICK && bar.classList.contains("pick") ? col("--brand") : "rgba(0,255,136,.55)"; g.fillRect(x, base - bh, cw - 4, bh); }
        g.fillStyle = col("--muted"); g.font = "500 13px JetBrains Mono, monospace"; g.textAlign = "center"; g.fillText(short(sym).slice(0, 5), x + (cw - 4) / 2, top + 4);
      });
      g.textAlign = "left";
      if (!alive) return;
      if (!document.hidden) requestAnimationFrame(frame); else document.addEventListener("visibilitychange", () => requestAnimationFrame(frame), {once: true, signal: life.signal});
    }
    requestAnimationFrame(frame);
    return {fire, reset};
  })();
  function barPick() {
    bought = true; document.getElementById("status").innerHTML = statusText(true);
    if (fly3d) fly3d.setHeld([...(META.held || []), ...(PICK ? [PICK] : [])]);
    const t = bar.querySelector(".t"), v = bar.querySelector(".v");
    if (!PICK) { bar.classList.remove("pick"); t.textContent = "Bought nothing"; v.textContent = META.sold.length ? `sold ${META.sold.map(short).join(", ")}` : ""; return; }
    bar.classList.add("pick"); t.innerHTML = FLYMARK + `Bought ${symLink(PICK)}`; v.textContent = `${money(META.dollars)}${META.half ? " · half size" : ""}`;
  }

  // ---- setup switcher: one chip per symbol, driving the diagram, the smell
  // card and the brain together. The replay moves it too.
  {
    const host = document.getElementById("setups");
    ORDER.forEach(sym => {
      const b = document.createElement("button"); b.dataset.sym = sym;
      b.innerHTML = (sym === PICK ? FLYMARK : "") + `${esc(short(sym))} <span class="vd">${STOCKS[sym].verdict.toFixed(2)}</span>`;
      b.title = sym === PICK ? "The one it bought" : "";
      b.addEventListener("click", () => { stop(); show(sym); });
      host.appendChild(b);
    });
  }

  // ---- replay ------------------------------------------------------------
  const steps = ORDER.map(s => ({sym: s, kind: "sniff"})).concat([{sym: PICK || ORDER[0], kind: "buy"}]);
  let i = steps.length - 1, timer = null, playing = false;
  const playBtn = document.getElementById("play");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  function go(k, quiet) { i = (k + steps.length) % steps.length; show(steps[i].sym, quiet); }
  function runStep(k) { if (steps[k].kind === "sniff") barSniff(steps[k].sym); else barPick(); }
  function stop() { playing = false; if (timer) { clearInterval(timer); timer = null; } if (fly3d) fly3d.abort(); playBtn.textContent = "Replay today"; }
  playBtn.onclick = () => {
    if (playing) { stop(); return; }
    barReset();
    if (reduce) { steps.forEach((_, k) => runStep(k)); go(steps.length - 1); return; }
    playing = true; playBtn.textContent = "Stop";
    if (fly3d) {
      let k = -1;
      const next = () => {
        if (!playing) return;
        k++; if (k >= steps.length) { stop(); return; }
        const arrive = () => { go(k, true); runStep(k); };
        if (k === steps.length - 1) { if (PICK) fly3d.settle(PICK, () => stop(), arrive); else { arrive(); stop(); } }
        else fly3d.visit(steps[k].sym, STOCKS[steps[k].sym].verdict, next, arrive);
      };
      fly3d.explore(3, next, true);
    } else {
      let k = -1; timer = setInterval(() => { k++; if (k >= steps.length) { stop(); return; } go(k); runStep(k); }, 1100);
    }
  };

  // ---- smell card ---------------------------------------------------------
  function renderSmell(sym){
    const s = STOCKS[sym];
    document.getElementById("smellTitle").innerHTML = `What ${symLink(sym)} smells like to a fly`;
    const host = document.getElementById("smell"); host.innerHTML = "";
    for(const f of FEATURES){
      const v = s.r[f.k];
      const d = document.createElement("div"); d.className="feat";
      const bands = f.c.map((c,k)=>{ const a=s.smell[`${f.k}[${k}]`]||0; return `<i data-l="${f.fmt(c)}" style="background:${a>0?`rgba(0,143,250,${.12+.88*a})`:"var(--cell)"}" title="band ${k}, center ${f.fmt(c)}: ${a.toFixed(2)}"></i>`; }).join("");
      d.innerHTML = `<div class="row"><span>${f.label}</span><b>${v==null?"dark":f.fmt(v)}</b></div><div class="bands">${bands}</div>`;
      host.appendChild(d);
    }
    for(const k in CATS){
      const d = document.createElement("div"); d.className="feat";
      const bands = CATS[k].map(v=>`<i data-l="${v}" style="background:${s.r[k]===v?"rgba(0,143,250,1)":"var(--cell)"}"></i>`).join("");
      d.innerHTML = `<div class="row"><span>${k==="rsi_trend"?"RSI trend":"Days to earnings"}</span><b>${esc(s.r[k]??"dark")}</b></div><div class="bands">${bands}</div>`;
      host.appendChild(d);
    }
  }

  if (window.Brain3D && document.getElementById("brain3d")) {
    fetch(base + "model/brain/channels.json").then(r => r.json()).then(ch => {
      if (!alive) return;
      brain3d = Brain3D({base, canvas: document.getElementById("brain3d"), col, channels: ch});
      const st = STOCKS[steps[i].sym]; brain3d.setSmell(st.smell, st.cells ? st.cells.length : st.n);
    }).catch(e => console.warn("brain view not started", e));
  }
  go(steps.length-1);
  if(!matchMedia("(prefers-reduced-motion: reduce)").matches) later(()=>{ if(!playing) playBtn.click(); }, 1800);
  return {dispose() { alive = false; life.abort(); stop(); timers.forEach(id => { clearTimeout(id); clearInterval(id); }); fly3d && fly3d.dispose(); brain3d && brain3d.dispose(); }};
};

// One replay, as the runner uploads it, becomes the session the page plays back. `fly` is what the
// replay does not know: {id, botId, name, holdsNow, roster: [{id, name, equity, ret}]}.
window.FlyPage.session = function (replay, fly) {
  const ev = t => replay.events.filter(e => e.type === t);
  const board = ev("board")[0].stocks, buy = ev("buy")[0], start = ev("start")[0], said = ev("thought")[0];
  const STOCKS = {}, ORDER = [], CANDLES = {};
  // A replay is outside input. Every value is forced to the type the page draws with.
  const num = v => { const n = Number(v); return Number.isFinite(n) ? n : 0; };
  const TRENDS = ["rising", "falling", "flat"];
  const reading = r => ({rsi: num(r.rsi), bb_position: num(r.bb_position), distance_from_sma50: num(r.distance_from_sma50),
    volume_ratio: num(r.volume_ratio), price_change_5d: num(r.price_change_5d), rsi_trend: TRENDS.includes(r.rsi_trend) ? r.rsi_trend : null});
  for (const e of ev("sniff")) {
    const sym = String(e.symbol), b = board[sym]; if (!b) continue;
    ORDER.push(sym);
    STOCKS[sym] = {price: num(b.price), verdict: num(e.verdict), r: reading(b.reading || {}), cells: (e.cells || []).map(num), held: !!e.held};
    CANDLES[sym] = (b.bars || []).map(bar => bar.map(num));
  }
  const when = new Date(replay.when), daily = start.cadence === "daily", hourly = /h$/.test(String(start.cadence));
  const META = {fly: fly.id, botId: fly.botId, name: fly.name, cadence: String(start.cadence), session: num(start.session), dry: !!replay.dry,
    flies: fly.roster.map(r => r.id), roster: fly.roster, holdsNow: fly.holdsNow,
    market: `${start.universe === "crypto" ? "Crypto" : "US stocks"}, ${daily ? "daily" : hourly ? "every " + parseInt(start.cadence) + " hours" : String(start.cadence).split(",").join(" and ") + " New York"}`,
    date: when.toLocaleDateString("en-GB", {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"}) + (daily ? "" : " " + when.toISOString().slice(11, 16) + " UTC"),
    dollars: buy ? (said && said.qty && said.price ? num(said.qty) * num(said.price) : num(buy.dollars)) : 0, half: buy ? num(buy.margin) < 0.36 : false,
    thought: said ? String(said.body) : null, sold: ev("sell").map(e => String(e.symbol)), held: (start.held || []).map(String)};
  return {STOCKS, ORDER, PICK: buy && STOCKS[String(buy.symbol)] ? String(buy.symbol) : null, CANDLES, META};
};
