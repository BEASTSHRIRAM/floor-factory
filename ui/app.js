/* THE FLOOR — Mission Control. Plain JS, no build step.
   Data flow: REST snapshots on load, then SSE /events drives live updates.
   Every fetch is defensive: unknown shapes render as empty, never crash. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var state = {
    agents: [], jobs: [], ledger: [], cycle: null,
    connected: false, lastSeq: 0, running: false,
    firedIds: {}, // agentId -> true once the firing animation has played
    hireIds: {}   // agentId -> true once the new-hire pulse has played
  };

  /* ---------- helpers ---------- */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function pick(obj) { // first defined of the argument names after obj
    for (var i = 1; i < arguments.length; i++) {
      if (obj && obj[arguments[i]] !== undefined && obj[arguments[i]] !== null) return obj[arguments[i]];
    }
    return undefined;
  }
  function asArray(x, keys) {
    if (Array.isArray(x)) return x;
    if (x && typeof x === "object") {
      for (var i = 0; i < keys.length; i++) if (Array.isArray(x[keys[i]])) return x[keys[i]];
    }
    return [];
  }
  function credits(n) {
    var v = Number(n);
    if (!isFinite(v)) return "₡0";
    return (v < 0 ? "−₡" : "₡") + Math.abs(v).toLocaleString("en-IN");
  }
  function signedCredits(n) {
    var v = Number(n);
    if (!isFinite(v) || v === 0) return "₡0";
    return (v > 0 ? "+₡" : "−₡") + Math.abs(v).toLocaleString("en-IN");
  }
  function payloadOf(ev) {
    if (!ev || typeof ev !== "object") return {};
    if (ev.payload && typeof ev.payload === "object") return ev.payload;
    if (ev.data && typeof ev.data === "object") return ev.data;
    return ev;
  }
  function eventText(ev, p) {
    return pick(p, "message", "text", "narration") || pick(ev, "message", "text", "narration") || "";
  }
  function toast(msg, isError) {
    var t = $("toast");
    t.textContent = msg;
    t.className = "toast" + (isError ? " error" : "");
    clearTimeout(toast._h);
    toast._h = setTimeout(function () { t.classList.add("hidden"); }, 4200);
  }

  /* ---------- agent normalisation ---------- */
  function agentId(a) { return String(pick(a, "id", "agent_id", "name") || ""); }
  function isFired(a) {
    var s = String(pick(a, "status") || "").toLowerCase();
    return s === "fired" || s === "terminated" || !!pick(a, "fired_at");
  }
  function isManagement(a) {
    var role = String(pick(a, "role", "kind", "type") || "").toLowerCase();
    var tier = String(pick(a, "tier") || "").toLowerCase();
    return /manager|review|reviewer|cfo/.test(role) || /manager|reviewer|cfo/.test(tier);
  }
  function agentStatus(a) {
    if (isFired(a)) return "fired";
    var s = String(pick(a, "status") || "idle").toLowerCase().replace(/\s+/g, "_");
    if (s === "inreview") s = "in_review";
    return s;
  }

  function renderAgents() {
    var grid = $("agent-grid"), mgmt = $("management-row"), grave = $("graveyard");
    var active = [], fired = [], mgmtList = [];
    state.agents.forEach(function (a) {
      if (isFired(a)) fired.push(a);
      else if (isManagement(a)) mgmtList.push(a);
      else active.push(a);
    });
    mgmt.innerHTML = mgmtList.map(agentCard).join("");
    grid.innerHTML = active.length ? active.map(agentCard).join("") : '<span class="empty">No workers on the floor yet.</span>';
    grave.innerHTML = fired.length ? fired.map(agentCard).join("") : '<span class="empty">No pink slips yet.</span>';
    $("stat-agents").textContent = String(active.length + mgmtList.length);
  }

  function agentCard(a) {
    var rep = Number(pick(a, "reputation", "rep"));
    if (!isFinite(rep)) rep = 0;
    rep = Math.max(0, Math.min(100, rep));
    var repCls = rep >= 60 ? "" : (rep >= 35 ? " mid" : " low");
    var bal = Number(pick(a, "balance", "balance_credits", "credits"));
    if (!isFinite(bal)) bal = 0;
    var st = agentStatus(a);
    var gen = pick(a, "generation", "gen");
    var firedNow = isFired(a) && state.firedIds[agentId(a)];
    var hireNow = !isFired(a) && state.hireIds[agentId(a)];
    var cls = "agent-card" + (isFired(a) ? " fired" : "") + (firedNow ? " shake" : "") + (hireNow ? " newhire" : "");
    var job = pick(a, "current_job", "current_job_title", "job_title");
    var tool = pick(a, "last_tool", "last_tool_call", "current_tool");
    var mut = pick(a, "mutation_note", "mutation");
    var html = '<div class="' + cls + '" data-agent="' + esc(agentId(a)) + '">';
    if (isFired(a)) html += '<span class="stamp">TERMINATED</span>';
    html += '<div class="row1"><span class="agent-name">' + esc(pick(a, "name") || "Agent") + "</span>";
    var tier = pick(a, "tier");
    if (tier) html += '<span class="badge tier">' + esc(tier) + "</span>";
    if (gen !== undefined) html += '<span class="badge">Gen ' + esc(gen) + "</span>";
    html += "</div>";
    var model = pick(a, "model");
    if (model) html += '<div class="agent-meta">' + esc(model) + "</div>";
    html += '<div class="rep-wrap"><div class="rep-bar"><div class="rep-fill' + repCls + '" style="width:' + rep + '%"></div></div><span class="rep-num">' + Math.round(rep) + "</span></div>";
    html += '<div class="agent-foot"><span class="balance ' + (bal < 0 ? "neg" : bal > 0 ? "pos" : "") + '">' + credits(bal) + '</span><span class="chip ' + esc(st) + '">' + esc(st.replace("_", " ")) + "</span></div>";
    if (job) html += '<div class="current-job">Working: ' + esc(job) + (tool ? ' · <code>' + esc(tool) + "</code>" : "") + "</div>";
    if (mut) html += '<div class="mutation-note">' + esc(mut) + "</div>";
    html += "</div>";
    return html;
  }

  /* ---------- jobs ---------- */
  function jobColumn(j) {
    var s = String(pick(j, "status") || "open").toLowerCase();
    if (["draft", "open", "posted", "new"].indexOf(s) >= 0) return "open";
    if (["bidding", "auction"].indexOf(s) >= 0) return "bidding";
    if (["awarded", "executing", "working", "in_progress", "assigned"].indexOf(s) >= 0) return "progress";
    if (["in_review", "review", "appealed", "appeal", "submitted"].indexOf(s) >= 0) return "review";
    return "done"; // paid, done, completed, failed, closed
  }
  function jobBids(j) {
    var b = pick(j, "bids");
    return Array.isArray(b) ? b : [];
  }
  function renderJobs() {
    var cols = { open: [], bidding: [], progress: [], review: [], done: [] };
    state.jobs.forEach(function (j) { cols[jobColumn(j)].push(j); });
    Object.keys(cols).forEach(function (key) {
      var body = document.querySelector('.job-col[data-col="' + key + '"] .col-body');
      if (!body) return;
      body.innerHTML = cols[key].length ? cols[key].map(jobCard).join("") : '<span class="empty">—</span>';
    });
    var done = 0, failed = 0;
    state.jobs.forEach(function (j) {
      var s = String(pick(j, "status") || "").toLowerCase();
      if (["paid", "done", "completed", "closed", "accepted"].indexOf(s) >= 0) done++;
      if (["failed", "rejected"].indexOf(s) >= 0) failed++;
    });
    $("stat-done").textContent = String(done);
    $("stat-failed").textContent = String(failed);
  }
  function jobCard(j) {
    var budget = pick(j, "budget_credits", "budget", "budget_cap", "cap");
    var winner = pick(j, "winner", "awarded_to", "assigned_to", "agent_name");
    var sev = pick(j, "severity");
    var html = '<div class="job-card"><div class="job-title">' + esc(pick(j, "title", "name") || "Job") + "</div>";
    var meta = [];
    var sys = pick(j, "system", "target_system", "target", "system_id");
    if (sys) meta.push(esc(sys));
    if (budget !== undefined) meta.push('<span class="job-budget">' + credits(budget) + "</span>");
    if (meta.length) html += '<div class="job-meta">' + meta.join(" · ") + "</div>";
    var bids = jobBids(j);
    if (bids.length) {
      html += '<div class="bid-stack">';
      bids.forEach(function (b) {
        var who = pick(b, "agent_name", "agent", "bidder", "agent_id") || "Agent";
        var price = pick(b, "price_credits", "price", "amount");
        var conf = pick(b, "confidence", "conf");
        var isWin = winner && String(who) === String(winner);
        html += '<div class="bid-line' + (isWin ? " winner" : "") + '"><span class="who">' + esc(who) + '</span><span class="amt">' +
          (price !== undefined ? credits(price) : "") +
          (conf !== undefined ? " · conf " + Number(conf).toFixed(2) : "") + "</span></div>";
      });
      html += "</div>";
    } else if (winner) {
      html += '<div class="job-status-note">Awarded to ' + esc(winner) + "</div>";
    }
    if (sev) html += '<div class="job-status-note">Review severity: <span class="sev ' + esc(sev) + '">' + esc(sev) + "</span></div>";
    html += "</div>";
    return html;
  }

  /* ---------- ledger / narration feeds ---------- */
  function feedItem(html, cls) {
    var d = document.createElement("div");
    d.className = "feed-item" + (cls ? " " + cls : "");
    d.innerHTML = html;
    return d;
  }
  function prependFeed(el, item) {
    var empty = el.querySelector(".empty");
    if (empty) empty.remove();
    el.insertBefore(item, el.firstChild);
    while (el.children.length > 120) el.removeChild(el.lastChild);
  }
  function renderLedger() {
    var el = $("ledger-feed");
    el.innerHTML = "";
    if (!state.ledger.length) { el.innerHTML = '<span class="empty">No credit movements yet.</span>'; }
    var paid = 0;
    state.ledger.slice().reverse().forEach(function (row) { prependFeed(el, ledgerItem(row)); });
    state.ledger.forEach(function (row) {
      var kind = String(pick(row, "kind", "type") || "").toLowerCase();
      var amt = Number(pick(row, "amount_credits", "amount"));
      if ((kind === "earning" || kind === "payment") && isFinite(amt) && amt > 0) paid += amt;
    });
    $("stat-paid").textContent = credits(paid);
    // Also honour a server-provided totals figure if present.
  }
  function ledgerItem(row) {
    var amt = Number(pick(row, "amount_credits", "amount"));
    var who = pick(row, "agent_name", "agent", "agent_id");
    var why = pick(row, "note", "reason", "kind", "type") || "";
    var cls = amt > 0 ? "pos" : amt < 0 ? "neg" : "";
    var html = '<span class="amt ' + cls + '">' + signedCredits(amt) + "</span> ";
    if (who) html += "<b>" + esc(who) + "</b> ";
    html += '<span class="why">' + esc(why) + "</span>";
    return feedItem(html, "");
  }
  function narrate(text, cls) {
    if (!text) return;
    var item = feedItem(esc(text), cls || "");
    prependFeed($("narration-log"), item);
  }

  /* ---------- ticker ---------- */
  function tickerAdd(html) {
    var track = $("ticker-track");
    var idle = track.querySelector(".ticker-item.muted");
    if (idle) idle.remove();
    var s = document.createElement("span");
    s.className = "ticker-item";
    s.innerHTML = html;
    track.appendChild(s);
    // Duplicate content once for a smooth loop when there is enough of it.
    if (track.children.length >= 4) track.classList.add("scrolling");
  }

  /* ---------- payroll ---------- */
  // The payroll overlay is a native <dialog>: showModal() gives the top
  // layer, focus trap, and Esc handling for free. Fallback for engines
  // without dialog support: toggle the `open` attribute / hidden class.
  function openPayroll() {
    var ov = $("payroll-overlay");
    ov.classList.remove("hidden");
    if (typeof ov.showModal === "function") {
      if (!ov.open) ov.showModal();
    } else {
      ov.setAttribute("open", "");
    }
  }
  function closePayroll() {
    var ov = $("payroll-overlay");
    if (typeof ov.close === "function" && ov.open) ov.close();
    ov.removeAttribute("open");
    ov.classList.add("hidden");
  }
  function showPayroll(p) {
    var banner = $("payroll-banner");
    banner.classList.remove("hidden");
    setTimeout(function () { banner.classList.add("hidden"); }, 6000);
    var cyc = pick(p, "cycle_no", "cycle");
    if (cyc !== undefined) { $("payroll-cycle").textContent = String(cyc); $("stat-cycle").textContent = String(cyc); }
    var rows = pick(p, "rows", "agents", "payroll");
    if (Array.isArray(rows) && rows.length) {
      $("payroll-body").innerHTML = rows.map(function (r) {
        var verdict = String(pick(r, "verdict", "status") || "SAFE").toUpperCase().replace("_", "-");
        var earn = Number(pick(r, "earnings", "earned")), cost = Number(pick(r, "costs", "cost", "upkeep"));
        var net = Number(pick(r, "net"));
        if (!isFinite(net)) net = (isFinite(earn) ? earn : 0) - (isFinite(cost) ? cost : 0);
        return "<tr><td>" + esc(pick(r, "agent_name", "name", "agent") || "Agent") + '</td><td class="num">' + credits(earn) +
          '</td><td class="num">' + credits(cost) + '</td><td class="num">' + signedCredits(net) +
          '</td><td><span class="verdict ' + esc(verdict) + '">' + esc(verdict) + "</span></td></tr>";
      }).join("");
      openPayroll();
      setTimeout(closePayroll, 12000);
    }
  }
  // Click anywhere (backdrop or card) dismisses; Esc is native in modal mode.
  $("payroll-overlay").addEventListener("click", closePayroll);

  /* ---------- event handling ---------- */
  var NAME_BY_ID = {};
  function refreshNames() {
    NAME_BY_ID = {};
    state.agents.forEach(function (a) { NAME_BY_ID[agentId(a)] = pick(a, "name") || agentId(a); });
  }
  function nameOf(p) {
    var n = pick(p, "agent_name", "name");
    if (n) return String(n);
    var id = pick(p, "agent_id", "agent");
    if (id && NAME_BY_ID[String(id)]) return NAME_BY_ID[String(id)];
    return id ? String(id) : "An agent";
  }
  function jobTitleOf(p) {
    return pick(p, "job_title", "title") || (pick(p, "job_id") ? "job " + pick(p, "job_id") : "a job");
  }
  function upsertJob(patch) {
    if (!patch || typeof patch !== "object") return;
    var id = pick(patch, "id", "job_id");
    if (id === undefined) { loadSnapshot(); return; }
    for (var i = 0; i < state.jobs.length; i++) {
      if (String(pick(state.jobs[i], "id", "job_id")) === String(id)) {
        Object.keys(patch).forEach(function (k) { state.jobs[i][k] = patch[k]; });
        renderJobs();
        return;
      }
    }
    state.jobs.push(patch);
    renderJobs();
  }
  function upsertAgent(patch) {
    if (!patch || typeof patch !== "object") return;
    var id = pick(patch, "id", "agent_id", "name");
    if (id === undefined) { loadSnapshot(); return; }
    for (var i = 0; i < state.agents.length; i++) {
      if (agentId(state.agents[i]) === String(id)) {
        Object.keys(patch).forEach(function (k) { state.agents[i][k] = patch[k]; });
        refreshNames(); renderAgents();
        return;
      }
    }
    state.agents.push(patch);
    refreshNames(); renderAgents();
  }

  function handleEvent(ev) {
    if (!ev || typeof ev !== "object") return;
    var type = pick(ev, "type", "event") || "";
    var p = payloadOf(ev);
    var seq = Number(pick(ev, "seq", "id"));
    if (isFinite(seq) && seq > state.lastSeq) state.lastSeq = seq;
    var text = eventText(ev, p);

    switch (type) {
      case "job.posted":
        narrate(text || ("Manager posted \"" + jobTitleOf(p) + "\"" + (pick(p, "budget_credits", "budget") !== undefined ? " at " + credits(pick(p, "budget_credits", "budget")) : "")));
        upsertJob(Object.assign({}, p, { status: pick(p, "status") || "open" }));
        break;
      case "bid.placed": {
        var price = pick(p, "price_credits", "price", "amount");
        var conf = pick(p, "confidence", "conf");
        tickerAdd("<b>" + esc(nameOf(p)) + "</b> bids " + (price !== undefined ? credits(price) : "") +
          (conf !== undefined ? " (conf " + Number(conf).toFixed(2) + ")" : "") + " on \"" + esc(jobTitleOf(p)) + "\"");
        narrate(text || (nameOf(p) + " placed a sealed bid on \"" + jobTitleOf(p) + "\"."));
        // Attach the bid to its job card if we can identify the job.
        var jid = pick(p, "job_id", "job");
        if (jid !== undefined) {
          for (var i = 0; i < state.jobs.length; i++) {
            if (String(pick(state.jobs[i], "id", "job_id")) === String(jid)) {
              var bids = jobBids(state.jobs[i]).slice();
              bids.push(p);
              state.jobs[i].bids = bids;
              if (jobColumn(state.jobs[i]) === "open") state.jobs[i].status = "bidding";
              renderJobs();
              break;
            }
          }
        }
        break;
      }
      case "job.awarded":
        narrate(text || (nameOf(p) + " won \"" + jobTitleOf(p) + "\"."));
        if (pick(p, "job_id", "id") !== undefined) {
          upsertJob({ id: pick(p, "job_id", "id"), status: "awarded", winner: nameOf(p) });
        }
        break;
      case "tool.executed":
        narrate(text || (nameOf(p) + " ran tool " + (pick(p, "tool_name", "tool") || "") + " on \"" + jobTitleOf(p) + "\"."));
        break;
      case "work.submitted":
        narrate(text || (nameOf(p) + " submitted work on \"" + jobTitleOf(p) + "\" for review."));
        if (pick(p, "job_id", "id") !== undefined) upsertJob({ id: pick(p, "job_id", "id"), status: "in_review" });
        break;
      case "review.completed": {
        var verdict = pick(p, "verdict");
        var sev = pick(p, "severity");
        narrate(text || ("Review complete on \"" + jobTitleOf(p) + "\" — " + (verdict || "") + (sev ? " (" + sev + ")" : "") + "."));
        break;
      }
      case "appeal.filed":
        narrate(text || (nameOf(p) + " is appealing the rejection on \"" + jobTitleOf(p) + "\"…"), "appeal");
        break;
      case "appeal.decided": {
        var upheld = pick(p, "upheld", "overturned");
        var outcome = pick(p, "outcome", "verdict");
        var line = text || (String(outcome).toLowerCase() === "upheld" || upheld === true || String(outcome).toLowerCase() === "overturned"
          ? "APPEAL UPHELD — the worker is paid and the original Reviewer is penalised."
          : "Appeal denied — the rejection stands.");
        narrate(line, "appeal");
        break;
      }
      case "payment.made": {
        var amt = pick(p, "amount_credits", "amount");
        narrate(text || (nameOf(p) + " was paid " + (amt !== undefined ? credits(amt) : "") + " for \"" + jobTitleOf(p) + "\"."));
        var row = Object.assign({}, p);
        if (pick(row, "note", "reason") === undefined) row.note = "earning — " + jobTitleOf(p) + " accepted";
        state.ledger.push(row);
        renderLedger();
        break;
      }
      case "cycle.closed":
        narrate(text || "Payroll ran — the cycle is closed.");
        showPayroll(p);
        loadSnapshot();
        break;
      case "agent.fired": {
        var fid = pick(p, "agent_id", "id", "agent");
        if (fid !== undefined) state.firedIds[String(fid)] = true;
        narrate(text || ("PinkSlip: " + nameOf(p) + " has been fired by the CFO."), "pinkslip");
        prependFeed($("ledger-feed"), feedItem('<span class="why">PinkSlip — ' + esc(nameOf(p)) + " terminated</span>", "pinkslip"));
        upsertAgent(Object.assign({}, p, { id: fid, status: "fired" }));
        setTimeout(function () { state.firedIds = {}; renderAgents(); }, 2500);
        break;
      }
      case "agent.hired": {
        var hid = pick(p, "agent_id", "id", "agent");
        if (hid !== undefined) state.hireIds[String(hid)] = true;
        narrate(text || ("New hire: " + nameOf(p) + (pick(p, "mutation_note", "mutation") ? " — " + pick(p, "mutation_note", "mutation") : "") + "."), "hire");
        upsertAgent(Object.assign({}, p, { id: hid, status: "idle" }));
        setTimeout(function () { state.hireIds = {}; renderAgents(); }, 2500);
        break;
      }
      case "narration":
        narrate(text);
        break;
      default:
        if (text) narrate(text);
        break;
    }
  }

  /* ---------- snapshot loading ---------- */
  function fetchJSON(url) {
    return fetch(url, { headers: { "Accept": "application/json" } }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }
  function setConnected(ok) {
    state.connected = ok;
    var c = $("stat-conn");
    c.textContent = ok ? "live" : "offline — retrying";
    c.className = "stat-value conn" + (ok ? " ok" : "");
    $("waiting").classList.toggle("hidden", ok);
  }
  function loadSnapshot() {
    var got = { agents: false, jobs: false, ledger: false, events: false };
    function mark(k) { got[k] = true; if (got.agents || got.jobs || got.ledger) setConnected(true); }

    fetchJSON("/state/agents").then(function (d) {
      state.agents = asArray(d, ["agents", "items", "results"]);
      refreshNames(); renderAgents(); mark("agents");
      var cyc = d && !Array.isArray(d) ? pick(d, "cycle", "cycle_no", "current_cycle") : undefined;
      if (cyc !== undefined) $("stat-cycle").textContent = String(cyc);
    }).catch(function () {});

    fetchJSON("/state/jobs").then(function (d) {
      state.jobs = asArray(d, ["jobs", "items", "results"]);
      renderJobs(); mark("jobs");
    }).catch(function () {});

    fetchJSON("/state/ledger").then(function (d) {
      var rows = asArray(d, ["ledger", "entries", "items", "results"]);
      state.ledger = rows;
      renderLedger(); mark("ledger");
      if (d && !Array.isArray(d)) {
        var tot = pick(d, "total_paid", "paid_out", "total_paid_credits");
        if (tot !== undefined) $("stat-paid").textContent = credits(tot);
        var cyc2 = pick(d, "cycle", "cycle_no", "current_cycle");
        if (cyc2 !== undefined) $("stat-cycle").textContent = String(cyc2);
      }
    }).catch(function () {});

    fetchJSON("/state/events").then(function (d) {
      var evs = asArray(d, ["events", "items", "results"]);
      // Replay history into the narration log, oldest first.
      evs.slice(-60).forEach(function (ev) {
        var p = payloadOf(ev);
        var t = eventText(ev, p);
        if (t) narrate(t);
        var seq = Number(pick(ev, "seq", "id"));
        if (isFinite(seq) && seq > state.lastSeq) state.lastSeq = seq;
      });
      mark("events");
    }).catch(function () {});

    // If nothing at all answered after a grace period, show the waiting state.
    setTimeout(function () {
      if (!got.agents && !got.jobs && !got.ledger && !got.events) setConnected(false);
    }, 2500);
  }

  /* ---------- SSE ---------- */
  function connectSSE() {
    var es;
    try { es = new EventSource("/events"); } catch (e) { setTimeout(connectSSE, 5000); return; }
    es.onopen = function () { setConnected(true); };
    es.onmessage = function (m) {
      try { handleEvent(JSON.parse(m.data)); } catch (e) { /* ignore malformed frames */ }
    };
    // Named events: some servers emit `event: bid.placed` etc.
    ["job.posted", "bid.placed", "job.awarded", "tool.executed", "work.submitted",
     "review.completed", "appeal.filed", "appeal.decided", "payment.made",
     "cycle.closed", "agent.fired", "agent.hired", "narration",
     "tool.proposed", "tool.confirmation_requested", "system.tools_updated"
    ].forEach(function (t) {
      es.addEventListener(t, function (m) {
        try {
          var d = JSON.parse(m.data);
          if (!d.type) d.type = t;
          handleEvent(d);
        } catch (e) { /* ignore */ }
      });
    });
    es.onerror = function () {
      // EventSource auto-reconnects; only flag offline if it fully closes.
      if (es.readyState === EventSource.CLOSED) {
        setConnected(false);
        setTimeout(connectSSE, 5000);
      }
    };
  }

  /* ---------- actions ---------- */
  $("btn-run").addEventListener("click", function () {
    if (state.running) return;
    state.running = true;
    var btn = $("btn-run");
    btn.disabled = true;
    btn.textContent = "Shift running…";
    fetch("/run/shift", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json().catch(function () { return {}; });
      })
      .then(function () { toast("Shift complete."); loadSnapshot(); })
      .catch(function () { toast("Could not run the shift — is the factory API up?", true); })
      .then(function () {
        state.running = false;
        btn.disabled = false;
        btn.textContent = "Run Shift";
      });
  });

  $("btn-reset").addEventListener("click", function () {
    if (!window.confirm("Reset the demo to its exact seeded start state?")) return;
    fetch("/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        toast("Demo reset to the seeded start state.");
        state.firedIds = {}; state.hireIds = {};
        $("narration-log").innerHTML = '<span class="empty">The floor is quiet.</span>';
        $("ticker-track").innerHTML = '<span class="ticker-item muted">Bid ticker idle — waiting for the auction.</span>';
        $("ticker-track").classList.remove("scrolling");
        loadSnapshot();
      })
      .catch(function () { toast("Reset failed — is the factory API up?", true); });
  });

  /* ---------- boot ---------- */
  renderAgents(); renderJobs(); renderLedger();
  loadSnapshot();
  connectSSE();
  // Gentle retry loop while the API is down; cheap snapshot refresh otherwise.
  setInterval(function () { if (!state.connected) loadSnapshot(); }, 8000);
})();
