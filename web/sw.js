const CACHE='tagro-echo-os-v8';
const CORE=[
  './','./index.html','./login.html','./runtime-config.js','./runtime-client.js','./echo-home-v1.css','./echo-home-v1.js',
  './operation.css','./business-intelligence.css','./business.js','./intelligence.js',
  './billing.html','./service.html','./stock-count.html','./po.html','./closing-cash.html','./business.html','./intelligence.html','./on-call.html',
  './manifest.webmanifest','./icon.svg'
];
const STATIC_URLS=new Set(CORE.map(path=>new URL(path,self.registration.scope).href));
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(CORE)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',event=>{const request=event.request;if(request.method!=='GET')return;const url=new URL(request.url);if(url.origin!==self.location.origin)return;if(request.mode==='navigate'){event.respondWith(fetch(request,{cache:'no-store'}).catch(()=>caches.match(request).then(hit=>hit||caches.match('./index.html'))));return}if(!STATIC_URLS.has(request.url))return;event.respondWith(fetch(request,{cache:'no-store'}).then(response=>{if(response.ok){const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(request,copy))}return response}).catch(()=>caches.match(request))) });
