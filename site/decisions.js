"use strict";
/* Evidence-first decision review. Shared read-only DATA and utilities from app.js. */
function renderAuditedScenarios(container) {
  const list=Array.isArray(DATA.audited_scenarios)?DATA.audited_scenarios:[];
  const pair=(DATA.matchups||[]).find(m=>
    Number(m.home_team_id)===Number(DATA.my_team_id) ||
    Number(m.away_team_id)===Number(DATA.my_team_id));
  const myHome=pair&&Number(pair.home_team_id)===Number(DATA.my_team_id);
  const myProjected=pair?(myHome?pair.home_projected:pair.away_projected):null;
  const opponentProjected=pair?(myHome?pair.away_projected:pair.home_projected):null;
  const effective=list.filter(p=>(p.drop_ids||[p.drop_id]).every(id=>!protect[String(id)])
    &&(riskMode==="aggressive" ||
       (!p.acquisition_risk && typeof p.next_two_weeks_delta==="number" && p.next_two_weeks_delta>=0)));
  effective.sort((a,b)=>b.scenario_margin-a.scenario_margin);
  const best=effective[0]||null;
  const startMargin=Number.isFinite(myProjected)&&Number.isFinite(opponentProjected)
      ?myProjected-opponentProjected:null;
  const p=panel("Can you close the projected deficit?","Evidence-based scenario comparison");
  if(startMargin===null) {
    p.append(el("p","hint","Matchup forecast is incomplete. Do not use a numeric what-if scenario until ESPN scores and game clocks are verified."));
  } else {
    const stats=el("div","stat-cards");
    add(stats,numberText("Current margin",startMargin),
       numberText("Best modeled gain",best?.gain_vs_optimized??null),
       numberText("After best scenario",best?.scenario_margin??startMargin));
    p.append(stats);
    p.append(el("p","hint",best?
      (best.scenario_margin>=0?
        "This scenario reaches a projected lead, but it is NOT a guaranteed win. Review every required acquisition, protected player, and future-week tradeoff.":
        "The best eligible modelled scenario STILL projects a loss. Avoid sacrificing long-term roster value just to reduce the margin."):
      "No modeled scenario satisfies your current protected-player and risk constraints. Keeping your roster is a reasonable outcome."));
  }
  const now=Date.now(),sourceTime=Date.parse(DATA.generated_at_utc);
  if(Number.isFinite(sourceTime) && (now-sourceTime)>6*3600000) {
    p.append(el("p","hint","Data freshness warning: this ESPN snapshot is more than six hours old. Availability, injuries and scores may have changed. Check the next refresh before making a transaction."));
  }
  const policy=DATA.transaction_rules||{};
  const teamKey=String(DATA.my_team_id);
  if(policy.usage_verified){
    const remaining=policy.remaining_by_team?.[teamKey];
    const pending=policy.pending_claims_by_team?.[teamKey]||0;
    p.append(el("p","hint","ESPN acquisition allowance: "+remaining+
      " remaining of "+policy.maximum_matchup_additions+
      " this matchup; "+pending+" pending claim(s). Pending claims may reduce the number of additional moves you can make."));
  }else{
    p.append(el("p","hint","ESPN acquisition usage could not be verified. Check your remaining matchup adds and pending claims before executing a multi-move plan."));
  }
  container.append(p);
  const myId=String(DATA.my_team_id);
  const oppId=pair?String(myHome?pair.away_team_id:pair.home_team_id):null;
  if(oppId&&DATA.daily_lineups){
    const sched=panel("Where the remaining points can come from",
                      "ESPN saved starters with upcoming NBA games");
    const wrap=el("div","table-wrap"),table=el("table"),head=el("tr");
    ["Date","Your starters with games","Opponent starters with games","Unfilled starting slots"].forEach(s=>head.append(el("th","",s)));
    table.append(head);
    Object.keys(DATA.daily_lineups).sort().forEach(day=>{
      const games=DATA.nba_schedule?.[day]||{};
      function countActive(tid){
        const rows=DATA.daily_lineups[day]?.[tid]||[];
        return rows.filter(p=>!([12,13].includes(p.lineup_slot_id))&&
          (games[String(p.pro_team_id)]||[]).includes("pre")&&
          !["OUT","SUSPENSION","INJURY_RESERVE","INJURED_RESERVE"].includes(p.injury_status)).length;
      }
      const ours=countActive(myId),theirs=countActive(oppId);
      const tr=el("tr");
      [dateLabel(day),String(ours)+"/10",String(theirs)+"/10",String(Math.max(0,10-ours))]
        .forEach((s,i)=>tr.append(el("td",i>0?"num":"",s)));
      table.append(tr);
    });
    wrap.append(table);sched.append(wrap);
    sched.append(el("p","hint","An unfilled slot matters only if an eligible new player has an unstarted game that day. Full days often provide zero extra points. Live or completed games are intentionally excluded."));
    container.append(sched);
  }
  const evidence=panel("Choose your risk tolerance","Make the tradeoffs visible");
  const controls=el("div","controls");
  for(const [mode,label] of [["conservative","Conservative"],["aggressive","Show risky alternatives"]]){
    const btn=el("button","link-btn",label);
    btn.setAttribute("aria-pressed",String(riskMode===mode));
    btn.addEventListener("click",()=>{riskMode=mode;render();});
    controls.append(btn);
  }
  evidence.append(controls);
  evidence.append(el("p","hint",
    "Conservative excludes protected-player drops and scenarios with negative or unknown next-two-week value. Aggressive relaxes that future-value filter but never overrides your explicit player protections. Both compare against the same no-acquisition optimized lineup."));
  const compare=el("div","table-wrap"),table=el("table");
  const head=el("tr");
  ["Plan","This week","Next 2 weeks","Projected margin","Moves"].forEach(x=>head.append(el("th","",x)));
  table.append(head);
  const hold=el("tr");
  ["Hold roster", "+0.0", "0.0",fmt(startMargin), "0"].forEach((v,i)=>hold.append(el("td",i>0?"num":"",v)));
  table.append(hold);
  effective.slice(0,6).forEach((plan,i)=>{
    const row=el("tr");
    [
      "Option "+(i+1)+": drop "+plan.drop,
      "+"+fmt(plan.gain_vs_optimized),
      plan.next_two_weeks_delta===undefined?"Unknown":fmt(plan.next_two_weeks_delta),
      fmt(plan.scenario_margin),
      String(plan.acquisitions)
    ].forEach((v,j)=>{
      const cell=el("td",j>0?"num":"",v);
      if(j===3)cell.classList.add(plan.scenario_margin>=0?"good":"danger");
      row.append(cell);
    });
    table.append(row);
  });
  compare.append(table);evidence.append(compare);
  container.append(evidence);
  if(!effective.length) {
    const none=panel("No eligible action","No speculative roster drop recommended");
    none.append(el("p","hint",
       "You can adjust protected players above, but protecting a high-value player may be more important than chasing this week's matchup. Already-started games cannot be recovered."));
    container.append(none);
    return;
  }
  const detailsPanel=panel("Why each plan changes the forecast","Expand an option for day-by-day lineup evidence");
  const distinct=[];
  const seen=new Set();
  for(const x of effective){
    const key=(x.drop_ids||[x.drop_id]).map(String).sort().join("+");
    if(seen.has(key))continue;
    seen.add(key);distinct.push(x);
    if(distinct.length>=5)break;
  }
  distinct.forEach((plan,i)=>{
    const details=el("details","decision-detail");
    if(i===0)details.open=true;
    const summary=el("summary","",
      (i===0?"Best eligible":"Alternative")+" · +"+fmt(plan.gain_vs_optimized)+
      " FP this week · "+fmt(plan.scenario_margin)+" projected margin");
    details.append(summary);
    const rows=el("div","stack");
    rows.append(el("p","hint","Changes to execute in ESPN (these are NOT transactions already made):"));
    if(plan.acquisition_risk){
      rows.append(el("p","warning","High-uncertainty scenario: a suggested free agent has an injury/availability flag. Future-week benefits have been withheld."));
    }
    (plan.acquired_player_statuses||[]).forEach(player=>{
      rows.append(el("p","hint",player.name+": "+(player.availability||"availability unconfirmed")+
        " · ESPN injury status "+(player.injury||"unknown")));
    });
    (plan.moves||[]).forEach((m,j)=>{
      rows.append(el("p","move-instruction",(j+1)+". "+dateLabel(m.day)+
         ": Drop "+m.drop+" → Add "+m.add));
    });
    const tableWrap=el("div","table-wrap"),dtable=el("table");
    const header=el("tr");
    ["Day","Saved lineup","Optimized no moves","With changes","Extra","Active new players"].forEach(t=>header.append(el("th","",t)));
    dtable.append(header);
    (plan.daily_evidence||[]).forEach(day=>{
      const tr=el("tr");
      [dateLabel(day.date),fmt(day.saved_lineup_fp),
       fmt(day.optimized_no_move_fp),fmt(day.scenario_fp),
       (day.extra_fp>=0?"+":"")+fmt(day.extra_fp),
       day.newly_acquired_starters?.map(p=>p.player+" → "+(p.assigned_slot||"slot unknown")+" ("+fmt(p.projected_points)+" FP)").join(", ")||"None"]
       .forEach((txt,j)=>tr.append(el("td",j>0&&j<5?"num":"",txt)));
      dtable.append(tr);
    });
    tableWrap.append(dtable);rows.append(tableWrap);
    const stats=el("div","stat-cards");
    add(stats,numberText("Free lineup fixes",plan.free_lineup_gain),
      numberText("Acquisition gain",plan.gain_vs_optimized),
      numberText("Next 2 weeks",plan.next_two_weeks_delta));
    rows.append(stats);
    if(plan.future_week_deltas) {
      const futureText=Object.entries(plan.future_week_deltas).map(([week,change])=>
        dateLabel(week)+": "+(change>=0?"+":"")+fmt(change)+" FP").join(" · ");
      rows.append(el("p","hint","Estimated subsequent matchup impact: "+futureText));
    }
    rows.append(el("p","hint","Every simulated starting player is assigned to one ESPN-eligible PG, SG, SF, PF, C, G, F, or UTIL slot (maximum three UTIL). The table labels the assigned slot for each acquired player. Existing locked starters are not displaced."));
    rows.append(el("p","hint","Audit: ESPN saved-lineup baseline → optimized existing lineup → acquired-player simulation. Gain is above the OPTIMIZED baseline, so free lineup improvements are not counted as streaming value."));
    rows.append(el("p","hint",
      "Constraints: "+(plan.acquisitions||0)+" hypothetical acquisitions; check current allowance. "+
      (plan.assumption||plan.availability_note||"Player availability not guaranteed.")));
    rows.append(el("p","hint",
      "Long-term limitation: "+(plan.future_uncertainty||
       "Future injury status and roster changes are not forecast. A dropped player may be claimed permanently.")));
    details.append(rows);detailsPanel.append(details);
  });
  detailsPanel.append(el("p","hint","These comparisons use season projected FP/G and current NBA schedule. Actual results vary. The optimizer explores only the candidate sequences it generated—not every possible combination or all seven acquisitions. An absent winning scenario is NOT proof that none exists."));
  container.append(detailsPanel);
}
