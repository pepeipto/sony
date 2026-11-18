// Nebulosa 3D del segundo cerebro (Three.js local, sin CDN).
// Mismos datos que la vista 2D (/api/cerebro). Todo texto de notas va por textContent.
// Reglas de GPU: render solo con la pagina visible, <=30 fps, bajo demanda (en reposo no dibuja),
// pixelRatio <=1.5, sin antialias, modo ligero automatico segun la VRAM libre (/api/stats),
// y liberacion completa del contexto WebGL si la pestana lleva >60 s oculta.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

// ------------------------------------------------------------------ configuracion
const RUTA = location.pathname.replace(/\/+$/, '');
const ESPIRAL = RUTA === '/galaxia-espiral';
const RUTA_2D = ESPIRAL ? '/galaxia-espiral-2d' : '/nebulosa-2d';
// Calidad elegida por el usuario (se recuerda): ahorro = 30 fps sin bloom · alta = 60 fps con bloom · maxima = 60 fps, bloom, antialias y más resolución.
let CALIDAD = 'ahorro'; try { CALIDAD = localStorage.getItem('nebCalidad') || 'ahorro'; } catch {}
const CAL = { ahorro: { fps: 30, pr: 1.5, aa: false, modo: 'ligero' }, alta: { fps: 60, pr: 1.5, aa: false, modo: 'completo' }, maxima: { fps: 60, pr: 2, aa: true, modo: 'completo' } }[CALIDAD] || { fps: 30, pr: 1.5, aa: false, modo: 'ligero' };
let FORZAR = new URLSearchParams(location.search).get('modo') || CAL.modo; // 'completo' | 'ligero'
let FPS_MAX = CAL.fps; const FPS_SIN_FOCO = 15; let PR_MAX = CAL.pr;
// Si un modelo está trabajando en la gráfica, Alta/Máxima bajan solas a Ahorro (presupuesto de gráfica) y vuelven al terminar.
async function vigilarModelo() {
  if (CALIDAD === 'ahorro') return;
  try {
    const g = (await (await fetch('/api/stats', { cache: 'no-store' })).json()).now?.gpu;
    const ocupada = g && g.util > 50;
    const quiero = ocupada ? 'ligero' : CAL.modo;
    FPS_MAX = ocupada ? 30 : CAL.fps;
    if (quiero !== FORZAR) { FORZAR = quiero; comprobarVRAM(); }
  } catch {}
}
setInterval(vigilarModelo, 5000);
const GB_LIGERO = 1.5, GB_VOLVER = 1.9, GB_MINIMO = 0.6; // histeresis para no oscilar
const LIBERAR_MS = 60000, SONDEO_MS = 10000;
const VEL_GIRO = 0.012; // rad/s en espiral (una vuelta ~9 min)
const FOV = 52;
const FONDO = 0x040308;

const $ = (id) => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const escena = $('escena'), tip = $('neb-tip'), info = $('n3-info'), aviso = $('n3-aviso');

if (ESPIRAL) {
  $('neb-titulo').textContent = 'Galaxia espiral';
  document.title = 'Galaxia espiral · Nebulosa IA';
  $('neb-alt').style.display = 'none';  // la nebulosa se retiró (15/11/2026)
}
$('neb-2d').href = RUTA_2D;

// ------------------------------------------------------------------ azar determinista
function hash(str) { // cyrb53 -> [0,1)
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
  for (let i = 0; i < str.length; i++) { const c = str.charCodeAt(i); h1 = Math.imul(h1 ^ c, 2654435761); h2 = Math.imul(h2 ^ c, 1597334677); }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)) / 9007199254740992;
}
const rnd = (...k) => hash(k.join('|'));
function prng(seed) { let s = seed >>> 0; return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const gauss = (a, b) => Math.sqrt(-2 * Math.log(Math.max(a, 1e-9))) * Math.cos(2 * Math.PI * b);

// ------------------------------------------------------------------ estado
let D = null;            // datos preparados (CPU, sobreviven a liberar el contexto)
let gl = null;           // recursos WebGL (renderer, escena, buffers...)
let ligero = false, vramLibre = null;
let hover = -1, sel = -1, foco = -1;
let giro = 0;            // angulo de la galaxia (espiral)
let vuelo = null, destello = null;
let raf = 0, ultimo = 0, sucio = true, frames = 0;
let tLiberar = 0;

const camara = new THREE.PerspectiveCamera(FOV, innerWidth / Math.max(1, innerHeight), 0.5, 30000);
const controles = new OrbitControls(camara, escena);
Object.assign(controles, { enableDamping: true, dampingFactor: 0.07, rotateSpeed: 0.55, zoomSpeed: 0.9, panSpeed: 0.7,
  screenSpacePanning: true, minDistance: 4, maxDistance: 5000, zoomToCursor: true });
controles.addEventListener('change', () => pedir());
controles.addEventListener('start', () => { vuelo = null; pedir(); });

// uniformes compartidos por estrellas y polvo
const U = {
  uEscala: { value: 500 }, uPR: { value: 1 }, uHover: { value: -1 }, uSel: { value: -1 },
  uFoco: { value: -1 }, uHaySel: { value: 0 },
};

// ------------------------------------------------------------------ shaders
const VS_ESTRELLA = /* glsl */`
attribute float aSize; attribute vec3 aColor; attribute float aIdx; attribute float aTema; attribute float aVec;
uniform float uEscala, uPR, uHover, uSel, uFoco, uHaySel;
varying vec3 vColor; varying float vAlpha; varying float vResalte;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float s = aSize, a = 1.0;
  bool esH = abs(aIdx - uHover) < 0.5, esS = abs(aIdx - uSel) < 0.5;
  if (uFoco >= 0.0 && abs(aTema - uFoco) > 0.5) a *= 0.1;
  if (uHaySel > 0.5 && aVec < 0.5) a *= 0.3;
  if (esH) s *= 1.45;
  if (esS) s *= 1.6;
  float px = s * uEscala / max(0.5, -mv.z);
  vAlpha = a * clamp(px / (3.0 * uPR), 0.2, 1.0); // las muy lejanas se apagan en vez de parpadear
  px = clamp(px, 1.6 * uPR, 260.0 * uPR);
  vResalte = (esH || esS) ? 1.0 : 0.0;
  vColor = aColor;
  gl_PointSize = px;
  gl_Position = projectionMatrix * mv;
}`;
const FS_ESTRELLA = /* glsl */`
varying vec3 vColor; varying float vAlpha; varying float vResalte;
void main() {
  vec2 p = gl_PointCoord * 2.0 - 1.0; float d2 = dot(p, p);
  if (d2 > 1.0) discard;
  float nucleo = exp(-d2 * 70.0);
  float brillo = exp(-d2 * 12.0) * 0.32;
  float halo = (1.0 - d2) * (1.0 - d2) * 0.04;
  vec3 c = vColor * (brillo + halo) + mix(vColor, vec3(1.0), 0.6) * nucleo * 1.35;
  c *= vAlpha * (1.0 + vResalte * 0.7);
  gl_FragColor = vec4(c, 1.0);
  #include <colorspace_fragment>
}`;
const VS_FONDO = /* glsl */`
attribute float aSize; attribute vec3 aColor; uniform float uPR; varying vec3 vColor;
void main() { vColor = aColor; gl_PointSize = aSize * uPR; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const FS_FONDO = /* glsl */`
varying vec3 vColor;
void main() { vec2 p = gl_PointCoord * 2.0 - 1.0; float d2 = dot(p, p); if (d2 > 1.0) discard;
  gl_FragColor = vec4(vColor * exp(-d2 * 3.5), 1.0);
  #include <colorspace_fragment>
}`;
const VS_LINEA = /* glsl */`
attribute vec3 aColor; attribute float aTema; uniform float uFoco, uAten; varying vec3 vC;
void main() { float a = uAten; if (uFoco >= 0.0 && abs(aTema - uFoco) > 0.5) a *= 0.12;
  vC = aColor * a; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const FS_LINEA = /* glsl */`
varying vec3 vC;
void main() { gl_FragColor = vec4(vC, 1.0);
  #include <colorspace_fragment>
}`;
const VS_HILO = /* glsl */`
attribute vec3 aColor; attribute float aT; varying vec3 vC; varying float vT;
void main() { vC = aColor; vT = aT; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const FS_HILO = /* glsl */`
uniform float uProg; varying vec3 vC; varying float vT;
void main() {
  float lleno = smoothstep(uProg + 0.04, uProg - 0.04, vT);
  float frente = exp(-pow((vT - uProg) * 14.0, 2.0)) * step(uProg, 1.05) * 1.6;
  gl_FragColor = vec4(vC * (lleno * 0.85 + frente), 1.0);
  #include <colorspace_fragment>
}`;
const VS_NUBE = /* glsl */`
attribute vec2 aEsq; attribute float aSize; attribute vec3 aColor; attribute float aAlpha; attribute float aRot; attribute float aTema; attribute float aVar;
uniform float uFoco; varying vec2 vUv; varying vec3 vC;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float c = cos(aRot), s = sin(aRot);
  mv.xy += vec2(c * aEsq.x - s * aEsq.y, s * aEsq.x + c * aEsq.y) * aSize;
  float d = -mv.z;
  float a = aAlpha * smoothstep(aSize * 0.15, aSize * 1.1, d); // se desvanece al atravesarla
  if (uFoco >= 0.0 && aTema >= 0.0 && abs(aTema - uFoco) > 0.5) a *= 0.15;
  vC = aColor * a;
  vUv = (aEsq * 0.5 + 0.5 + vec2(mod(aVar, 2.0), floor(aVar / 2.0))) * 0.5;
  gl_Position = projectionMatrix * mv;
}`;
const FS_NUBE = /* glsl */`
uniform sampler2D uMapa; varying vec2 vUv; varying vec3 vC;
void main() { float t = texture2D(uMapa, vUv).r; gl_FragColor = vec4(vC * t, 1.0);
  #include <colorspace_fragment>
}`;
const VS_MARCA = /* glsl */`
attribute float aSize; uniform float uEscala, uPR;
void main() { vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = clamp(max(26.0 * uPR, aSize * uEscala / max(0.5, -mv.z) * 0.42), 10.0, 300.0 * uPR);
  gl_Position = projectionMatrix * mv; }`;
const FS_MARCA = /* glsl */`
void main() { vec2 p = gl_PointCoord * 2.0 - 1.0; float d = length(p);
  float anillo = smoothstep(0.08, 0.0, abs(d - 0.82)) ;
  if (anillo < 0.01) discard;
  gl_FragColor = vec4(vec3(0.82, 0.44, 0.31) * anillo * 1.4, 1.0);
  #include <colorspace_fragment>
}`;

// ------------------------------------------------------------------ preparacion de datos (CPU)
const lin = (hex) => new THREE.Color(hex); // Color.set convierte sRGB -> lineal

function prepararDatos(G) {
  const temas = G.temas, nodos = G.nodos, N = nodos.length;
  const pos = new Float32Array(N * 3), size = new Float32Array(N);
  const col = temas.map((t) => lin(t.color));
  const grupos = new Map();
  nodos.forEach((n, i) => {
    const k = n.c + '|' + (ESPIRAL ? '' : (n.s || ''));
    if (!grupos.has(k)) grupos.set(k, []);
    grupos.get(k).push(i);
    size[i] = (1.6 + Math.pow(n.g, 0.42) * 0.95) * 5.5;
  });
  const listaGrupos = [];
  if (!ESPIRAL) {
    for (const [k, ids] of grupos) {
      let cx = 0, cy = 0;
      for (const i of ids) { cx += nodos[i].x; cy += nodos[i].y; }
      cx /= ids.length; cy /= ids.length;
      let m2 = 0;
      for (const i of ids) { const dx = nodos[i].x - cx, dy = nodos[i].y - cy; m2 += dx * dx + dy * dy; }
      const R = Math.sqrt(m2 / ids.length) + 8;
      const t = temas[nodos[ids[0]].c];
      const tz = (rnd('tz', t.id) - 0.5) * 220;
      const gz = (rnd('gz', k) - 0.5) * Math.min(t.r * 0.9, 340);
      for (const i of ids) {
        const n = nodos[i], d = Math.hypot(n.x - cx, n.y - cy) / R;
        const z = tz + gz + gauss(rnd(n.id, 'z1'), rnd(n.id, 'z2')) * R * 0.55 * Math.sqrt(Math.max(0.12, 1 - d * d * 0.22));
        pos[i * 3] = n.x; pos[i * 3 + 1] = -n.y; pos[i * 3 + 2] = z;
      }
      listaGrupos.push({ ids, R, c: nodos[ids[0]].c, k });
    }
    // centrar el conjunto en el origen
    const bb = new THREE.Box3().setFromArray(pos), cen = bb.getCenter(new THREE.Vector3());
    for (let i = 0; i < N; i++) { pos[i * 3] -= cen.x; pos[i * 3 + 1] -= cen.y; pos[i * 3 + 2] -= cen.z; }
  } else {
    // Brazos mas definidos: se acerca cada estrella a la linea central del brazo mas cercano
    // (misma espiral logaritmica que hacer_nebulosa.py: r = 70 e^(0.3 th), 4 brazos).
    const B = 0.30, TH0 = 0.5, THMAX = 2.15 * Math.PI, TAU = Math.PI * 2;
    for (let i = 0; i < N; i++) {
      const n = nodos[i], r = Math.hypot(n.sx, n.sy), ang = Math.atan2(n.sy, n.sx);
      let mejor = null;
      for (let b = 0; b < 4; b++) {
        const base = (((ang - b / 4 * TAU) % TAU) + TAU) % TAU;
        for (let w = -1; w <= 2; w++) {
          const th = base + w * TAU;
          if (th < TH0 - 0.6 || th > TH0 + THMAX + 0.6) continue;
          const rc = 70 * Math.exp(B * th), err = Math.abs(Math.log(Math.max(r, 1) / rc));
          if (!mejor || err < mejor.err) mejor = { err, rc };
        }
      }
      const rr = mejor ? mejor.rc + (r - mejor.rc) * 0.42 : r;
      const k = r > 0 ? rr / r : 1;
      const y = gauss(rnd(n.id, 'y1'), rnd(n.id, 'y2')) * (3 + 36 * Math.exp(-rr / 130));
      pos[i * 3] = n.sx * k; pos[i * 3 + 1] = y; pos[i * 3 + 2] = n.sy * k;
    }
    for (const [k, ids] of grupos) listaGrupos.push({ ids, R: 40, c: nodos[ids[0]].c, k });
  }
  const P = (i) => new THREE.Vector3(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]);

  // esfera de cada grupo y de cada tema (para nubes, encuadre y rotulos)
  for (const g of listaGrupos) {
    const c = new THREE.Vector3(); g.ids.forEach((i) => c.add(P(i))); c.divideScalar(g.ids.length); g.centro = c;
  }
  const temasGeo = temas.map((t, ti) => {
    const ids = []; nodos.forEach((n, i) => { if (n.c === ti) ids.push(i); });
    const c = new THREE.Vector3(); ids.forEach((i) => c.add(P(i))); c.divideScalar(Math.max(1, ids.length));
    let r = 0; ids.forEach((i) => { r = Math.max(r, P(i).distanceTo(c)); });
    let rotulo = c.clone().add(new THREE.Vector3(0, Math.max(14, r * 0.8), 0));
    if (ESPIRAL && ids.length) { // como el "ancla" del servidor: nota central del tramo del tema
      const ord = [...ids].sort((a, b) => (nodos[b].g - nodos[a].g) || (nodos[a].id < nodos[b].id ? -1 : 1));
      rotulo = P(ord[Math.floor(ord.length / 2)]).setY(22);
    }
    return { ids, centro: c, radio: Math.max(30, r), rotulo };
  });
  const todo = new THREE.Sphere(); todo.setFromPoints(nodos.map((_, i) => P(i)));

  const vecinos = nodos.map(() => []);
  for (const [a, b] of G.aristas) { vecinos[a].push(b); vecinos[b].push(a); }
  vecinos.forEach((v) => v.sort((a, b) => nodos[b].g - nodos[a].g));

  D = { G, temas, nodos, aristas: G.aristas, vecinos, pos, size, col, grupos: listaGrupos, temasGeo, todo, P,
    norm: nodos.map((n) => norm(n.t + ' ' + n.id)) };
  D.polvo = hacerPolvo();
  D.nubes = hacerListaNubes();
}

function hacerPolvo() { // estrellas decorativas (no se pueden pulsar)
  const { nodos, pos, col, grupos } = D, R = prng(ESPIRAL ? 4242 : 2424);
  const p = [], c = [], s = [], t = [];
  const add = (x, y, z, color, k, size, tema) => { p.push(x, y, z); c.push(color.r * k, color.g * k, color.b * k); s.push(size); t.push(tema); };
  const blanco = new THREE.Color(1, 1, 1), calido = lin('#ffd9b0'), tmp = new THREE.Color();
  if (!ESPIRAL) {
    for (const g of grupos) {
      for (const i of g.ids) for (let k = 0; k < 2; k++) {
        tmp.copy(col[g.c]).lerp(blanco, 0.3);
        add(pos[i * 3] + gauss(R(), R()) * g.R * 0.7, pos[i * 3 + 1] + gauss(R(), R()) * g.R * 0.7, pos[i * 3 + 2] + gauss(R(), R()) * g.R * 0.7,
          tmp, 0.12 + R() * 0.22, 2.5 + R() * 3, g.c);
      }
    }
  } else {
    for (let k = 0; k < 900; k++) { // bulbo central (15/11: menos denso)
      const r = Math.abs(gauss(R(), R())) * 48 + R() * 12, th = R() * Math.PI * 2, ph = Math.acos(2 * R() - 1);
      tmp.copy(calido).lerp(blanco, R() * 0.4);
      add(r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph) * 0.55, r * Math.sin(ph) * Math.sin(th), tmp, 0.03 + R() * 0.07, 2.2 + R() * 2.8, -1);
    }
    for (let k = 0; k < 1500; k++) { // disco difuso
      const r = 60 + -Math.log(Math.max(R(), 1e-6)) * 190, a = R() * Math.PI * 2;
      if (r > 760) continue;
      tmp.copy(calido).lerp(blanco, 0.6);
      add(r * Math.cos(a), gauss(R(), R()) * (3 + 20 * Math.exp(-r / 160)), r * Math.sin(a), tmp, 0.06 + R() * 0.1, 2.5 + R() * 3, -1);
    }
    nodos.forEach((n, i) => { // polvo a lo largo de los brazos
      const r = Math.hypot(pos[i * 3], pos[i * 3 + 2]), w = 5 + r * 0.035, fc = 0.35 + 0.65 * Math.min(1, r / 230);
      for (let k = 0; k < 3; k++) {
        tmp.copy(col[n.c]).lerp(blanco, 0.35);
        add(pos[i * 3] + gauss(R(), R()) * w, pos[i * 3 + 1] + gauss(R(), R()) * w * 0.25, pos[i * 3 + 2] + gauss(R(), R()) * w, tmp, (0.12 + R() * 0.25) * fc, 2.5 + R() * 3.5, n.c);
      }
    });
  }
  return { p: new Float32Array(p), c: new Float32Array(c), s: new Float32Array(s), t: new Float32Array(t) };
}

function hacerListaNubes() {
  const { temas, nodos, pos, col, grupos, temasGeo } = D, R = prng(ESPIRAL ? 909 : 707);
  const L = [];
  const nube = (x, y, z, s, color, a, tema) => L.push({ x, y, z, s, color, a, tema, rot: R() * Math.PI * 2, v: Math.floor(R() * 4) });
  const tono = (c, k) => { const t = c.clone(); t.offsetHSL((R() - 0.5) * 0.06, (R() - 0.5) * 0.1, 0); return t.multiplyScalar(k); };
  if (!ESPIRAL) {
    for (const g of grupos) {
      const n = Math.min(9, Math.max(1, Math.round(1 + Math.sqrt(g.ids.length) * 0.6)));
      for (let j = 0; j < n; j++) {
        const i = g.ids[Math.floor(R() * g.ids.length)];
        nube(pos[i * 3] + gauss(R(), R()) * g.R * 0.35, pos[i * 3 + 1] + gauss(R(), R()) * g.R * 0.35, pos[i * 3 + 2] + gauss(R(), R()) * g.R * 0.35,
          g.R * (0.9 + R() * 0.9) + 16, tono(col[g.c], 1), (0.03 + R() * 0.03) * Math.min(1, 5 / Math.sqrt(g.ids.length + 1) + 0.2), g.c);
      }
    }
    temasGeo.forEach((tg, ti) => { if (tg.ids.length) nube(tg.centro.x, tg.centro.y, tg.centro.z, tg.radio * 1.25 + 40, tono(col[ti], 1), 0.03, ti); });
  } else {
    temas.forEach((t, ti) => {
      const ids = temasGeo[ti].ids, paso = Math.max(1, Math.round(ids.length / 70));
      for (let k = 0; k < ids.length; k += paso) {
        const i = ids[k], r = Math.hypot(pos[i * 3], pos[i * 3 + 2]);
        nube(pos[i * 3] + gauss(R(), R()) * 10, pos[i * 3 + 1] * 0.5, pos[i * 3 + 2] + gauss(R(), R()) * 10,
          24 + r * 0.08 + R() * 14, tono(col[ti], 1), ids.length < 40 ? 0.1 : 0.075, ti);
      }
    });
    const nucleo = lin('#ffd7a6'), rosado = lin('#ffb08a');
    nube(0, 0, 0, 60, nucleo.clone(), 0.2, -1);
    nube(0, 0, 0, 140, nucleo.clone(), 0.07, -1);
    nube(0, 0, 0, 300, rosado.clone(), 0.04, -1);
    nube(0, 0, 0, 650, lin('#8fa0d0'), 0.02, -1);
  }
  const pal = temas.map((_, i) => col[i]);
  for (let k = 0; k < 7; k++) { // velos lejanos del fondo
    const th = R() * Math.PI * 2, ph = Math.acos(2 * R() - 1), r = 2600 + R() * 1200;
    nube(r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph), r * Math.sin(ph) * Math.sin(th), 1300 + R() * 900, tono(pal[k % pal.length], 1), 0.018, -1);
  }
  return L;
}

let atlasCache = null;
function atlasNubes() { // 4 nubes de ruido fBm con deformacion de dominio, atlas 512x512 de 1 canal
  if (atlasCache) return atlasCache;
  const S = 256, A = 512, out = new Uint8Array(A * A);
  for (let v = 0; v < 4; v++) {
    const R = prng(101 + v * 31), G = 64, red = new Float32Array(G * G);
    for (let i = 0; i < red.length; i++) red[i] = R();
    const ruido = (x, y) => {
      const xi = Math.floor(x), yi = Math.floor(y), fx = x - xi, fy = y - yi;
      const u = fx * fx * (3 - 2 * fx), w = fy * fy * (3 - 2 * fy);
      const g = (a, b) => red[((b & (G - 1)) * G) + (a & (G - 1))];
      return (g(xi, yi) * (1 - u) + g(xi + 1, yi) * u) * (1 - w) + (g(xi, yi + 1) * (1 - u) + g(xi + 1, yi + 1) * u) * w;
    };
    const fbm = (x, y) => { let s = 0, a = 0.5, f = 1; for (let o = 0; o < 5; o++) { s += a * ruido(x * f, y * f); f *= 2.03; a *= 0.5; } return s; };
    const ox = (v % 2) * S, oy = Math.floor(v / 2) * S;
    for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
      const u = (x + 0.5) / S * 2 - 1, w = (y + 0.5) / S * 2 - 1, r2 = u * u + w * w;
      let val = 0;
      if (r2 < 1) {
        const px = u * 2.4 + v * 7.3, py = w * 2.4 + v * 3.1;
        const q = fbm(px + 5.2, py + 1.3), q2 = fbm(px + 1.7, py + 9.2);
        const n = fbm(px + 2.2 * q, py + 2.2 * q2);
        const caida = Math.pow(1 - r2, 2.2);
        val = (Math.pow(Math.max(0, n - 0.25) / 0.75, 1.5) * 1.6 + 0.18) * caida;
      }
      out[(oy + y) * A + ox + x] = Math.min(255, val * 255);
    }
  }
  atlasCache = out;
  return out;
}

// ------------------------------------------------------------------ construccion WebGL
function geo(attrs, index) {
  const g = new THREE.BufferGeometry();
  for (const [k, [arr, n]] of Object.entries(attrs)) g.setAttribute(k, new THREE.BufferAttribute(arr, n));
  if (index) g.setIndex(new THREE.BufferAttribute(index, 1));
  return g;
}
const aditivo = { transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending };

function crearFondoEstrellas() {
  const R = prng(1311), N = 5000, p = new Float32Array(N * 3), c = new Float32Array(N * 3), s = new Float32Array(N);
  const banda = new THREE.Vector3(0.3, 1, 0.2).normalize(), v = new THREE.Vector3(), tmp = new THREE.Color();
  for (let i = 0; i < N; i++) {
    v.set(gauss(R(), R()), gauss(R(), R()), gauss(R(), R())).normalize();
    if (R() < 0.4) { v.addScaledVector(banda, -v.dot(banda) * (0.85 + R() * 0.15)).normalize(); } // via lactea tenue
    v.multiplyScalar(9000 + R() * 3000);
    p.set([v.x, v.y, v.z], i * 3);
    const m = R(), k = 0.12 + m * m * m * 0.9;
    tmp.setHSL(R() < 0.7 ? 0.6 : 0.08, 0.25 + R() * 0.3, 0.75);
    c.set([tmp.r * k, tmp.g * k, tmp.b * k], i * 3);
    s[i] = m > 0.985 ? 3.6 : m > 0.85 ? 2.4 : 1.6;
  }
  const mat = new THREE.ShaderMaterial({ uniforms: { uPR: U.uPR }, vertexShader: VS_FONDO, fragmentShader: FS_FONDO, ...aditivo });
  const pts = new THREE.Points(geo({ position: [p, 3], aColor: [c, 3], aSize: [s, 1] }), mat);
  pts.frustumCulled = false; pts.renderOrder = -10;
  return pts;
}

function crearEstrellas() {
  const { nodos, pos, size, col } = D, N = nodos.length;
  const c = new Float32Array(N * 3), idx = new Float32Array(N), tema = new Float32Array(N), vec = new Float32Array(N);
  const tam = ESPIRAL ? new Float32Array(size) : size;
  nodos.forEach((n, i) => {
    const k = col[n.c]; let f = 1;
    if (ESPIRAL) { const r = Math.hypot(pos[i * 3], pos[i * 3 + 2]); f = 0.28 + 0.72 * Math.min(1, r / 260); tam[i] = size[i] * (0.65 + 0.35 * Math.min(1, r / 230)); }
    c.set([k.r * f, k.g * f, k.b * f], i * 3); idx[i] = i; tema[i] = n.c;
  });
  const mat = new THREE.ShaderMaterial({ uniforms: U, vertexShader: VS_ESTRELLA, fragmentShader: FS_ESTRELLA, ...aditivo });
  const pts = new THREE.Points(geo({ position: [pos, 3], aColor: [c, 3], aSize: [tam, 1], aIdx: [idx, 1], aTema: [tema, 1], aVec: [vec, 1] }), mat);
  pts.geometry.computeBoundingSphere();
  pts.renderOrder = 5;
  return pts;
}

function crearPolvo() {
  const P = D.polvo, n = P.s.length, idx = new Float32Array(n).fill(-1), vec = new Float32Array(n);
  const mat = new THREE.ShaderMaterial({ uniforms: U, vertexShader: VS_ESTRELLA, fragmentShader: FS_ESTRELLA, ...aditivo });
  const pts = new THREE.Points(geo({ position: [P.p, 3], aColor: [P.c, 3], aSize: [P.s, 1], aIdx: [idx, 1], aTema: [P.t, 1], aVec: [vec, 1] }), mat);
  pts.frustumCulled = false; pts.renderOrder = 2;
  return pts;
}

function crearLineas() {
  const { aristas, nodos, pos, col } = D, E = aristas.length;
  const p = new Float32Array(E * 6), c = new Float32Array(E * 6), t = new Float32Array(E * 2);
  const k0 = ESPIRAL ? 0.0065 : 0.045; // 15/11: enlaces de la galaxia más tenues (se sumaban en el centro)
  aristas.forEach(([a, b], e) => {
    p.set([pos[a * 3], pos[a * 3 + 1], pos[a * 3 + 2], pos[b * 3], pos[b * 3 + 1], pos[b * 3 + 2]], e * 6);
    const ca = col[nodos[a].c], cb = col[nodos[b].c], k = k0 / (1 + Math.max(nodos[a].g, nodos[b].g) / 140);
    c.set([ca.r * k, ca.g * k, ca.b * k, cb.r * k, cb.g * k, cb.b * k], e * 6);
    t[e * 2] = nodos[a].c; t[e * 2 + 1] = nodos[b].c;
  });
  const mat = new THREE.ShaderMaterial({ uniforms: { uFoco: U.uFoco, uAten: { value: 1 } }, vertexShader: VS_LINEA, fragmentShader: FS_LINEA, ...aditivo });
  const ls = new THREE.LineSegments(geo({ position: [p, 3], aColor: [c, 3], aTema: [t, 1] }), mat);
  ls.frustumCulled = false; ls.renderOrder = 1;
  return ls;
}

function crearMarca() {
  const mat = new THREE.ShaderMaterial({ uniforms: { uEscala: U.uEscala, uPR: U.uPR }, vertexShader: VS_MARCA, fragmentShader: FS_MARCA, ...aditivo });
  const pts = new THREE.Points(geo({ position: [new Float32Array(3), 3], aSize: [new Float32Array(1), 1] }), mat);
  pts.visible = false; pts.frustumCulled = false; pts.renderOrder = 8;
  return pts;
}

function crearNubes() {
  const L = D.nubes, M = L.length;
  const p = new Float32Array(M * 12), e = new Float32Array(M * 8), s = new Float32Array(M * 4), c = new Float32Array(M * 12);
  const a = new Float32Array(M * 4), r = new Float32Array(M * 4), t = new Float32Array(M * 4), v = new Float32Array(M * 4), ix = new Uint16Array(M * 6);
  const esq = [-1, -1, 1, -1, 1, 1, -1, 1];
  L.forEach((n, i) => {
    for (let k = 0; k < 4; k++) {
      const j = i * 4 + k;
      p.set([n.x, n.y, n.z], j * 3); e.set([esq[k * 2], esq[k * 2 + 1]], j * 2); s[j] = n.s;
      c.set([n.color.r, n.color.g, n.color.b], j * 3); a[j] = n.a; r[j] = n.rot; t[j] = n.tema; v[j] = n.v;
    }
    ix.set([i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3], i * 6);
  });
  const tex = new THREE.DataTexture(atlasNubes(), 512, 512, THREE.RedFormat, THREE.UnsignedByteType);
  tex.generateMipmaps = true; tex.minFilter = THREE.LinearMipmapLinearFilter; tex.magFilter = THREE.LinearFilter;
  tex.unpackAlignment = 1; tex.needsUpdate = true;
  const mat = new THREE.ShaderMaterial({ uniforms: { uMapa: { value: tex }, uFoco: U.uFoco }, vertexShader: VS_NUBE, fragmentShader: FS_NUBE, ...aditivo });
  const m = new THREE.Mesh(geo({ position: [p, 3], aEsq: [e, 2], aSize: [s, 1], aColor: [c, 3], aAlpha: [a, 1], aRot: [r, 1], aTema: [t, 1], aVar: [v, 1] }, ix), mat);
  m.frustumCulled = false; m.renderOrder = 0;
  m.userData.tex = tex;
  return m;
}

function montar() {
  if (gl || !D) return;
  const canvas = document.createElement('canvas');
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: CAL.aa, alpha: false, stencil: false, depth: true, powerPreference: 'default' });
  } catch (e) { console.warn('WebGL no disponible', e); return irA2D('webgl'); }
  escena.prepend(canvas);
  canvas.addEventListener('webglcontextlost', (ev) => {
    ev.preventDefault();
    if (canvas.dataset.liberado) return;
    console.warn('Contexto WebGL perdido; se reintentara');
    setTimeout(() => { liberar(); comprobarVRAM().then((ok) => { if (ok && visible()) montar(); }); }, 2000);
  });
  renderer.info.autoReset = false;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(FONDO);
  const grupo = new THREE.Group(); grupo.rotation.y = giro; scene.add(grupo);
  gl = { renderer, canvas, scene, grupo, composer: null, bloom: null, nubes: null, hilos: null };
  gl.fondo = crearFondoEstrellas(); scene.add(gl.fondo);
  gl.lineas = crearLineas(); grupo.add(gl.lineas);
  gl.polvo = crearPolvo(); grupo.add(gl.polvo);
  gl.estrellas = crearEstrellas(); grupo.add(gl.estrellas);
  gl.marca = crearMarca(); grupo.add(gl.marca);
  ajustarTam();
  aplicarModo();
  aplicarSeleccionGL(false);
  pedir();
}

function liberar() {
  if (!gl) return;
  cancelAnimationFrame(raf); raf = 0;
  quitarExtras();
  if (gl.hilos) { gl.hilos.geometry.dispose(); gl.hilos.material.dispose(); }
  gl.scene.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
  gl.canvas.dataset.liberado = '1';
  gl.renderer.dispose();
  gl.renderer.forceContextLoss();
  gl.canvas.remove();
  gl = null;
  for (const r of rotulos) r.style.opacity = 0;
}

function ponerExtras() { // bloom + nubes (solo en modo completo)
  if (!gl || gl.composer) return;
  const { renderer, scene } = gl;
  const composer = new EffectComposer(renderer);
  composer.setPixelRatio(renderer.getPixelRatio()); composer.setSize(innerWidth, innerHeight);
  composer.addPass(new RenderPass(scene, camara));
  const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), ESPIRAL ? 0.38 : 0.55, 0.5, ESPIRAL ? 0.5 : 0.32); // 15/11: galaxia menos quemada
  composer.addPass(bloom);
  composer.addPass(new OutputPass());
  gl.composer = composer; gl.bloom = bloom;
  gl.nubes = crearNubes(); gl.grupo.add(gl.nubes);
}

function quitarExtras() {
  if (!gl) return;
  if (gl.composer) { gl.composer.passes.forEach((p) => p.dispose && p.dispose()); gl.composer.dispose(); gl.composer = gl.bloom = null; }
  if (gl.nubes) { gl.grupo.remove(gl.nubes); gl.nubes.geometry.dispose(); gl.nubes.material.dispose(); gl.nubes.userData.tex.dispose(); gl.nubes = null; }
}

function aplicarModo() {
  aviso.hidden = !ligero;
  aviso.title = vramLibre != null ? `VRAM libre: ${vramLibre.toFixed(2)} GB (sin bloom ni nubes)` : '';
  if (!gl) return;
  if (ligero) quitarExtras(); else ponerExtras();
  pedir();
}

function ajustarTam() {
  camara.aspect = innerWidth / Math.max(1, innerHeight); camara.updateProjectionMatrix();
  if (!gl) return;
  const pr = Math.min(PR_MAX, devicePixelRatio || 1);
  gl.renderer.setPixelRatio(pr); gl.renderer.setSize(innerWidth, innerHeight, false);
  gl.canvas.style.width = '100vw'; gl.canvas.style.height = '100vh';
  if (gl.composer) { gl.composer.setPixelRatio(pr); gl.composer.setSize(innerWidth, innerHeight); }
  U.uPR.value = pr;
  U.uEscala.value = innerHeight * pr / (2 * Math.tan(THREE.MathUtils.degToRad(FOV) / 2));
  pedir();
}
addEventListener('resize', ajustarTam);

// ------------------------------------------------------------------ bucle (bajo demanda, <=30 fps)
const visible = () => document.visibilityState === 'visible';
function pedir() { sucio = true; programar(); }
let enTick = false;
function programar() { if (!raf && !enTick && gl && visible()) raf = requestAnimationFrame(tick); }
function girando() { return ESPIRAL && !vuelo; }

function tick(t) {
  raf = 0;
  enTick = true;
  try { paso(t); } finally { enTick = false; }
}
function paso(t) {
  if (!gl || !visible()) return;
  const continuo = girando() || vuelo || destello;
  const objetivo = continuo && !document.hasFocus() ? FPS_SIN_FOCO : FPS_MAX;
  if (ultimo && t - ultimo < 1000 / objetivo - 2) { raf = requestAnimationFrame(tick); return; }
  const dt = ultimo ? Math.min(0.1, (t - ultimo) / 1000) : 0;
  ultimo = t;
  let anim = false;
  if (vuelo) anim = pasoVuelo(t) || anim;
  if (destello) anim = pasoDestello(t) || anim;
  if (girando()) { giro += VEL_GIRO * dt; gl.grupo.rotation.y = giro; anim = true; }
  sucio = false;
  const movido = controles.update();
  dibujar();
  if (movido || anim || sucio) raf = requestAnimationFrame(tick);
  else ultimo = 0; // en reposo: el siguiente cuadro no hereda un dt enorme
}

function dibujar() {
  gl.fondo.position.copy(camara.position);
  gl.renderer.info.reset();
  if (gl.composer) gl.composer.render(); else gl.renderer.render(gl.scene, camara);
  frames++;
  colocarRotulos();
}

document.addEventListener('visibilitychange', () => {
  if (!visible()) {
    cancelAnimationFrame(raf); raf = 0; ultimo = 0;
    clearTimeout(tLiberar); tLiberar = setTimeout(() => { if (!visible()) liberar(); }, LIBERAR_MS);
  } else {
    clearTimeout(tLiberar);
    comprobarVRAM().then((ok) => { if (!ok) return; if (!gl) montar(); else pedir(); });
  }
});
addEventListener('focus', () => pedir());

// contador: fps reales y VRAM estimada
setInterval(() => {
  if (!visible()) return;
  const fps = frames; frames = 0;
  if (!gl) { info.textContent = 'sin contexto WebGL'; return; }
  const mb = estimarMB();
  const m = gl.renderer.info.memory;
  info.textContent = `${fps ? fps + ' fps' : 'reposo'} · ≈ ${mb.toFixed(0)} MB VRAM${ligero ? ' · ligero' : ''}`;
  info.title = `Estimado: buffers de pantalla + post-proceso + geometrias + texturas.\nGeometrias: ${m.geometries} · texturas: ${m.textures} · llamadas de dibujo: ${gl.renderer.info.render.calls}` +
    (vramLibre != null ? `\nVRAM libre en la GPU: ${vramLibre.toFixed(2)} GB` : '');
}, 1000);

function estimarMB() {
  const w = gl.canvas.width, h = gl.canvas.height, px = w * h;
  let b = px * 8; // lienzo: color + profundidad
  if (gl.composer) b += 2 * px * 12 + px * 8 * 0.92; // 2 destinos HalfFloat + mips del bloom
  gl.scene.traverse((o) => {
    if (!o.geometry) return;
    for (const a of Object.values(o.geometry.attributes)) b += a.array.byteLength;
    if (o.geometry.index) b += o.geometry.index.array.byteLength;
  });
  if (gl.nubes) b += 512 * 512 * 1.34;
  return b / 1048576;
}

// ------------------------------------------------------------------ VRAM / modo ligero
async function leerVRAMLibre() {
  try {
    const ctl = new AbortController(), to = setTimeout(() => ctl.abort(), 5000);
    const r = await fetch('/api/stats', { signal: ctl.signal, cache: 'no-store' });
    clearTimeout(to);
    if (!r.ok) return null;
    const g = (await r.json()).now?.gpu;
    return g && g.vram_total ? g.vram_total - g.vram_used : null;
  } catch { return null; }
}

async function comprobarVRAM() {
  const libre = await leerVRAMLibre();
  vramLibre = libre;
  if (libre != null && libre < GB_MINIMO) { irA2D('vram'); return false; }
  let lig = ligero;
  if (FORZAR === 'ligero') lig = true;
  else if (FORZAR === 'completo') lig = false;
  else if (libre != null) {
    if (!ligero && libre < GB_LIGERO) lig = true;
    else if (ligero && libre >= GB_VOLVER) lig = false;
  }
  if (lig !== ligero) { ligero = lig; aplicarModo(); } else { aviso.hidden = !ligero; }
  return true;
}
setInterval(() => { if (visible()) comprobarVRAM(); }, SONDEO_MS);

function irA2D(motivo) {
  liberar();
  location.replace(RUTA_2D + '?motivo=' + encodeURIComponent(motivo));
  return false;
}

// ------------------------------------------------------------------ camara: vuelos y encuadres
const facil = (f) => f < 0.5 ? 4 * f * f * f : 1 - Math.pow(-2 * f + 2, 3) / 2;
const aMundo = (v) => { if (gl) gl.grupo.updateMatrixWorld(); return v.clone().applyAxisAngle(new THREE.Vector3(0, 1, 0), giro); };

function volar(objLocal, dist, ms = 1100, dir = null) {
  const d = dir || camara.position.clone().sub(controles.target).normalize();
  vuelo = { t0: performance.now(), ms, p0: camara.position.clone(), q0: controles.target.clone(), obj: objLocal.clone(), dist, dir: d };
  pedir();
}
function pasoVuelo(t) {
  const v = vuelo, f = Math.min(1, (t - v.t0) / v.ms), e = facil(f);
  const tg = aMundo(v.obj), fin = tg.clone().addScaledVector(v.dir, v.dist);
  camara.position.lerpVectors(v.p0, fin, e);
  controles.target.lerpVectors(v.q0, tg, e);
  if (f >= 1) { vuelo = null; return false; }
  return true;
}
function distPara(radio) {
  const vf = THREE.MathUtils.degToRad(FOV) / 2, hf = Math.atan(Math.tan(vf) * camara.aspect);
  return radio / Math.sin(Math.min(vf, hf)) * 1.02;
}
function encuadrar(centro, radio, ms) { volar(centro, distPara(radio), ms); }
const encuadrarTodo = (ms) => encuadrar(D.todo.center, D.todo.radius, ms);
function volarA(i) { volar(D.P(i), Math.max(28, D.size[i] * 3.2)); }

// ------------------------------------------------------------------ seleccion, foco y destello
function aplicarSeleccionGL(animar) {
  if (!gl) return;
  U.uSel.value = sel; U.uHaySel.value = sel >= 0 ? 1 : 0;
  gl.lineas.material.uniforms.uAten.value = sel >= 0 ? 0.35 : 1;
  const vec = gl.estrellas.geometry.attributes.aVec;
  vec.array.fill(0);
  if (sel >= 0) { vec.array[sel] = 1; for (const j of D.vecinos[sel]) vec.array[j] = 1; }
  vec.needsUpdate = true;
  if (gl.hilos) { gl.grupo.remove(gl.hilos); gl.hilos.geometry.dispose(); gl.hilos.material.dispose(); gl.hilos = null; }
  gl.marca.visible = sel >= 0;
  if (sel < 0) { pedir(); return; }
  const { pos, size, col, nodos } = D, vs = D.vecinos[sel], n = vs.length;
  gl.marca.geometry.attributes.position.array.set(pos.subarray(sel * 3, sel * 3 + 3));
  gl.marca.geometry.attributes.position.needsUpdate = true;
  gl.marca.geometry.attributes.aSize.array[0] = size[sel]; gl.marca.geometry.attributes.aSize.needsUpdate = true;
  if (n) {
    const p = new Float32Array(n * 6), c = new Float32Array(n * 6), t = new Float32Array(n * 2), blanco = new THREE.Color(1, 1, 1);
    const c0 = col[nodos[sel].c].clone().lerp(blanco, 0.5);
    vs.forEach((j, k) => {
      p.set([pos[sel * 3], pos[sel * 3 + 1], pos[sel * 3 + 2], pos[j * 3], pos[j * 3 + 1], pos[j * 3 + 2]], k * 6);
      const c1 = col[nodos[j].c].clone().lerp(blanco, 0.35);
      c.set([c0.r, c0.g, c0.b, c1.r, c1.g, c1.b], k * 6);
      t[k * 2] = 0; t[k * 2 + 1] = 1;
    });
    const mat = new THREE.ShaderMaterial({ uniforms: { uProg: { value: animar ? 0 : 1.2 } }, vertexShader: VS_HILO, fragmentShader: FS_HILO, ...aditivo });
    gl.hilos = new THREE.LineSegments(geo({ position: [p, 3], aColor: [c, 3], aT: [t, 1] }), mat);
    gl.hilos.frustumCulled = false; gl.hilos.renderOrder = 6;
    gl.grupo.add(gl.hilos);
    if (animar) destello = { t0: performance.now(), ms: 750 };
  }
  pedir();
}
function pasoDestello(t) {
  if (!gl || !gl.hilos) { destello = null; return false; }
  const f = Math.min(1, (t - destello.t0) / destello.ms);
  gl.hilos.material.uniforms.uProg.value = f * 1.2;
  if (f >= 1) { destello = null; return false; }
  return true;
}

// ------------------------------------------------------------------ picking (Raycaster sobre Points)
const rayo = new THREE.Raycaster(), ptr = new THREE.Vector2();
function estrellaEn(x, y) {
  if (!gl || !D) return -1;
  ptr.set(x / innerWidth * 2 - 1, -(y / innerHeight) * 2 + 1);
  rayo.setFromCamera(ptr, camara);
  const k = 2 * Math.tan(THREE.MathUtils.degToRad(FOV) / 2) / innerHeight; // mundo por pixel a distancia 1
  const dist = camara.position.distanceTo(controles.target);
  rayo.params.Points.threshold = Math.max(0.3, 40 * k * dist);
  gl.grupo.updateMatrixWorld();
  const hits = rayo.intersectObject(gl.estrellas, false);
  let mejor = -1, md = Infinity;
  for (const h of hits) {
    const i = h.index;
    if (foco >= 0 && D.nodos[i].c !== foco) continue;
    const px = h.distanceToRay / (k * Math.max(0.5, h.distance));
    const lim = Math.max(8, D.size[i] / (k * Math.max(0.5, h.distance)) * 0.14);
    if (px < lim && px - lim * 0.3 < md) { md = px - lim * 0.3; mejor = i; }
  }
  return mejor;
}

let pend = false, ultimoPtr = null, abajo = null;
escena.addEventListener('pointermove', (e) => {
  ultimoPtr = e;
  if (e.buttons) { tip.hidden = true; return; }
  if (pend) return;
  pend = true;
  requestAnimationFrame(() => {
    pend = false;
    const ev = ultimoPtr, i = estrellaEn(ev.clientX, ev.clientY);
    if (i !== hover) { hover = i; U.uHover.value = i; escena.classList.toggle('sobre', i >= 0); pedir(); }
    if (i >= 0) {
      tip.textContent = D.nodos[i].t; tip.hidden = false;
      tip.style.left = Math.min(ev.clientX + 14, innerWidth - tip.offsetWidth - 8) + 'px';
      tip.style.top = (ev.clientY + 14) + 'px';
    } else tip.hidden = true;
  });
});
escena.addEventListener('pointerleave', () => { tip.hidden = true; if (hover >= 0) { hover = -1; U.uHover.value = -1; pedir(); } });
escena.addEventListener('pointerdown', (e) => { abajo = { x: e.clientX, y: e.clientY, b: e.button }; });
escena.addEventListener('pointerup', (e) => {
  const a = abajo; abajo = null;
  if (!a || a.b !== 0 || Math.abs(e.clientX - a.x) + Math.abs(e.clientY - a.y) > 5) return;
  const i = estrellaEn(e.clientX, e.clientY);
  if (i >= 0) seleccionar(i, false); else if (sel >= 0) cerrarFicha();
});
escena.addEventListener('dblclick', (e) => {
  const i = estrellaEn(e.clientX, e.clientY);
  if (i >= 0) { if (sel !== i) seleccionar(i, false); volarA(i); }
  else if (foco >= 0) encuadrar(D.temasGeo[foco].centro, D.temasGeo[foco].radio);
  else encuadrarTodo();
});
addEventListener('keydown', (e) => {
  if (e.key !== 'Escape' || e.target === q) return;
  if (sel >= 0) cerrarFicha(); else if (foco >= 0) enfocar(foco);
});

// ------------------------------------------------------------------ rotulos de constelacion (DOM)
const rotulos = [];
const vtmp = new THREE.Vector3();
function crearRotulos() {
  const cont = $('n3-rotulos'); cont.replaceChildren(); rotulos.length = 0;
  D.temas.forEach((t) => { const r = el('div', 'n3-rotulo', t.nombre); r.style.color = t.color; cont.append(r); rotulos.push(r); });
  rotulos.forEach((r) => { r._w = r.offsetWidth || 80; r._h = r.offsetHeight || 18; });
  ordenRotulos = D.temas.map((_, i) => i).sort((a, b) => D.temas[b].n - D.temas[a].n);
}
let ordenRotulos = [];
function colocarRotulos() {
  if (!D) return;
  const puestos = [];
  const lista = foco >= 0 ? [foco, ...ordenRotulos.filter((i) => i !== foco)] : ordenRotulos;
  lista.forEach((ti) => {
    const tg = D.temasGeo[ti], r = rotulos[ti]; if (!r) return;
    vtmp.copy(tg.rotulo).applyAxisAngle(new THREE.Vector3(0, 1, 0), giro).project(camara);
    if (vtmp.z > 1 || Math.abs(vtmp.x) > 1.2 || Math.abs(vtmp.y) > 1.2 || !tg.ids.length) { r.style.opacity = 0; return; }
    const x = (vtmp.x + 1) / 2 * innerWidth, y = (1 - vtmp.y) / 2 * innerHeight;
    const caja = [x - r._w / 2 - 4, y - r._h - 2, x + r._w / 2 + 4, y + 2];
    if (puestos.some((b) => caja[0] < b[2] && caja[2] > b[0] && caja[1] < b[3] && caja[3] > b[1])) { r.style.opacity = 0; return; }
    puestos.push(caja);
    r.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(-50%, -100%)`;
    r.style.opacity = foco >= 0 && ti !== foco ? 0.25 : 0.88;
  });
}

// ------------------------------------------------------------------ ficha de nota
const ficha = $('neb-ficha');
$('neb-cerrar').addEventListener('click', () => cerrarFicha());
function cerrarFicha() { sel = -1; ficha.hidden = true; aplicarSeleccionGL(false); }

function punto(color) { const p = el('span', 'neb-punto'); p.style.color = color; p.style.background = color; return p; }
function itemNota(j, onClick) {
  const li = el('li'); li.append(punto(D.temas[D.nodos[j].c].color), el('span', null, D.nodos[j].t));
  li.addEventListener('click', onClick); return li;
}

async function seleccionar(i, mover) {
  sel = i; aplicarSeleccionGL(true);
  const n = D.nodos[i], t = D.temas[n.c];
  if (mover) volarA(i);
  const ft = $('f-tema'); ft.replaceChildren(punto(t.color), el('span', null, t.nombre + (n.s ? ' · ' + n.s : '')));
  $('f-titulo').textContent = n.t;
  $('f-meta').replaceChildren(); $('f-texto').replaceChildren(el('p', null, '…'));
  $('f-enl').replaceChildren(); $('f-enl-h').textContent = `Enlaces (${D.vecinos[i].length})`;
  D.vecinos[i].forEach((j) => $('f-enl').append(itemNota(j, () => seleccionar(j, true))));
  ficha.hidden = false;
  try {
    const r = await fetch('/api/cerebro?nota=' + encodeURIComponent(n.id));
    if (!r.ok) throw new Error(r.status);
    const d = await r.json();
    if (sel !== i) return;
    const meta = $('f-meta');
    if (d.tipo) meta.append(el('span', null, String(d.tipo)));
    (d.tags || []).forEach((tg) => meta.append(el('span', null, '#' + tg)));
    if (d.ruta) meta.append(el('span', 'ruta', String(d.ruta)));
    const tx = $('f-texto'); tx.replaceChildren();
    (d.extracto || []).forEach((l) => tx.append(el('p', null, String(l))));
    if (!(d.extracto || []).length) tx.append(el('p', null, '(nota sin texto)'));
  } catch (_) { if (sel === i) $('f-texto').replaceChildren(el('p', null, 'No se pudo leer la nota.')); }
}

// ------------------------------------------------------------------ leyenda y buscador
function enfocar(ti) {
  foco = foco === ti ? -1 : ti;
  U.uFoco.value = foco;
  document.querySelectorAll('.neb-leyenda button').forEach((b, k) => { b.classList.toggle('activo', k === foco); b.classList.toggle('apagado', foco >= 0 && k !== foco); });
  if (foco >= 0) encuadrar(D.temasGeo[foco].centro, D.temasGeo[foco].radio); else encuadrarTodo();
}
function leyenda() {
  const L = $('neb-leyenda'); L.replaceChildren();
  D.temas.forEach((t, ti) => {
    const b = el('button'); b.append(punto(t.color), el('span', null, t.nombre), el('span', 'n', String(t.n)));
    b.addEventListener('click', () => enfocar(ti)); L.append(b);
  });
}
const q = $('neb-q'), res = $('neb-res');
let hallados = [], act = 0;
function norm(s) { return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
q.addEventListener('input', () => {
  const v = norm(q.value.trim()); res.replaceChildren(); act = 0;
  if (!v || !D) { res.hidden = true; return; }
  hallados = D.norm.map((s, i) => [i, s.indexOf(v)]).filter(([, k]) => k >= 0)
    .sort((a, b) => (a[1] - b[1]) || (D.nodos[b[0]].g - D.nodos[a[0]].g)).slice(0, 30).map(([i]) => i);
  hallados.forEach((j, k) => { const li = itemNota(j, () => { seleccionar(j, true); res.hidden = true; }); if (k === 0) li.classList.add('activo'); res.append(li); });
  res.hidden = !hallados.length;
});
q.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { res.hidden = true; q.blur(); return; }
  if (!hallados.length) return;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault(); act = (act + (e.key === 'ArrowDown' ? 1 : hallados.length - 1)) % hallados.length;
    [...res.children].forEach((li, k) => li.classList.toggle('activo', k === act));
  } else if (e.key === 'Enter') { seleccionar(hallados[act], true); res.hidden = true; q.blur(); }
});

// ------------------------------------------------------------------ arranque
async function arrancar() {
  const ok = await comprobarVRAM(); // antes de crear ningun contexto WebGL
  if (!ok) return;
  let G;
  try {
    const r = await fetch('/api/cerebro');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    G = await r.json();
  } catch (e) { $('neb-stats').textContent = 'No se pudo cargar el grafo (' + e.message + ').'; return; }
  prepararDatos(G);
  leyenda(); crearRotulos();
  const s = G.stats;
  $('neb-stats').textContent = `${s.notas.toLocaleString('es-ES')} notas · ${s.enlaces.toLocaleString('es-ES')} enlaces · ${s.temas} constelaciones · 3D`;
  // camara inicial: algo alejada, y entrada suave hacia el encuadre
  const dir = (ESPIRAL ? new THREE.Vector3(0.1, 1.5, 0.75) : new THREE.Vector3(0.32, 0.22, 1)).normalize();
  const d = distPara(D.todo.radius * (ESPIRAL ? 0.85 : 1));
  controles.target.copy(D.todo.center);
  camara.position.copy(D.todo.center).addScaledVector(dir, d * 1.7);
  controles.update();
  if (!visible()) return; // se montara al hacerse visible
  montar();
  volar(D.todo.center, d, 2200, dir);
}
arrancar();
