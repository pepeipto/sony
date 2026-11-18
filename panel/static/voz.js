'use strict';
// Voz de Sony en el Mac: oír (Whisper local) y hablar (Piper local). El audio solo vive en memoria: no se graba ni se guarda.
const Voz = (() => {
  let ctx, stream, nodo, fuente, activo = false, estado = 'apagado', microActual = '', nivelUi = 0;
  let grabando = false, trozos = [], silencioMs = 0, vozMs = 0, ruido = 0.008, finHabla = 0;
  let cola = [], reproduciendo = false, dicho = 0, audioActual = null, medido = false, nivelActual = 0;
  const pausa = () => (S.ajustes.voz?.pausa_ms || 700);

  function ui(e, extra = '') {
    estado = e;
    const txt = { escuchando: 'Escuchando…', oyendo: 'Te escucho…', transcribiendo: 'Transcribiendo…', pensando: 'Pensando…', hablando: 'Hablando…', apagado: '' }[e] || e;
    let b = $('#vozBarra');
    if (!b) {
      b = document.createElement('div'); b.id = 'vozBarra';
      b.innerHTML = '<span class="onda"><i></i><i></i><i></i><i></i></span><span class="t"></span><span class="nivel" title="Nivel del micrófono"><i></i></span><small class="m"></small><button class="btn small" id="vozSalir">Salir del modo voz</button>';
      $('#composer').prepend(b); $('#vozSalir').onclick = parar;
    }
    b.className = 'voz-' + e; b.querySelector('.t').textContent = txt; if (extra) b.querySelector('.m').textContent = extra;
    b.classList.toggle('hidden', e === 'apagado');
    $('#btnVoz').classList.toggle('on', activo);
  }

  async function iniciar() {
    if (activo) return parar();
    try {
      const dev = await elegirMicro();
      stream = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: dev ? { exact: dev.deviceId } : undefined, echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
      microActual = stream.getAudioTracks()[0]?.label || '';
    } catch { return toast('No hay permiso para usar el micrófono'); }
    ctx = new AudioContext({ sampleRate: 16000 }); try { await ctx.resume(); } catch {}
    fuente = ctx.createMediaStreamSource(stream);
    nodo = ctx.createScriptProcessor(1024, 1, 1);
    nodo.onaudioprocess = procesar;
    fuente.connect(nodo); nodo.connect(ctx.destination);
    activo = true; ui('escuchando', microActual ? 'Micro: ' + microActual.replace(/\s*\(.*\)$/, '') : 'Habla cuando quieras');
    fetch('/api/voz/precargar', { method: 'POST' }).catch(() => {});
    fetch('/api/chat/cargar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ modelo: S.modelo }) }).catch(() => {});
  }
  function parar() {
    activo = false; grabando = false; trozos = [];
    try { nodo?.disconnect(); fuente?.disconnect(); stream?.getTracks().forEach(t => t.stop()); ctx?.close(); } catch {}
    callar(); ui('apagado');
  }

  function procesar(ev) { trama(new Float32Array(ev.inputBuffer.getChannelData(0))); }
  function trama(d) {
    if (!activo || estado === 'transcribiendo') return;
    let s = 0; for (let i = 0; i < d.length; i++) s += d[i] * d[i];
    const rms = Math.sqrt(s / d.length), ms = d.length / 16;
    medir(rms);
    const ocupada = estado === 'pensando' || estado === 'hablando';
    if (!grabando && !ocupada) ruido = ruido * 0.97 + Math.min(rms, 0.05) * 0.03;
    // Mientras la IA habla o piensa hace falta más voz para interrumpirla (el eco ya lo quita el navegador).
    const umbral = ocupada ? Math.max(0.04, ruido * 6) : Math.max(0.015, ruido * 3);
    const minimo = ocupada ? 300 : 120;
    if (rms > umbral) {
      vozMs += ms; silencioMs = 0;
      if (!grabando && vozMs > minimo) {
        if (ocupada) { callar(); pararGeneracion(); dicho = Infinity; }  // interrupción (barge-in)
        grabando = true; ui('oyendo');
      }
    } else { silencioMs += ms; if (!grabando) vozMs = 0; }
    if (grabando) {
      trozos.push(new Float32Array(d));
      if (silencioMs > pausa()) { grabando = false; vozMs = 0; enviarAudio(); }
      if (trozos.length * 64 > 60000) { grabando = false; enviarAudio(); }  // máx. 60 s
    } else {
      const n = ocupada ? 14 : 6;  // audio de antes (~0,9 s si interrumpes, ~0,4 s si no)
      trozos = trozos.slice(-n).concat([new Float32Array(d)]).slice(-n);
    }
  }

  async function enviarAudio() {
    const total = trozos.reduce((a, t) => a + t.length, 0); const buf = new Float32Array(total);
    let o = 0; for (const t of trozos) { buf.set(t, o); o += t.length; } trozos = [];
    finHabla = performance.now(); ui('transcribiendo');
    try {
      const r = await fetch('/api/voz/transcribir', { method: 'POST', headers: { 'Content-Type': 'application/octet-stream', 'X-Formato': 'f32-16k' }, body: buf.buffer });
      const j = await r.json(); if (!r.ok) throw new Error(j.error);
      const texto = (j.texto || '').trim();
      if (texto.length < 2) return ui('escuchando');
      if (/^\W*(adi[oó]s|para|cuelga|colgar|hasta luego)\W*$/i.test(texto)) { leerDespedida(); return; }
      ui('pensando', `Oído en ${((performance.now() - finHabla) / 1000).toFixed(1)} s`);
      dicho = 0; medido = false; enviar(texto);
    } catch (e) { toast('Voz: ' + e.message); ui('escuchando'); }
  }

  // Habla la respuesta por frases según va llegando.
  function delta(texto, fin) {
    if (!activo) return;
    const limpio = limpiar(texto);
    const resto = limpio.slice(dicho);
    const re = /[^.!?¡¿\n]+[.!?]+["»)]?\s|[^\n]+\n/g; let m, ult = 0;
    while ((m = re.exec(resto))) { const f = m[0].trim(); if (f.length > 1) decir(f); ult = m.index + m[0].length; }
    dicho += ult;
    if (fin) { const f = limpio.slice(dicho).trim(); if (f) decir(f); dicho = limpio.length; if (!cola.length && !reproduciendo && !grabando) ui('escuchando'); }
  }
  function limpiar(t) {
    return t.replace(/<think>[\s\S]*?(<\/think>|$)/g, '').replace(/```[\s\S]*?(```|$)/g, ' (te dejo el código en pantalla) ')
      .replace(/[#*_`>|]/g, '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/-{3,}/g, '');
  }
  function decir(frase) {
    const p = fetch('/api/voz/hablar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texto: frase, voz: (S.ajustes.voz?.por_modelo || {})[S.modelo] || S.ajustes.voz?.nombre }) })
      .then(async r => { if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || 'La voz no respondió'); return URL.createObjectURL(await r.blob()); });
    cola.push(p); if (!reproduciendo) siguiente();
  }
  async function siguiente() {
    if (!cola.length) { reproduciendo = false; if (activo && !S.generando && !grabando) ui('escuchando'); return; }
    reproduciendo = true; if (!grabando) ui('hablando');
    try {
      const url = await cola.shift();
      audioActual = new Audio(url); audioActual.volume = Math.max(.1, Math.min(1, (S.ajustes.voz?.volumen ?? 10) / 10));
      if (!medido && finHabla) { medido = true; const s = ((performance.now() - finHabla) / 1000).toFixed(1); ui('hablando', `Empezó a hablar a los ${s} s`); console.log('voz: segundos hasta hablar', s); window.ultimaLatenciaVoz = +s; }
      await new Promise(res => { audioActual.onended = audioActual.onerror = res; audioActual.play().catch(res); });
      URL.revokeObjectURL(url);
    } catch (e) { toast('Voz: ' + e.message); }
    siguiente();
  }
  function callar() { cola = []; if (audioActual) { audioActual.pause(); audioActual = null; } reproduciendo = false; }

  // Botón «escuchar» de cada respuesta.
  function leer(texto) { callar(); finHabla = 0; const t = limpiar(texto); (t.match(/[^.!?\n]+[.!?]*\s*/g) || [t]).map(s => s.trim()).filter(s => s.length > 1).forEach(decir); }

  // Micrófono: el elegido en Ajustes → Voz; si no hay, la webcam (OBSBOT) o el predeterminado.
  async function micros() {
    let ds = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'audioinput');
    if (ds.length && !ds[0].label) { const s = await navigator.mediaDevices.getUserMedia({ audio: true }); s.getTracks().forEach(t => t.stop()); ds = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'audioinput'); }
    return ds.filter(d => d.deviceId !== 'communications');
  }
  async function elegirMicro() {
    const ds = await micros(), pref = S.ajustes.voz?.microfono;
    return ds.find(d => pref && d.label === pref) || ds.find(d => /obsbot|webcam|cam/i.test(d.label)) || ds.find(d => d.deviceId === 'default') || ds[0];
  }
  function medir(rms) {
    nivelActual = rms; const now = performance.now(); if (now - nivelUi < 60) return; nivelUi = now;
    const i = document.querySelector('#vozBarra .nivel i'); if (i) i.style.width = Math.min(100, Math.sqrt(rms) * 300) + '%';
  }
  // Medidor para Ajustes → Voz (sin activar el modo voz).
  async function probarMicro(label, pintar) {
    const ds = await micros(), d = ds.find(x => x.label === label) || ds[0];
    const st = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: d ? { exact: d.deviceId } : undefined, echoCancellation: true, noiseSuppression: true } });
    const c = new AudioContext(), src = c.createMediaStreamSource(st), an = c.createAnalyser(); an.fftSize = 1024; src.connect(an);
    const buf = new Float32Array(an.fftSize); let vivo = true;
    (function bucle() { if (!vivo) return; an.getFloatTimeDomainData(buf); let s = 0; for (const v of buf) s += v * v; pintar(Math.sqrt(s / buf.length)); requestAnimationFrame(bucle); })();
    return () => { vivo = false; st.getTracks().forEach(t => t.stop()); c.close(); };
  }

  function leerDespedida() { ui('hablando'); decir('Hasta luego, el usuario. Aquí estaré, soy Sony.'); const fin = setInterval(() => { if (!reproduciendo && !cola.length) { clearInterval(fin); parar(); } }, 300); }

  // Prueba sin micrófono: recibe audio Float32 a 16 kHz y hace el ciclo completo.
  function _probar(f32) { activo = true; ui('escuchando', 'Prueba'); trozos = [f32]; enviarAudio(); }
  // Prueba del bucle real: mete audio como si llegara del micrófono, a tiempo real.
  async function _alimentar(f32) {
    activo = true; if (estado === 'apagado') ui('escuchando');
    for (let i = 0; i < f32.length; i += 1024) { trama(f32.subarray(i, i + 1024)); await new Promise(r => setTimeout(r, 64)); }
  }

  return { micros, probarMicro, iniciar, parar, delta, leer, callar, _probar, _alimentar, get activo() { return activo; }, get nivel() { return activo ? nivelActual : 0; }, get estado() { return estado; } };
})();
