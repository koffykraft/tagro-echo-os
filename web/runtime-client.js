(()=>{
  'use strict';

  const cfg=()=>window.ECHO_RUNTIME_CONFIG||{};
  const SESSION_KEY='echo.runtime.session.v1';
  const DEVICE_KEY='echo.runtime.device.v1';
  const QUEUE_VERSION='v1';
  const JOURNAL_LIMIT=100;

  class EchoRuntimeError extends Error{
    constructor(message,{status=0,body=null,code='runtime_error',retryable=false}={}){
      super(message);this.name='EchoRuntimeError';this.status=status;this.body=body;this.code=code;this.retryable=retryable;
    }
  }

  const randomId=prefix=>`${prefix}-${crypto.randomUUID()}`;
  const nowIso=()=>new Date().toISOString();
  const parseJson=s=>{try{return JSON.parse(s)}catch{return null}};
  const b64url=s=>{const pad='='.repeat((4-s.length%4)%4);return atob((s+pad).replace(/-/g,'+').replace(/_/g,'/'))};
  function jwtPayload(token){
    if(!token||typeof token!=='string'||token.split('.').length<2)return null;
    try{return JSON.parse(decodeURIComponent(Array.from(b64url(token.split('.')[1])).map(c=>'%'+c.charCodeAt(0).toString(16).padStart(2,'0')).join('')))}catch{return null}
  }
  function loadSession(){return parseJson(sessionStorage.getItem(SESSION_KEY)||'null')}
  function saveSession(s){sessionStorage.setItem(SESSION_KEY,JSON.stringify(s));return s}
  function clearSession(){sessionStorage.removeItem(SESSION_KEY)}
  function tokenValid(token,skewSeconds=30){
    const p=jwtPayload(token);if(!p||!p.exp)return false;
    const conf=cfg();
    if(conf.issuer&&p.iss&&p.iss!==conf.issuer)return false;
    const audience=p.aud||p.client_id;
    if(conf.userPoolClientId&&audience&&audience!==conf.userPoolClientId)return false;
    return Number(p.exp)*1000>Date.now()+skewSeconds*1000;
  }
  function principalFromSession(s=loadSession()){const p=jwtPayload(s?.idToken);return p?.sub||''}
  function emailFromSession(s=loadSession()){const p=jwtPayload(s?.idToken);return p?.email||p?.['cognito:username']||''}
  function deviceId(){
    let v=localStorage.getItem(DEVICE_KEY);
    if(!v){v=randomId('device');localStorage.setItem(DEVICE_KEY,v)}
    return v;
  }
  function selectedEnterpriseId(){return loadSession()?.enterpriseId||''}
  function requireScope(){
    const sub=principalFromSession(),enterpriseId=selectedEnterpriseId();
    if(!sub)throw new EchoRuntimeError('Sign in is required before local operational work can be scoped.',{code:'sign_in_required'});
    if(!enterpriseId)throw new EchoRuntimeError('Choose an enterprise before operational work.',{code:'enterprise_required'});
    return{sub,enterpriseId,deviceId:deviceId()};
  }
  function scopedKey(name){const s=requireScope();return`echo.${name}.${QUEUE_VERSION}:${s.sub}:${s.enterpriseId}:${s.deviceId}`}

  async function cognito(target,payload){
    const conf=cfg();
    if(!conf.cognitoEndpoint||!conf.userPoolClientId)throw new EchoRuntimeError('Cognito runtime configuration is incomplete.',{code:'auth_config_missing'});
    let response;
    try{
      response=await fetch(conf.cognitoEndpoint,{method:'POST',cache:'no-store',headers:{'content-type':'application/x-amz-json-1.1','x-amz-target':`AWSCognitoIdentityProviderService.${target}`},body:JSON.stringify(payload)});
    }catch(err){throw new EchoRuntimeError('Authentication service is unreachable.',{code:'auth_network',retryable:true,body:String(err)})}
    const body=await response.json().catch(()=>({}));
    if(!response.ok){
      const message=body.message||body.Message||body.__type||`Cognito ${response.status}`;
      throw new EchoRuntimeError(message,{status:response.status,body,code:'auth_rejected',retryable:response.status>=500});
    }
    return body;
  }

  function persistAuthentication(result,prior={}){
    const auth=result?.AuthenticationResult;
    if(!auth?.IdToken)throw new EchoRuntimeError('Cognito did not return an ID token.',{code:'auth_contract'});
    const current=loadSession()||{};
    return saveSession({
      idToken:auth.IdToken,
      accessToken:auth.AccessToken||'',
      refreshToken:auth.RefreshToken||prior.refreshToken||current.refreshToken||'',
      enterpriseId:prior.enterpriseId||current.enterpriseId||'',
      authenticatedAt:nowIso()
    });
  }

  async function login(email,password){
    const username=String(email||'').trim();
    if(!username||!password)throw new EchoRuntimeError('Email and password are required.',{code:'credentials_required'});
    const body=await cognito('InitiateAuth',{AuthFlow:'USER_PASSWORD_AUTH',ClientId:cfg().userPoolClientId,AuthParameters:{USERNAME:username,PASSWORD:String(password)}});
    if(body.ChallengeName){return{challenge:body.ChallengeName,session:body.Session||'',username,parameters:body.ChallengeParameters||{}}}
    return{session:persistAuthentication(body),challenge:null};
  }

  async function completeNewPassword({username,newPassword,challengeSession}){
    if(!username||!newPassword||!challengeSession)throw new EchoRuntimeError('New-password challenge data is incomplete.',{code:'challenge_incomplete'});
    const body=await cognito('RespondToAuthChallenge',{ClientId:cfg().userPoolClientId,ChallengeName:'NEW_PASSWORD_REQUIRED',Session:challengeSession,ChallengeResponses:{USERNAME:String(username),NEW_PASSWORD:String(newPassword)}});
    if(body.ChallengeName)throw new EchoRuntimeError(`Unsupported additional Cognito challenge: ${body.ChallengeName}`,{code:'unsupported_auth_challenge',body});
    return persistAuthentication(body);
  }

  async function refresh(){
    const current=loadSession();
    if(!current?.refreshToken)throw new EchoRuntimeError('Session expired. Sign in again.',{code:'refresh_token_missing'});
    const body=await cognito('InitiateAuth',{AuthFlow:'REFRESH_TOKEN_AUTH',ClientId:cfg().userPoolClientId,AuthParameters:{REFRESH_TOKEN:current.refreshToken}});
    return persistAuthentication(body,current);
  }

  async function ensureSession(){
    let s=loadSession();
    if(s&&tokenValid(s.idToken))return s;
    if(s?.refreshToken){try{s=await refresh();if(tokenValid(s.idToken))return s}catch{}}
    clearSession();
    throw new EchoRuntimeError('Session expired. Sign in again.',{code:'session_expired'});
  }

  async function request(path,{method='GET',body=null,headers={},retryAuth=true}={}){
    const conf=cfg();
    if(!conf.apiBase)throw new EchoRuntimeError('API base is not configured.',{code:'api_config_missing'});
    const s=await ensureSession();
    const url=String(path||'').startsWith('http')?String(path):conf.apiBase.replace(/\/$/,'')+'/'+String(path||'').replace(/^\//,'');
    const h={accept:'application/json',authorization:`Bearer ${s.idToken}`,...headers};
    let payload=body;
    if(body!==null&&body!==undefined&&typeof body!=='string'&&!(body instanceof FormData)){
      h['content-type']=h['content-type']||'application/json';payload=JSON.stringify(body);
    }
    let response;
    try{response=await fetch(url,{method,headers:h,body:payload,cache:'no-store',mode:'cors'})}
    catch(err){throw new EchoRuntimeError('ECHO runtime is unreachable.',{code:'network_unavailable',retryable:true,body:String(err)})}
    if(response.status===401&&retryAuth&&loadSession()?.refreshToken){
      try{await refresh();return request(path,{method,body,headers,retryAuth:false})}catch{}
    }
    const responseBody=await response.json().catch(()=>null);
    if(!response.ok){
      const message=responseBody?.detail||responseBody?.error||`ECHO runtime ${response.status}`;
      throw new EchoRuntimeError(message,{status:response.status,body:responseBody,code:responseBody?.error||'http_error',retryable:response.status>=500||response.status===429});
    }
    return responseBody;
  }

  async function tenantContext(){return request('/tenant-context')}
  async function loadContext(){
    const body=await tenantContext();
    const enterprises=Array.isArray(body.enterprises)?body.enterprises:[];
    const s=loadSession()||{};
    if(s.enterpriseId&&!enterprises.some(x=>x.enterprise_id===s.enterpriseId)){s.enterpriseId='';saveSession(s)}
    if(!s.enterpriseId&&enterprises.length===1){s.enterpriseId=enterprises[0].enterprise_id;saveSession(s)}
    return body;
  }
  function chooseEnterprise(enterpriseId){
    const s=loadSession();if(!s)throw new EchoRuntimeError('Sign in first.',{code:'sign_in_required'});
    s.enterpriseId=String(enterpriseId||'').trim();saveSession(s);return s.enterpriseId;
  }

  function queueRead(){return parseJson(localStorage.getItem(scopedKey('queue'))||'[]')||[]}
  function queueWrite(rows){localStorage.setItem(scopedKey('queue'),JSON.stringify(rows));window.dispatchEvent(new CustomEvent('echo:queue-updated',{detail:{count:rows.filter(x=>x.state==='pending').length}}))}
  function journalRead(){return parseJson(localStorage.getItem(scopedKey('journal'))||'[]')||[]}
  function journalAppend(row){const rows=journalRead();rows.push(row);localStorage.setItem(scopedKey('journal'),JSON.stringify(rows.slice(-JOURNAL_LIMIT)))}

  function enqueueMutation({path,body,method='POST',expectedSchema='',idempotencyKey=''}){
    const scope=requireScope();
    const payload={...(body||{})};
    payload.enterprise_id=payload.enterprise_id||scope.enterpriseId;
    const key=idempotencyKey||payload.idempotency_key||randomId('cmd');
    payload.idempotency_key=payload.idempotency_key||key;
    const rows=queueRead();
    const existing=rows.find(x=>x.idempotencyKey===key);
    const stable=JSON.stringify({path,method,payload});
    if(existing){
      if(existing.stable!==stable)throw new EchoRuntimeError('Idempotency key was reused with changed offline payload.',{code:'idempotency_conflict'});
      return existing;
    }
    const item={queueId:randomId('queue'),idempotencyKey:key,path,method,expectedSchema,payload,stable,state:'pending',attempts:0,createdAt:nowIso(),lastAttemptAt:null,lastError:null};
    rows.push(item);queueWrite(rows);return item;
  }

  async function flushQueue(){
    if(!navigator.onLine)return{acknowledged:0,pending:queueRead().filter(x=>x.state==='pending').length,review:queueRead().filter(x=>x.state==='review').length};
    const rows=queueRead();let acknowledged=0;
    for(const item of rows){
      if(item.state!=='pending')continue;
      item.attempts=Number(item.attempts||0)+1;item.lastAttemptAt=nowIso();
      try{
        const response=await request(item.path,{method:item.method,body:item.payload});
        if(item.expectedSchema&&response?.schema!==item.expectedSchema)throw new EchoRuntimeError('Unexpected ECHO confirmation contract.',{code:'confirmation_contract'});
        item.state='acknowledged';item.acknowledgedAt=nowIso();item.response=response;item.lastError=null;acknowledged++;
        journalAppend({queueId:item.queueId,idempotencyKey:item.idempotencyKey,path:item.path,acknowledgedAt:item.acknowledgedAt,response});
      }catch(err){
        item.lastError={at:nowIso(),message:err.message,status:err.status||0,code:err.code||'runtime_error'};
        if(err.retryable||!err.status){item.state='pending';break}
        item.state='review';
      }
      queueWrite(rows);
    }
    const retained=rows.filter(x=>x.state!=='acknowledged');queueWrite(retained);
    return{acknowledged,pending:retained.filter(x=>x.state==='pending').length,review:retained.filter(x=>x.state==='review').length};
  }

  async function enqueueAndFlush(spec){
    const item=enqueueMutation(spec);
    const result=await flushQueue().catch(()=>({acknowledged:0,pending:1,review:0}));
    const pending=queueRead().find(x=>x.idempotencyKey===item.idempotencyKey);
    if(!pending){
      const journal=journalRead().slice().reverse().find(x=>x.idempotencyKey===item.idempotencyKey);
      return{state:'acknowledged',response:journal?.response||null,queue:item,result};
    }
    return{state:pending.state,response:null,queue:pending,result};
  }

  function pendingQueue(){return queueRead().filter(x=>x.state==='pending')}
  function reviewQueue(){return queueRead().filter(x=>x.state==='review')}
  function localKey(name){return scopedKey(`local.${String(name||'data')}`)}
  function sessionInfo(){const s=loadSession(),p=jwtPayload(s?.idToken);return{signedIn:Boolean(s&&tokenValid(s.idToken,0)),subject:p?.sub||'',email:p?.email||'',enterpriseId:s?.enterpriseId||'',expiresAt:p?.exp?new Date(Number(p.exp)*1000).toISOString():null,deviceId:deviceId()}}
  function signOut(){clearSession();window.dispatchEvent(new CustomEvent('echo:signed-out'))}
  async function reference(kind,q='',limit=40){const s=await ensureSession();const enterpriseId=s.enterpriseId;if(!enterpriseId)throw new EchoRuntimeError('Choose an enterprise first.',{code:'enterprise_required'});const p=new URLSearchParams({kind,enterprise_id:enterpriseId,limit:String(limit)});if(q)p.set('q',q);return request('/reference-data?'+p.toString())}

  window.addEventListener('online',()=>{if(loadSession())flushQueue().catch(()=>{})});

  window.EchoRuntime=Object.freeze({
    EchoRuntimeError,login,completeNewPassword,refresh,ensureSession,request,tenantContext,loadContext,chooseEnterprise,
    enqueueMutation,enqueueAndFlush,flushQueue,pendingQueue,reviewQueue,localKey,reference,sessionInfo,signOut,
    principalFromSession,emailFromSession,selectedEnterpriseId,deviceId
  });
})();
