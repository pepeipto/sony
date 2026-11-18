'use strict';
// Pantallas de Sony (diseños aprobados por el usuario, 18/11), cada una en un marco a pantalla completa encima del chat de siempre:
//   hud.html   → pantalla principal (núcleo)
//   chat2.html → chat completo nuevo
// Los marcos son de la misma web: leen el estado real de esta página (voz, conversación, permisos) y usan sus funciones.
// El chat antiguo sigue debajo («Más opciones») con proyectos, programados y todos los ajustes.
const Nucleo = (() => {
  let hud, chat, vista = 'nucleo', iniciado = false;
  function marco(id, src, titulo) {
    const f = document.createElement('iframe'); f.id = id; f.className = 'marco-sony hidden'; f.title = titulo; f.src = src; f.allow = 'autoplay';
    document.body.appendChild(f); return f;
  }
  function poner(v) {
    vista = v;
    hud.classList.toggle('hidden', v !== 'nucleo'); chat.classList.toggle('hidden', v !== 'chat');
    try { localStorage.setItem('vistaSony', v); } catch {}
    if (v === 'nucleo') hud.focus(); else if (v === 'chat') chat.focus(); else document.getElementById('entrada')?.focus();
  }
  function iniciar() {
    if (iniciado) return; iniciado = true;
    hud = marco('nucleo', '/static/hud.html?v=202611182400', 'Sony');
    chat = marco('chatSony', '/static/chat2.html?v=202611182400', 'Sony · Chat');
    let v = 'nucleo'; try { v = localStorage.getItem('vistaSony') || 'nucleo'; } catch {}
    poner(['nucleo', 'chat', 'antiguo'].includes(v) ? v : 'nucleo');
  }
  return {
    iniciar,
    mostrar(si) { poner(si ? 'nucleo' : 'antiguo'); },   // ◉ Núcleo / chat antiguo
    chat(si) { poner(si ? 'chat' : 'antiguo'); },        // chat completo nuevo / «Más opciones»
    get visible() { return vista === 'nucleo'; }, get vista() { return vista; },
  };
})();
window.Nucleo = Nucleo;
