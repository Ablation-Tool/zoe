/* Dorothy Brain Observatory Offline Service Worker (iPhone, iPad, Android & Desktop PWA) */
const CACHE_NAME = 'dorothy-brain-observatory-v0.9.6';
const CORE_ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './assets/dorothy-icon.svg',
  './assets/apple-touch-icon.png',
  './assets/icon-512.png',
  './assets/three.min.js',
  './assets/observatory.js',
  './data/brain_meshes.js',
  './data/atlas_encyclopedia.js',
  './data/library_vault.js',
  './mri_slices/axial_sheet.jpg',
  './mri_slices/coronal_sheet.jpg',
  './mri_slices/sagittal_sheet.jpg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const reqUrl = new URL(event.request.url);
  if (reqUrl.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response && response.status === 200 && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => cached || caches.match('./index.html'));
    })
  );
});
