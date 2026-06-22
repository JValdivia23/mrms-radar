// MRMS Radar — Service Worker
// Caches the app shell and recent radar images for offline/PWA use.

const CACHE = 'mrms-v1';
const SHELL = [
  '/',
  '/static/manifest.json',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Cache radar images as they're fetched
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Cache API radar images
  if (url.pathname === '/api/radar' && !url.searchParams.has('meta')) {
    e.respondWith(
      caches.open(CACHE).then(cache =>
        cache.match(e.request).then(cached =>
          cached || fetch(e.request).then(resp => {
            if (resp.ok) cache.put(e.request, resp.clone());
            return resp;
          })
        )
      )
    );
    return;
  }

  // Cache shell
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
