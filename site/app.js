"use strict";
let DATA=null, view="strategy", currentTeam="4", chartPlayer=null, daySelected=null;
let riskMode="conservative", protect={};
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
  if(view==="strategy")renderStrategy();
  if(view==="league")renderLeague();
  if(view==="lineups")renderLineups();
  if(view==="trends")renderTrends();
  if(view==="moves")renderMoves();
}
function getProtectedPlayers(){
  const days=Object.keys(DATA.daily_lineups||{}).sort();
  const roster=(DATA.daily_lineups[days[0]]||{})[String(DATA.my_team_id)]||[];
  const unique=[...new Map(roster.filter(p=>p.id!=null).map(p=>[String(p.id),p])).values()];
  unique.sort((a,b)=>(b.projected_fppg||0)-(a.projected_fppg||0));
  return unique;
}
function initProtect(){
  if(!DATA)return;
  const team=String(DATA.my_team_id);
  try{
    const saved=JSON.parse(localStorage.getItem("courtside-protected-"+team)||"null");
    if(saved&&typeof saved==="object"&&!Array.isArray(saved)){protect=saved;return;}
  }catch(e){}
  protect={};
  getProtectedPlayers().forEach((p,i)=>{if(i<10 || (p.projected_fppg||0)>=35)protect[String(p.id)]=true});
}
function saveProtect(){
  try{localStorage.setItem("courtside-protected-"+DATA.my_team_id,JSON.stringify(protect));}catch(e){}
}
function renderStrategy(){
  const outlook=DATA.three_week_outlook||[];
  const guidance=DATA.season_guidance||{};
  section.append(heading("Season strategy","Your next three matchups, not just tonight's score"));
  if(outlook.length!==3){
    section.append(el("div","help","Three-week matchup data is not yet complete. The dashboard won't invent future opponents or schedules."));
  }else{
    const recap=panel(guidance.recommendation||"Review matchup",
      "Schedule-based guidance · not a calibrated win probability");
    recap.append(el("p","hint",guidance.reason||"Evaluate current and future lineups."));
    const metrics=el("div","stat-cards");
    add(metrics,numberText("This-week margin",guidance.current_margin),
      numberText("Next-week margin",guidance.next_week_margin),
      numberText("Avg. next 2 weeks",guidance.team_future_weekly_average));
    recap.append(metrics);section.append(recap);
    const grid=el("div","grid");
    outlook.forEach((w,i)=>{
      const tid=String(DATA.my_team_id);
      const mine=w.teams?.[tid]||{};
      const opponents=w.matchups||[];
      const pair=opponents.find(m=>String(m.home_team_id)===tid||String(m.away_team_id)===tid);
      const opponentId=pair?(String(pair.home_team_id)===tid?pair.away_team_id:pair.home_team_id):null;
      const rival=opponentId===null?null:w.teams?.[String(opponentId)];
      const card=panel(w.label,dateLabel(w.week_start));
      add(card,el("div","team-name",opponentId===null?"Bye week":"vs. "+getTeam(opponentId).name));
      const row=el("div","versus");
      add(row,info(el("div"),"Your projection",fmt(mine.projected_points)),info(el("div"),"Opponent projection",rival?fmt(rival.projected_points):"—"));
      card.append(row);
      const rank=mine.league_rank?"Projected "+mine.league_rank+" of "+w.ranked_count+" teams":"Projection rank unavailable";
      card.append(pill(rank));
      if(i>0){
        const p=el("p","hint","Usable starts: "+(mine.usable_starts??"—")+
          " · Scheduled player-games: "+(mine.potential_player_games??"—")+
          ". Relative to your next-two-week average: "+(mine.relative_to_own_future_average>0?"+":"")+
          fmt(mine.relative_to_own_future_average)+" FP.");
        card.append(p);
      }else{
        card.append(el("p","hint","Includes ESPN points earned plus remaining projected starts."));
      }
      grid.append(card);
    });
    section.append(grid);
    const evidence=panel("Is your opponent getting lucky?","Separate performance variance from schedule strength");
    const observations=DATA.performance_signals||{};
    const own=observations[String(DATA.my_team_id)]||{};
    const opponent=guidance.opponent_id!=null?observations[String(guidance.opponent_id)]||{}:{};
    if((own.matched_games||0)<5||(opponent.matched_games||0)<5){
      evidence.append(el("p","hint","Insufficient matched pregame projections to make a reliable performance-versus-expectation comparison. The archived projection series is still accumulating. A favorable schedule or high total alone does not establish luck."));
    }else{
      const margin=el("div","stat-cards");
      add(margin,numberText("Your roster vs expectation",own.actual_minus_expected),
        numberText("Opponent vs expectation",opponent.actual_minus_expected),
        numberText("Matched opponent games",opponent.matched_games));
      evidence.append(margin);
      evidence.append(el("p","hint","Figures measure rostered players' game-level averages vs saved pregame projections, not just credited starter points; small samples may be noisy."));
    }
    section.append(evidence);
  }
  const prefs=panel("Protect your roster","Stored only on this device");
  prefs.append(el("p","hint","Protected players are excluded from streaming-plan drop suggestions. Your strongest players start protected (top ten and anyone projected for at least 35 FP/G); change these based on your preferences."));
  const choices=el("div","protection-grid");
  getProtectedPlayers().forEach(p=>{
    const label=el("label","player-check"),check=el("input");
    check.type="checkbox";check.checked=!!protect[String(p.id)];
    check.addEventListener("change",()=>{protect[String(p.id)]=check.checked;saveProtect();render();});
    const desc=el("span","",p.name+" · "+fmt(p.projected_fppg)+" FP/G");
    add(label,check,desc);choices.append(label);
  });
  prefs.append(choices);section.append(prefs);
  const plans=panel("Streaming scenarios","No roster changes made automatically");
  const actions=el("div","controls");
  const conservative=el("button","link-btn","Conservative");
  const aggressive=el("button","link-btn","Aggressive");
  conservative.setAttribute("aria-pressed",String(riskMode==="conservative"));
  aggressive.setAttribute("aria-pressed",String(riskMode==="aggressive"));
  conservative.onclick=()=>{riskMode="conservative";render();};
  aggressive.onclick=()=>{riskMode="aggressive";render();};
  add(actions,conservative,aggressive);plans.append(actions);
  const all=DATA.streaming_plans||[];
  const filtered=all.filter(p=>!protect[String(p.drop_id)]&&
      (riskMode==="aggressive" || (p.three_week_net_points!==null&&p.three_week_net_points>=0)));
  if(!filtered.length){
    plans.append(el("div","empty","No eligible streaming plan passes the current player protection and risk settings. Holding your roster is a valid decision."));
  }else{
    filtered.slice(0,4).forEach((p,i)=>{
      const item=el("div","plan-card");
      const lead=el("div","row between");
      add(lead,el("strong","",i===0?"Best eligible scenario":"Alternative scenario"),
        pill(p.acquisitions+" acquisition"+(p.acquisitions===1?"":"s")));
      item.append(lead);
      const stats=el("div","stat-cards");
      add(stats,numberText("This-week gain",p.this_week_gain),
        numberText("Next 2 weeks",p.next_two_weeks_delta),
        numberText("3-week net",p.three_week_net_points));
      item.append(stats);
      p.moves.forEach((m,j)=>{
        item.append(el("p","hint",(j+1)+". "+dateLabel(m.day)+": Drop "+m.drop+" → Add "+m.add));
      });
      item.append(el("p","hint","Risk: "+p.risk+". "+p.availability_note));
      plans.append(item);
    });
  }
  plans.append(el("p","hint","When an injured player is dropped, future-week value is unknown until their return date is established. Such moves are hidden in Conservative mode. Schedules and injury statuses can change. Plans assume listed free agents remain available and their acquisitions clear before the specified days. Three-week point differences are not calibrated win probabilities."));
  section.append(plans);
}
function renderLeague(){
  const liveTeams=Object.values(DATA.nba_schedule||{}).flatMap(byDay=>Object.values(byDay||{})).flat().filter(state=>state==="in").length;
  if(liveTeams>0){
    const notice=el("div","alert"),detail=el("div","stack");
    const incomplete=DATA.matchups.some(m=>m.projection_incomplete);
    add(detail,
      el("strong","",incomplete?"Live forecasts need more data":"NBA games in progress — projections are provisional"),
      el("span","hint",incomplete?
        "Some games lack verified clock data. Forecast totals are withheld rather than showing misleading numbers.":
        "ESPN live matchup points are credited. Remaining in-progress points are estimated from the regulation game clock and season-long per-game projections; this is not a live statistical forecast."));
    add(notice,el("span","warning","⚠"),detail);section.append(notice);
  }
  const top=el("div","stat-cards");
  const matches=DATA.matchups.filter(m=>!m.bye);
  const your=matches.find(m=>String(m.home_team_id)===String(DATA.my_team_id)||String(m.away_team_id)===String(DATA.my_team_id));
  const margins=your&&Number.isFinite(your.home_projected)&&Number.isFinite(your.away_projected)?(your.home_team_id===DATA.my_team_id?your.home_projected-your.away_projected:your.away_projected-your.home_projected):null;
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
      add(right,el("span","score",projected===null?(m.bye?"Bye":"Unavailable"):fmt(projected)),el("span","subscore","Projected final"));
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
  const rules=DATA.transaction_rules;
  if(rules){
    const max=rules.maximum_matchup_additions;
    const used=rules.executed_additions_by_team?.[String(DATA.my_team_id)];
    const remaining=rules.remaining_by_team?.[String(DATA.my_team_id)];
    const pending=rules.pending_claims_by_team?.[String(DATA.my_team_id)];
    const allowance=max===null?"Matchup limit unavailable":max+" additions allowed this matchup";
    const usage=rules.usage_verified?
      " Team TayTay has used "+used+"; "+remaining+" remain.":
      " Completed-transaction counts could not be verified.";
    const hours=rules.waiver_hours!==null?rules.waiver_hours+"-hour":"unspecified";
    const note=el("div","help","ESPN: "+allowance+"."+usage+
      (pending?" "+pending+" pending claims may consume additional moves.":"")+
      " Traditional "+hours+" waivers; players already listed as free agents may be added immediately. Confirm each player's transaction timing in ESPN.");
    section.append(note);
  }
  section.append(el("div","help","Scenarios are provisional: they assume immediately available replacements, and do not guarantee waiver clearance, unlocked games, or that dropping a player is worth the permanent-loss risk. No transactions are performed."));
  if(!DATA.opportunities.length){section.append(el("div","empty","No meaningful simple add/drop opportunities found in the imported free-agent sample."));return;}
  const layout=el("div","grid");
  DATA.opportunities.forEach(m=>{
    const box=panel("+"+fmt(m.projected_gain)+" projected FP","One hypothetical acquisition");
    const x=el("div","versus");
    add(x,info(el("div"),"DROP",m.drop),el("span","accent","→"),info(el("div"),"ADD",m.add));
    add(box,x,
      pill(m.availability_status==="WAIVERS"?"On waivers — claim not guaranteed":"Free agent"),
      el("p","hint","Conservative first usable day: "+(m.first_usable_day||"unverified")),
      el("p","hint",m.note),pill(m.risk,true));
    layout.append(box);
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
    const matched=games.filter(g=>typeof g.expected_at_game==="number");
    const priorActual=matched.length?matched.reduce((n,g)=>n+g.actual,0)/matched.length:null;
    const priorExpected=matched.length?matched.reduce((n,g)=>n+g.expected_at_game,0)/matched.length:null;
    return {...p,id,games,actual,matchedActual:priorActual,matchedCount:matched.length,priorExpected,
      delta:matched.length?priorActual-priorExpected:null};
  }).filter(Boolean).sort((a,b)=>(b.delta??-999)-(a.delta??-999));
  section.append(heading("Performance trends","Actual game points vs. the ESPN projections saved before tipoff"));
  section.append(el("div","help","Pre-game expectations are saved on each successful refresh. Games before tracking began have no historical expectation; they are NOT compared against today's projection. Three or more matched games are required for the ranking."));
  if(!players.length){section.append(el("div","empty","No game-by-game history returned from ESPN yet. The trend view will populate as validated game results become available."));return;}
  const controls=el("div","controls");
  add(controls,el("label","","Select player"),playerSelect(players));section.append(controls);
  const chosen=players.find(p=>String(p.id)===chartPlayer)||players[0];
  const top=el("div","stat-cards");
  add(top,numberText("Matched actual FP/G",chosen.matchedActual),numberText("Pregame expectation",chosen.priorExpected),numberText("Matched-game difference",chosen.delta));
  section.append(top);
  const chartBox=panel(chosen.name,"Game-by-game production · "+chosen.games.length+" observed games");
  chartBox.append(makeGraph(chosen.games));
  const legend=el("div","legend");
  [["#7cd8c7","Actual FP"],["#f0bd75","As-of-game ESPN projection"],["#9e96ed","3-game average"]].forEach(([color,label])=>{
    const x=el("div","row");const dot=el("span","dot");dot.style.background=color;add(x,dot,el("span","",label));legend.append(x);
  });
  chartBox.append(legend);section.append(chartBox);
  const ranking=panel("Largest projection gaps","Minimum 3 games with saved pre-tipoff projections");
  const table=el("table");
  const h=el("tr");["Player","Games","Actual","Expected","Δ / game"].forEach(x=>h.append(el("th","",x)));table.append(h);
  [...players].filter(p=>p.matchedCount>=3&&p.delta!==null).sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta)).slice(0,25).forEach(p=>{
    const row=el("tr");
    [p.name,p.matchedCount,fmt(p.matchedActual),fmt(p.priorExpected),fmt(p.delta)].forEach((val,i)=>{
      const c=el("td",i>0?"num":"",val);
      if(i===4)c.classList.add(p.delta>0?"good":"danger");
      row.append(c);
    });
    table.append(row);
  });
  ranking.append(table);section.append(ranking);
}
function makeGraph(games){
  const expected=games.map(g=>typeof g.expected_at_game==="number"?g.expected_at_game:null);
  const width=730,height=295,pad={l:44,r:18,t:24,b:44};
  const svg=svgPoint("svg",{viewBox:"0 0 "+width+" "+height,role:"img","aria-label":"Actual fantasy game points and three-game rolling averages versus current ESPN projection",class:"chart"});
  const actual=games.map(g=>g.actual),roll=games.map((g,i)=>i>=2?(g.actual+games[i-1].actual+games[i-2].actual)/3:null);
  const max=Math.max(15,...actual,...roll.filter(Number.isFinite),...expected.filter(Number.isFinite))*1.15;
  const xx=i=>pad.l+(games.length<=1?.5:i/(games.length-1))*(width-pad.l-pad.r);
  const yy=v=>height-pad.b-v/max*(height-pad.t-pad.b);
  for(let tick=0;tick<=4;tick++){
    const y=yy(max*tick/4);
    svg.append(svgPoint("line",{x1:pad.l,x2:width-pad.r,y1:y,y2:y,stroke:"#304451","stroke-width":1}));
    const text=svgPoint("text",{x:pad.l-9,y:y+4,fill:"#91aaba","font-size":12,"text-anchor":"end"});
    text.textContent=String(Math.round(max*tick/4));svg.append(text);
  }

  const poly=(values,color)=>{
    let segment=[];
    const flush=()=>{if(segment.length>=2)svg.append(svgPoint("polyline",{points:segment.map(p=>p.join(",")).join(" "),fill:"none",stroke:color,"stroke-width":3,"stroke-linejoin":"round","stroke-linecap":"round"}));segment=[];};
    values.forEach((v,i)=>{
      if(!Number.isFinite(v)){flush();return;}
      const x=xx(i),y=yy(v);segment.push([x,y]);
      svg.append(svgPoint("circle",{cx:x,cy:y,r:3,fill:color}));
    });
    flush();
  };
  poly(actual,"#7cd8c7");poly(roll,"#9e96ed");poly(expected,"#f0bd75");
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
    initProtect();
    const d=new Date(data.generated_at_utc);
    document.getElementById("update").textContent="Updated "+d.toLocaleString("en-US",{month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZone:"America/Los_Angeles"})+" PT";
    render();
  }catch(error){
    showError("Dashboard not yet populated: "+error.message+" The site build must complete successfully before data will appear.");
    section.replaceChildren(el("div","empty","League data not published yet."));
  }
})();
