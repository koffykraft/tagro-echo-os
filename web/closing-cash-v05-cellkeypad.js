(()=>{
'use strict';
function install(){
  if(typeof renderRows!=='function'||typeof renderDenoms!=='function'||typeof data==='undefined'||typeof counts==='undefined')return false;

  function numericCell(r,key,cls=''){
    const value=String(r[key]??'');
    return `<div class="cellnum ${cls}" role="button" tabindex="0" data-id="${r.id}" data-key="${key}" aria-label="${key==='sale'?'Sale amount':'Expense amount'}">${value}</div>`;
  }

  window.renderRows=function(){
    rows.innerHTML=data.map(r=>`<tr data-row="${r.id}"><td class="sale">${numericCell(r,'sale','num')}</td><td><input data-id="${r.id}" data-key="bill" enterkeyhint="next" value="${r.bill}"></td><td class="exp">${numericCell(r,'expense','num')}</td><td><input data-id="${r.id}" data-key="part" enterkeyhint="next" value="${r.part}"></td></tr>`).join('');
    rows.querySelectorAll('input').forEach(bindCell);
    rows.querySelectorAll('.cellnum').forEach(el=>{
      el.value=el.textContent||'';
      const activate=e=>{
        if(e)e.preventDefault();
        active=el;
        rows.querySelectorAll('tr.active').forEach(x=>x.classList.remove('active'));
        el.closest('tr')?.classList.add('active');
        openKeypad(el,labelFor(el));
      };
      el.addEventListener('pointerdown',activate);
      el.addEventListener('click',activate);
      el.addEventListener('keydown',e=>{
        if(e.key==='Enter'||e.key===' '){e.preventDefault();openKeypad(el,labelFor(el));}
        else if(e.key==='ArrowDown'){e.preventDefault();moveVertical(1);}
        else if(e.key==='ArrowUp'){e.preventDefault();moveVertical(-1);}
      });
    });
    calc();
  };

  window.renderDenoms=function(){
    denoms.innerHTML=DENOMS.map(d=>`<tr><td>${d==='Coins'?'Coins':'₹'+d}</td><td><div class="denomnum" role="button" tabindex="0" data-denom="${d}" aria-label="${d==='Coins'?'Coins':'₹'+d+' quantity'}">${counts[d]}</div></td><td data-amount="${d}">${d==='Coins'?counts[d]:n(d)*counts[d]}</td></tr>`).join('');
    denoms.querySelectorAll('.denomnum').forEach(el=>{
      el.value=el.textContent||'0';
      const activate=e=>{if(e)e.preventDefault();active=el;openKeypad(el,labelFor(el));};
      el.addEventListener('pointerdown',activate);
      el.addEventListener('click',activate);
      el.addEventListener('keydown',e=>{
        if(e.key==='Enter'||e.key===' '){e.preventDefault();openKeypad(el,labelFor(el));}
        else if(e.key==='ArrowDown'){e.preventDefault();advanceDenom(1);}
        else if(e.key==='ArrowUp'){e.preventDefault();advanceDenom(-1);}
      });
    });
  };

  window.openKeypad=function(el,label){
    kpTarget=el;active=el;kpLabel.textContent=label;
    const raw=String(el.value??el.textContent??'').trim();
    kpDisplay.textContent=raw||'0';kpReplace=true;
    keypad.classList.add('show');document.body.classList.add('keypad-open');
    try{el.scrollIntoView({block:'center',behavior:'smooth'});}catch{}
  };

  window.updateNumericTarget=function(){
    if(!kpTarget)return;
    const value=String(kpDisplay.textContent||'0');
    kpTarget.value=value;kpTarget.textContent=value;
    if(kpTarget.dataset.denom){
      const key=kpTarget.dataset.denom;counts[key]=n(value);
      const amount=key==='Coins'?counts[key]:n(key)*counts[key];
      const amt=denoms.querySelector(`[data-amount="${CSS.escape(key)}"]`);if(amt)amt.textContent=amount;
      calc();return;
    }
    const r=data.find(x=>x.id===kpTarget.dataset.id);if(!r)return;
    r[kpTarget.dataset.key]=value;calc();
  };

  window.focus=function(id,key){
    const selector=key==='sale'||key==='expense'?`.cellnum[data-id="${id}"][data-key="${key}"]`:`input[data-id="${id}"][data-key="${key}"]`;
    const el=rows.querySelector(selector);if(!el)return;
    if(key==='sale'||key==='expense'){
      active=el;rows.querySelectorAll('tr.active').forEach(x=>x.classList.remove('active'));el.closest('tr')?.classList.add('active');openKeypad(el,labelFor(el));
    }else{
      closeKeypad(false);el.focus({preventScroll:true});try{el.select()}catch{};try{el.scrollIntoView({block:'center'})}catch{}
    }
  };

  window.moveVertical=function(dir){
    if(!active||!active.dataset?.id)return;
    const i=data.findIndex(r=>r.id===active.dataset.id),ni=Math.max(0,Math.min(data.length-1,i+dir));
    focus(data[ni].id,active.dataset.key);
  };

  window.advanceDenom=function(dir){
    const cells=[...denoms.querySelectorAll('.denomnum')],i=cells.indexOf(kpTarget);if(i<0)return;
    const target=cells[Math.max(0,Math.min(cells.length-1,i+dir))];active=target;openKeypad(target,labelFor(target));
  };

  const style=document.createElement('style');
  style.textContent=`
    .cellnum{width:100%;height:34px;display:flex;align-items:center;justify-content:flex-end;padding:4px 5px;outline:0;font-size:13px;cursor:text;user-select:none;-webkit-user-select:none;touch-action:manipulation}
    .cellnum:focus,.cellnum.active{box-shadow:inset 0 0 0 2px var(--focus);background:rgba(255,255,255,.45)}
    .denomnum{width:100%;height:30px;display:flex;align-items:center;justify-content:flex-end;background:var(--grey);padding:2px 5px;outline:0;font-size:12px;cursor:text;user-select:none;-webkit-user-select:none;touch-action:manipulation}
    .denomnum:focus{box-shadow:inset 0 0 0 2px var(--focus)}
  `;
  document.head.appendChild(style);
  renderRows();renderDenoms();calc();
  return true;
}
let tries=0;const timer=setInterval(()=>{tries++;if(install()||tries>50)clearInterval(timer)},80);
})();