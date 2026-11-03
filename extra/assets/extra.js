/* Table filters + combined day scoreboard */
(function(){
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
  // generic table filters
  $$('[data-filter-table]').forEach(inp=>{
    const id=inp.dataset.filterTable, tbl=document.getElementById(id);
    if(!tbl) return;
    const rows=$$('tbody tr',tbl);
    const year=$(`[data-filter-year="${id}"]`), league=$(`[data-filter-league="${id}"]`),
          status=$(`[data-filter-status="${id}"]`), count=$(`[data-filter-count="${id}"]`);
    const apply=()=>{
      const q=inp.value.trim().toLowerCase(), y=year?year.value:'', l=league?league.value:'', s=status?status.value:'';
      let n=0;
      rows.forEach(tr=>{
        const host=tr.querySelector('[data-year]')||tr;
        const ry=host.dataset.year||'', rl=host.dataset.league||'', rs=host.dataset.status||'';
        let ok=(!q||tr.textContent.toLowerCase().includes(q))&&(!y||ry===y)&&(!l||rl===l);
        if(s==='high') ok=ok&&rs.includes('high');
        else if(s) ok=ok&&rs.includes(s);
        tr.style.display=ok?'':'none'; if(ok)n++;
      });
      if(count)count.textContent=`${n} / ${rows.length} rows`;
    };
    inp.addEventListener('input',apply);
    [year,league,status].forEach(el=>el&&el.addEventListener('change',apply));
    apply();
  });

  // day scoreboard
  const cal=$('#x-dayhead'); if(!cal) return;
  const START='2026-11-02', END='2030-02-28';
  const today='2026-11-02'; // compiled date; user local timezone is UTC
  let cur=new URLSearchParams(location.search).get('d')||today;
  let pack=null, includeEst=false;
  const toMin=h=>{const [a,b]=h.split(':').map(Number);return a*60+b;};
  const fmt=m=>`${String(Math.floor(m/60)%24).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;
  const addDays=(iso,n)=>{const d=new Date(iso+'T12:00:00Z');d.setDate(d.getDate()+n);return d.toISOString().slice(0,10);};
  const pretty=iso=>new Date(iso+'T12:00:00Z').toLocaleDateString('en-US',{weekday:'long',year:'numeric',month:'long',day:'numeric',timeZone:'UTC'});
  const clamp=s=>s<START?START:(s>END?END:s);
  const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const a=(u,t)=>u?`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(t||'official source')}</a>`:'';
  const badge=st=>{st=(st||'').toLowerCase();return st==='verified'?'<span class="tag ver">verified</span>':st==='estimated'?'<span class="tag est">ESTIMATE</span>':'<span class="tag flag">unverified / TBA</span>';};
  function intervals(e){
    const out=[];
    if(e.start){
      const s=toMin(e.start);
      let en=e.end?toMin(e.end):s+(Number(e.durationMin)||165);
      if(en<=s)en+=1440; // overnight network window
      if(en>1440){out.push([s,1440]);out.push([0,en-1440]);}else out.push([s,en]);
    } else if(e.startWindow){
      const [x,y]=e.startWindow.split('-').map(toMin);out.push([x,y]);
    } else if(e.altWindow&&e.altWindow.start){
      const s=toMin(e.altWindow.start);out.push([s,s+(e.altWindow.durationMin||165)]);
    }
    return out;
  }
  function merge(ivs){
    const s=ivs.slice().sort((a,b)=>a[0]-b[0]),out=[];
    for(const [x,y] of s){if(out.length&&x<=out[out.length-1][1])out[out.length-1][1]=Math.max(out[out.length-1][1],y);else out.push([x,y]);}
    return out;
  }
  function render(){
    const b=pack.days[cur]||{verified:[],estimated:[],tba:[],anchors:[],future:[]};
    const rows=[...b.verified,...(includeEst?b.estimated:[])];
    $('#x-date').value=cur;
    $('#x-today-label').textContent=today;
    $('#x-dayhead').textContent=pretty(cur)+' · '+(cur.slice(5).replace('-','/'))+' Pacific';
    $('#x-estbanner').style.display=includeEst?'':'none';
    const ivs=merge(rows.flatMap(intervals)).map(([x,y])=>[Math.max(0,x),Math.min(1440,y)]);
    const bar=$('#x-bar');bar.innerHTML='';let cursor=0;const free=[];
    for(const [x,y] of ivs){if(x>cursor)free.push([cursor,x]);cursor=Math.max(cursor,y);}
    if(cursor<1440)free.push([cursor,1440]);
    free.forEach(([x,y])=>{const d=document.createElement('div');d.className='seg free';d.style.left=(x/1440*100)+'%';d.style.width=((y-x)/1440*100)+'%';bar.appendChild(d);});
    ivs.forEach(([x,y])=>{const d=document.createElement('div');d.className='seg busy';d.style.left=(x/1440*100)+'%';d.style.width=((y-x)/1440*100)+'%';d.title=fmt(x)+'–'+fmt(y)+' busy';bar.appendChild(d);});
    const busyH=ivs.reduce((t,[x,y])=>t+(y-x),0)/60;
    $('#x-busy').textContent=busyH.toFixed(1);$('#x-free').textContent=(b.tba.length||b.future.length)?'Unknown':(24-busyH).toFixed(1);
    const fw=(b.tba.length||b.future.length)?[]:free.filter(([x,y])=>y-x>=30);
    $('#x-freewin').innerHTML=fw.length?fw.map(([x,y])=>`<span class="tag ver">${fmt(x)}–${fmt(y)} model gap (${((y-x)/60).toFixed(1)}h PT)</span>`).join(' '):'<span class="tag flag">No model gap of 30 minutes or more</span>';
    const uv=[...b.tba,...b.future];
    $('#x-unverified').innerHTML=uv.length?`<div class="callout warn"><strong>Unverified / TBA on this day (${uv.length}).</strong> Exact free minutes cannot be computed for these rows because no official start time is published; they are not inferred.<ul>${uv.map(e=>`<li>${esc(e.title||'published future date')} — ${esc(e.note||'time not published')} ${a(e.sourceUrl,'official source')}</li>`).join('')}</ul></div>`:'';
    const evs=[...rows,...uv];
    $('#x-events').innerHTML=evs.length?evs.map(e=>`<tr>
      <td>${esc(e.start||'—')}</td><td>${esc(e.end||'—')}</td><td>${esc(e.league||e.sport||'')}${e.phase?` <span class="small">${esc(e.phase)}</span>`:''}</td>
      <td>${esc(e.title||'')}${e.venue?`<br><span class="small">${esc(e.venue)}</span>`:''}${e.note?`<br><span class="small">${esc(e.note)}</span>`:''}</td>
      <td>${e.priority==='high'?'<span class="tag high">HIGH PRIORITY</span>':'—'}</td>
      <td>${e.radio?'<span class="tag est">RADIO CANDIDATE</span>':'—'}</td>
      <td>${badge(e.status||'unverified')}</td><td>${a(e.sourceUrl,'official source')}</td></tr>`).join(''):'<tr><td colspan="8">No scheduled sports programming found on the official feeds for this day.</td></tr>';
    const ctx=[...b.anchors.map(x=>`<span class="chip">${esc(x.label)} · ${esc(x.league)} ${a(x.sourceUrl,'source')}</span>`),
               ...b.future.map(x=>`<span class="chip">${esc(x.title)} ${a(x.sourceUrl,'source')}</span>`)];
    $('#x-context').innerHTML=ctx.length?ctx.join(' '):'<span class="small">No official season anchor for this day.</span>';
    let strip='';for(let i=-3;i<=3;i++){const d=addDays(cur,i);if(d<START||d>END)continue;const bb=pack.days[d]||{};const busy=(bb.verified||[]).length;strip+=`<a class="chip" href="?d=${d}">${d.slice(5)} <span class="tag ${busy?'flag':'ver'}">${busy?busy+' events':'free?'}</span></a>`;}
    $('#x-strip').innerHTML=strip;
    history.replaceState(null,'','?d='+cur);
  }
  $('#x-prev').onclick=()=>{cur=clamp(addDays(cur,-1));render();};
  $('#x-next').onclick=()=>{cur=clamp(addDays(cur,1));render();};
  $('#x-today').onclick=()=>{cur=today;render();};
  $('#x-date').onchange=e=>{cur=clamp(e.target.value);render();};
  $('#x-est').onchange=e=>{includeEst=e.target.checked;render();};
  fetch('data/calendar.json').then(r=>r.json()).then(p=>{pack=p;cur=clamp(cur);render();}).catch(e=>{$('#x-dayhead').textContent='Could not load calendar.json: '+e;});
})();
