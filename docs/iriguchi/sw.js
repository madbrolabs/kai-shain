// 電波が無い時のための写し。いつも新しい物を先に取りに行き（版の入れ替えは自動）、取れない時だけ写しを出す。
var NA = "iriguchi-v1";
self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(NA).then(function (c) { return c.addAll(["./", "index.html", "app.js", "style.css", "manifest.json"]); }));
  self.skipWaiting();
});
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", function (e) {
  var u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  e.respondWith(fetch(e.request).then(function (r) {
    if (r.ok && !/\.(apk|exe)$/.test(u.pathname)) {
      var k = r.clone();
      caches.open(NA).then(function (c) { c.put(e.request, k); });
    }
    return r;
  }).catch(function () {
    return caches.match(e.request, { ignoreSearch: true }).then(function (m) { return m || caches.match("./"); });
  }));
});
