(()=>{
'use strict';
function install(){
  if(typeof window.renderDenoms!=='function' || typeof DENOMS==='undefined' || typeof counts==='undefined') return false;
  window.renderDenoms=function(){
    const html=DENOMS.map(d=>`<tr><td>${d==='Coins'?'Coins':'₹'+d}</td><td><input data-denom="${d}" inputmode="${d==='Coins'?'decimal':'numeric'}" enterkeyhint="next" value="${counts[d]??0}"></td><td class="amt" data-amt="${d}">${money(d==='Coins'?counts[d]:n(d)*counts[d]).toFixed(0)}</td></tr>`).join('');
    deskDenoms.innerHTML=html;
    mobDenoms.innerHTML=html;
    [deskDenoms,mobDenoms].forEach(t=>{
      const inputs=[...t.querySelectorAll('input[data-denom]')];
      inputs.forEach((el,i)=>{
        el.addEventListener('focus',()=>{requestAnimationFrame(()=>{try{el.select()}catch{}})});
        el.addEventListener('click',()=>{try{el.select()}catch{}});
        el.addEventListener('input',()=>{
          const key=el.dataset.denom;
          counts[key]=n(el.value);
          const amount=money(key==='Coins'?counts[key]:n(key)*counts[key]);
          document.querySelectorAll(`[data-amt="${CSS.escape(key)}"]`).forEach(a=>a.textContent=amount.toFixed(0));
          document.querySelectorAll(`input[data-denom="${CSS.escape(key)}"]`).forEach(peer=>{if(peer!==el && peer.value!==el.value) peer.value=el.value});
          calcRender();
          markDirty();
        });
        el.addEventListener('keydown',e=>{
          if(e.key==='Enter'){
            e.preventDefault();
            e.stopPropagation();
            const target=inputs[e.shiftKey?Math.max(0,i-1):Math.min(inputs.length-1,i+1)];
            if(target){target.focus({preventScroll:true});try{target.select()}catch{}target.scrollIntoView({block:'nearest'});}
          } else if(e.key==='ArrowDown'){
            e.preventDefault();
            const target=inputs[Math.min(inputs.length-1,i+1)]; if(target){target.focus({preventScroll:true});try{target.select()}catch{}}
          } else if(e.key==='ArrowUp'){
            e.preventDefault();
            const target=inputs[Math.max(0,i-1)]; if(target){target.focus({preventScroll:true});try{target.select()}catch{}}
          }
        });
      });
    });
  };
  renderDenoms();
  return true;
}
let tries=0;
const timer=setInterval(()=>{tries++;if(install()||tries>40)clearInterval(timer)},100);
})();
