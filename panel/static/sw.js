// Service worker de Sony (solo en el móvil/pantalla de inicio): notificaciones y lectura sin conexión.
// Se sirve en /sw.js. Nada de 3D ni cálculos: solo red y caché.
const CACHE = 'sony-v6';  // v6: Intro con beforeinput (iPhone)  // v5: copiar mensajes  // v4: Intro envía en el móvil, avisos si no hay respuesta  // v3: icono 7 «Halo rojo»  // v2 (15/11/2026): las páginas nunca pasan por la caché si hay red; sin páginas en blanco tras redirecciones
const BASE = ['/chat', '/static/tema.css', '/static/temas-extra.css', '/static/chat.css', '/static/movil.css', '/static/chat.js', '/static/voz.js',
              '/static/icono-sony-180.png', '/static/icono-sony-192.png'];

self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(BASE).catch(() => {}))); self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))); self.clients.claim(); });

// Red primero; si falla (PC apagado o Tailscale desconectado), lo último guardado. Solo GET y solo lectura.
const GUARDABLE = u => u.pathname === '/' || u.pathname === '/chat' || u.pathname.startsWith('/static/')
  || u.pathname.startsWith('/api/hilos') || u.pathname === '/api/ajustes' || u.pathname === '/api/sesion';
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;
  // Navegaciones (abrir la web): el navegador va directo a la red (así Safari sigue bien la redirección al PIN).
  // Solo si no hay conexión se enseña la última copia guardada del chat.
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).catch(async () => (await caches.match('/chat')) || (await caches.match('/')) ||
      new Response('<meta name=viewport content="width=device-width,initial-scale=1"><body style="font:16px system-ui;padding:24px;background:#0e0c0c;color:#f1e9e6">Sony no está disponible ahora: revisa que el PC esté encendido y Tailscale conectado.</body>',
        { headers: { 'Content-Type': 'text/html; charset=utf-8' } })));
    return;
  }
  if (!GUARDABLE(u)) return;
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok && !r.redirected) { const copia = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copia)); }
    return r;
  }).catch(async () => (await caches.match(e.request)) || (u.pathname.startsWith('/api/')
    ? new Response(JSON.stringify({ error: 'Sony no está disponible', sin_conexion: true }), { status: 503, headers: { 'Content-Type': 'application/json' } })
    : Response.error())));
});

// Notificaciones: el texto es genérico (pasa por los servidores de Apple), nunca el contenido del chat.
self.addEventListener('push', e => {
  let d = {}; try { d = e.data.json(); } catch {}
  e.waitUntil(self.registration.showNotification(d.titulo || 'Sony', { body: d.cuerpo || 'Tienes un aviso de Sony', icon: '/static/icono-sony-192.png',
    badge: '/static/icono-sony-192.png', data: { url: d.url || '/' }, tag: d.tag || 'sony' }));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: 'window' }).then(cs => cs.length ? cs[0].focus() : self.clients.openWindow(e.notification.data.url || '/')));
});
