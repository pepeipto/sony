// Nebulosa del segundo cerebro: canvas 2D, layout precomputado en el servidor.
// Todo el texto de las notas se pinta con textContent (nunca innerHTML).
(() => {
  "use strict";
  const RUTA = location.pathname.replace(/\/+$/, "");
  const ESPIRAL = RUTA === "/galaxia-espiral" || RUTA === "/galaxia-espiral-2d";
  const ES2D = RUTA.endsWith("-2d");
  const cv = document.getElementById("cielo");
  const ctx = cv.getContext("2d");
  const $ = (id) => document.getElementById(id);
  const tip = $("neb-tip");

  let G = null, nodos = [], aristas = [], temas = [], vecinos = [];
  let W = 0, H = 0, DPR = 1;
  const cam = { x: 0, y: 0, k: 1 };
  let fondo = null, sprites = [], halos = [];
  let hover = -1, sel = -1, foco = -1; // foco = indice de tema resaltado
  let sucio = true, anim = null, ordenRotulos = null;

  if (ESPIRAL) {
    $("neb-titulo").textContent = "Galaxia espiral";
    document.title = "Galaxia espiral · Nebulosa IA";
    $("neb-alt").style.display = "none";  // la nebulosa se retiró (15/11/2026)
  } else if (ES2D) $("neb-alt").href = "/galaxia-espiral-2d";
  if ($("neb-3d")) $("neb-3d").href = ESPIRAL ? "/galaxia-espiral" : "/nebulosa";

  // ------------------------------------------------------------ utilidades
  const hex = (c) => [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)];
  const rgba = (c, a) => { const [r, g, b] = hex(c); return `rgba(${r},${g},${b},${a})`; };
  function prng(seed) { let s = seed >>> 0; return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const pedir = () => { sucio = true; };

  function radio(n) { return 2 + Math.pow(n.g, 0.42) * 1.1; } // radio en unidades de mundo

  // ------------------------------------------------------------ recursos graficos
  function hacerSprite(color) {
    const S = 64, c = document.createElement("canvas"); c.width = c.height = S;
    const g = c.getContext("2d"), [r, gg, b] = hex(color);
    const gr = g.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
    gr.addColorStop(0, "rgba(255,252,246,1)");
    gr.addColorStop(0.10, `rgba(${Math.min(255, r + 60)},${Math.min(255, gg + 60)},${Math.min(255, b + 60)},0.95)`);
    gr.addColorStop(0.22, `rgba(${r},${gg},${b},0.55)`);
    gr.addColorStop(0.5, `rgba(${r},${gg},${b},0.12)`);
    gr.addColorStop(1, `rgba(${r},${gg},${b},0)`);
    g.fillStyle = gr; g.fillRect(0, 0, S, S);
    return c;
  }

  function hacerFondo() {
    const c = document.createElement("canvas"); c.width = Math.max(1, W * DPR); c.height = Math.max(1, H * DPR);
    const g = c.getContext("2d"); g.scale(DPR, DPR);
    const gr = g.createRadialGradient(W * 0.5, H * 0.45, 0, W * 0.5, H * 0.5, Math.max(W, H) * 0.8);
    gr.addColorStop(0, "#17141c"); gr.addColorStop(0.55, "#0e0d12"); gr.addColorStop(1, "#08070a");
    g.fillStyle = gr; g.fillRect(0, 0, W, H);
    const R = prng(1311);
    // nubes de polvo muy tenues
    const tonos = temas.length ? temas.map((t) => t.color) : ["#8fb0d0"];
    g.globalCompositeOperation = "lighter";
    for (let i = 0; i < 7; i++) {
      const x = R() * W, y = R() * H, rr = (0.25 + R() * 0.35) * Math.max(W, H);
      const n = g.createRadialGradient(x, y, 0, x, y, rr);
      n.addColorStop(0, rgba(tonos[i % tonos.length], 0.035)); n.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = n; g.fillRect(0, 0, W, H);
    }
    // estrellas de fondo
    const cuantas = Math.round(W * H / 2600);
    for (let i = 0; i < cuantas; i++) {
      const x = R() * W, y = R() * H, m = R();
      const a = 0.15 + m * m * 0.6, s = m > 0.97 ? 1.3 : m > 0.8 ? 0.9 : 0.6;
      g.fillStyle = `rgba(${220 + R() * 35 | 0},${215 + R() * 30 | 0},${205 + R() * 40 | 0},${a})`;
      g.beginPath(); g.arc(x, y, s, 0, 6.2832); g.fill();
    }
    g.globalCompositeOperation = "source-over";
    fondo = c;
  }

  function calcularHalos() {
    halos = [];
    if (!ESPIRAL) {
      temas.forEach((t, ti) => t.halos.forEach(([x, y, r, n]) => halos.push({ x, y, r, ti, a: Math.min(0.26, 0.1 + Math.log2(n + 1) * 0.02) })));
      return;
    }
    // espiral: nubes a lo largo de cada brazo (muestreo de nodos)
    const R = prng(77);
    temas.forEach((t, ti) => {
      const mios = nodos.filter((n) => n.c === ti);
      const paso = Math.max(1, Math.floor(mios.length / 40));
      for (let i = 0; i < mios.length; i += paso) {
        const n = mios[i], d = Math.hypot(n.X, n.Y);
        halos.push({ x: n.X, y: n.Y, r: 45 + d * 0.1 + R() * 30, ti, a: mios.length < 40 ? 0.16 : 0.09 });
      }
    });
    halos.push({ x: 0, y: 0, r: 220, ti: -1, a: 0.2 }); // nucleo galactico
  }

  // ------------------------------------------------------------ camara
  const aPantalla = (x, y) => [(x - cam.x) * cam.k + W / 2, (y - cam.y) * cam.k + H / 2];
  const aMundo = (px, py) => [(px - W / 2) / cam.k + cam.x, (py - H / 2) / cam.k + cam.y];

  function limites(lista) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const n of lista) { const r = radio(n); x0 = Math.min(x0, n.X - r); y0 = Math.min(y0, n.Y - r); x1 = Math.max(x1, n.X + r); y1 = Math.max(y1, n.Y + r); }
    return { x: (x0 + x1) / 2, y: (y0 + y1) / 2, k: Math.min(W / Math.max(60, x1 - x0), H / Math.max(60, y1 - y0)) * 0.82 };
  }

  function volar(dest, ms = 650) {
    const ini = { ...cam }, t0 = performance.now();
    const lk0 = Math.log(ini.k), lk1 = Math.log(dest.k);
    cancelAnimationFrame(anim);
    const paso = (t) => {
      const f = Math.min(1, (t - t0) / ms), e = f < 0.5 ? 4 * f * f * f : 1 - Math.pow(-2 * f + 2, 3) / 2;
      cam.x = ini.x + (dest.x - ini.x) * e; cam.y = ini.y + (dest.y - ini.y) * e; cam.k = Math.exp(lk0 + (lk1 - lk0) * e);
      sucio = true;
      if (f < 1) anim = requestAnimationFrame(paso);
    };
    anim = requestAnimationFrame(paso);
  }

  const encuadrarTodo = (ms) => volar(limites(nodos), ms);

  // ------------------------------------------------------------ pintado
  function pintar() {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    if (fondo) ctx.drawImage(fondo, 0, 0, W, H); else { ctx.fillStyle = "#0b0a0e"; ctx.fillRect(0, 0, W, H); }
    if (!G) return;
    const k = cam.k;
    const resalt = sel >= 0 ? sel : hover;
    const vecSet = resalt >= 0 ? new Set(vecinos[resalt]) : null;

    // halos de constelacion
    ctx.globalCompositeOperation = "lighter";
    for (const h of halos) {
      const [x, y] = aPantalla(h.x, h.y), r = h.r * k;
      if (x + r < 0 || y + r < 0 || x - r > W || y - r > H || r < 2) continue;
      const color = h.ti < 0 ? "#e8d9c0" : temas[h.ti].color;
      const a = h.a * (foco >= 0 && h.ti !== foco ? 0.25 : 1);
      const g = ctx.createRadialGradient(x, y, 0, x, y, r);
      g.addColorStop(0, rgba(color, a)); g.addColorStop(0.45, rgba(color, a * 0.45)); g.addColorStop(1, rgba(color, 0));
      ctx.fillStyle = g; ctx.fillRect(x - r, y - r, r * 2, r * 2);
    }
    ctx.globalCompositeOperation = "source-over";

    // aristas tenues, agrupadas por color
    const aBase = Math.min(0.16, 0.05 + k * 0.05);
    ctx.lineWidth = Math.max(0.4, Math.min(1.2, k * 0.6));
    for (let ti = 0; ti < temas.length; ti++) {
      ctx.beginPath();
      let hay = false;
      for (const [a, b] of aristas) {
        const na = nodos[a], nb = nodos[b];
        if (na.c !== ti) continue;
        const [x1, y1] = aPantalla(na.X, na.Y), [x2, y2] = aPantalla(nb.X, nb.Y);
        if ((x1 < 0 && x2 < 0) || (y1 < 0 && y2 < 0) || (x1 > W && x2 > W) || (y1 > H && y2 > H)) continue;
        ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); hay = true;
      }
      if (!hay) continue;
      const atenuar = (foco >= 0 && ti !== foco) || resalt >= 0 ? 0.35 : 1;
      ctx.strokeStyle = rgba(temas[ti].color, aBase * atenuar);
      ctx.stroke();
    }
    if (resalt >= 0) { // aristas de la nota activa
      const n0 = nodos[resalt], [x0, y0] = aPantalla(n0.X, n0.Y);
      ctx.lineWidth = Math.max(0.8, Math.min(1.8, k)); ctx.strokeStyle = "rgba(245,230,210,0.55)";
      ctx.beginPath();
      for (const j of vecinos[resalt]) { const [x, y] = aPantalla(nodos[j].X, nodos[j].Y); ctx.moveTo(x0, y0); ctx.lineTo(x, y); }
      ctx.stroke();
    }

    // estrellas
    ctx.globalCompositeOperation = "lighter";
    for (let i = 0; i < nodos.length; i++) {
      const n = nodos[i];
      const [x, y] = aPantalla(n.X, n.Y);
      const r = Math.max(0.9, Math.min(15, radio(n) * k)) * (i === resalt ? 1.35 : 1);
      const s = r * 4.2;
      if (x + s < 0 || y + s < 0 || x - s > W || y - s > H) continue;
      let a = 1;
      if (foco >= 0 && n.c !== foco) a = 0.18;
      if (resalt >= 0 && i !== resalt && !vecSet.has(i)) a *= 0.4;
      ctx.globalAlpha = a;
      ctx.drawImage(sprites[n.c], x - s, y - s, s * 2, s * 2);
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";

    if (sel >= 0) { // anillo de seleccion
      const n = nodos[sel], [x, y] = aPantalla(n.X, n.Y), r = Math.max(6, radio(n) * k * 1.6);
      ctx.strokeStyle = "rgba(210,113,80,0.9)"; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(x, y, r, 0, 6.2832); ctx.stroke();
    }

    // rotulos: nombres de constelacion y notas grandes
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.font = `500 ${k > 0.9 ? 11 : 12}px "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif`;
    const minR = k < 0.5 ? 99 : k < 1 ? 9 : k < 2 ? 6 : 3.5;
    const ocupados = []; // evitar rotulos solapados (los mas enlazados primero)
    if (!ordenRotulos) ordenRotulos = nodos.map((_, i) => i).sort((a, b) => nodos[b].g - nodos[a].g);
    const cand = resalt >= 0 ? [resalt, ...ordenRotulos] : ordenRotulos;
    for (const i of cand) {
      const n = nodos[i], r = radio(n) * k;
      if (r < minR && i !== resalt && !(vecSet && vecSet.has(i) && k > 0.6)) continue;
      if (foco >= 0 && n.c !== foco) continue;
      const [x, y] = aPantalla(n.X, n.Y);
      if (x < -100 || y < -20 || x > W + 100 || y > H + 20) continue;
      const t = n.t.length > 34 ? n.t.slice(0, 33) + "…" : n.t;
      const w = ctx.measureText(t).width / 2 + 3, yy = y + r + 10;
      if (ocupados.some((o) => Math.abs(o[0] - x) < o[2] + w && Math.abs(o[1] - yy) < 13)) continue;
      ocupados.push([x, yy, w]);
      ctx.fillStyle = "rgba(10,9,12,0.55)"; ctx.fillText(t, x + 0.6, y + r + 10.6);
      ctx.fillStyle = i === resalt ? "#fff" : "rgba(236,232,222,0.78)"; ctx.fillText(t, x, y + r + 10);
    }
    if (!ESPIRAL || k < 1.2) {
      ctx.font = `400 ${Math.max(13, Math.min(22, 15 * Math.sqrt(k)))}px "Iowan Old Style","Palatino Linotype",Georgia,serif`;
      temas.forEach((t, ti) => {
        let cx = t.cx, cy = t.cy, rr = t.r;
        if (ESPIRAL) { if (!t.ancla) return; cx = t.ancla[0]; cy = t.ancla[1]; rr = 30; }
        const [x, y] = aPantalla(cx, cy - rr);
        if (x < -200 || x > W + 200 || y < -40 || y > H + 40) return;
        ctx.fillStyle = rgba(t.color, foco >= 0 && ti !== foco ? 0.3 : 0.9);
        ctx.fillText(t.nombre, x, y - 12);
      });
    }
  }

  function bucle() {
    if (sucio && W > 0 && H > 0) { sucio = false; try { pintar(); } catch (e) { console.error(e); } }
    requestAnimationFrame(bucle);
  }

  // ------------------------------------------------------------ interaccion
  function nodoEn(px, py) {
    const [wx, wy] = aMundo(px, py);
    let mejor = -1, md = Infinity;
    for (let i = 0; i < nodos.length; i++) {
      const n = nodos[i]; if (foco >= 0 && n.c !== foco) continue;
      const d = Math.hypot(n.X - wx, n.Y - wy), lim = Math.max(radio(n) * 1.3, 7 / cam.k);
      if (d < lim && d < md) { md = d; mejor = i; }
    }
    return mejor;
  }

  let drag = null;
  cv.addEventListener("pointerdown", (e) => { cv.setPointerCapture(e.pointerId); drag = { x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y, mov: false }; });
  cv.addEventListener("pointermove", (e) => {
    if (drag) {
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) { drag.mov = true; cv.classList.add("arrastrando"); tip.hidden = true; }
      if (drag.mov) { cancelAnimationFrame(anim); cam.x = drag.cx - dx / cam.k; cam.y = drag.cy - dy / cam.k; pedir(); }
      return;
    }
    const i = nodoEn(e.clientX, e.clientY);
    if (i !== hover) { hover = i; pedir(); cv.classList.toggle("sobre", i >= 0); }
    if (i >= 0) {
      tip.textContent = nodos[i].t; tip.hidden = false;
      const x = Math.min(e.clientX + 14, W - tip.offsetWidth - 8);
      tip.style.left = x + "px"; tip.style.top = (e.clientY + 14) + "px";
    } else tip.hidden = true;
  });
  cv.addEventListener("pointerup", (e) => {
    const d = drag; drag = null; cv.classList.remove("arrastrando");
    if (d && !d.mov) { const i = nodoEn(e.clientX, e.clientY); if (i >= 0) seleccionar(i, false); else if (sel >= 0) cerrarFicha(); }
  });
  cv.addEventListener("pointerleave", () => { if (hover >= 0) { hover = -1; pedir(); } tip.hidden = true; });
  cv.addEventListener("dblclick", (e) => { const i = nodoEn(e.clientX, e.clientY); if (i < 0) { foco >= 0 ? volar(limites(nodos.filter((n) => n.c === foco))) : encuadrarTodo(); } });
  cv.addEventListener("wheel", (e) => {
    e.preventDefault(); cancelAnimationFrame(anim);
    const f = Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0015));
    const [wx, wy] = aMundo(e.clientX, e.clientY);
    cam.k = Math.max(0.03, Math.min(40, cam.k * f));
    cam.x = wx - (e.clientX - W / 2) / cam.k; cam.y = wy - (e.clientY - H / 2) / cam.k;
    pedir();
  }, { passive: false });
  addEventListener("keydown", (e) => { if (e.key === "Escape") { if (sel >= 0) cerrarFicha(); else if (foco >= 0) enfocar(foco); } });

  function redimensionar() {
    const sinTam = !W || !H;
    DPR = Math.min(2, devicePixelRatio || 1); W = innerWidth; H = innerHeight;
    cv.width = Math.max(1, W * DPR); cv.height = Math.max(1, H * DPR); hacerFondo(); pedir();
    if (sinTam && W && H && nodos.length) Object.assign(cam, limites(nodos));
  }
  addEventListener("resize", redimensionar);

  // ------------------------------------------------------------ ficha de nota
  const ficha = $("neb-ficha");
  $("neb-cerrar").addEventListener("click", () => cerrarFicha());
  function cerrarFicha() { sel = -1; ficha.hidden = true; pedir(); }

  function itemNota(j, onClick) {
    const li = el("li"), p = el("span", "neb-punto");
    p.style.color = temas[nodos[j].c].color; p.style.background = temas[nodos[j].c].color;
    li.append(p, el("span", null, nodos[j].t)); li.addEventListener("click", onClick);
    return li;
  }

  async function seleccionar(i, mover) {
    sel = i; pedir();
    const n = nodos[i], t = temas[n.c];
    if (mover) volar({ x: n.X, y: n.Y, k: Math.max(cam.k, 2.4) });
    const ft = $("f-tema"); ft.replaceChildren();
    const p = el("span", "neb-punto"); p.style.color = t.color; p.style.background = t.color;
    ft.append(p, el("span", null, t.nombre + (n.s ? " · " + n.s : "")));
    $("f-titulo").textContent = n.t;
    $("f-meta").replaceChildren(); $("f-texto").replaceChildren(el("p", null, "…"));
    $("f-enl").replaceChildren(); $("f-enl-h").textContent = `Enlaces (${vecinos[i].length})`;
    vecinos[i].forEach((j) => $("f-enl").append(itemNota(j, () => seleccionar(j, true))));
    ficha.hidden = false;
    try {
      const r = await fetch("/api/cerebro?nota=" + encodeURIComponent(n.id));
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      if (sel !== i) return;
      const meta = $("f-meta");
      if (d.tipo) meta.append(el("span", null, d.tipo));
      (d.tags || []).forEach((tg) => meta.append(el("span", null, "#" + tg)));
      if (d.ruta) meta.append(el("span", "ruta", d.ruta));
      const tx = $("f-texto"); tx.replaceChildren();
      (d.extracto || []).forEach((l) => tx.append(el("p", null, l)));
      if (!(d.extracto || []).length) tx.append(el("p", null, "(nota sin texto)"));
    } catch (_) { if (sel === i) $("f-texto").replaceChildren(el("p", null, "No se pudo leer la nota.")); }
  }

  // ------------------------------------------------------------ leyenda y busqueda
  function enfocar(ti) {
    foco = foco === ti ? -1 : ti;
    document.querySelectorAll(".neb-leyenda button").forEach((b, k) => { b.classList.toggle("activo", k === foco); b.classList.toggle("apagado", foco >= 0 && k !== foco); });
    if (foco >= 0) volar(limites(nodos.filter((n) => n.c === foco))); else encuadrarTodo();
    pedir();
  }

  function leyenda() {
    const L = $("neb-leyenda"); L.replaceChildren();
    temas.forEach((t, ti) => {
      const b = el("button"), p = el("span", "neb-punto");
      p.style.color = t.color; p.style.background = t.color;
      b.append(p, el("span", null, t.nombre), el("span", "n", String(t.n)));
      b.addEventListener("click", () => enfocar(ti));
      L.append(b);
    });
  }

  const q = $("neb-q"), res = $("neb-res");
  let hallados = [], act = 0;
  const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  q.addEventListener("input", () => {
    const v = norm(q.value.trim()); res.replaceChildren(); act = 0;
    if (!v) { res.hidden = true; return; }
    hallados = nodos.map((n, i) => [i, n]).filter(([, n]) => n._q.includes(v))
      .sort((a, b) => (a[1]._q.indexOf(v) - b[1]._q.indexOf(v)) || (b[1].g - a[1].g)).slice(0, 30).map(([i]) => i);
    hallados.forEach((j, k) => { const li = itemNota(j, () => { seleccionar(j, true); res.hidden = true; }); if (k === 0) li.classList.add("activo"); res.append(li); });
    res.hidden = !hallados.length;
  });
  q.addEventListener("keydown", (e) => {
    if (!hallados.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault(); act = (act + (e.key === "ArrowDown" ? 1 : hallados.length - 1)) % hallados.length;
      [...res.children].forEach((li, k) => li.classList.toggle("activo", k === act));
    } else if (e.key === "Enter") { seleccionar(hallados[act], true); res.hidden = true; q.blur(); }
    else if (e.key === "Escape") { res.hidden = true; q.blur(); }
  });

  // ------------------------------------------------------------ arranque
  async function cargar() {
    redimensionar(); bucle();
    try {
      const r = await fetch("/api/cerebro");
      if (!r.ok) throw new Error("HTTP " + r.status);
      G = await r.json();
    } catch (e) { $("neb-stats").textContent = "No se pudo cargar el grafo (" + e.message + ")."; return; }
    temas = G.temas; aristas = G.aristas;
    nodos = G.nodos.map((n) => ({ ...n, X: ESPIRAL ? n.sx : n.x, Y: ESPIRAL ? n.sy : n.y, _q: norm(n.t + " " + n.id) }));
    vecinos = nodos.map(() => []);
    for (const [a, b] of aristas) { vecinos[a].push(b); vecinos[b].push(a); }
    vecinos.forEach((v) => v.sort((a, b) => nodos[b].g - nodos[a].g));
    temas.forEach((t) => { if (!t.ancla || t.ancla.length !== 2) t.ancla = null; });
    sprites = temas.map((t) => hacerSprite(t.color));
    calcularHalos(); hacerFondo(); leyenda();
    const s = G.stats;
    $("neb-stats").textContent = `${s.notas.toLocaleString("es-ES")} notas · ${s.enlaces.toLocaleString("es-ES")} enlaces · ${s.temas} constelaciones`;
    Object.assign(cam, limites(nodos)); pedir();
  }
  cargar();
})();
