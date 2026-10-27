"use strict";
let DATA=null, view="league", currentTeam="4", chartPlayer=null, daySelected=null;
const section=document.getElementById("content"), message=document.getElementById("message");
const slots={0:"PG",1:"SG",2:"SF",3:"PF",4:"C",5:"G",6:"F",11:"UTIL",12:"BENCH",13:"IR"};
const el=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined&&text!==null)e.textContent=String(text);return e;};
const add=(parent,...children)=>{children.forEach(c=>{if(c)parent.append(c)});return parent;};
const fmt=n=>Number.isFinite(Number(n))&&n!==null?Number(n).toLocaleString("en-US",{maximumFractionDigits:1,minimumFractionDigits:1}):"—";
const getTeam=id=>DATA.teams.find(t=>String(t.id)===String(id))||{name:"Team "+id,id};
const proj=p=>p&&typeof p.projected_fppg==="number"?p.projected_fppg:null;
const info=(parent,title,content)=>{const div=el("div","stack");add(div,el("span","muted",title),el("strong","",content));add(parent,div);return div;};
const panel=(title,sub)=>{const box=el("article","panel"),head=el("div","section-head");add(head,el("h2","",title),el("small","",sub||""));box.append(head);return box;};
const pill=(str,isWarn=false)=>el("span","pill"+(isWarn?" warn":""),str);
const numberText=(label,n)=>{const block=el("div","stat");add(block,el("small","",label),el("b","",fmt(n)));return block;};
function showError(text){message.hidden=false;message.textContent=text;}
function dateLabel(iso){return new Intl.DateTimeFormat("en-US",{weekday:"short",month:"short",day:"numeric",timeZone:"UTC"}).format(new Date(iso+"T12:00:00Z"));}
function heading(title,sub){const x=el("div","section-head");add(x,el("h2","",title),el("small","",sub||""));return x;}
function nav(){document.querySelectorAll(".tab").forEach(b=>b.classList.toggle("active",b.dataset.view===view));}
function render(){
  nav();section.replaceChildren();
  if(!DATA){section.append(el("div","empty","No snapshot loaded yet. Run the site builder in GitHub Actions."));return;}
  if(view==="league")renderLeague();
  if(view==="lineups")renderLineups();
  if(view==="trends")renderTrends();
  if(view==="moves")renderMoves();
}
function renderLeague(){
  const liveTeams=Object.values(DATA.nba_schedule||{}).flatMap(byDay=>Object.values(byDay||{})).flat().filter(state=>state==="in").length;
  if(liveTeams>0){
    const notice=el("div","alert");
    const detail=el("div","stack");
    add(detail,
      el("strong","","Live-game projections are temporarily incomplete"),
      el("span","hint","NBA games are in progress, but ESPN may not yet have added their scores to matchup totals. These estimates currently exclude points from games already underway. Treat the projected winner and margin as provisional until the scores update."));
    add(notice,el("span","warning","⚠"),detail);
    section.append(notice);
  }
  const top=el("div","stat-cards");
  const matches=DATA.matchups.filter(m=>!m.bye);
  const your=matches.find(m=>String(m.home_team_id)===String(DATA.my_team_id)||String(m.away_team_id)===String(DATA.my_team_id));
  const margins=your?(your.home_team_id===DATA.my_team_id?your.home_projected-your.away_projected:your.away_projected-your.home_projected):null;
  add(top,numberText("Matchups",matches.length),numberText("League alerts",Object.values(DATA.team_analysis).reduce((n,t)=>n+t.alerts.length,0)),numberText("Your projected margin",margins));section.append(top);
  section.append(heading("This week's matchups",dateLabel(DATA.week_start)+" – "+dateLabel(DATA.week_end)));
  const grid=el("div","scoreboard");
  DATA.matchups.forEach(m=>{
    const box=panel(m.bye?"Bye":"Projected matchup",m.bye?"No opponent":"Remaining games included");
    const contestants=[[m.home_team_id,m.home_projected,m.home_actual]];
    if(m.away_team_id!==null)contestants.push([m.away_team_id,m.away_projected,m.away_actual]);
    contestants.forEach(([id,projected,actual])=>{
      const row=el("div","versus"),left=el("div","stack"),right=el("div","stack");
      const title=el("span","team-name"+(id===DATA.my_team_id?" you":""),getTeam(id).name);
      add(left,title,el("span","subscore","Earned "+fmt(actual)+" FP"));
      add(right,el("span","score",projected===null?"Bye":fmt(projected)),el("span","subscore","Projected final"));
      right.style.textAlign="right";add(row,left,right);box.append(row);
    });
    const warns=contestants.reduce((total,[id])=>total+(DATA.team_analysis[String(id)]?.alerts.length||0),0);
    const summary=el("div","row between");
    add(summary,pill(warns?warns+" potential lineup issues":"No detected lineup issues",!!warns));
    const btn=el("button","link-btn","Inspect lineups");
    btn.addEventListener("click",()=>{currentTeam=String(m.home_team_id);view="lineups";render();});
    add(summary,btn);box.append(summary);grid.append(box);
  });
  section.append(grid);
  const note=el("div","help","Projected final = ESPN matchup points already earned + ESPN season-long projected FP/G for remaining unstarted games in the saved daily lineup. Live games are omitted from the remaining-game projection, so refresh timing affects the estimate. No win probability is claimed.");
  section.append(note);
}
function teamSelect(){
  const s=el("select");s.setAttribute("aria-label","Choose fantasy team");
  DATA.teams.forEach(t=>{const opt=el("option","",t.name);opt.value=String(t.id);s.append(opt)});
  s.value=currentTeam;s.addEventListener("change",()=>{currentTeam=s.value;daySelected=null;render()});return s;
}
function daySelect(days){
  const s=el("select");s.setAttribute("aria-label","Choose lineup date");
  days.forEach(d=>{const option=el("option","",dateLabel(d));option.value=d;s.append(option)});
  if(!daySelected||!days.includes(daySelected))daySelected=days[0];
  s.value=daySelected;s.addEventListener("change",()=>{daySelected=s.value;render()});return s;
}
function renderLineups(){
  const controls=el("div","controls");add(controls,el("label","","Fantasy team"),teamSelect());section.append(controls);
  const analysis=DATA.team_analysis[currentTeam];
  const dates=Object.keys(DATA.daily_lineups).sort();
  if(!analysis||!dates.length){section.append(el("div","empty","ESPN daily lineup data is not yet available."));return;}
  const top=el("div","stat-cards");
  add(top,numberText("Saved-lineup points left",analysis.remaining_expected),numberText("Optimized points left",analysis.remaining_optimized),numberText("Potential gain",analysis.remaining_optimized-analysis.remaining_expected));section.append(top);
  section.append(heading("Lineup checks",analysis.alerts.length+" dates with potential improvements"));
  if(!analysis.alerts.length)section.append(el("div","panel muted","No significant lineup improvements identified for the remaining week."));
  analysis.alerts.forEach(a=>{
    const box=el("div","alert"),inner=el("div","stack");
    add(inner,el("strong","",dateLabel(a.date)+" · +"+fmt(a.potential_gain)+" FP possible"),
      el("span","hint","Consider starting: "+(a.bench_to_start.join(", ")||"Review eligibility")),
      el("small","","Potentially replace: "+(a.start_to_bench.join(", ")||"none")));
    add(box,el("span","warning","⚠"),inner);section.append(box);
  });
  const dateBar=el("div","controls");
  add(dateBar,el("label","","Inspect day"),daySelect(dates));section.append(dateBar);
  const box=panel("Saved lineup · "+dateLabel(daySelected),"From ESPN daily lineup");
  const rosters=DATA.daily_lineups[daySelected][currentTeam]||[];
  const body=el("div","table-wrap"),table=el("table");
  const tr=el("tr");["Slot","Player","Status","Proj. FP"].forEach(t=>tr.append(el("th","",t)));table.append(tr);
  const sorted=[...rosters].sort((a,b)=>a.lineup_slot_id-b.lineup_slot_id);
  sorted.forEach(p=>{
    const row=el("tr");
    [slots[p.lineup_slot_id]||String(p.lineup_slot_id),p.name,p.injury_status||"—",
     p.lineup_slot_id===12?"BENCH":p.lineup_slot_id===13?"IR":fmt(gamePoints(p,daySelected))]
    .forEach((cell,i)=>row.append(el("td",i===3?"num":"",cell)));
    table.append(row);
  });
  body.append(table);box.append(body);
  box.append(el("p","hint","Projected points count only scheduled games that have not started. Bench/IR players earn no active lineup points. Lineups are read-only; make changes in ESPN."));
  section.append(box);
}
function gamePoints(p,date){
  if(["OUT","SUSPENSION","INJURY_RESERVE","INJURED_RESERVE"].includes(p.injury_status)||proj(p)===null)return 0;
  const states=(DATA.nba_schedule?.[date]||{})[String(p.pro_team_id)]||[];
  return proj(p)*states.filter(s=>s==="pre").length;
}
function renderMoves(){
  section.append(heading("Potential one-player swaps","Team TayTay · advisory only"));
  section.append(el("div","help","These are hypothetical points gained from optimizing remaining future lineups after a single add/drop. They assume an immediately usable addition. Waiver delays, acquisition limits and permanent loss of dropped players are not yet modeled. No transactions are performed."));
  if(!DATA.opportunities.length){section.append(el("div","empty","No meaningful simple add/drop opportunities found in the imported free-agent sample."));return;}
  const layout=el("div","grid");
  DATA.opportunities.forEach(m=>{
    const box=panel("+"+fmt(m.projected_gain)+" projected FP","One hypothetical acquisition");
    const x=el("div","versus");
    add(x,info(el("div"),"DROP",m.drop),el("span","accent","→"),info(el("div"),"ADD",m.add));
    add(box,x,el("p","hint",m.note),pill(m.risk,true));layout.append(box);
  });
  section.append(layout);
}
function svgPoint(tag,attrs){
  const element=document.createElementNS("http://www.w3.org/2000/svg",tag);
  for(const [key,value] of Object.entries(attrs||{}))element.setAttribute(key,String(value));
  return element;
}
function playerSelect(players){
  const s=el("select");s.setAttribute("aria-label","Player performance chart");
  players.forEach(p=>{const x=el("option","",p.name);x.value=String(p.id);s.append(x)});
  if(!chartPlayer||!players.some(p=>String(p.id)===chartPlayer))chartPlayer=String(players[0].id);
  s.value=chartPlayer;s.addEventListener("change",()=>{chartPlayer=s.value;render()});return s;
}
function renderTrends(){
  const players=Object.entries(DATA.history).map(([id,games])=>{
    const p=DATA.players[id];
    if(!p||!Array.isArray(games)||games.length===0)return null;
    const actual=games.reduce((n,g)=>n+g.actual,0)/games.length;
    return {...p,id,games,actual,delta:proj(p)!==null?actual-proj(p):null};
  }).filter(Boolean).sort((a,b)=>(b.delta??-999)-(a.delta??-999));
  section.append(heading("Performance trends","Actual game results vs today's ESPN projected FP/G"));
  section.append(el("div","help","The projection line uses ESPN's CURRENT season-long estimate, not the projection that existed before each historical game. Players need multiple games to establish a meaningful pattern. A future update will save historical projection snapshots."));
  if(!players.length){section.append(el("div","empty","No game-by-game history returned from ESPN yet. The trend view will populate as validated game results become available."));return;}
  const controls=el("div","controls");
  add(controls,el("label","","Select player"),playerSelect(players));section.append(controls);
  const chosen=players.find(p=>String(p.id)===chartPlayer)||players[0];
  const top=el("div","stat-cards");
  add(top,numberText("Actual FP/G",chosen.actual),numberText("ESPN projected",proj(chosen)),numberText("Difference",chosen.delta));
  section.append(top);
  const chartBox=panel(chosen.name,"Game-by-game production · "+chosen.games.length+" observed games");
  chartBox.append(makeGraph(chosen.games,proj(chosen)));
  const legend=el("div","legend");
  [["#7cd8c7","Actual FP"],["#f0bd75","Current projection"],["#9e96ed","3-game average"]].forEach(([color,label])=>{
    const x=el("div","row");const dot=el("span","dot");dot.style.background=color;add(x,dot,el("span","",label));legend.append(x);
  });
  chartBox.append(legend);section.append(chartBox);
  const ranking=panel("Largest projection gaps","Minimum 3 recorded games");
  const table=el("table");
  const h=el("tr");["Player","Games","Actual","Expected","Δ / game"].forEach(x=>h.append(el("th","",x)));table.append(h);
  [...players].filter(p=>p.games.length>=3&&p.delta!==null).sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta)).slice(0,25).forEach(p=>{
    const row=el("tr");
    [p.name,p.games.length,fmt(p.actual),fmt(proj(p)),fmt(p.delta)].forEach((val,i)=>{
      const c=el("td",i>0?"num":"",val);
      if(i===4)c.classList.add(p.delta>0?"good":"danger");
      row.append(c);
    });
    table.append(row);
  });
  ranking.append(table);section.append(ranking);
}
function makeGraph(games,expected){
  const width=730,height=295,pad={l:44,r:18,t:24,b:44};
  const svg=svgPoint("svg",{viewBox:"0 0 "+width+" "+height,role:"img","aria-label":"Actual fantasy game points and three-game rolling averages versus current ESPN projection",class:"chart"});
  const actual=games.map(g=>g.actual),roll=games.map((g,i)=>i>=2?(g.actual+games[i-1].actual+games[i-2].actual)/3:null);
  const max=Math.max(15,...actual,...roll.filter(Number.isFinite),expected||0)*1.15;
  const xx=i=>pad.l+(games.length<=1?.5:i/(games.length-1))*(width-pad.l-pad.r);
  const yy=v=>height-pad.b-v/max*(height-pad.t-pad.b);
  for(let tick=0;tick<=4;tick++){
    const y=yy(max*tick/4);
    svg.append(svgPoint("line",{x1:pad.l,x2:width-pad.r,y1:y,y2:y,stroke:"#304451","stroke-width":1}));
    const text=svgPoint("text",{x:pad.l-9,y:y+4,fill:"#91aaba","font-size":12,"text-anchor":"end"});
    text.textContent=String(Math.round(max*tick/4));svg.append(text);
  }
  if(expected!==null){
    const y=yy(expected);svg.append(svgPoint("line",{x1:pad.l,x2:width-pad.r,y1:y,y2:y,stroke:"#f0bd75","stroke-width":2,"stroke-dasharray":"7 5"}));
  }
  const poly=(values,color)=>{
    const points=values.map((v,i)=>v===null?null:[xx(i),yy(v)]).filter(Boolean);
    if(points.length>=2)svg.append(svgPoint("polyline",{points:points.map(p=>p.join(",")).join(" "),fill:"none",stroke:color,"stroke-width":3,"stroke-linejoin":"round","stroke-linecap":"round"}));
    points.forEach(([x,y])=>svg.append(svgPoint("circle",{cx:x,cy:y,r:2.8,fill:color})));
  };
  poly(actual,"#7cd8c7");poly(roll,"#9e96ed");
  const indexes=[0,Math.floor((games.length-1)/2),games.length-1];
  [...new Set(indexes)].forEach(i=>{
    const t=svgPoint("text",{x:xx(i),y:height-16,fill:"#92acbb","font-size":12,"text-anchor":"middle"});
    t.textContent=games[i].date.slice(5);svg.append(t);
  });
  return svg;
}
document.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>{view=b.dataset.view;render();}));
(async()=>{
  try{
    const response=await fetch("data.json?bust="+Date.now(),{cache:"no-store"});
    if(!response.ok)throw new Error("Data file unavailable (HTTP "+response.status+").");
    const data=await response.json();
    if(data.schema_version!==2)throw new Error("Dashboard data version mismatch.");
    DATA=data;
    const d=new Date(data.generated_at_utc);
    document.getElementById("update").textContent="Updated "+d.toLocaleString("en-US",{month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZone:"America/Los_Angeles"})+" PT";
    render();
  }catch(error){
    showError("Dashboard not yet populated: "+error.message+" The site build must complete successfully before data will appear.");
    section.replaceChildren(el("div","empty","League data not published yet."));
  }
})();
