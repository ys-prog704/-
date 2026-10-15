/* 검 키우기 대장간 — 홈 화면 앱용 서비스 워커
   새 버전이 바로 보이도록 "인터넷 먼저": 인터넷이 되면 항상 서버에서 받고, 받은 것을 복사해 두었다가
   인터넷이 안 될 때만 그 복사본으로 엽니다(게임 진행은 원래 이 기기에 저장되므로 오프라인으로도 강화 가능).
   같은 주소(이 게임)의 GET 요청만 다루고, 구글 로그인 · Firebase · 글꼴 같은 다른 주소는 건드리지 않습니다. */
var CACHE = 'forge-app-v1';
var CORE = ['./', 'manifest.webmanifest', 'assets/app/icon-192.png', 'assets/app/icon-512.png'];
var SLOW_MS = 6000;   // 복사본이 있을 때, 인터넷이 이보다 느리면 복사본으로 먼저 엽니다

self.addEventListener('install', function(e){
  e.waitUntil(caches.open(CACHE).then(function(c){ return c.addAll(CORE); }).then(function(){ return self.skipWaiting(); }));
});

self.addEventListener('activate', function(e){
  e.waitUntil(caches.keys().then(function(keys){
    return Promise.all(keys.filter(function(k){ return k.indexOf('forge-app-') === 0 && k !== CACHE; }).map(function(k){ return caches.delete(k); }));
  }).then(function(){ return self.clients.claim(); }));
});

self.addEventListener('fetch', function(e){
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  var page = req.mode === 'navigate';
  // 게임 화면은 ?room= · ?duel= 같은 꼬리가 붙어도 같은 파일이라 한 칸('./')에 둡니다
  var key = page ? new URL('./', self.registration.scope).href : req;
  var net = fetch(page ? new Request(url.href, { cache: 'no-cache', credentials: 'same-origin' }) : req).then(function(res){
    if (res && res.ok && res.type === 'basic'){
      var copy = res.clone();
      caches.open(CACHE).then(function(c){ return c.put(key, copy); });
    }
    return res;
  });
  e.respondWith(caches.match(key).then(function(hit){
    if (!hit) return net;
    var slow = new Promise(function(done){ setTimeout(function(){ done(hit); }, SLOW_MS); });
    return Promise.race([net.catch(function(){ return hit; }), slow]);
  }));
});
