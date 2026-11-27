var CACHE = "uc-v2";
var URLS = ["index.html", "manifest.json", "icon-192.png", "icon-512.png"];

self.addEventListener("install", function(event) {
  event.waitUntil(caches.open(CACHE).then(function(cache) { return cache.addAll(URLS); }));
  self.skipWaiting();
});

self.addEventListener("activate", function(event) {
  event.waitUntil(caches.keys().then(function(keys) {
    return Promise.all(keys.filter(function(key) { return key !== CACHE; }).map(function(key) { return caches.delete(key); }));
  }));
  self.clients.claim();
});

self.addEventListener("fetch", function(event) {
  if (event.request.url.indexOf("safeconvert/") === -1 && event.request.url.indexOf("icon-") === -1) {
    event.respondWith(new Response("Offline resource not available", {status: 404}));
    return;
  }
  event.respondWith(caches.match(event.request).then(function(response) { return response || fetch(event.request); }));
});
