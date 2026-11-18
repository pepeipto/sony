'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nuevoId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
const api = async (url, opt = {}) => {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opt, body: opt.body && typeof opt.body !== 'string' && !(opt.body instanceof Blob) ? JSON.stringify(opt.body) : opt.body });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.headers.get('content-type')?.includes('json') ? r.json() : r;
};
const ICO = {
  copiar: '<svg class="ico" viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>',
  regen: '<svg class="ico" viewBox="0 0 24 24"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6"/></svg>',
  editar: '<svg class="ico" viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>',
  up: '<svg class="ico" viewBox="0 0 24 24"><path d="M7 11v9H4v-9zM7 11l4-7a2 2 0 0 1 3 2l-1 4h6a2 2 0 0 1 2 2.3l-1.3 6A2 2 0 0 1 17.7 20H7"/></svg>',
  down: '<svg class="ico" viewBox="0 0 24 24"><path d="M7 13V4H4v9zM7 13l4 7a2 2 0 0 0 3-2l-1-4h6a2 2 0 0 0 2-2.3l-1.3-6A2 2 0 0 0 17.7 4H7"/></svg>',
  oir: '<svg class="ico" viewBox="0 0 24 24"><path d="M4 10v4h4l5 4V6L8 10zM16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/></svg>',
  mas: '<svg class="ico" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/></svg>',
  pin: '<svg class="ico" viewBox="0 0 24 24"><path d="M9 4h6l-1 6 4 4H6l4-4zM12 14v6"/></svg>',
};

/* ---------------- estado ---------------- */
const S = {
  ajustes: {}, hilos: [], proyectos: [], programados: [],
  hilo: null, adjuntos: [], generando: null, modelo: 'rapido', modelos: [],
  vista: 'chat', derTab: 'artefacto', artefacto: null, sinLeer: false,
};

function hiloNuevo(proyecto = null) {
  return { id: nuevoId(), titulo: '', proyecto, fijado: false, mensajes: [], creado: Date.now() / 1000 };
}

/* ---------------- arranque ---------------- */
async function init() {
  try { S.sesion = await api('/api/sesion'); } catch { S.sesion = { rol: 'local' }; }
  if (S.sesion.rol === 'invitada') {
    document.body.classList.add('invitada');
    SECCIONES = ['General', 'Voz'];
    $$('.nav-item[data-vista], a.nav-item').forEach(n => n.remove());
    ['#btnAgente', '#btnHerr', '#btnSelModelo', '#btnModelo', '#btnMenuHilo'].forEach(s => $(s)?.remove());
  }
  if (S.sesion.rol !== 'local') {
    const b = document.createElement('button'); b.className = 'nav-item'; b.textContent = '↩ Salir'; b.onclick = async () => { await api('/api/salir', { method: 'POST', body: {} }); location.href = '/login'; };
    $('.side-nav')?.appendChild(b);
  }
  S.ajustes = await api('/api/ajustes');
  aplicarAjustes();
  S.modelo = S.ajustes.modelo || 'rapido';
  [S.hilos, S.proyectos, S.programados] = await Promise.all([api('/api/hilos'), api('/api/proyectos'), api('/api/programados')]);
  pintarLateral();
  const ultimo = localGet('ultimoHilo');
  if (ultimo && S.hilos.find(h => h.id === ultimo)) await abrirHilo(ultimo); else nuevoChat();
  refrescarEstado(); setInterval(refrescarEstado, 3000);
  // Mac (18/11): «escuchar siempre»: al abrir Sony se enciende el modo voz manos libres (se puede apagar en Ajustes → Voz).
  if (S.sesion?.rol !== 'invitada' && S.ajustes.voz?.siempre !== false && !matchMedia('(max-width: 760px)').matches) setTimeout(() => { if (!Voz.activo) Voz.iniciar(); }, 1200);
  try { const w = +localGet('anchoDer'); if (w > 300) $('#der').style.width = w + 'px'; } catch {}
  if (localGet('sinSide') === '1') $('#app').classList.add('sin-side'), $('#btnSide2').classList.remove('hidden');
}
function localGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
function localSet(k, v) { try { localStorage.setItem(k, v); } catch {} }

function aplicarAjustes() {
  const a = S.ajustes;
  const tema = a.tema === 'auto' ? null : a.tema;
  if (tema) document.documentElement.dataset.theme = tema; else delete document.documentElement.dataset.theme;
  { const mc = document.querySelector('meta[name=theme-color]'); if (mc) mc.content = tema === 'sombra' ? '#0e0c0c' : '#262522'; }
  document.body.classList.toggle('letra-grande', a.letra === 'grande');
  $('#uname').textContent = a.nombre || 'el usuario';
  $('#avatar').textContent = (a.nombre || 'C')[0].toUpperCase();
  const h = new Date().getHours();
  const parte = h < 6 ? 'Buenas noches' : h < 13 ? 'Buenos días' : h < 21 ? 'Buenas tardes' : 'Buenas noches';
  $('#saludo').textContent = `${parte}, ${a.nombre || 'el usuario'}`;
}

/* ---------------- estado del modelo ---------------- */
async function refrescarEstado() {
  try {
    const e = await api('/api/chat/estado'); S.modelos = e.modelos;
    const pill = $('#estadoModelo'), b = $('#btnModelo');
    const txt = { listo: 'Modelo listo', cargando: 'Cargando modelo…', apagado: 'Modelo apagado', error: 'Error del modelo', falta_modelo: 'Falta el modelo' }[e.estado] || e.estado;
    pill.textContent = txt; pill.className = 'pill ' + e.estado;
    b.textContent = e.estado === 'apagado' || e.estado === 'error' ? 'Cargar modelo' : 'Descargar modelo';
    b.disabled = e.estado === 'cargando';
    const m = S.modelos.find(x => x.id === S.modelo); $('#nombreModelo').textContent = m ? m.nombre : (S.modelo === 'agente' ? 'Agente' : $('#nombreModelo').textContent);
  } catch { $('#estadoModelo').textContent = 'Sin servidor'; }
}
$('#btnModelo').onclick = async () => {
  const cargar = $('#btnModelo').textContent.startsWith('Cargar');
  $('#btnModelo').disabled = true;
  await api(cargar ? '/api/chat/cargar' : '/api/chat/descargar', { method: 'POST', body: { modelo: S.modelo } }).catch(e => toast(e.message));
  refrescarEstado();
};

/* ---------------- barra lateral ---------------- */
function pintarLateral() {
  const item = h => `<div class="hilo-item ${S.hilo?.id === h.id ? 'on' : ''}" data-id="${h.id}"><span>${esc(h.titulo || 'Chat nuevo')}</span><button class="icon-btn mas" data-menu="${h.id}" title="Más">${ICO.mas}</button></div>`;
  const fij = S.hilos.filter(h => h.fijado), rec = S.hilos.filter(h => !h.fijado).slice(0, 60);
  $('#secFijados').classList.toggle('hidden', !fij.length);
  $('#listaFijados').innerHTML = fij.map(item).join('');
  $('#listaRecientes').innerHTML = rec.length ? rec.map(item).join('') : '<div class="vacio">Aún no hay chats</div>';
  $$('.nav-item[data-vista]').forEach(b => b.classList.toggle('on', S.vista === b.dataset.vista));
}
document.addEventListener('click', e => {
  const m = e.target.closest('[data-menu]');
  if (m) { e.stopPropagation(); return menuHilo(m.dataset.menu, m); }
  const it = e.target.closest('.hilo-item');
  if (it) abrirHilo(it.dataset.id);
  if (!e.target.closest('#menuFlot, #btnSelModelo, #btnHerr, #btnMenuHilo')) $('#menuFlot').classList.add('hidden');
});

function menuFlot(anchor, items) {
  const m = $('#menuFlot'); const r = anchor.getBoundingClientRect();
  m.innerHTML = items.map((it, i) => it === '-' ? '<div class="sep"></div>' : `<button data-i="${i}" class="${it.rojo ? 'rojo' : ''}">${it.t}${it.k ? `<small>${it.k}</small>` : ''}</button>`).join('');
  m.classList.remove('hidden');
  const top = Math.min(r.bottom + 4, innerHeight - m.offsetHeight - 8);
  m.style.top = top + 'px'; m.style.left = Math.min(r.left, innerWidth - m.offsetWidth - 8) + 'px';
  m.onclick = e => { const b = e.target.closest('button'); if (!b) return; m.classList.add('hidden'); items[+b.dataset.i].f(); };
}

// Copiar que funciona también en Safari/iPhone y sin permiso de portapapeles (respaldo con execCommand).
async function copiarTexto(txt) {
  try { await navigator.clipboard.writeText(txt); return; } catch {}
  const ta = document.createElement('textarea'); ta.value = txt; ta.setAttribute('readonly', ''); ta.style.cssText = 'position:fixed;top:-1000px;opacity:0';
  document.body.appendChild(ta); ta.select(); ta.setSelectionRange(0, txt.length); document.execCommand('copy'); ta.remove();
}

async function menuHilo(id, anchor) {
  const h = S.hilos.find(x => x.id === id) || S.hilo;
  menuFlot(anchor, [
    { t: h.fijado ? 'Quitar de fijados' : 'Fijar', f: () => cambiarHilo(id, { fijado: !h.fijado }) },
    { t: 'Cambiar nombre', f: () => renombrar(id) },
    { t: 'Mover a proyecto…', f: () => moverProyecto(id) },
    { t: 'Copiar toda la conversación', f: async () => {
      const hh = (S.hilo?.id === id ? S.hilo : await api('/api/hilos/' + id).catch(() => S.hilo));
      const txt = (hh?.mensajes || []).map(m => (m.rol === 'ia' ? 'Sony' : (S.ajustes?.nombre || 'el usuario')) + ':\n' + (m.texto || m.error || '')).join('\n\n');
      await copiarTexto(txt); toast('Conversación copiada'); } },
    '-',
    { t: 'Borrar', rojo: true, f: () => borrarHilo(id) },
  ]);
}
async function cambiarHilo(id, cambios) {
  const d = S.hilo?.id === id ? S.hilo : await api('/api/hilos/' + id);
  Object.assign(d, cambios); await guardar(d);
}
function renombrar(id) {
  const h = S.hilos.find(x => x.id === id) || S.hilo;
  modal(`<h3>Cambiar nombre</h3><div class="campo"><input id="mNom" value="${esc(h?.titulo || '')}"></div><div class="fila-btn"><button class="btn" data-cerrar>Cancelar</button><button class="btn btn-accent" id="mOk">Guardar</button></div>`);
  $('#mNom').focus(); $('#mNom').select();
  const ok = () => { cambiarHilo(id, { titulo: $('#mNom').value.trim() || 'Chat nuevo' }); cerrarModal(); };
  $('#mOk').onclick = ok; $('#mNom').onkeydown = e => e.key === 'Enter' && ok();
}
function moverProyecto(id) {
  modal(`<h3>Mover a proyecto</h3><div class="campo"><select id="mProy"><option value="">Sin proyecto</option>${S.proyectos.map(p => `<option value="${p.id}">${esc(p.nombre)}</option>`).join('')}</select></div><div class="fila-btn"><button class="btn" data-cerrar>Cancelar</button><button class="btn btn-accent" id="mOk">Mover</button></div>`);
  $('#mOk').onclick = () => { cambiarHilo(id, { proyecto: $('#mProy').value || null }); cerrarModal(); };
}
async function borrarHilo(id) {
  await api('/api/hilos/' + id, { method: 'DELETE' });
  S.hilos = S.hilos.filter(h => h.id !== id);
  if (S.hilo?.id === id) nuevoChat(); else pintarLateral();
  toast('Chat movido a la papelera');
}

/* ---------------- Mac (18/11): borrar la conversación y activar la voz, con botón o diciéndolo ---------------- */
const BORRAR_CONV = /^\W*((por favor\W+)?(borra|limpia|olvida|elimina)(r|me)?\W+(toda\W+)?(la|esta|esa|nuestra)?\W*(conversaci[oó]n|charla|chat)|empe(ce|za)mos de (nuevo|cero)|empieza de (nuevo|cero)|vamos a empezar de (nuevo|cero)|borr[oó]n y cuenta nueva)\W*$/i;
const CAMBIAR_VOZ = /^\W*(pon(me)?|cambia(me)?( a)?|usa)\W+(la\W+)?(voz (de|del)\W+)?(mujer|femenina|hombre|masculina|otro hombre|la (primera|segunda|de siempre))\W*$|^\W*(pon|usa|cambia a)\W+(la\W+)?voz (de|del)\W+(mujer|hombre|otro hombre)\W*$/i;
const ACTIVAR_VOZ = /^\W*((a[ñn]ade|activa|pon|enciende|act[ií]vame|ponme)\W+(la|tu)?\W*voz|(activa|pon|entra en)\W+(el\W+)?modo voz|quiero hablar contigo)\W*$/i;
async function borrarConversacion() {
  const h = S.hilo; const habia = h && h.mensajes && h.mensajes.length;
  if (habia && S.hilos.find(x => x.id === h.id)) { try { await borrarHilo(h.id); } catch { nuevoChat(); } } else nuevoChat();
  toast(habia ? 'Conversación borrada: empezamos de cero (está en la papelera por si acaso)' : 'Ya estabas en una conversación nueva');
  if (Voz.activo) Voz.leer('Listo, conversación nueva.');
}
function frasesEspeciales(texto) {
  if (texto.length > 70) return false;
  if (BORRAR_CONV.test(texto)) { borrarConversacion(); return true; }
  if (ACTIVAR_VOZ.test(texto) && !Voz.activo) { Voz.iniciar(); return true; }
  const cv = texto.match(CAMBIAR_VOZ);
  if (cv) {
    const n = /mujer|femenina/i.test(cv[0]) ? 'Sharvard mujer (España)' : /otro hombre|segunda|sharvard/i.test(cv[0]) ? 'Sharvard hombre (España)' : 'Davefx (España)';
    guardarAj({ voz: { ...(S.ajustes.voz || {}), nombre: n } }).then(() => Voz.leer('Vale, ahora hablo con esta voz.'));
    toast('Voz cambiada: ' + n); return true;
  }
  return false;
}

/* ---------------- hilos ---------------- */
function nuevoChat(proyecto = null) {
  if (S.generando) pararGeneracion();
  S.hilo = hiloNuevo(proyecto); S.adjuntos = []; pintarAdj();
  mostrarVista('chat'); pintarHilo(); pintarLateral(); $('#entrada').focus();
}
async function abrirHilo(id) {
  if (S.generando) pararGeneracion();
  try { S.hilo = await api('/api/hilos/' + id); } catch { return nuevoChat(); }
  localSet('ultimoHilo', id); mostrarVista('chat'); pintarHilo(); pintarLateral();
}
let guardando = null;
async function guardar(h = S.hilo) {
  if (!h.mensajes.length && h === S.hilo) return;
  await api('/api/hilos/' + h.id, { method: 'POST', body: h });
  const i = S.hilos.findIndex(x => x.id === h.id);
  const resumen = { id: h.id, titulo: h.titulo, proyecto: h.proyecto, fijado: h.fijado, actualizado: Date.now() / 1000 };
  if (i >= 0) S.hilos[i] = resumen; else S.hilos.unshift(resumen);
  S.hilos.sort((a, b) => b.actualizado - a.actualizado);
  localSet('ultimoHilo', h.id); pintarLateral(); pintarTitulo();
}
function pintarTitulo() {
  const p = S.proyectos.find(p => p.id === S.hilo?.proyecto);
  $('#tituloHilo').innerHTML = S.hilo?.mensajes.length ? (p ? `<span style="color:var(--muted)">${esc(p.nombre)} / </span>` : '') + esc(S.hilo.titulo || 'Chat nuevo') : (p ? `<span style="color:var(--muted)">${esc(p.nombre)}</span>` : '');
}
$('#tituloHilo').ondblclick = () => S.hilo?.mensajes.length && renombrar(S.hilo.id);
$('#btnMenuHilo').onclick = e => S.hilo?.mensajes.length ? menuHilo(S.hilo.id, e.currentTarget) : menuFlot(e.currentTarget, [{ t: 'Exportar todos los chats (.zip)', f: () => location.href = '/api/exportar' }]);

function pintarHilo() {
  const h = S.hilo; $('#app').classList.toggle('con-msgs', h.mensajes.length > 0);
  const fij = h.mensajes.map((m, i) => [m, i]).filter(([m]) => m.fijado);
  const franja = fij.length ? `<div id="franjaFijados"><b>📌 Fijados</b> ${fij.map(([m, i]) => `<button class="chip-fijado" data-ir="${i}" title="Ir al mensaje">${esc((m.texto || '').replace(/\s+/g, ' ').slice(0, 60))}${(m.texto || '').length > 60 ? '…' : ''}</button>`).join('')}</div>` : '';
  $('#mensajes').innerHTML = franja + h.mensajes.map((m, i) => htmlMensaje(m, i)).join('');
  $$('#franjaFijados [data-ir]').forEach(b => b.onclick = () => $(`.msg[data-i="${b.dataset.ir}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  pintarTitulo(); abajo(true);
  if (S.derTab !== 'artefacto' && !$('#der').classList.contains('hidden')) pintarDer();
}
function htmlMensaje(m, i) {
  if (m.rol === 'user') {
    const adj = (m.adjuntos || []).map(a => a.tipo === 'imagen' ? `<img src="/api/adjuntos/${a.id}" alt="">` : `<div class="chip"><span class="tipo">${esc(ext(a.nombre))}</span><span class="nom">${esc(a.nombre)}</span></div>`).join('');
    return `<div class="msg user${m.fijado ? ' fijado' : ''}" data-i="${i}">${adj ? `<div class="adjs">${adj}</div>` : ''}<div class="burbuja">${esc(m.texto)}</div>
      <div class="acciones"><button class="icon-btn" data-acc="copiar" title="Copiar">${ICO.copiar}</button><button class="icon-btn" data-acc="editar" title="Editar">${ICO.editar}</button><button class="icon-btn ${m.fijado ? 'on' : ''}" data-acc="fijar" title="${m.fijado ? 'Quitar de fijados' : 'Fijar (Sony lo tendrá siempre presente)'}">${ICO.pin}</button></div></div>`;
  }
  const pasos = (m.pasos || []).map(p => htmlPaso(p, i)).join('');
  const cuerpo = pasos + (m.error ? `<p class="err">${esc(m.error)}</p>` : (m.texto ? md(m.texto, i) : (pasos ? '' : '<div class="pensando cursor">Pensando</div>')));
  return `<div class="msg ia" data-i="${i}"><div class="ia-body ${m.vivo ? 'cursor-final' : ''}">${cuerpo}</div>
    ${m.cerebro?.length ? `<div class="cerebro-usado">🧠 usé: ${m.cerebro.map(n => `<a href="/api/cerebro/nota?ruta=${encodeURIComponent(n.ruta)}" target="_blank" title="${esc(n.ruta)}">${esc(n.titulo || n.ruta)}</a>`).join(' · ')}</div>` : ''}
    ${m.vivo ? '' : `<div class="acciones"><button class="icon-btn" data-acc="copiar" title="Copiar">${ICO.copiar}</button><button class="icon-btn" data-acc="oir" title="Escuchar">${ICO.oir}</button><button class="icon-btn ${m.fijado ? 'on' : ''}" data-acc="fijar" title="${m.fijado ? 'Quitar de fijados' : 'Fijar (Sony lo tendrá siempre presente)'}">${ICO.pin}</button>
    <button class="icon-btn ${m.voto === 1 ? 'on' : ''}" data-acc="bien" title="Buena respuesta">${ICO.up}</button><button class="icon-btn ${m.voto === -1 ? 'on' : ''}" data-acc="mal" title="Mala respuesta">${ICO.down}</button>
    <button class="icon-btn" data-acc="regen" title="Regenerar">${ICO.regen}</button></div>`}</div>`;
}
const ext = n => (n.split('.').pop() || '').slice(0, 4);
function abajo(forzar) { const s = $('#scroll'); if (forzar || s.scrollHeight - s.scrollTop - s.clientHeight < 140) s.scrollTop = s.scrollHeight; }

$('#mensajes').addEventListener('click', async e => {
  const b = e.target.closest('[data-acc]'); if (!b) return codeClick(e);
  const i = +b.closest('.msg').dataset.i, m = S.hilo.mensajes[i];
  const acc = b.dataset.acc;
  if (acc === 'copiar') { await copiarTexto(m.texto || m.error || ''); toast('Copiado'); }
  if (acc === 'fijar') { m.fijado = !m.fijado; await guardar(); pintarHilo(); toast(m.fijado ? '📌 Fijado: Sony lo tendrá siempre presente y nunca se recorta' : 'Quitado de fijados'); }
  if (acc === 'bien' || acc === 'mal') { const v = acc === 'bien' ? 1 : -1; m.voto = m.voto === v ? 0 : v; pintarHilo(); guardar(); }
  if (acc === 'regen') { if (S.generando) return; S.hilo.mensajes.splice(i); pintarHilo(); responder(); }
  if (acc === 'oir') Voz.leer(m.texto);
  if (acc === 'editar') editarMensaje(i);
});
function editarMensaje(i) {
  if (S.generando) return;
  const nodo = $(`.msg[data-i="${i}"] .burbuja`), m = S.hilo.mensajes[i];
  nodo.outerHTML = `<div class="burbuja" style="width:85%"><textarea id="edTxt" style="width:100%;min-height:80px;border:0;background:transparent;font:inherit;color:inherit;resize:vertical;outline:0">${esc(m.texto)}</textarea>
    <div class="fila-btn"><button class="btn" id="edNo">Cancelar</button><button class="btn btn-accent" id="edSi">Enviar</button></div></div>`;
  $('#edTxt').focus();
  $('#edNo').onclick = pintarHilo;
  $('#edSi').onclick = () => { m.texto = $('#edTxt').value; S.hilo.mensajes.splice(i + 1); pintarHilo(); guardar(); responder(); };
}

/* ---------------- markdown ---------------- */
function md(src, idx) {
  src = src.replace(/<think>[\s\S]*?(<\/think>|$)/g, '');
  const bloques = []; let n = 0;
  src = src.replace(/```([\w-]*)[^\n]*\n([\s\S]*?)(```|$)/g, (_, lang, code) => { bloques.push([lang.toLowerCase(), code.replace(/\n$/, '')]); return `\u0000B${n++}\u0000`; });
  let h = esc(src);
  h = h.replace(/^(#{1,3}) (.+)$/gm, (_, s, t) => `<h${s.length}>${t}</h${s.length}>`)
    .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/(^|\n)((?:\|.*\|\n?)+)/g, (_, pre, t) => pre + tabla(t))
    .replace(/(^|\n)((?:[ \t]*(?:[-*]|\d+\.) .+(?:\n|$))+)/g, (_, pre, l) => pre + lista(l));
  h = h.replace(/`([^`\n]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  h = h.split(/\n{2,}/).map(p => /^\s*(<h\d|<ul|<ol|<table|<blockquote|\u0000B)/.test(p) ? p : `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
  return h.replace(/\u0000B(\d+)\u0000/g, (_, k) => bloque(bloques[k], idx, k));
}
function lista(t) {
  const ord = /^\s*\d+\./.test(t);
  const items = t.trim().split('\n').map(l => `<li>${l.replace(/^\s*(?:[-*]|\d+\.) /, '')}</li>`).join('');
  return ord ? `<ol>${items}</ol>` : `<ul>${items}</ul>`;
}
function tabla(t) {
  const filas = t.trim().split('\n').filter(f => !/^\|[\s:|-]+\|$/.test(f));
  return '<table>' + filas.map((f, i) => '<tr>' + f.replace(/^\||\|$/g, '').split('|').map(c => i ? `<td>${c.trim()}</td>` : `<th>${c.trim()}</th>`).join('') + '</tr>').join('') + '</table>';
}
function bloque([lang, code], idx, k) {
  if (lang === 'progreso') { try { const d = JSON.parse(code); return `<div class="tarjeta"><h4>${esc(d.titulo || 'Progreso')}</h4>${(d.pasos || []).map(p => `<div class="paso ${esc(p.estado)}"><span class="p">${p.estado === 'hecho' ? '✓' : ''}</span><span>${esc(p.texto)}</span></div>`).join('')}</div>`; } catch { return '<div class="tarjeta pensando cursor">Preparando pasos</div>'; } }
  if (lang === 'decision') { try { const d = JSON.parse(code); const elegida = S.hilo.mensajes[idx]?.eleccion; return `<div class="tarjeta"><h4>${esc(d.pregunta)}</h4><div class="opciones">${(d.opciones || []).map(o => `<button data-elegir="${esc(o)}" data-msg="${idx}" class="${elegida === o ? 'elegida' : ''}" ${elegida ? 'disabled' : ''}>${esc(o)}</button>`).join('')}</div></div>`; } catch { return '<div class="tarjeta pensando cursor">Preparando opciones</div>'; } }
  const ver = lang === 'html' || lang === 'svg' ? `<button data-ver="${idx}:${k}">▶ Ver</button>` : '';
  return `<div class="code"><div class="code-h">${esc(lang || 'código')}<span class="sp"></span>${ver}<button data-copiar="${idx}:${k}">Copiar</button></div><pre><code>${esc(code)}</code></pre></div>`;
}
function codigoDe(ref) {
  const [i, k] = ref.split(':').map(Number); const bl = []; S.hilo.mensajes[i].texto.replace(/```([\w-]*)[^\n]*\n([\s\S]*?)(```|$)/g, (_, l, c) => bl.push([l.toLowerCase(), c]));
  return bl[k];
}
async function codeClick(e) {
  const c = e.target.closest('[data-copiar]'), v = e.target.closest('[data-ver]'), el = e.target.closest('[data-elegir]');
  if (c) { await navigator.clipboard.writeText(codigoDe(c.dataset.copiar)[1]); toast('Código copiado'); }
  if (v) { const [lang, code] = codigoDe(v.dataset.ver); abrirArtefacto({ lang, code, titulo: (S.hilo.titulo || 'Artefacto') }); }
  if (el && !S.generando) { S.hilo.mensajes[+el.dataset.msg].eleccion = el.dataset.elegir; if (/pesado/i.test(el.dataset.elegir) && /^S[ií]/.test(el.dataset.elegir)) { ponerModelo('pesado'); toast('Cambiado al modelo Pesado: se carga ahora (descarga el anterior)'); pintarHilo(); guardar(); enviar('Continúa con la tarea anterior.'); return; } enviar(el.dataset.elegir); }
  const pm = e.target.closest('[data-permiso]'); if (pm) responderPermiso(pm.dataset.permiso, pm.dataset.dec, +pm.dataset.msg);
  const pp = e.target.closest('[data-pend]'), pn = e.target.closest('[data-pend-no]');
  if (pp || pn) { const m = S.hilo.mensajes[+(pp || pn).dataset.msg], p = m.pasos.find(x => x.id === (pp || pn).dataset[pp ? 'pend' : 'pendNo']);
    if (pn) { p.estado = 'denegado'; p.resumen = 'Descartado por ti'; pintarHilo(); guardar(); return; }
    await api('/api/agente/aprobar_pendiente', { method: 'POST', body: { herramienta: p.herramienta } });
    p.estado = 'hecho'; p.resumen = 'Permitido: se hace ahora'; ponerModelo('agente'); pintarHilo(); guardar();
    enviar(`Tienes mi permiso para esta acción que quedó pendiente: ${p.titulo}\n${p.detalle || ''}\nHazla ahora y termina la tarea.`); }
}

/* ---------------- artefactos y panel derecho ---------------- */
function abrirArtefacto(a) { S.artefacto = a; S.derTab = 'artefacto'; abrirDer(); }
function abrirDer() { $('#der').classList.remove('hidden'); pintarDer(); }
$('#btnPanelDer').onclick = () => $('#der').classList.contains('hidden') ? abrirDer() : $('#der').classList.add('hidden');
$('#btnCerrarDer').onclick = () => $('#der').classList.add('hidden');
$('#derTabs').onclick = e => { const b = e.target.closest('button'); if (b) { S.derTab = b.dataset.tab; pintarDer(); } };
async function pintarDer() {
  $$('#derTabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === S.derTab));
  const body = $('#derBody');
  if (S.derTab === 'artefacto') {
    if (!S.artefacto) { body.innerHTML = '<div class="lista-arch vacio">Cuando una respuesta traiga HTML o SVG, pulsa «▶ Ver» y aparecerá aquí, funcionando y aislado.</div>'; return; }
    const a = S.artefacto;
    const csp = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:">`;
    const doc = a.lang === 'svg' ? `<!doctype html><html><head>${csp}</head><body style="margin:0;display:grid;place-items:center;min-height:100vh">${a.code}</body></html>` : (a.code.includes('<head>') ? a.code.replace('<head>', '<head>' + csp) : csp + a.code);
    body.innerHTML = `<div class="art-bar"><span class="t">${esc(a.titulo)} · ${a.lang.toUpperCase()}</span><button class="btn small" id="artCop">Copiar</button><button class="btn small" id="artDes">Descargar</button></div><iframe sandbox="allow-scripts" referrerpolicy="no-referrer"></iframe>`;
    body.querySelector('iframe').srcdoc = doc;
    $('#artCop').onclick = () => navigator.clipboard.writeText(a.code).then(() => toast('Copiado'));
    $('#artDes').onclick = () => { const u = URL.createObjectURL(new Blob([a.code], { type: 'text/plain' })); const l = document.createElement('a'); l.href = u; l.download = 'artefacto.' + a.lang; l.click(); URL.revokeObjectURL(u); };
  } else if (S.derTab === 'archivos') {
    const arch = S.hilo.mensajes.flatMap(m => m.adjuntos || []);
    body.innerHTML = `<div class="lista-arch">${arch.length ? arch.map(filaArch).join('') : '<div class="vacio">Este chat no tiene archivos.</div>'}</div>`;
  } else {
    const bib = await api('/api/biblioteca');
    body.innerHTML = `<div class="lista-arch">${bib.length ? bib.map(filaArch).join('') : '<div class="vacio">Aún no has subido archivos.</div>'}</div>`;
  }
}
const filaArch = a => `<a class="fila-arch" href="/api/adjuntos/${a.id}" target="_blank" style="text-decoration:none;color:inherit"><span class="tipo">${esc(ext(a.nombre))}</span><span class="n">${esc(a.nombre)}</span><small>${(a.bytes / 1e6).toFixed(1)} MB</small></a>`;
(() => {
  const h = $('#derResize'); let x0, w0;
  h.onmousedown = e => { x0 = e.clientX; w0 = $('#der').offsetWidth; document.onmousemove = ev => { const w = Math.max(320, Math.min(innerWidth * 0.7, w0 + x0 - ev.clientX)); $('#der').style.width = w + 'px'; }; document.onmouseup = () => { document.onmousemove = null; localSet('anchoDer', $('#der').offsetWidth); }; e.preventDefault(); };
})();

/* ---------------- adjuntos ---------------- */
$('#btnAdj').onclick = () => $('#fileIn').click();
$('#fileIn').onchange = () => { subirArchivos([...$('#fileIn').files]); $('#fileIn').value = ''; };
async function subirArchivos(files) {
  for (const f of files) {
    if (f.size > 500 * 1024 * 1024) { toast(`${f.name}: máximo 500 MB`); continue; }
    const tmp = { id: 'sub' + nuevoId(), nombre: f.name, subiendo: true, local: f.type.startsWith('image/') ? URL.createObjectURL(f) : null };
    S.adjuntos.push(tmp); pintarAdj();
    try {
      const meta = await api('/api/adjuntos', { method: 'POST', body: f, headers: { 'Content-Type': 'application/octet-stream', 'X-Nombre': encodeURIComponent(f.name) } });
      Object.assign(tmp, meta, { subiendo: false });
    } catch (e) { S.adjuntos = S.adjuntos.filter(a => a !== tmp); toast('No se pudo subir ' + f.name); }
    pintarAdj();
  }
}
function pintarAdj() {
  $('#adjPrev').innerHTML = S.adjuntos.map((a, i) => `<div class="chip">${a.local ? `<img src="${a.local}">` : `<span class="tipo">${esc(ext(a.nombre))}</span>`}<span class="nom">${esc(a.nombre)}${a.subiendo ? ' · subiendo…' : ''}</span><button data-quitar="${i}" title="Quitar">✕</button></div>`).join('');
}
$('#adjPrev').onclick = e => { const b = e.target.closest('[data-quitar]'); if (b) { S.adjuntos.splice(+b.dataset.quitar, 1); pintarAdj(); } };
let dragN = 0;
addEventListener('dragenter', e => { if (e.dataTransfer?.types.includes('Files')) { dragN++; $('#drop').classList.remove('hidden'); } });
addEventListener('dragleave', () => { if (--dragN <= 0) { dragN = 0; $('#drop').classList.add('hidden'); } });
addEventListener('dragover', e => e.preventDefault());
addEventListener('drop', e => { e.preventDefault(); dragN = 0; $('#drop').classList.add('hidden'); if (e.dataTransfer.files.length) subirArchivos([...e.dataTransfer.files]); });
addEventListener('paste', e => { const f = [...(e.clipboardData?.files || [])]; if (f.length) subirArchivos(f); });

/* ---------------- enviar y responder ---------------- */
const entrada = $('#entrada');
entrada.addEventListener('input', () => { entrada.style.height = 'auto'; entrada.style.height = entrada.scrollHeight + 'px'; slash(); });
entrada.addEventListener('keydown', e => {
  const menu = $('#slashMenu');
  if (!menu.classList.contains('hidden')) {
    const bs = $$('#slashMenu button'); let i = bs.findIndex(b => b.classList.contains('sel'));
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); bs[i]?.classList.remove('sel'); i = (i + (e.key === 'ArrowDown' ? 1 : -1) + bs.length) % bs.length; bs[i].classList.add('sel'); return; }
    if ((e.key === 'Enter' || e.key === 'Tab') && i >= 0) { e.preventDefault(); bs[i].click(); return; }
  }
  // Intro envía (también en el iPhone); Mayús+Intro = salto de línea. Nunca a mitad de una composición (dictado, autocorrector, acentos).
  S.mayus = e.shiftKey;
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.keyCode !== 229) { e.preventDefault(); enviar(); }
});
// 15/11: red de seguridad para el iPhone (teclado predictivo), el dictado de Windows y los IME: allí la tecla llega como
// «composición» (keyCode 229) y el keydown no envía. El salto de línea sí llega aquí como insertLineBreak/insertParagraph.
entrada.addEventListener('beforeinput', e => {
  if ((e.inputType === 'insertLineBreak' || e.inputType === 'insertParagraph') && !S.mayus) { e.preventDefault(); setTimeout(() => enviar(), 0); }
});
entrada.addEventListener('keyup', e => { if (e.key === 'Shift') S.mayus = false; });
$('#btnEnviar').onclick = () => S.generando ? pararGeneracion() : enviar();

// 15/11: la caja nunca se bloquea. Si Sony está respondiendo, el mensaje se pone EN COLA y se envía solo al terminar
// (si hay varios seguidos, se juntan en un solo turno). El botón ⏹ corta la respuesta.
S.cola = [];
function pintarCola() {
  let c = $('#colaMsgs');
  if (!c) { c = document.createElement('div'); c.id = 'colaMsgs'; $('#composer').prepend(c); }
  c.innerHTML = S.cola.map((x, i) => `<div class="en-cola"><span class="et">en cola</span><span class="tx">${esc(x.texto.slice(0, 120))}${x.texto.length > 120 ? '…' : ''}</span><button class="icon-btn" data-quitar-cola="${i}" title="Quitar de la cola">✕</button></div>`).join('');
  c.querySelectorAll('[data-quitar-cola]').forEach(b => b.onclick = () => { S.cola.splice(+b.dataset.quitarCola, 1); pintarCola(); });
}
function enviarCola() {
  if (S.generando || !S.cola.length) return;
  const juntos = S.cola.splice(0); pintarCola();
  S.adjuntos = juntos.flatMap(x => x.adjuntos || []);
  enviar(juntos.map(x => x.texto).filter(Boolean).join('\n\n'));
}
async function enviar(texto) {
  texto = (texto ?? entrada.value).trim();
  if (S.adjuntos.some(a => a.subiendo)) return toast('Espera a que termine de subir el archivo');
  if (S.generando) {
    if (!texto && !S.adjuntos.length) return;
    S.cola.push({ texto, adjuntos: S.adjuntos.splice(0) }); pintarAdj(); entrada.value = ''; entrada.style.height = 'auto';
    pintarCola(); toast('En cola: se envía en cuanto Sony termine'); return;
  }
  if (!texto && !S.adjuntos.length) return;
  if (texto.startsWith('/') && comando(texto)) { entrada.value = ''; return; }
  if (!S.adjuntos.length && frasesEspeciales(texto)) { entrada.value = ''; entrada.style.height = 'auto'; return; }
  const m = { rol: 'user', texto, t: Date.now() / 1000 };
  if (S.adjuntos.length) m.adjuntos = S.adjuntos.map(({ id, nombre, tipo, bytes }) => ({ id, nombre, tipo, bytes }));
  S.hilo.mensajes.push(m); S.adjuntos = []; pintarAdj();
  entrada.value = ''; entrada.style.height = 'auto';
  if (!S.hilo.titulo) S.hilo.titulo = (await api('/api/chat/titulo', { method: 'POST', body: { texto } })).titulo;
  pintarHilo(); await guardar(); responder();
}

// Mac (18/11): frases habladas que también son acciones (en modo voz la charla normal va sin herramientas)
const ACCION_VOZ = /(^|[^a-záéíóúñ])(pon(me|le)?\b|env[ií]a\w*|m[aá]nda\w*|ap[uú]nta\w*|an[oó]ta\w*|recu[eé]rda\w*|alarma|av[ií]sa\w*|qu[eé] tengo|tengo (algo|alguna|cita|reuni)|ll[aá]ma\w*|escrib[eií]\w*|crea\w*|borra\w*|guarda\w*|abre\w*|programa\w*|reserva\w*|compra\w*|qu[eé] tiempo|noticias|whatsapp|mensaje)/i;
// 15/11: más verbos y objetos que necesitan herramientas (leer, resumir, PDF, Drive, imagen, foto, mira…)
const NIEGA = /no (puedo|tengo (acceso|manos|o[ií]dos|herramienta)|lee|leo|soy capaz)|mi herramienta[^.]{0,60}no|tendr[aá]s que (descargar|copiar|pegar|abrir)|desc[aá]rga(lo|los|las)? (t[uú]|a mano)|solo recibo texto|no tengo forma/i;
const ACCION2 = /enci[eé]nd|ap[aá]g[aáu]|ejecut|\bl[eé]e(me|lo|la|los|las)?\b|\bleer\b|resum|pdf|docx?\b|excel|word\b|powerpoint|\bdrive\b|carpeta|imagen|foto|captura|pantalla|\bmira\b|m[ií]rame|revisa|busca|b[uú]scame|comprueba|consulta|apunta|anota|gu[aá]rda|recuerda|recordatorio|tiempo hace|llover|correo|agenda|calendario|luz|luces|sai\b|github|repo|telegram|nota\b|notas\b|cerebro|chat anterior|ayer|skill/i;
const ACCION = /(^|[^a-záéíóúñ])(enci[eé]nd|encender|ap[aá]g|ejecut|haz(lo)?\b|pon(me|le)? (la|el|las|los)|sube|baja|cambia|luz|luces|l[aá]mpara|govee|tira|mueble|correos?|e-?mails?|gmail|bandeja|sin leer|borrador|env[ií]a|manda|responde a|drive|calendario|agenda|evento|cita|contactos?|github|repo|issue|telegram|publica|archivo|carpeta|fichero|documento|abre|ejecuta|instala|descarga|busca en|mira en|revisa (mi|el|la|los|las)|lista|crea|guarda|escribe en|lee (el|la|mi)|sai|bater[ií]a|recu[eé]rdame|programa|av[ií]same|busca en internet|busca en la web|qu[eé] herramientas)\b/i;
async function responder() {
  const h = S.hilo, r = { rol: 'ia', texto: '', vivo: true, t: Date.now() / 1000 };
  h.mensajes.push(r); pintarHilo();
  const ctl = new AbortController(); S.generando = ctl;
  $('#btnEnviar').classList.add('parar'); $('#btnEnviar').title = 'Parar';
  const autosave = setInterval(() => guardar(h).catch(() => {}), 2000);
  let ultimoDato = Date.now(), porTiempo = false;  // Mac (18/11): vigilante: 4 min sin recibir nada → se para y se avisa
  const vigia = setInterval(() => { if (Date.now() - ultimoDato > 240000) { porTiempo = true; ctl.abort(); } }, 5000);
  let agente = false;  // Mac (18/11): fuera del try, porque se usa también después (antes daba ReferenceError y la cola se quedaba parada)
  try {
    // 15/11/2026: si pides una ACCIÓN (luces, correo, archivos, calendario, GitHub, Telegram, web…), Sony pasa sola al Agente
    // para ese mensaje (con sus herramientas y tarjetas de permiso). La conversación normal sigue en el modelo de chat.
    const ultimo = (h.mensajes[h.mensajes.length - 2]?.texto || '').toLowerCase();
    const seguidaDeAccion = h.mensajes.slice(-5, -2).some(x => x.rol === 'ia' && (x.auto || x.pasos?.length));  // «apágala», «hazlo»… tras una acción
    // 15/11 (examen): con el modelo Diario, el usuario SIEMPRE habla con Sony con sus herramientas (Agente). Es más fiable y además
    // más rápido, porque alternar chat/Agente rompía la caché del prompt. Con Pesado o Nocturno elegidos a mano, solo las acciones.
    // Mac (18/11): en modo voz la charla normal va por el chat (responde en streaming y empieza a hablar en pocos segundos);
    // solo si pides una acción pasa al Agente con sus herramientas y tarjetas de permiso.
    const pideAccion = ACCION.test(ultimo) || ACCION2.test(ultimo) || ACCION_VOZ.test(ultimo) || seguidaDeAccion;
    const autoAgente = S.sesion?.rol !== 'invitada' && S.modelo !== 'agente' && (Voz.activo ? pideAccion : (['rapido', 'auto', 'haiku', 'sonnet'].includes(S.modelo) || pideAccion));
    agente = S.modelo === 'agente' || autoAgente || S.forzarAgente; if (S.forzarAgente) { r.auto = true; r.reintento = true; S.forzarAgente = false; }
    if (autoAgente) r.auto = true;
    const resp = await fetch(agente ? '/api/agente/turno' : '/api/chat/completar', { method: 'POST', signal: ctl.signal, headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hilo: h.id, mensajes: h.mensajes.slice(0, -1).map(({ rol, texto, adjuntos, fijado }) => ({ rol, texto, adjuntos, fijado })), modelo: agente ? 'agente' : S.modelo, base: ['rapido', 'pesado', 'auto', 'haiku', 'sonnet'].includes(S.modelo) ? S.modelo : 'rapido', proyecto: h.proyecto, tono: Voz.tono?.() || null, canal: Voz.activo ? 'voz' : (matchMedia('(max-width: 760px)').matches || navigator.standalone ? 'movil' : null) }) });
    if (!resp.ok) throw new Error((await resp.json().catch(() => ({}))).error || 'Error del servidor');
    const rd = resp.body.getReader(), dec = new TextDecoder(); let buf = '', ultimoPinte = 0;
    for (;;) {
      const { value, done } = await rd.read(); if (done) break; ultimoDato = Date.now();
      buf += dec.decode(value, { stream: true });
      const lineas = buf.split('\n'); buf = lineas.pop();
      for (const l of lineas) {
        if (!l.startsWith('data: ') || l.includes('[DONE]')) continue;
        try { const d = JSON.parse(l.slice(6)); if (d.cerebro) r.cerebro = d.cerebro; else if (agente) eventoAgente(r, d); else r.texto += d.choices?.[0]?.delta?.content || ''; } catch {}
        if (h === S.hilo) Voz.delta(r.texto, false);
      }
      if (performance.now() - ultimoPinte > 60) { ultimoPinte = performance.now(); pintarUltimo(); }
    }
  } catch (e) { if (porTiempo) r.error = 'Sony ha tardado demasiado (4 minutos sin contestar) y lo he parado. Vuelve a enviarlo; si se repite, cierra Sony y ábrela otra vez.'; else if (e.name !== 'AbortError') r.error = (e.message === 'Load failed' || e.message === 'Failed to fetch') ? 'Se cortó la conexión con el PC (¿Tailscale o el PC dormido?). Pulsa reintentar.' : e.message; }
  // 15/11: si el chat normal (que no tiene herramientas) dice que no puede o se lo deja al usuario, se repite en modo Agente.
  if (!agente && !r.error && S.sesion?.rol !== 'invitada' && NIEGA.test(r.texto || '') && !r.reintento) {
    S.reintentoAgente = true;
  }
  // Nunca dejar un mensaje sin respuesta: si no llegó nada, se dice.
  if (!r.texto.trim() && !r.error && !(r.pasos || []).length && (!ctl.signal.aborted || porTiempo)) r.error = 'Sony no ha llegado a responder (el modelo estaba ocupado o se cortó la conexión). Vuelve a enviarlo.';
  clearInterval(autosave); clearInterval(vigia);
  // Barge-in: si el usuario interrumpió en modo voz, en el historial solo queda lo que Sony llegó a decir.
  const corte = Voz.tomarCorte?.();
  if (corte != null) { r.no_dicho = r.texto; r.texto = (corte ? corte + ' …' : '…') + '\n\n_(el usuario me interrumpió aquí)_'; }
  if (h === S.hilo && !ctl.signal.aborted) Voz.delta(r.texto || r.error || '', true);  // Mac: si le cortaste, no repite lo anterior
  delete r.vivo; S.generando = null;
  $('#btnEnviar').classList.remove('parar'); $('#btnEnviar').title = 'Enviar (Enter)';
  if (h === S.hilo) pintarHilo();
  await guardar(h);
  if (document.hidden) { S.sinLeer = true; document.title = '● IA Sony'; if (S.ajustes.avisos_windows && Notification.permission === 'granted') new Notification('IA Sony', { body: 'Respuesta terminada' }); }
  refrescarEstado();
  if (S.reintentoAgente) {  // la respuesta sin herramientas se cambia por la del Agente
    S.reintentoAgente = false; h.mensajes.pop(); pintarHilo(); S.forzarAgente = true; return responder();
  }
  if (S.cola.length) setTimeout(enviarCola, 300);  // lo que escribiste mientras respondía
}
function pintarUltimo() {
  const i = S.hilo.mensajes.length - 1, nodo = $(`.msg[data-i="${i}"] .ia-body`);
  if (nodo) { nodo.innerHTML = S.hilo.mensajes[i].texto ? md(S.hilo.mensajes[i].texto, i) : '<div class="pensando cursor">Cargando el modelo y pensando</div>'; nodo.lastElementChild?.classList.add('cursor'); abajo(); }
}
function pararGeneracion() { S.generando?.abort(); }
document.addEventListener('visibilitychange', () => { if (!document.hidden && S.sinLeer) { S.sinLeer = false; document.title = 'IA Sony'; } });

/* ---------------- agente (Hermes) ---------------- */
const ICO_H = { cerebro_buscar: '🧠', web_leer: '📰', drive_buscar: '🗂️', drive_leer: '📄', doc_crear: '📝', sheets_leer: '📊', calendario_ver: '📅', calendario_crear: '📅', contactos_buscar: '👤', github_repos: '🐙', github_leer: '🐙', github_issues: '🐙', github_crear_issue: '🐙', github_comentar: '💬', correo_buscar: '📬', correo_leer: '✉️', correo_borrador: '📝', correo_enviar: '📤', correo_mover: '📦', notas_buscar: '🔎', notas_leer: '📖', nota_escribir: '📝', nota_borrar: '🗑️', archivos_listar: '📁', archivo_leer: '📄', archivo_escribir: '💾', archivo_borrar: '🗑️', ver_pantalla: '🖥️', ejecutar: '⌨️', abrir: '🚀', web_buscar: '🌐' };
function eventoAgente(r, d) {
  r.pasos = r.pasos || [];
  if (d.tipo === 'texto') r.texto += d.texto;
  else if (d.tipo === 'error') r.error = d.texto;
  else if (d.tipo === 'cerebro') r.cerebro = d.notas;
  else if (d.tipo === 'permiso') { r.pasos.push({ id: d.id, herramienta: d.herramienta, titulo: d.titulo, detalle: d.detalle, estado: 'permiso', siempre: d.siempre !== false }); pintarHilo(); avisarPermiso(); }
  else if (d.tipo === 'paso') {
    const p = r.pasos.find(x => x.id === d.id);
    if (p) Object.assign(p, { estado: d.estado, resumen: d.resumen, imagen: d.imagen || p.imagen }); else r.pasos.push({ ...d });
    pintarHilo();
  }
}
function htmlPaso(p, i) {
  const ico = ICO_H[p.herramienta] || '🔧';
  if (p.estado === 'permiso' && !(S.generando && i === S.hilo.mensajes.length - 1)) { p.estado = 'denegado'; p.resumen = 'Tarjeta caducada (no se hizo nada)'; }
  if (p.estado === 'permiso') return `<div class="tarjeta permiso"><h4>🔐 Sony quiere: ${ico} ${esc(p.titulo)}</h4><pre class="det">${esc(p.detalle || '')}</pre>
    <div class="fila-btn" style="justify-content:flex-start"><button class="btn btn-accent" data-permiso="${p.id}" data-dec="una" data-msg="${i}">Permitir una vez</button>${p.siempre === false ? '' : `<button class="btn" data-permiso="${p.id}" data-dec="siempre" data-msg="${i}">Permitir siempre en este proyecto</button>`}<button class="btn" data-permiso="${p.id}" data-dec="denegar" data-msg="${i}">Denegar</button></div>
    <small style="color:var(--faint)">Si no respondes en 5 minutos, no hará nada.</small></div>`;
  if (p.estado === 'pendiente') return `<div class="tarjeta permiso"><h4>🔐 Pendiente de tu permiso: ${ico} ${esc(p.titulo)}</h4><pre class="det">${esc(p.detalle || '')}</pre>
    <div class="fila-btn" style="justify-content:flex-start"><button class="btn btn-accent" data-pend="${p.id}" data-msg="${i}">Permitir y continuar</button><button class="btn" data-pend-no="${p.id}" data-msg="${i}">Descartar</button></div></div>`;
  const est = { hecho: '✓', en_curso: '…', denegado: '⛔', bloqueado: '🚫 bloqueado', error: '⚠️' }[p.estado] || '';
  return `<details class="paso-ag ${esc(p.estado)}"><summary>${ico} ${esc(p.titulo || p.herramienta)} <span class="st">${est}</span></summary>${p.imagen ? `<img src="/api/agente/captura/${encodeURIComponent(p.imagen)}" alt="captura">` : ''}<pre class="det">${esc(p.resumen || p.detalle || '')}</pre></details>`;
}
async function responderPermiso(id, dec, i) {
  const m = S.hilo.mensajes[i], p = m?.pasos?.find(x => x.id === id);
  try { await api('/api/agente/aprobar', { method: 'POST', body: { id, decision: dec } }); if (p) { p.estado = dec === 'denegar' ? 'denegado' : 'en_curso'; p.resumen = dec === 'denegar' ? 'Denegado por ti' : 'Permitido'; } }
  catch (e) { toast(e.message); if (p) p.estado = 'error'; }
  pintarHilo();
}
function avisarPermiso() { if (document.hidden) document.title = '🔐 IA Sony'; }

/* ---------------- comandos «/» ---------------- */
const COMANDOS = [
  ['/nuevo', 'Chat nuevo', () => nuevoChat()],
  ['/borrar', 'Borrar esta conversación y empezar de cero', () => borrarConversacion()],
  ['/rapido', 'Usar Qwen 27B', () => { S.modelo = 'rapido'; refrescarEstado(); toast('Modelo: Qwen 27B'); }],
  ['/hermes', 'Usar el agente Hermes', () => { S.modelo = 'agente'; $('#nombreModelo').textContent = 'Agente'; toast('Agente Hermes activado'); }],
  ['/pesado', 'Usar el modelo Pesado (el más listo, más lento)', () => { ponerModelo('pesado'); toast('Modelo: Pesado'); }],
  ['/buscar', 'Buscar en los chats', () => abrirBuscar()],
  ['/programados', 'Tareas programadas', () => mostrarVista('programados')],
  ['/recuerda', 'Guardar algo en la memoria', t => recordar(t)],
  ['/voz', 'Modo voz manos libres', () => Voz.iniciar()],
  ['/liberar', 'Liberar la memoria (descargar el Qwen local)', () => liberarAhora()],
  ['/ajustes', 'Abrir ajustes', () => abrirAjustes()],
  ['/exportar', 'Exportar los chats (.zip)', () => location.href = '/api/exportar'],
  ['/ayuda', 'Ver comandos y atajos', () => ayuda()],
];
function slash() {
  const v = entrada.value, menu = $('#slashMenu');
  if (!v.startsWith('/') || v.includes(' ')) return menu.classList.add('hidden');
  const f = COMANDOS.filter(c => c[0].startsWith(v.toLowerCase()));
  if (!f.length) return menu.classList.add('hidden');
  menu.innerHTML = f.map((c, i) => `<button data-c="${c[0]}" class="${i ? '' : 'sel'}">${c[0]}<small>${c[1]}</small></button>`).join('');
  menu.classList.remove('hidden');
  menu.onclick = e => { const b = e.target.closest('button'); if (!b) return; menu.classList.add('hidden'); if (b.dataset.c === '/recuerda') { entrada.value = '/recuerda '; entrada.focus(); } else { entrada.value = ''; COMANDOS.find(c => c[0] === b.dataset.c)[2](''); } };
}
function comando(t) {
  const [c, ...resto] = t.split(' '); const cmd = COMANDOS.find(x => x[0] === c.toLowerCase());
  if (!cmd) return false; $('#slashMenu').classList.add('hidden'); cmd[2](resto.join(' ')); return true;
}
async function recordar(t) {
  if (!t.trim()) return toast('Escribe: /recuerda lo que quieras guardar');
  S.ajustes = await api('/api/ajustes', { method: 'POST', body: { memoria: [...(S.ajustes.memoria || []), t.trim()] } });
  toast('Guardado en la memoria');
}
function ayuda() {
  modal(`<h3>Comandos y atajos</h3>${COMANDOS.map(c => `<div class="aj-fila"><code>${c[0]}</code><span class="d">${c[1]}</span></div>`).join('')}
    <div class="aj-fila"><code>Ctrl+K</code><span class="d">Buscar</span></div><div class="aj-fila"><code>Ctrl+Shift+O</code><span class="d">Chat nuevo</span></div>
    <div class="aj-fila"><code>Ctrl+B</code><span class="d">Mostrar u ocultar la barra lateral</span></div><div class="aj-fila"><code>Esc</code><span class="d">Cerrar</span></div>
    <div class="fila-btn"><button class="btn" data-cerrar>Cerrar</button></div>`);
}

/* ---------------- selector de modelo y herramientas ---------------- */
$('#btnSelModelo').onclick = e => menuFlot(e.currentTarget, [
  ...S.modelos.map(m => ({ t: `${m.id === S.modelo ? '✓ ' : ''}${m.reserva ? '⏸ ' : ''}${m.nombre} — ${m.desc}${m.disponible ? '' : (['haiku', 'sonnet'].includes(m.id) ? ' (falta la clave en Ajustes → Modelo)' : ' (sin descargar)')}`, f: () => (m.reserva && !confirm('DeepSeek está en reserva. ¿Cargarlo a mano igualmente?')) ? null : ponerModelo(m.id) })),
  { t: `Agente (Hermes) — usa herramientas con tu permiso`, f: () => ponerModelo('agente') },
  '-',
  { t: `${S.ajustes.razonamiento ? '✓ ' : ''}Razonamiento ampliado`, f: async () => { S.ajustes = await api('/api/ajustes', { method: 'POST', body: { razonamiento: !S.ajustes.razonamiento } }); toast(S.ajustes.razonamiento ? 'Razonamiento activado' : 'Razonamiento desactivado'); } },
]);
$('#btnHerr').onclick = e => menuFlot(e.currentTarget, [
  { t: 'Adjuntar archivos', f: () => $('#fileIn').click() },
  { t: 'Usar instrucciones del proyecto…', f: () => moverProyectoActual() },
  { t: 'Buscar en el segundo cerebro (Sony ya lo consulta sola en cada mensaje)', f: () => { entrada.value = 'Busca en mi segundo cerebro: '; entrada.focus(); } },
  { t: 'Búsqueda web (SearXNG privado, con tarjeta)', f: () => { entrada.value = 'Busca en internet: '; entrada.focus(); } },
  { t: 'Crear una imagen (FLUX, con tarjeta)', f: () => { entrada.value = 'Crea una imagen de '; entrada.focus(); } },
]);
function moverProyectoActual() { if (S.hilo.mensajes.length) return moverProyecto(S.hilo.id); modal(`<h3>Proyecto para este chat</h3><div class="campo"><select id="mProy"><option value="">Sin proyecto</option>${S.proyectos.map(p => `<option value="${p.id}">${esc(p.nombre)}</option>`).join('')}</select></div><div class="fila-btn"><button class="btn" data-cerrar>Cancelar</button><button class="btn btn-accent" id="mOk">Usar</button></div>`); $('#mOk').onclick = () => { S.hilo.proyecto = $('#mProy').value || null; pintarTitulo(); cerrarModal(); }; }
$('#btnVoz').onclick = () => Voz.iniciar();  // Mac: Whisper + Piper locales
function ponerModelo(m) {
  S.modelo = m;
  $('#btnAgente')?.classList.toggle('on', m === 'agente');
  if (m === 'agente') $('#nombreModelo').textContent = 'Agente';
  refrescarEstado();
}
$('#btnAgente').onclick = () => { ponerModelo(S.modelo === 'agente' ? 'rapido' : 'agente'); toast(S.modelo === 'agente' ? 'Agente Hermes activado: puede usar herramientas con tu permiso' : 'Modo conversación (Qwen 27B)'); };

/* ---------------- vistas: proyectos, programados, artefactos ---------------- */
$$('.nav-item[data-vista]').forEach(b => b.onclick = () => mostrarVista(b.dataset.vista));
$('#btnNuevo').onclick = () => nuevoChat();
$('#btnBorrarConv').onclick = () => borrarConversacion();
function mostrarVista(v, extra) {
  S.vista = v; $('#vistaChat').classList.toggle('hidden', v !== 'chat'); $('#vistaLista').classList.toggle('hidden', v === 'chat');
  pintarLateral();
  if (v === 'chat') return pintarTitulo();
  $('#tituloHilo').textContent = '';
  const L = $('#vistaLista');
  if (v === 'proyectos') {
    L.innerHTML = `<div class="lista-wrap"><div class="lista-head"><h2 class="serif">Proyectos</h2><button class="btn btn-accent" id="nuevoProy">+ Nuevo proyecto</button></div>
      ${S.proyectos.length ? `<div class="grid-proy">${S.proyectos.map(p => `<div class="card-proy" data-proy="${p.id}"><h3>${esc(p.nombre)}</h3><p>${esc(p.descripcion || '')}</p><p style="margin-top:10px;color:var(--faint)">${S.hilos.filter(h => h.proyecto === p.id).length} chats</p></div>`).join('')}</div>`
      : '<div class="vacio-grande"><h3>Aún no hay proyectos</h3><p>Agrupa chats y dales instrucciones propias que la IA respetará.</p></div>'}</div>`;
    $('#nuevoProy').onclick = () => editarProyecto();
    L.onclick = e => { const c = e.target.closest('[data-proy]'); if (c) mostrarVista('proyecto', c.dataset.proy); };
  }
  if (v === 'proyecto') {
    const p = S.proyectos.find(x => x.id === extra); const hs = S.hilos.filter(h => h.proyecto === extra);
    L.innerHTML = `<div class="lista-wrap"><div class="lista-head"><h2 class="serif">${esc(p.nombre)}</h2><button class="btn" id="edProy">Ajustes del proyecto</button><button class="btn btn-accent" id="chatProy">+ Chat nuevo</button></div>
      <p style="color:var(--muted)">${esc(p.descripcion || '')}</p>${p.instrucciones ? `<div class="tarjeta"><h4>Instrucciones</h4><div style="white-space:pre-wrap;color:var(--muted)">${esc(p.instrucciones)}</div></div>` : ''}
      ${hs.length ? hs.map(h => `<div class="hilo-item" data-id="${h.id}"><span>${esc(h.titulo || 'Chat nuevo')}</span></div>`).join('') : '<div class="vacio-grande"><h3>Sin chats todavía</h3></div>'}</div>`;
    $('#edProy').onclick = () => editarProyecto(p); $('#chatProy').onclick = () => nuevoChat(p.id); L.onclick = null;
    if (p.carpeta && S.correctorActivo) {  // Corrector Claude (API) y Claude Code: apagado mientras no se active
      const bar = document.createElement('div'); bar.className = 'fila-btn'; bar.style.margin = '10px 0';
      bar.innerHTML = '<button class="btn" id="corrClaude">🔧 Corregir con Claude</button> <button class="btn" id="abrirCC">Abrir en Claude Code</button> <small style="color:var(--muted)">' + esc(p.carpeta) + '</small>';
      L.querySelector('.lista-head').after(bar);
      $('#corrClaude').onclick = async e => { e.target.disabled = true; e.target.textContent = 'Corrigiendo…'; try { const r = await api('/api/corrector/corregir', { method: 'POST', body: { proyecto: p.id } }); alert(r.texto); } catch (er) { toast(er.message); } e.target.disabled = false; e.target.textContent = '🔧 Corregir con Claude'; };
      $('#abrirCC').onclick = () => api('/api/corrector/abrir_claude_code', { method: 'POST', body: { proyecto: p.id } }).then(() => toast('Abriendo Claude Code en la carpeta del proyecto')).catch(er => toast(er.message));
    }
  }
  if (v === 'programados') {
    const cuando = t => t.cada_min ? `cada ${t.cada_min} min` : t.repeticion === 'una' ? `una vez · ${esc(t.fecha || '')} ${esc(t.hora || '')}` : t.repeticion === 'laborables' ? `días laborables · ${esc(t.hora)}` : t.repeticion === 'semanal' ? `${esc((t.dias || []).join(', '))} · ${esc(t.hora)}` : `cada día · ${esc(t.hora || '')}`;
    const tipo = t => t.tipo === 'citas' ? '📅 sin IA' : t.tipo === 'correos' ? '✉️ sin IA' : '🤖 con Sony (Qwen 27B)';
    const fecha = s => s ? new Date(s * 1000).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : 'nunca';
    L.innerHTML = `<div class="lista-wrap"><div class="lista-head"><h2 class="serif">Programados</h2><button class="btn btn-accent" id="nuevaTarea">+ Nueva tarea</button></div>
      <p style="color:var(--muted);font-size:13.5px">Solo funcionan mientras la app (o su servidor) está encendida. Nada arranca con el Mac. Las tareas con Sony usan Qwen 27B y esperan si la gráfica está ocupada; lo que necesite permiso queda pendiente en su chat.</p>
      ${S.programados.length ? S.programados.map((t, i) => `<div class="tarjeta"><h4>${esc(t.nombre)} <span class="estado ${t.pausada ? '' : 'listo'}">${t.pausada ? 'En pausa' : 'Activa'}</span> <span class="estado">${tipo(t)}</span></h4>
        <div style="color:var(--muted)">${cuando(t)} · última: ${fecha(t.ultima)}${t.ultimo_resultado ? ' · ' + esc(t.ultimo_resultado) : ''}</div><p>${esc(t.prompt || '')}</p>
        <div class="fila-btn" style="justify-content:flex-start"><button class="btn small" data-t="ahora" data-i="${i}">▶ Ejecutar ahora</button><button class="btn small" data-t="editar" data-i="${i}">Editar</button><button class="btn small" data-t="pausar" data-i="${i}">${t.pausada ? 'Reanudar' : 'Pausar'}</button><button class="btn small" data-t="borrar" data-i="${i}">Borrar</button></div></div>`).join('')
      : '<div class="vacio-grande"><h3>No hay tareas programadas</h3><p>Crea una para que Sony haga algo a una hora y deje el resultado en un chat nuevo.</p></div>'}</div>`;
    $('#nuevaTarea').onclick = () => editarTarea();
    L.onclick = async e => {
      const b = e.target.closest('[data-t]'); if (!b) return; const i = +b.dataset.i, t = S.programados[i];
      if (b.dataset.t === 'ahora') { await api('/api/programados/ejecutar', { method: 'POST', body: { id: t.id } }); toast('Ejecutando «' + t.nombre + '»…'); setTimeout(async () => { S.programados = await api('/api/programados'); if (S.vista === 'programados') mostrarVista('programados'); }, 4000); return; }
      if (b.dataset.t === 'editar') return editarTarea(t);
      if (b.dataset.t === 'borrar') { if (!confirm('¿Borrar la tarea «' + t.nombre + '»?')) return; S.programados.splice(i, 1); }
      else t.pausada = !t.pausada;
      await api('/api/programados', { method: 'POST', body: S.programados }); mostrarVista('programados');
    };
  }
  if (v === 'artefactos') {
    L.innerHTML = '<div class="lista-wrap"><div class="lista-head"><h2 class="serif">Artefactos</h2></div><div id="listaArt" class="vacio">Buscando…</div></div>';
    listarArtefactos();
  }
}
async function listarArtefactos() {
  const out = [];
  for (const h of S.hilos.slice(0, 80)) {
    const d = await api('/api/hilos/' + h.id).catch(() => null); if (!d) continue;
    d.mensajes.forEach((m, i) => { if (m.rol === 'ia') m.texto.replace(/```(html|svg)[^\n]*\n([\s\S]*?)```/gi, (_, l, c) => out.push({ hilo: d, lang: l.toLowerCase(), code: c, i })); });
  }
  $('#listaArt').outerHTML = out.length ? `<div class="grid-proy">${out.map((a, k) => `<div class="card-proy" data-art="${k}"><h3>${esc(a.hilo.titulo || 'Chat')}</h3><p>${a.lang.toUpperCase()} · ${a.code.length} caracteres</p></div>`).join('')}</div>`
    : '<div class="vacio-grande"><h3>Aún no hay artefactos</h3><p>Aparecerán aquí las páginas y gráficos (HTML/SVG) que cree la IA.</p></div>';
  $('#vistaLista').onclick = e => { const c = e.target.closest('[data-art]'); if (c) { const a = out[+c.dataset.art]; abrirArtefacto({ lang: a.lang, code: a.code, titulo: a.hilo.titulo }); } };
}
function editarProyecto(p) {
  modal(`<h3>${p ? 'Ajustes del proyecto' : 'Nuevo proyecto'}</h3>
    <div class="campo"><label>Nombre</label><input id="pNom" value="${esc(p?.nombre || '')}"></div>
    <div class="campo"><label>Descripción</label><input id="pDesc" value="${esc(p?.descripcion || '')}"></div>
    <div class="campo"><label>Instrucciones (la IA las respetará en todos los chats del proyecto)</label><textarea id="pIns">${esc(p?.instrucciones || '')}</textarea></div>
    <div class="fila-btn">${p ? '<button class="btn" id="pBorrar" style="margin-right:auto;color:var(--bad)">Borrar proyecto</button>' : ''}<button class="btn" data-cerrar>Cancelar</button><button class="btn btn-accent" id="pOk">Guardar</button></div>`);
  $('#pNom').focus();
  $('#pOk').onclick = async () => {
    const d = { ...(p || {}), id: p?.id || nuevoId(), nombre: $('#pNom').value.trim() || 'Proyecto', descripcion: $('#pDesc').value.trim(), instrucciones: $('#pIns').value.trim() };
    S.proyectos = p ? S.proyectos.map(x => x.id === p.id ? d : x) : [...S.proyectos, d];
    await api('/api/proyectos', { method: 'POST', body: S.proyectos }); cerrarModal(); mostrarVista(p ? 'proyecto' : 'proyectos', d.id);
  };
  if (p) $('#pBorrar').onclick = async () => { S.proyectos = S.proyectos.filter(x => x.id !== p.id); await api('/api/proyectos', { method: 'POST', body: S.proyectos }); cerrarModal(); mostrarVista('proyectos'); };
}
function editarTarea(t) {
  const dias = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom'], sis = t && t.tipo && t.tipo !== 'ia';
  const rep = t ? (t.cada_min ? 'intervalo' : t.repeticion || (t.dias ? 'semanal' : 'diaria')) : 'diaria';
  modal(`<h3>${t ? 'Editar tarea' : 'Nueva tarea programada'}</h3>
    <div class="campo"><label>Nombre</label><input id="tNom" value="${esc(t?.nombre || '')}"></div>
    ${sis ? `<p style="color:var(--muted);font-size:13px">${esc(t.prompt)}</p>` : `<div class="campo"><label>Qué tiene que hacer Sony</label><textarea id="tPrompt">${esc(t?.prompt || '')}</textarea></div>`}
    <div class="campo"><label>Repetición</label><select id="tRep">
      <option value="una">Una vez</option><option value="diaria">Cada día</option><option value="laborables">Días laborables</option><option value="semanal">Algunos días de la semana</option><option value="intervalo">Cada X minutos</option></select></div>
    <div class="campo" id="cFecha"><label>Fecha</label><input id="tFecha" type="date" value="${esc(t?.fecha || new Date().toISOString().slice(0, 10))}"></div>
    <div class="campo" id="cHora"><label>Hora</label><input id="tHora" type="time" value="${esc(t?.hora || '09:00')}"></div>
    <div class="campo" id="cDias"><label>Días</label><div>${dias.map(d => `<label style="margin-right:10px"><input type="checkbox" value="${d}" ${!t || (t.dias || dias).includes(d) ? 'checked' : ''}> ${d}</label>`).join('')}</div></div>
    <div class="campo" id="cMin"><label>Cada cuántos minutos</label><input id="tMin" type="number" min="1" value="${t?.cada_min || 15}"></div>
    ${t?.tipo === 'citas' ? `<div class="campo"><label>Avisar cuántos minutos antes</label><input id="tAviso" type="number" min="5" value="${t.aviso_min || 30}"></div>` : ''}
    <div class="fila-btn"><button class="btn" data-cerrar>Cancelar</button><button class="btn btn-accent" id="tOk">${t ? 'Guardar' : 'Crear'}</button></div>`);
  const ver = () => { const r = $('#tRep').value; $('#cFecha').classList.toggle('hidden', r !== 'una'); $('#cHora').classList.toggle('hidden', r === 'intervalo'); $('#cDias').classList.toggle('hidden', r !== 'semanal'); $('#cMin').classList.toggle('hidden', r !== 'intervalo'); };
  $('#tRep').value = rep; $('#tRep').onchange = ver; ver();
  $('#tOk').onclick = async () => {
    const r = $('#tRep').value;
    const d = { ...(t || { id: nuevoId(), tipo: 'ia', creada: Date.now() / 1000, pausada: false }), nombre: $('#tNom').value.trim() || 'Tarea', repeticion: r === 'intervalo' ? undefined : r };
    if (!sis) d.prompt = $('#tPrompt').value.trim();
    if (r === 'intervalo') d.cada_min = Math.max(1, +$('#tMin').value); else { delete d.cada_min; d.hora = $('#tHora').value; }
    if (r === 'una') d.fecha = $('#tFecha').value; if (r === 'semanal') d.dias = $$('#cDias input:checked').map(c => c.value);
    if ($('#tAviso')) d.aviso_min = +$('#tAviso').value;
    if (!t) d.creada = Date.now() / 1000; else if (r !== 'intervalo') d.ultima = Math.max(d.ultima || 0, Date.now() / 1000 - 60);
    S.programados = t ? S.programados.map(x => x.id === t.id ? d : x) : [...S.programados, d];
    await api('/api/programados', { method: 'POST', body: S.programados }); cerrarModal(); mostrarVista('programados');
  };
}

/* ---------------- búsqueda ---------------- */
$('#btnBuscar').onclick = () => abrirBuscar();
function abrirBuscar() {
  modal(`<div class="campo" style="margin:0 0 10px"><input id="bq" placeholder="Buscar en tus chats…"></div><div id="bres"></div>`);
  const q = $('#bq'); q.focus(); let t;
  const pinta = r => $('#bres').innerHTML = r.map((x, i) => `<div class="res-busq ${i ? '' : 'sel'}" data-id="${x.id}">${esc(x.titulo || 'Chat')}<small>${esc(x.fragmento || '')}</small></div>`).join('') || '<div class="vacio">Sin resultados</div>';
  pinta(S.hilos.slice(0, 8).map(h => ({ id: h.id, titulo: h.titulo })));
  q.oninput = () => { clearTimeout(t); t = setTimeout(async () => pinta(q.value.trim() ? await api('/api/buscar?q=' + encodeURIComponent(q.value)) : S.hilos.slice(0, 8)), 150); };
  q.onkeydown = e => { if (e.key === 'Enter') $('#bres .res-busq.sel')?.click(); };
  $('#bres').onclick = e => { const r = e.target.closest('[data-id]'); if (r) { cerrarModal(); abrirHilo(r.dataset.id); } };
}

/* ---------------- ajustes ---------------- */
$('#btnUser').onclick = () => abrirAjustes();
let SECCIONES = ['General', 'Modelo', 'Instrucciones', 'Memoria', 'Voz', 'Skills', 'Conectores', 'Permisos', 'Datos'];  // Mac: «Móvil» se añadirá cuando se instale
function abrirAjustes(sec = 'General') {
  modal(`<div class="aj-nav"><h3 class="serif">Ajustes</h3>${SECCIONES.map(s => `<button data-sec="${s}" class="${s === sec ? 'on' : ''}">${s}</button>`).join('')}</div><div class="aj-body" id="ajBody"></div>`, true);
  $('.aj-nav').onclick = e => { const b = e.target.closest('[data-sec]'); if (b) { $$('.aj-nav button').forEach(x => x.classList.toggle('on', x === b)); seccion(b.dataset.sec); } };
  seccion(sec);
}
const sw = (k, v) => `<button class="switch ${v ? 'on' : ''}" data-sw="${k}"></button>`;
async function guardarAj(c) { S.ajustes = await api('/api/ajustes', { method: 'POST', body: c }); aplicarAjustes(); }
async function seccion(s) {
  const a = S.ajustes, B = $('#ajBody');
  const fila = (t, d, ctrl) => `<div class="aj-fila"><div><div>${t}</div>${d ? `<div class="d">${d}</div>` : ''}</div>${ctrl}</div>`;
  if (s === 'General') B.innerHTML = `<h4>General</h4>
    ${fila('Tu nombre', 'Así te saluda la IA', `<input id="ajNom" class="btn" style="cursor:text" value="${esc(a.nombre)}">`)}
    ${fila('Tema', '', `<select id="ajTema" class="btn"><option value="auto">Automático</option><option value="sombra">Sombra (negro y carmesí, el de Sony)</option><option value="light">Claro (crema)</option><option value="dark">Oscuro (gris cálido)</option><option value="nebulosa">Nebulosa (azul y violeta)</option><option value="contraste">Alto contraste</option><option value="bosque">Bosque (verde claro)</option><option value="atardecer">Atardecer (cálido oscuro)</option><option value="oceano">Océano (azul claro)</option></select>`)}
    ${fila('Tamaño de letra', '', `<select id="ajLetra" class="btn"><option value="normal">Normal</option><option value="grande">Grande</option></select>`)}
    ${fila('Avisos del Mac', 'Aviso cuando termina una respuesta y la ventana no está delante', sw('avisos_windows', a.avisos_windows))}`;
  if (s === 'Modelo') B.innerHTML = `<h4>Modelo</h4>
    ${fila('Modelo por defecto', '', `<select id="ajModelo" class="btn">${S.modelos.filter(m => !m.reserva).map(m => `<option value="${m.id}">${m.nombre}</option>`).join('')}</select>`)}
    ${fila('Creatividad', 'Temperatura: más baja = más preciso', `<input id="ajTemp" type="range" min="0" max="1.5" step="0.1" value="${a.temperatura}">`)}
    ${fila('Longitud máxima', 'Tokens por respuesta', `<select id="ajMax" class="btn"><option>1024</option><option>2048</option><option>4096</option><option>8192</option></select>`)}
    ${fila('Razonamiento ampliado', 'Piensa antes de responder (más lento)', sw('razonamiento', a.razonamiento))}
    ${fila('Liberar la memoria', 'Descargar el Qwen local tras estos minutos sin uso (0 = nunca)', `<input id="ajDesc" type="number" min="0" class="btn" style="width:80px" value="${a.descargar_tras_min}">`)}
    <div id="claudeAj" class="vacio">Cargando Claude (API)…</div>`;
  if (s === 'Modelo') setTimeout(() => { const c = $('#ajModoCpu'); if (c) c.onchange = e => api('/api/gpu/modo', { method: 'POST', body: { modo_cpu: e.target.checked } }).then(r => { S.ajustes.modo_cpu = r.modo_cpu; S.ajustes.pausa_gpu = r.modo_cpu; toast(r.modo_cpu ? 'Modo CPU activado' : 'Modo gráfica activado'); }).catch(er => toast(er.message)); }, 0);
  if (s === 'Modelo') api('/api/claude/config').then(c => {
    const el = $('#claudeAj'); if (!el) return;
    el.className = '';
    el.innerHTML = `<h4 style="font-size:17px;margin-top:22px">Claude (API)</h4><p class="d" style="color:var(--muted)">Haiku y Sonnet salen en el selector de modelo del chat, junto al Qwen local. Cada mensaje se envía a Anthropic y se paga por uso. El modelo local sigue siendo gratis y privado.</p>
      ${fila('Clave de la API', c.clave ? 'Guardada en el Llavero de macOS.' : 'Pégala aquí: se guarda en el Llavero y no se vuelve a mostrar.', c.clave ? '<button class="btn" id="clBorrar">Quitar clave</button>' : '<span><input id="clClave" type="password" autocomplete="off" class="btn" style="width:230px;cursor:text" placeholder="sk-ant-…"> <button class="btn btn-accent" id="clGuardar">Guardar</button></span>')}
      ${fila('Tope mensual', `Gastado este mes: ${c.gasto_usd.toFixed(2)} $ en ${c.llamadas} llamadas (estimación local; la cifra real está en la consola de Anthropic). Al llegar al tope, Sony se para.`, `<span><input id="clTope" type="number" min="0" step="5" class="btn" style="width:80px;cursor:text" value="${c.tope_usd}"> $</span>`)}`;
    const guardar = async (body, msg) => { try { await api('/api/claude/config', { method: 'POST', body }); toast(msg); } catch (e) { toast(e.message); } await refrescarEstado(); seccion('Modelo'); };
    on('#clGuardar', 'onclick', () => guardar({ clave: $('#clClave').value }, 'Clave guardada en el Llavero'));
    on('#clBorrar', 'onclick', () => guardar({ borrar_clave: true }, 'Clave eliminada'));
    on('#clTope', 'onchange', e => guardar({ tope_usd: +e.target.value }, 'Tope guardado'));
  }).catch(() => { const el = $('#claudeAj'); if (el) el.textContent = 'No se pudo leer la configuración de Claude.'; });
  if (s === 'Instrucciones') B.innerHTML = `<h4>Instrucciones personales</h4><p class="d" style="color:var(--muted)">La IA las tendrá en cuenta en todos los chats.</p>
    <div class="campo"><textarea id="ajIns" style="min-height:220px">${esc(a.instrucciones)}</textarea></div><div class="fila-btn"><button class="btn btn-accent" id="ajInsOk">Guardar</button></div>`;
  if (s === 'Memoria') B.innerHTML = `<h4>Memoria</h4><p style="color:var(--muted)">Datos que la IA tiene presentes siempre. Los decides tú (también con <code>/recuerda</code>).</p>
    <div id="memLista">${(a.memoria || []).map((m, i) => `<div class="mem-item"><span>${esc(m)}</span><button class="icon-btn" data-borrar-mem="${i}">✕</button></div>`).join('') || '<div class="vacio">Vacía</div>'}</div>
    <div class="campo" style="margin-top:12px"><input id="memNuevo" placeholder="Añadir un dato y pulsar Enter"></div>
    <div id="cerebroFila">${fila('Segundo cerebro', '~/segundo-cerebro · comprobando…', '<span class="estado">…</span>')}</div>
    <h4 style="font-size:17px;margin-top:22px">Diario de los últimos 7 días</h4><p style="color:var(--muted);margin:0 0 8px">Resúmenes de tus chats que Sony lleva siempre en la cabeza. Se hacen solos cuando un chat lleva 5 minutos parado y el modelo ya está cargado y libre (nunca carga un modelo para esto). Los chats de la invitada no entran.</p>
    <div id="diarioLista" class="vacio">Cargando…</div>`;
  if (s === 'Memoria') {
    const pintarDiario = () => api('/api/diario').then(D => {
      if (!$('#diarioLista')) return;
      $('#diarioLista').className = '';
      $('#diarioLista').innerHTML = (D.resumenes.map(r => fila(`${new Date(r.fecha_t * 1000).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' })} · ${esc(r.titulo)}`,
        esc([r.tema, r.decisiones && 'Decidido: ' + r.decisiones, r.pendientes && 'Pendiente: ' + r.pendientes].filter(Boolean).join(' · ')),
        `<button class="btn small" data-borrar-res="${esc(r.id)}">Borrar</button>`)).join('') || '<div class="vacio">Todavía no hay resúmenes.</div>')
        + (D.en_cola ? `<p style="color:var(--muted)">${D.en_cola} chat(s) en cola: se resumirán cuando el modelo esté cargado y libre.</p>` : '');
      $$('[data-borrar-res]').forEach(b => b.onclick = async () => { await api('/api/diario/borrar', { method: 'POST', body: { id: b.dataset.borrarRes } }); toast('Resumen borrado'); pintarDiario(); });
    }).catch(() => { if ($('#diarioLista')) $('#diarioLista').textContent = 'No se pudo cargar el diario.'; });
    pintarDiario();
  }
  if (s === 'Memoria') api('/api/cerebro/estado').then(e => {  // estado REAL, leído en vivo
    const ult = new Date(e.ultima * 1000).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
    if ($('#cerebroFila')) $('#cerebroFila').innerHTML = fila('Segundo cerebro', `~/segundo-cerebro · ${e.notas} notas (${e.hoy} cambiadas en las últimas 24 h) · última ${ult} · índice ${e.al_dia ? 'al día' : 'actualizándose'}. Sony lo consulta sola en cada mensaje.`, `<span class="estado listo">activo</span>`);
  }).catch(() => { if ($('#cerebroFila')) $('#cerebroFila').innerHTML = fila('Segundo cerebro', 'No se pudo comprobar ahora', '<span class="estado">error</span>'); });
  if (s === 'Skills') {  // 15/11: lista real de ~/IA/sony/skills, buscador, activar/desactivar y «Modo automático»
    B.innerHTML = '<h4>Skills</h4><div class="vacio">Cargando…</div>';
    const K = await api('/api/skills');
    const pintar = (q = '') => {
      const f = K.skills.filter(x => !q || (x.nombre + ' ' + x.desc + ' ' + x.categoria).toLowerCase().includes(q.toLowerCase()));
      const cats = [...new Set(f.map(x => x.categoria))];
      $('#skLista').innerHTML = cats.map(c => `<h4 style="font-size:15px;margin:18px 0 6px">${esc(c)}</h4>` + f.filter(x => x.categoria === c).map(x =>
        fila(`${esc(x.nombre)} <span class="estado ${x.prueba === 'probada' ? 'listo' : ''}" style="margin-left:6px">${esc(x.prueba)}</span>`, esc(x.desc),
          `<button class="btn small" data-skver="${esc(x.nombre)}">Ver</button> <label><input type="checkbox" data-skact="${esc(x.nombre)}" ${x.activa ? 'checked' : ''}> activa</label>`)).join('')).join('') || '<div class="vacio">Ninguna coincide.</div>';
      $('#skLista').querySelectorAll('[data-skact]').forEach(i => i.onchange = async () => { await api('/api/skills/config', { method: 'POST', body: { nombre: i.dataset.skact, activa: i.checked } }); K.skills.find(x => x.nombre === i.dataset.skact).activa = i.checked; $('#skCuenta').textContent = `${K.skills.filter(x => x.activa).length} activas de ${K.total}`; toast(i.checked ? 'Skill activada' : 'Skill desactivada: Sony ya no la ve'); });
      $('#skLista').querySelectorAll('[data-skver]').forEach(b => b.onclick = () => window.open('/api/skills/ver?nombre=' + encodeURIComponent(b.dataset.skver), '_blank'));
    };
    B.innerHTML = `<h4>Skills</h4><p style="color:var(--muted)">Guías paso a paso que Sony puede seguir (en ~/IA/sony/skills). <b id="skCuenta">${K.activas} activas de ${K.total}</b>.</p>
      ${fila('Modo automático', 'Encendido: Sony elige y lee sola la skill que encaje. Apagado: solo usa una skill cuando tú se lo pides.', `<label><input type="checkbox" id="skAuto" ${K.auto ? 'checked' : ''}> <span id="skAutoTxt">${K.auto ? 'encendido' : 'apagado'}</span></label>`)}
      <input id="skBuscar" class="btn" style="width:100%;margin:10px 0;text-align:left" placeholder="Buscar skill (marketing, código, ventas…)"><div id="skLista"></div>`;
    $('#skAuto').onchange = async e => { await api('/api/skills/config', { method: 'POST', body: { auto: e.target.checked } }); $('#skAutoTxt').textContent = e.target.checked ? 'encendido' : 'apagado'; toast(e.target.checked ? 'Modo automático encendido' : 'Modo automático apagado: Sony usará skills solo si se lo pides'); };
    $('#skBuscar').oninput = e => pintar(e.target.value);
    pintar();
  }
  if (s === 'Conectores') {
    B.innerHTML = '<h4>Conectores <button class="btn small" id="conAhora" style="margin-left:8px">Comprobar ahora</button></h4><p id="conHora" style="color:var(--muted);margin:0 0 8px">Comprobando en vivo…</p><div id="conLista" class="vacio">Comprobando…</div><h4 style="font-size:17px;margin-top:22px">Correo</h4><div id="correoLista" class="vacio">Cargando cuentas…</div>';
    // Estado REAL, comprobado en vivo (solo lectura): al abrir, cada 3 minutos mientras está abierta y con «Comprobar ahora».
    const pintarCon = d => {
      const ico = { ok: '✅', error: '⚠️', sin_configurar: '⏸' }, txt = { ok: 'Conectado', error: 'Error', sin_configurar: 'Sin configurar' };
      if (!$('#conLista')) return;
      $('#conHora').textContent = 'Comprobado a las ' + new Date(d.t * 1000).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }) + ' · se actualiza solo cada 3 minutos';
      $('#conLista').className = ''; $('#conLista').innerHTML = d.conectores.map(x => fila(`${ico[x.estado] || '•'} ${esc(x.nombre)}`, esc(x.detalle), `<span class="estado ${x.estado === 'ok' ? 'listo' : ''}">${txt[x.estado] || esc(x.estado)}</span>`)).join('');
    };
    const cargarCon = forzar => api('/api/conectores/estado' + (forzar ? '?forzar=1' : '')).then(pintarCon).catch(e => { if ($('#conHora')) $('#conHora').textContent = 'No se pudo comprobar: ' + e.message; });
    await cargarCon(true);
    $('#conAhora').onclick = () => { $('#conHora').textContent = 'Comprobando…'; cargarCon(true); };
    clearInterval(S.conTimer); S.conTimer = setInterval(() => { if ($('#conLista')) cargarCon(true); else clearInterval(S.conTimer); }, 180000);
    try {  // Govee (API en la nube, respaldo del control local LAN)
      const G = await api('/api/govee/estado'), gc = document.createElement('div');
      gc.innerHTML = `<h4 style="font-size:17px;margin-top:22px">Govee (luces)</h4><p class="d" style="color:var(--muted)">Las luces con «LAN Control» se manejan en local, sin internet. La clave de la API (Govee Home → Perfil → Ajustes → Apply for API Key) sirve para las demás. Se guarda en el Administrador de credenciales.</p>
        ${fila('Clave de la API', G.clave ? 'Guardada' : 'Pégala aquí (nunca en el chat)', G.clave ? '<button class="btn small" id="gvProbar">Probar</button> <button class="btn small" id="gvBorrar">Quitar</button>' : '<input id="gvK" type="password" class="btn" style="width:220px" placeholder="clave de Govee"> <button class="btn small" id="gvOk">Guardar</button> <button class="btn small" id="gvProbar">Buscar en local</button>')}`;
      B.appendChild(gc);
      const gv = d => api('/api/govee/config', { method: 'POST', body: d });
      $('#gvOk') && ($('#gvOk').onclick = () => gv({ clave: $('#gvK').value }).then(() => seccion('Conectores')).catch(e => toast(e.message)));
      $('#gvBorrar') && ($('#gvBorrar').onclick = () => gv({ borrar: true }).then(() => seccion('Conectores')));
      $('#gvProbar') && ($('#gvProbar').onclick = () => gv({ probar: true }).then(r => alert(r.ok ? `Govee: ${r.total} luces (${r.local} en local)\n\n${r.nombres.join('\n')}` : 'Govee: ' + r.error)));
    } catch {}
    try {  // Cámaras Dahua: usuario y contraseña (Administrador de credenciales) y botón Probar
      const C = await api('/api/camaras/lista'), cc = document.createElement('div');
      cc.innerHTML = `<h4 style="font-size:17px;margin-top:22px">Cámaras (Dahua, ${C.camaras.length})</h4><p class="d" style="color:var(--muted)">Se ven en la pestaña Cámaras (PC y móvil por Tailscale). El vídeo no se recodifica: 0 gráfica. Se guarda en el Llavero de macOS.</p>
        ${fila('Usuario y contraseña', C.credenciales ? 'Guardados' : 'Los de tus cámaras / grabador (normalmente admin)', C.credenciales ? '<button class="btn small" id="camProbar">Probar</button> <button class="btn small" id="camBorrar">Quitar</button>' : '<input id="camU" class="btn" style="width:90px" value="admin"> <input id="camP" type="password" class="btn" style="width:150px" placeholder="contraseña"> <button class="btn small" id="camOk">Guardar</button>')}`;
      B.appendChild(cc);
      const cm = d => api('/api/camaras/config', { method: 'POST', body: d });
      $('#camOk') && ($('#camOk').onclick = () => cm({ usuario: $('#camU').value, contrasena: $('#camP').value }).then(() => seccion('Conectores')).catch(e => toast(e.message)));
      $('#camBorrar') && ($('#camBorrar').onclick = () => cm({ borrar: true }).then(() => seccion('Conectores')));
      $('#camProbar') && ($('#camProbar').onclick = () => cm({ probar: true }).then(r => toast(r.ok ? 'Cámaras: conexión correcta' : 'Cámaras: ' + r.error)));
    } catch {}
    try {  // Claude (API): el Corrector de lo que construye el Pesado
      const K = await api('/api/corrector/estado'), caja = document.createElement('div'); S.correctorActivo = K.activo; if (!K.activo) throw 0;
      caja.innerHTML = `<h4 style="font-size:17px;margin-top:22px">Claude (API) · Corrector</h4><p class="d" style="color:var(--muted)">Claude Opus 5.5 corrige lo que construye el Pesado en la carpeta de cada proyecto (seguridad primero). Un commit aparte por corrección. Los .env y claves nunca salen del PC. No usa la gráfica.</p>
        ${fila('Clave de API', K.clave ? 'Guardada en el Administrador de credenciales' : 'console.anthropic.com → API Keys → Create Key', K.clave ? '<button class="btn small" id="kBorrar">Quitar clave</button>' : '<input id="kVal" type="password" class="btn" style="width:220px" placeholder="sk-ant-…"> <button class="btn small" id="kOk">Guardar</button>')}
        ${fila('Gasto de hoy', `Tope diario (se para al llegar y avisa). Registro: ~/IA/logs/claude-api.jsonl`, `${K.hoy_eur.toFixed(2)} € de <input id="kTope" type="number" min="0" max="20" step="0.5" class="btn" style="width:70px" value="${K.tope_eur_dia}"> €`)}
        ${fila('Corregir solo al acabar el Pesado', '', `<label class="interruptor"><input type="checkbox" id="kAuto" ${K.auto_tras_pesado ? 'checked' : ''}> activado</label>`)}`;
      B.appendChild(caja);
      const kc = d => api('/api/corrector/config', { method: 'POST', body: d }).then(() => seccion('Conectores')).catch(e => toast(e.message));
      $('#kOk') && ($('#kOk').onclick = () => kc({ clave: $('#kVal').value }));
      $('#kBorrar') && ($('#kBorrar').onclick = () => kc({ borrar_clave: true }));
      $('#kTope').onchange = e => kc({ tope_eur_dia: +e.target.value });
      $('#kAuto').onchange = e => kc({ auto_tras_pesado: e.target.checked });
    } catch {}
    const cs = await api('/api/correo/cuentas');
    $('#correoLista').outerHTML = cs.map(x => fila(`<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${esc(x.color)};margin-right:8px"></span>${esc(x.nombre)}`,
      `${esc(x.direccion || 'sin dirección')} · ${esc(x.proveedor_nombre)}`,
      x.conectada ? `<span class="estado listo">conectada</span> <button class="btn small" data-desc="${x.id}">Desconectar</button>` : `<button class="btn btn-accent small" data-con="${x.id}">Conectar</button>`)).join('')
      + '<p style="color:var(--muted);font-size:13px">Las contraseñas se guardan cifradas en el Llavero de macOS. Leer, buscar y hacer borradores es libre; enviar, mover o borrar siempre te pedirá una tarjeta 🔐.</p>';
    B.querySelectorAll('[data-desc]').forEach(b => b.onclick = async () => { await api('/api/correo/desconectar', { method: 'POST', body: { id: b.dataset.desc } }); seccion('Conectores'); });
    B.querySelectorAll('[data-con]').forEach(b => b.onclick = () => conectarCorreo(cs.find(x => x.id === b.dataset.con)));
    const G = await api('/api/google/estado'), GH = await api('/api/github/estado');
    B.insertAdjacentHTML('beforeend', `<h4 style="font-size:17px;margin-top:22px">Google (Drive, Docs, Sheets, Calendar, Gmail, Contactos)</h4>
      ${G.conectado ? G.cuentas.map(x => fila(`🔵 ${esc(x.nombre || 'Google')}`, esc(x.email), `<span class="estado listo">conectada</span> <button class="btn small" data-gquitar="${esc(x.email)}">Quitar</button>`)).join('') + '<div class="fila-btn" style="justify-content:flex-start"><button class="btn btn-accent" id="gCon">➕ Añadir otra cuenta de Google</button></div><p id="gMsg" style="color:var(--muted);font-size:13px">Se abre Google: elige la otra cuenta (por ejemplo la del trabajo) y entra con tu llave de acceso. Si sale «acceso bloqueado», añade ese Gmail como usuario de prueba en Google Cloud → Público.</p>'
        : `<div class="pasos-con">
            <div class="paso-con"><b>1.</b> En Google Cloud → Clientes, abre «Sony escritorio» y pulsa <b>Descargar JSON</b>. <a class="btn small" href="https://console.cloud.google.com/auth/clients" target="_blank" rel="noopener">Abrir Google Cloud</a></div>
            <div class="paso-con"><b>2.</b> <button class="btn ${G.cliente ? '' : 'btn-accent'}" id="gArchivo">📄 Cargar archivo de Google</button> ${G.cliente ? '<span class="estado listo">credencial guardada</span>' : ''}<input type="file" id="gFile" accept=".json,application/json" hidden></div>
            <div class="paso-con"><b>3.</b> <button class="btn ${G.cliente ? 'btn-accent' : ''}" id="gCon" ${G.cliente ? '' : 'disabled'}>🔑 Conectar Google</button> <span class="d">elige tu cuenta y entra con tu llave de acceso (QR con el móvil)</span></div>
            <p id="gMsg" style="color:var(--muted);font-size:13px"></p>
            <details class="manual"><summary>Pegar a mano</summary><div class="campo"><label>ID de cliente</label><input id="gId" autocomplete="off"></div><div class="campo"><label>Secreto de cliente</label><input id="gSec" type="password" autocomplete="new-password"></div><button class="btn small" id="gGuardar">Guardar</button></details>
          </div>`}
      <h4 style="font-size:17px;margin-top:22px">GitHub</h4>
      ${GH.conectado ? fila('GitHub', esc(GH.usuario || ''), '<span class="estado listo">conectado</span> <button class="btn small" id="ghDesc">Desconectar</button>')
        : `<div class="pasos-con">
            <div class="paso-con"><b>1.</b> <a class="btn small" href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">Crear token en GitHub</a> <span class="d">entra con tu llave de acceso (QR)</span></div>
            <div class="campo" style="margin:0"><label><b>2.</b> Pega aquí el token (github_pat_…)</label><input id="ghTok" type="password" autocomplete="new-password"></div>
            <div class="paso-con"><button class="btn btn-accent" id="ghCon">3. Conectar GitHub</button></div>
            <p id="ghMsg" style="color:var(--muted);font-size:13px">${GH.error ? esc(GH.error) : 'Se guarda en el Llavero de macOS y nunca se muestra.'}</p>
          </div>`}`);
    const on = (id, f) => { const el = $(id); if (el) el.onclick = f; };
    const guardarCliente = async datos => {
      try { await api('/api/google/cliente', { method: 'POST', body: datos }); toast('Credencial de Google guardada (en el Llavero de macOS)');
        const r = await api('/api/google/borrar_json', { method: 'POST', body: {} }).catch(() => ({ movidos: [] }));
        if (r.movidos?.length) toast('Archivo de Descargas movido a la papelera'); seccion('Conectores');
      } catch (e) { $('#gMsg').textContent = e.message; }
    };
    on('#gArchivo', () => $('#gFile').click());
    if ($('#gFile')) $('#gFile').onchange = async e => { const f = e.target.files[0]; if (!f) return; try { await guardarCliente(JSON.parse(await f.text())); } catch { $('#gMsg').textContent = 'Ese archivo no es el JSON de Google.'; } e.target.value = ''; };
    on('#gGuardar', () => guardarCliente({ client_id: $('#gId').value, client_secret: $('#gSec').value }));
    on('#gCon', async () => { $('#gMsg').textContent = 'Se ha abierto Google en tu navegador: elige tu cuenta, entra con tu llave de acceso y acepta…'; const r = await api('/api/google/conectar', { method: 'POST', body: {} }); $('#gMsg').textContent = r.mensaje; if (r.ok) { toast(r.mensaje); seccion('Conectores'); } });
    B.querySelectorAll('[data-gquitar]').forEach(b => b.onclick = async () => { await api('/api/google/desconectar', { method: 'POST', body: { email: b.dataset.gquitar } }); seccion('Conectores'); });
    on('#ghDisp', async () => {
      $('#ghMsg').textContent = 'Preparando…'; const d = await api('/api/github/dispositivo', { method: 'POST', body: {} });
      if (!d.codigo) { $('#ghMsg').textContent = d.mensaje || 'No se pudo iniciar.'; return; }
      $('#ghCodigo').classList.remove('hidden'); $('#ghCod').textContent = d.codigo; $('#ghMsg').textContent = 'Se ha abierto github.com/login/device: pega este código y autoriza.';
      const t = setInterval(async () => { const s = await api('/api/github/dispositivo').catch(() => ({})); if (s.estado === 'listo' || s.estado === 'error') { clearInterval(t); toast(s.mensaje); seccion('Conectores'); } }, 2000);
    });
    on('#ghCopiar', () => navigator.clipboard.writeText($('#ghCod').textContent).then(() => toast('Código copiado')));
    on('#ghCon', async () => { try { const r = await api('/api/github/token', { method: 'POST', body: { token: $('#ghTok').value } }); $('#ghTok').value = ''; $('#ghMsg').textContent = r.mensaje; if (r.ok) { toast(r.mensaje); seccion('Conectores'); } } catch (e) { $('#ghMsg').textContent = e.message; } });
    on('#ghDesc', async () => { await api('/api/github/desconectar', { method: 'POST', body: {} }); seccion('Conectores'); });
  }
  if (s === 'Permisos') {
    const P = await api('/api/agente/permisos'); const proy = id => id === '-' ? 'chats sin proyecto' : id === '*' ? 'todo' : (S.proyectos.find(p => p.id === id)?.nombre || id);
    B.innerHTML = `<h4>Permisos del agente (Hermes)</h4><p style="color:var(--muted)">Cuando Hermes quiere hacer algo delicado se para y te muestra una tarjeta 🔐: <b>Permitir una vez</b>, <b>Permitir siempre en este proyecto</b> o <b>Denegar</b>. Sin respuesta en 5 minutos, no hace nada. Todo queda anotado en ~/IA/logs/agente.log.</p>
      <h4 style="font-size:17px;margin-top:18px">Qué puede hacer</h4>
      ${Object.entries(P.herramientas).map(([n, h]) => fila(`${ICO_H[n] || ''} ${esc(h.titulo)}`, '', `<span class="estado ${h.permiso === false ? 'listo' : ''}">${h.permiso === false ? 'libre' : h.permiso === 'carpeta' ? 'libre en tus carpetas' : 'pide permiso'}</span>`)).join('')}
      <h4 style="font-size:17px;margin-top:18px">Permisos «siempre» que has dado</h4>
      <div id="reglas">${P.reglas.length ? P.reglas.map((r, i) => `<div class="mem-item"><span>${ICO_H[r.herramienta] || ''} ${esc(P.herramientas[r.herramienta]?.titulo || r.herramienta)} · <small>${esc(proy(r.proyecto))}${r.carpeta ? ' · solo dentro de ' + esc(r.carpeta) : ''} · ${esc(r.creada || '')}</small></span><button class="btn small" data-quitar-regla="${i}">Quitar</button></div>`).join('') : '<div class="vacio">Ninguno: siempre pregunta.</div>'}</div>
      <h4 style="font-size:17px;margin-top:18px">Carpetas aprobadas</h4><p class="d" style="color:var(--muted)">Aquí puede leer sin preguntar. Escribir o borrar siempre pregunta. ~/IA está prohibida.</p>
      <div>${P.carpetas.map((c, i) => `<div class="mem-item"><span>📁 ${esc(c)}</span><button class="btn small" data-quitar-carpeta="${i}">Quitar</button></div>`).join('')}</div>
      <div class="campo" style="margin-top:8px"><input id="nuevaCarpeta" placeholder="Añadir carpeta (p. ej. ~/Proyecto final) y pulsar Enter"></div>
      <h4 style="font-size:17px;margin-top:18px">Prohibido siempre</h4><p style="color:var(--muted)">Contraseñas, claves y datos de pago · tocar ~/IA/sony, la propia IA o cargar modelos · borrar sin pasar por la papelera · ejecutar como administrador · poner nada en el arranque del Mac · captura de pantalla continua o en segundo plano.</p>`;
    B.querySelectorAll('[data-quitar-regla]').forEach(b => b.onclick = async () => { P.reglas.splice(+b.dataset.quitarRegla, 1); await api('/api/agente/permisos', { method: 'POST', body: { reglas: P.reglas } }); seccion('Permisos'); });
    B.querySelectorAll('[data-quitar-carpeta]').forEach(b => b.onclick = async () => { P.carpetas.splice(+b.dataset.quitarCarpeta, 1); await api('/api/agente/permisos', { method: 'POST', body: { carpetas: P.carpetas } }); seccion('Permisos'); });
    $('#nuevaCarpeta').onkeydown = async e => { if (e.key === 'Enter' && e.target.value.trim()) { await api('/api/agente/permisos', { method: 'POST', body: { carpetas: [...P.carpetas, e.target.value.trim()] } }); seccion('Permisos'); } };
    // Publicar en redes: por defecto siempre con tarjeta; «sin preguntar» lo activa solo el usuario, por red y con límite diario.
    try {
      const RS = await api('/api/redes/estado');
      const caja = document.createElement('div');
      caja.innerHTML = `<h4 style="font-size:17px;margin-top:18px">Publicar en redes</h4><p class="d" style="color:var(--muted)">Solo con la API oficial y en tu propia cuenta. Por defecto cada publicación te pide tarjeta. Si activas «publicar sin preguntar», Sony publica sola hasta el límite diario y todo queda en ~/IA/logs/redes.jsonl. Nada de likes, follows ni mensajes directos.</p>
        ${RS.map(r => fila(`${esc(r.nombre)} <small style="color:var(--muted)">${r.api ? (r.conectada ? '· conectada' : '· sin conectar') : '· solo borradores por ahora'} · hoy ${r.hoy}</small>`, '',
          r.api ? `<span style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><label class="interruptor"><input type="checkbox" data-red-sp="${r.id}" ${r.sin_preguntar ? 'checked' : ''}> publicar sin preguntar</label>
            límite/día <input type="number" min="0" max="10" class="btn" style="width:64px" data-red-lim="${r.id}" value="${r.limite_dia}">
            <input type="password" class="btn" style="width:150px" placeholder="pegar token" data-red-tok="${r.id}">${r.id !== 'x' ? `<input class="btn" style="width:120px" placeholder="${r.id === 'reddit' ? 'tu usuario' : 'id de persona'}" data-red-us="${r.id}">` : ''}
            <button class="btn small" data-red-ok="${r.id}">Guardar token</button>${r.conectada ? `<button class="btn small" data-red-borrar="${r.id}">Desconectar</button>` : ''}</span>` : '<span class="estado">borrador</span>')).join('')}
        <p class="d" style="color:var(--muted)">Cómo conseguir cada token: nota del cerebro «Conectar redes sociales a Sony».</p>`;
      B.appendChild(caja);
      const cfg = (red, d) => api('/api/redes/config', { method: 'POST', body: { red, ...d } }).then(() => toast('Guardado')).catch(e => toast(e.message));
      caja.querySelectorAll('[data-red-sp]').forEach(c => c.onchange = () => cfg(c.dataset.redSp, { sin_preguntar: c.checked }));
      caja.querySelectorAll('[data-red-lim]').forEach(c => c.onchange = () => cfg(c.dataset.redLim, { limite_dia: +c.value }));
      caja.querySelectorAll('[data-red-ok]').forEach(b => b.onclick = async () => { const red = b.dataset.redOk; try { await api('/api/redes/token', { method: 'POST', body: { red, token: caja.querySelector(`[data-red-tok="${red}"]`).value, usuario: caja.querySelector(`[data-red-us="${red}"]`)?.value || '' } }); toast('Token guardado en el Administrador de credenciales'); seccion('Permisos'); } catch (e) { toast(e.message); } });
      caja.querySelectorAll('[data-red-borrar]').forEach(b => b.onclick = async () => { await api('/api/redes/token', { method: 'POST', body: { red: b.dataset.redBorrar, borrar: true } }); seccion('Permisos'); });
    } catch {}
  }
  if (s === 'Voz') {
    B.innerHTML = `<h4>Voz</h4>${fila('Modo voz manos libres', 'Botón de onda junto al selector de modelo, o /voz', '<span class="estado listo">listo</span>')}
      ${fila('Micrófono', 'Habla y mira la barra: si se mueve, te oye', '<div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end"><select id="ajMic" class="btn" style="max-width:320px"><option>Buscando micrófonos…</option></select><span class="nivel grande"><i id="ajNivel"></i></span></div>')}
      ${fila('Voz por defecto', 'Voces de tu cuenta de ElevenLabs (Flash v2.5)', '<select id="ajVoz" class="btn"><option>Cargando…</option></select>')}
      ${fila('Voz de Qwen 27B (conversación)', '', '<select class="btn sel-vm" data-vm="rapido"></select>')}${fila('Voz del Agente (Hermes)', '', '<select class="btn sel-vm" data-vm="agente"></select>')}${fila('Voz del modelo Pesado', '', '<select class="btn sel-vm" data-vm="pesado"></select>')}
      ${fila('Probar', '', '<button class="btn" id="ajProbar">▶ Escuchar</button>')}
      ${fila('Pausa de fin de frase', 'Milisegundos de silencio para enviar lo que dices', `<input id="ajPausa" type="number" min="300" max="3000" step="100" class="btn" style="width:90px" value="${a.voz?.pausa_ms || 900}">`)}
      ${fila('Sensibilidad para interrumpir', 'Alta: te oye antes (puede saltar con ruido). Baja: hace falta hablar más claro. Detector de voz Silero en el procesador (0 VRAM).', `<select id="ajSens" class="btn">${['alta', 'media', 'baja'].map(x => `<option ${(a.voz?.sensibilidad || 'media') === x ? 'selected' : ''}>${x}</option>`).join('')}</select>`)}
      ${fila('Escuchar siempre', 'Al abrir Sony, el micrófono se queda escuchando sin pulsar nada. El audio no se graba ni se guarda: solo se convierte a texto en este Mac.', `<label class="interruptor"><input type="checkbox" id="ajSiempre" ${a.voz?.siempre === false ? '' : 'checked'}> activado</label>`)}
      ${fila('Tono personal contigo', 'Solo en modo voz y solo contigo. Voz femenina: simpática y algo coqueta. Voz masculina: amigo de confianza, con bromas ligeras. Con clientes, WhatsApp e invitada: siempre amable y profesional. Si estás serio o con prisa, va al grano.', `<label class="interruptor"><input type="checkbox" id="ajTono" ${a.voz?.tono_personal === false ? '' : 'checked'}> activado</label>`)}
      ${fila('Oído', 'Whisper turbo en este Mac (local, con filtro de ruido)', '<span class="estado listo">local</span>')}`;
    $('#ajSens').onchange = e => guardarAj({ voz: { ...(S.ajustes.voz || {}), sensibilidad: e.target.value } });
    $('#ajSiempre').onchange = e => guardarAj({ voz: { ...(S.ajustes.voz || {}), siempre: e.target.checked } });
    $('#ajTono').onchange = e => guardarAj({ voz: { ...(S.ajustes.voz || {}), tono_personal: e.target.checked } });
    try {
      const vs = await api('/api/voz/voces'); const actual = a.voz?.nombre || 'Mayordomo IA';
      vs.sort((x, y) => (y.nombre === 'Mayordomo IA') - (x.nombre === 'Mayordomo IA') || x.nombre.localeCompare(y.nombre));
      $('#ajVoz').innerHTML = vs.map(v => `<option ${v.nombre === actual ? 'selected' : ''}>${esc(v.nombre)}</option>`).join('');
      const pm = S.ajustes.voz?.por_modelo || {};
      B.querySelectorAll('.sel-vm').forEach(s => { s.innerHTML = '<option value="">(la de por defecto)</option>' + vs.map(v => `<option ${pm[s.dataset.vm] === v.nombre ? 'selected' : ''}>${esc(v.nombre)}</option>`).join('');
        s.onchange = async () => { const p = { ...(S.ajustes.voz?.por_modelo || {}) }; if (s.value) p[s.dataset.vm] = s.value; else delete p[s.dataset.vm]; await guardarAj({ voz: { ...(S.ajustes.voz || {}), por_modelo: p } }); const ant = S.modelo; S.modelo = s.dataset.vm; Voz.leer('Hola el usuario, esta será mi voz en este modo.'); S.modelo = ant; }; });
    } catch (e) { $('#ajVoz').innerHTML = `<option>${esc(e.message)}</option>`; }
    $('#ajVoz').onchange = e => guardarAj({ voz: { ...(S.ajustes.voz || {}), nombre: e.target.value } });
    $('#ajPausa').onchange = e => guardarAj({ voz: { ...(S.ajustes.voz || {}), pausa_ms: +e.target.value } });
    $('#ajProbar').onclick = () => Voz.leer('Hola el usuario. Esta es la voz que usaré para hablarte.');
    try {
      const ms = await Voz.micros(); const pref = S.ajustes.voz?.microfono || (ms.find(d => /obsbot|webcam|cam/i.test(d.label)) || ms[0])?.label;
      $('#ajMic').innerHTML = ms.map(d => `<option ${d.label === pref ? 'selected' : ''}>${esc(d.label)}</option>`).join('');
      const medir = async () => { window._paraMic?.(); window._paraMic = await Voz.probarMicro($('#ajMic').value, r => { const n = $('#ajNivel'); if (n) n.style.width = Math.min(100, Math.sqrt(r) * 300) + '%'; else window._paraMic?.(); }); };
      $('#ajMic').onchange = async e => { await guardarAj({ voz: { ...(S.ajustes.voz || {}), microfono: e.target.value } }); medir(); };
      if (!S.ajustes.voz?.microfono && pref) guardarAj({ voz: { ...(S.ajustes.voz || {}), microfono: pref } });
      medir();
    } catch (e) { $('#ajMic').innerHTML = `<option>Sin permiso de micrófono: ${esc(e.message)}</option>`; }
  }
  if (s === 'Móvil') {
    const P = await api('/api/remoto/pines'), T = await api('/api/remoto/tailscale');
    B.innerHTML = `<h4>Acceso desde el móvil (Tailscale)</h4>
      <p style="color:var(--muted)">Abre el chat de Sony desde tu móvil y el de tu familia <b>solo dentro de tu red privada de Tailscale</b>; nada queda abierto a internet. Siempre pide PIN. Tailscale no usa la gráfica.</p>
      ${fila('Tailscale', T.instalado ? (T.direccion ? 'Dirección: ' + esc(T.direccion) : 'Instalado · ' + esc(T.estado || 'parado')) : 'No disponible en el Mac', `<span class="estado ${T.estado === 'Running' ? 'listo' : ''}">${T.instalado ? esc(T.estado || 'parado') : 'pendiente'}</span>`)}
      ${fila('Encender Tailscale al abrir la app', 'Lo enciende al abrir «IA Sony» y lo apaga al salir del todo. Windows pedirá permiso de administrador cada vez.', sw('acceso_movil', P.acceso_movil))}
      <h4 style="font-size:17px;margin-top:18px">PIN</h4>
      ${fila('Tu PIN (perfil el usuario)', P.usuario ? 'Puesto' : 'Sin poner: nadie podrá entrar desde el móvil', '<input id="pinC" type="password" inputmode="numeric" class="btn" style="width:140px" placeholder="6+ números">')}
      ${fila('PIN de invitada', 'Solo chatear con Sony (Qwen 27B). Sin tarjetas, correos, Drive, GitHub, comandos, ajustes ni tus datos. ' + (P.invitada ? 'Puesto.' : 'Sin poner.'), '<input id="pinI" type="password" inputmode="numeric" class="btn" style="width:140px" placeholder="6+ números">')}
      <div class="fila-btn"><button class="btn" id="pinQuitar">Quitar PINs</button><button class="btn btn-accent" id="pinOk">Guardar PIN</button></div>`;
    B.querySelector('[data-sw="acceso_movil"]').onclick = async e => { const r = await api('/api/remoto/pines', { method: 'POST', body: { acceso_movil: !P.acceso_movil } }); toast(r.acceso_movil ? 'Tailscale se encenderá al abrir la app' : 'Tailscale ya no se encenderá con la app'); seccion('Móvil'); };
    $('#pinOk').onclick = async () => { try { await api('/api/remoto/pines', { method: 'POST', body: { usuario: $('#pinC').value, invitada: $('#pinI').value } }); toast('PIN guardado'); seccion('Móvil'); } catch (e) { toast(e.message); } };
    $('#pinQuitar').onclick = async () => { await api('/api/remoto/pines', { method: 'POST', body: { quitar_usuario: true, quitar_invitada: true } }); toast('PINs quitados'); seccion('Móvil'); };
    // Telegram: bot propio del usuario (Bot API oficial, sin abrir nada a internet). Solo responde a su cuenta.
    try {
      const T = await api('/api/telegram/estado'), caja = document.createElement('div');
      caja.innerHTML = `<h4 style="font-size:17px;margin-top:18px">Telegram</h4><p class="d" style="color:var(--muted)">Habla con Sony desde Telegram (texto y notas de voz) mientras la app está abierta. Solo te contesta a ti; las tarjetas llegan como botones Sí/No. Los mensajes pasan por los servidores de Telegram.</p>
        ${fila('Token del bot', T.token ? 'Guardado en el Administrador de credenciales' : 'Créalo con @BotFather y pégalo aquí', T.token ? '<button class="btn small" id="tgBorrar">Quitar token</button>' : '<input id="tgTok" type="password" class="btn" style="width:220px" placeholder="123456:ABC…"> <button class="btn small" id="tgOk">Guardar</button>')}
        ${fila('Estado', T.error ? esc(T.error) : '', `<span class="estado ${T.conectado ? 'listo' : ''}">${T.conectado ? 'conectado' : T.token ? 'conectando…' : 'sin token'}</span>`)}
        ${fila('Tu cuenta', T.emparejado ? 'Emparejada el ' + esc(T.fecha || '') : 'Abre tu bot en Telegram y mándale este código:', T.emparejado ? '<button class="btn small" id="tgDes">Desemparejar</button>' : `<b style="font-size:22px;letter-spacing:3px">${esc(T.codigo || '')}</b>`)}
        ${fila('Avisos de citas y correos por Telegram', '', `<label class="interruptor"><input type="checkbox" id="tgAv" ${T.avisos ? 'checked' : ''}> activado</label>`)}`;
      B.appendChild(caja);
      const tg = d => api('/api/telegram/config', { method: 'POST', body: d }).then(() => seccion('Móvil')).catch(e => toast(e.message));
      $('#tgOk') && ($('#tgOk').onclick = () => tg({ token: $('#tgTok').value }));
      $('#tgBorrar') && ($('#tgBorrar').onclick = () => tg({ borrar_token: true }));
      $('#tgDes') && ($('#tgDes').onclick = () => tg({ desemparejar: true }));
      $('#tgAv').onchange = e => tg({ avisos: e.target.checked });
    } catch {}
    return;
  }
  if (s === 'Datos') { const d = await api('/api/datos'); B.innerHTML = `<h4>Datos</h4>${fila('Chats', `${d.hilos} chats · ${d.chats_mb} MB en ~/IA/sony/panel/chats`, '')}${fila('Adjuntos', `${d.adjuntos_mb} MB en ~/IA/sony/panel/adjuntos`, '')}${fila('Exportar', 'Todos los chats en un .zip', '<button class="btn" id="ajExp">Exportar</button>')}${fila('Papelera', 'Los chats borrados quedan en chats\\_papelera', '')}`; $('#ajExp').onclick = () => location.href = '/api/exportar'; }
  // eventos
  B.onclick = async e => {
    const t = e.target.closest('[data-sw]'); if (t) { const k = t.dataset.sw, v = !S.ajustes[k]; if (k === 'avisos_windows' && v && 'Notification' in window) await Notification.requestPermission(); await guardarAj({ [k]: v }); t.classList.toggle('on', v); }
    const bm = e.target.closest('[data-borrar-mem]'); if (bm) { const mem = [...S.ajustes.memoria]; mem.splice(+bm.dataset.borrarMem, 1); await guardarAj({ memoria: mem }); seccion('Memoria'); }
  };
  const on = (id, ev, f) => { const el = $(id); if (el) el[ev] = f; };
  if ($('#ajTema')) $('#ajTema').value = a.tema; if ($('#ajLetra')) $('#ajLetra').value = a.letra;
  if ($('#ajModelo')) $('#ajModelo').value = a.modelo; if ($('#ajMax')) $('#ajMax').value = a.max_tokens;
  on('#ajNom', 'onchange', e => guardarAj({ nombre: e.target.value.trim() || 'el usuario' }));
  on('#ajTema', 'onchange', e => guardarAj({ tema: e.target.value }));
  on('#ajLetra', 'onchange', e => guardarAj({ letra: e.target.value }));
  on('#ajModelo', 'onchange', e => { S.modelo = e.target.value; guardarAj({ modelo: e.target.value }); });
  on('#ajTemp', 'onchange', e => guardarAj({ temperatura: +e.target.value }));
  on('#ajMax', 'onchange', e => guardarAj({ max_tokens: +e.target.value }));
  on('#ajDesc', 'onchange', e => guardarAj({ descargar_tras_min: Math.max(0, +e.target.value) }));
  on('#ajInsOk', 'onclick', () => guardarAj({ instrucciones: $('#ajIns').value }).then(() => toast('Instrucciones guardadas')));
  on('#memNuevo', 'onkeydown', async e => { if (e.key === 'Enter' && e.target.value.trim()) { await guardarAj({ memoria: [...(S.ajustes.memoria || []), e.target.value.trim()] }); seccion('Memoria'); } });
}

function conectarCorreo(x) {
  modal(`<h3>Conectar «${esc(x.nombre)}»</h3><p style="color:var(--muted)">${esc(x.ayuda)}</p>
    <div class="campo"><label>Dirección de correo</label><input id="cDir" type="email" autocomplete="off" value="${esc(x.direccion)}" placeholder="tu@dominio.com"></div>
    <div class="campo"><label>Contraseña (o contraseña de aplicación)</label><input id="cPass" type="password" autocomplete="new-password"></div>
    <p id="cMsg" style="color:var(--muted);font-size:13px">Se comprueba con el servidor y se guarda en el Llavero de macOS. No se escribe en ningún archivo.</p>
    <div class="fila-btn"><button class="btn" data-cerrar>Cancelar</button><button class="btn btn-accent" id="cOk">Conectar</button></div>`);
  $('#cDir').focus();
  $('#cOk').onclick = async () => {
    $('#cOk').disabled = true; $('#cMsg').textContent = 'Comprobando…';
    const r = await api('/api/correo/conectar', { method: 'POST', body: { id: x.id, direccion: $('#cDir').value, clave: $('#cPass').value } }).catch(e => ({ ok: false, mensaje: e.message }));
    $('#cPass').value = ''; $('#cMsg').textContent = r.mensaje; $('#cOk').disabled = false;
    if (r.ok) { toast(r.mensaje); setTimeout(() => abrirAjustes('Conectores'), 900); }
  };
}

/* ---------------- modal, toast, atajos ---------------- */
function modal(html, ancho) { const c = $('#modalCard'); c.className = 'modal-card' + (ancho ? ' ancho' : ''); c.innerHTML = html; $('#modal').classList.remove('hidden'); }
function cerrarModal() { $('#modal').classList.add('hidden'); window._paraMic?.(); window._paraMic = null; }
$('#modal').onclick = e => { if (e.target.id === 'modal' || e.target.closest('[data-cerrar]')) cerrarModal(); };
let tt; function toast(t) { const el = $('#toast'); el.textContent = t; el.classList.remove('hidden'); clearTimeout(tt); tt = setTimeout(() => el.classList.add('hidden'), 2200); }
function alternarSide() { const s = $('#app').classList.toggle('sin-side'); $('#btnSide2').classList.toggle('hidden', !s); localSet('sinSide', s ? '1' : '0'); }
$('#btnSide').onclick = alternarSide; $('#btnSide2').onclick = alternarSide;
addEventListener('keydown', e => {
  const k = e.key.toLowerCase();
  if (e.ctrlKey && k === 'k') { e.preventDefault(); abrirBuscar(); }
  else if (e.ctrlKey && e.shiftKey && k === 'o') { e.preventDefault(); nuevoChat(); }
  else if (e.ctrlKey && k === 'b') { e.preventDefault(); alternarSide(); }
  else if (k === 'escape') { cerrarModal(); $('#menuFlot').classList.add('hidden'); $('#slashMenu').classList.add('hidden'); }
});

init();

// ---------- Sony en el móvil: service worker, notificaciones y aviso sin conexión ----------
(function movil() {
  const esMovil = matchMedia('(max-width: 760px)').matches || navigator.standalone || matchMedia('(display-mode: standalone)').matches;
  if (esMovil && localGet('sinSide') !== '0') $('#app').classList.add('sin-side'), $('#btnSide2').classList.remove('hidden');
  // tocar fuera de la barra lateral la cierra
  document.addEventListener('click', e => { if (esMovil && !$('#app').classList.contains('sin-side') && !e.target.closest('#side, #btnSide2')) alternarSide(); });
  // Latido: el icono del escritorio lo usa para saber si la ventana sigue abierta
  const latido = () => fetch('/api/ventana/latido', { cache: 'no-store' }).catch(() => {});
  latido(); setInterval(latido, 15000);
  window.addEventListener('pagehide', () => { try { navigator.sendBeacon('/api/ventana/cerrada'); } catch (e) {} });
  if (!('serviceWorker' in navigator) || location.protocol !== 'https:') return;  // solo en el móvil (https por Tailscale)
  navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
  // «Estoy mirando»: si miras la app no te llega aviso; si no, sí.
  const visto = () => { if (document.visibilityState === 'visible') fetch('/api/push/visible', { method: 'POST' }).catch(() => {}); };
  visto(); setInterval(visto, 20000); document.addEventListener('visibilitychange', visto);
  // Aviso cuando Sony no está disponible (PC apagado o Tailscale desconectado)
  const banda = () => { let b = $('#sinConexion'); if (!b) { b = document.createElement('div'); b.id = 'sinConexion'; document.body.appendChild(b); } return b; };
  const comprobar = () => fetch('/api/chat/estado', { cache: 'no-store' }).then(r => r.json()).then(j => {
    if (j.sin_conexion) throw 0; $('#sinConexion')?.remove(); }).catch(() => { banda().textContent = 'Sony no está disponible · puedes leer tus últimos chats'; });
  comprobar(); setInterval(comprobar, 30000); addEventListener('online', comprobar); addEventListener('offline', comprobar);
  // Botón para activar notificaciones (iOS: solo desde el icono de la pantalla de inicio)
  if (!('PushManager' in window) || Notification.permission !== 'default') return;
  const b = document.createElement('button'); b.className = 'btn btn-accent'; b.textContent = '🔔 Activar notificaciones';
  b.style.cssText = 'position:fixed;right:12px;bottom:calc(96px + env(safe-area-inset-bottom));z-index:70';
  document.body.appendChild(b);
  b.onclick = async () => {
    try {
      if (await Notification.requestPermission() !== 'granted') { b.remove(); return toast('Notificaciones no permitidas'); }
      const reg = await navigator.serviceWorker.ready, { publica } = await api('/api/push/clave');
      const k = Uint8Array.from(atob(publica.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((publica.length + 3) % 4)), c => c.charCodeAt(0));
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: k });
      await api('/api/push/suscribir', { method: 'POST', body: { sub: sub.toJSON(), disp: navigator.userAgent.slice(0, 60) } });
      toast('Notificaciones activadas'); b.remove();
    } catch (e) { toast('No se pudieron activar: ' + e.message); }
  };
})();

// ⏏ Liberar ahora: descarga el modelo y Whisper al momento.
async function liberarAhora() {
  if (S.generando) pararGeneracion();
  toast('Liberando memoria…');
  try { const r = await api('/api/liberar', { method: 'POST' }); toast(r.texto); refrescarEstado?.(); } catch (e) { toast('No se pudo liberar: ' + e.message); }
}
$('#btnLiberar') && ($('#btnLiberar').onclick = liberarAhora);
