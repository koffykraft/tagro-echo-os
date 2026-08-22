const CACHE='tagro-echo-os-v8';
const CORE=[
  './','./index.html','./login.html','./styles.css','./app.js','./runtime-config.js','./runtime-client.js',
  './on-call.html','./billing.html','./service.html','./po.html','./stock-count.html','./reports.html','./page-builder.html',
  './counter.html','./cash.html','./bank.html','./payments.html','./documents.html','./manifest.webmanifest','./icon.svg',
  './forms/index.html','./forms/form.html','./forms/closing-cash.html','./forms/billing.html','./forms/echo-forms.css','./forms/echo-forms.js'
];
const STATIC_URLS=new Set(CORE.map(path=>new URL(path,self.registration.scope).href));

self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(CORE)).then(()=>self.skipWaiting()));
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener('fetch',event=>{
  const request=event.request;
  if(request.method!=='GET')return;
  const url=new URL(request.url);

  // Critical boundary: API/auth/financial/reference responses are never cached.
  // Only same-origin admitted static assets and navigations are handled here.
  if(url.origin!==self.location.origin)return;

  if(request.mode==='navigate'){
    event.respondWith(
      fetch(request,{cache:'no-store'})
        .then(response=>response)
        .catch(()=>caches.match(request).then(hit=>hit||caches.match('./index.html')))
    );
    return;
  }

  if(!STATIC_URLS.has(request.url))return;
  event.respondWith(
    fetch(request,{cache:'no-store'}).then(response=>{
      if(response.ok){const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(request,copy));}
      return response;
    }).catch(()=>caches.match(request))
  );
});
