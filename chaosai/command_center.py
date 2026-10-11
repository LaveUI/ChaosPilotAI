"""Command-center dashboard page. The numbers are injected as JSON; this file only draws them."""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ChaosPilot AI — Resilience Command Center</title>
<style>
:root{
  --bg:#14110f;--side:#1c1714;--card:#241f1b;--card2:#2e2823;--line:#433a33;
  --ink:#f7f4f1;--muted:#b7aa9e;--blue:#e08a45;--blue2:#c56a2d;--green:#3ecf8e;
  --red:#e85d4c;--amber:#e6b15a;--purple:#c47ad4;--cyan:#e7c4a8;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);
  font:14px/1.45 "Segoe UI",system-ui,sans-serif}
button,input{font:inherit;color:inherit}
.app{display:flex;min-height:100vh}
aside{width:232px;flex:none;background:var(--side);border-right:1px solid var(--line);
  padding:18px 14px;display:flex;flex-direction:column;position:sticky;top:0;height:100vh}
.logo{display:flex;gap:10px;align-items:center;padding:0 8px 18px}
.logo b{display:block;font-size:15px}
.logo span{color:var(--muted);font-size:11px}
.mark{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#e08a45,#c45c6a);
  display:grid;place-items:center;font-weight:800;color:#fff}
nav button{width:100%;text-align:left;background:transparent;border:0;border-radius:10px;
  padding:10px 12px;margin:2px 0;color:var(--muted);cursor:pointer;display:flex;gap:10px;align-items:center}
nav button.on{background:var(--blue);color:#fff}
nav button:hover:not(.on){background:#2e2823;color:var(--ink)}
.workspace{flex:1;min-width:0;display:flex;flex-direction:column}
header{display:flex;justify-content:flex-end;align-items:center;gap:10px;padding:14px 22px;
  border-bottom:1px solid var(--line);position:sticky;top:0;background:#14110ee6;backdrop-filter:blur(8px);z-index:3}
.pill{border:1px solid var(--line);background:#2a241f;border-radius:999px;padding:6px 12px;font-size:12px;color:var(--muted)}
.pill.ok{background:#1a2e24;color:#8eebc0;border-color:#246b48}
.pill.warn{background:#3a2a1c;color:#f3d2a4;border-color:#8a5a32}
.iconbtn{width:34px;height:34px;border-radius:10px;border:1px solid var(--line);background:#2a241f;cursor:pointer;color:#fff}
.switch{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px}
.avatar{width:34px;height:34px;border-radius:50%;background:#c45c6a;display:grid;place-items:center;font-size:12px;font-weight:700;color:#fff}
main{padding:22px;max-width:1280px}
h1{font-size:28px;margin:0 0 4px}
.sub{color:var(--muted);margin:0 0 16px}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.kpi{display:flex;gap:12px;align-items:flex-start}
.ic{width:38px;height:38px;border-radius:10px;display:grid;place-items:center;flex:none}
.kpi .n{font-size:26px;font-weight:750;line-height:1}
.kpi .l{color:var(--muted);font-size:12px}
.delta{font-size:12px;margin-top:4px}
.up{color:var(--green)}.down{color:var(--red)}.flat{color:var(--muted)}
.bar{height:6px;border-radius:99px;background:#1c1714;margin-top:8px;overflow:hidden}
.bar span{display:block;height:100%;background:var(--green)}
.topgrid{display:grid;grid-template-columns:1.35fr .9fr .82fr;gap:14px;margin-top:14px}
.midgrid{display:grid;grid-template-columns:1.25fr .85fr;gap:14px;margin-top:14px}
.foot{display:grid;grid-template-columns:.8fr 1fr 1fr .9fr;gap:14px;margin-top:14px}
h2{font-size:15px;margin:0 0 8px}
.muted{color:var(--muted)}
.row{display:flex;justify-content:space-between;gap:8px;align-items:center}
.tag{font-size:11px;border-radius:99px;padding:2px 8px;font-weight:700}
.tag.bad{background:#3d221c;color:#ffb4a8}.tag.warn{background:#3a2a1c;color:#f3d2a4}
.tag.ok{background:#1a2e24;color:#8eebc0}.tag.mid{background:#322c27;color:#ddd4cb}
.svc-name{font-weight:700;font-size:16px}
.meta{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}
.meta div{background:var(--card2);border-radius:10px;padding:8px 10px}
.meta b{display:block;font-size:13px}
.btn{display:inline-block;background:var(--blue);color:#fff;border:0;border-radius:8px;padding:8px 12px;
  cursor:pointer;margin-top:10px}
.btn.ghost{background:transparent;border:1px solid var(--line);color:var(--ink)}
.legend{display:flex;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin-top:8px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px}
.recent{display:flex;gap:10px;align-items:center;padding:8px 0;border-top:1px solid var(--line)}
.recent:first-of-type{border-top:0}
.mapsvg{width:100%;height:auto;display:block}
.node{cursor:pointer}
.hint{display:none;color:#e7c4a8;font-size:12px;margin-top:6px}
body.beginner .hint{display:block}
.rec{display:flex;gap:10px;align-items:center;padding:10px 0;border-top:1px solid var(--line)}
.num{width:22px;height:22px;border-radius:50%;background:#6b3a28;display:grid;place-items:center;font-size:12px;flex:none;color:#fff}
.tip{background:linear-gradient(180deg,#6b3a28,#3d241c);border-color:#c45c6a}
.gridcards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.phases{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:10px 0}
.phases div{background:var(--card2);border-radius:10px;padding:8px}
pre{background:#1a1613;border:1px solid var(--line);border-radius:8px;padding:10px;overflow:auto;font-size:12px;color:#f7f4f1}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--muted);font-weight:600;padding:8px;border-bottom:1px solid var(--line)}
td{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}
.modal{position:fixed;inset:0;background:#0008;display:none;place-items:center;z-index:5}
.modal.show{display:grid}
.modal .card{width:min(440px,92vw)}
@media(max-width:980px){
  .kpis{grid-template-columns:1fr 1fr}
  .topgrid,.midgrid,.foot{grid-template-columns:1fr}
}
@media(max-width:760px){
  aside{position:relative;height:auto;width:100%}
  .app{flex-direction:column}
  .kpis,.phases{grid-template-columns:1fr}
}
</style>
</head>
<body>
<div class="app">
<aside>
  <div class="logo"><div class="mark">C</div><div><b>ChaosPilot AI</b><span>Resilience Command Center</span></div></div>
  <nav id="nav"></nav>
</aside>
<div class="workspace">
<header id="head"></header>
<main id="view"></main>
</div>
</div>
<div class="modal" id="modal"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById("data").textContent);
const VIEWS = [
  ["overview","Overview"],["services","Service Explorer"],["lab","Experiment Lab"],
  ["investigate","AI Investigation"],["fixes","Fix Recommendations"],
  ["history","Reports & History"],["help","Help & Documentation"]
];
let selected = (D.experiments[0] && D.experiments[0].service) || (D.services[0] && D.services[0].name);
let beginner = localStorage.getItem("cp-beginner");
beginner = beginner === null ? true : beginner === "1";
if (beginner) document.body.classList.add("beginner");

function esc(s){return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));}
function svc(name){return D.services.find(s => s.name === name);}
function sevColor(s){return {critical:"#e85d4c",high:"#e08a45",medium:"#e6b15a",low:"#c47ad4",none:"#3ecf8e",untested:"#8a7e74"}[s] || "#8a7e74";}
function sevLabel(s){return {critical:"Unhealthy",high:"Degraded",medium:"Degraded",low:"Watch",none:"Healthy",untested:"Not tested"}[s] || s;}
function outcome(e){
  if (e.aborted || e.severity === "critical") return ["Failed","bad"];
  if (e.severity === "none") return ["Passed","ok"];
  return ["Degraded","warn"];
}
function pct(n){return n == null ? "n/a" : Math.round(n * 1000) / 10 + "%";}
function ms(n){return n == null ? "n/a" : Math.round(n) + " ms";}
function go(v){location.hash = v;}

function header(){
  const sim = D.env === "simulated";
  document.getElementById("head").innerHTML =
    (sim ? '<span class="pill warn">Demo Mode (Simulation)</span><span class="pill">Kubernetes not connected</span>'
         : '<span class="pill ok">Live cluster</span><span class="pill ok">Namespace ' + esc(D.namespace) + '</span>') +
    '<button class="iconbtn" id="settings" title="Safety limits">&#9881;</button>' +
    '<label class="switch">Beginner Mode <input type="checkbox" id="beg"' + (beginner ? " checked" : "") + '></label>' +
    '<div class="avatar" title="ChaosPilot">CP</div>';
  document.getElementById("beg").onchange = (ev) => {
    beginner = ev.target.checked;
    document.body.classList.toggle("beginner", beginner);
    localStorage.setItem("cp-beginner", beginner ? "1" : "0");
  };
  document.getElementById("settings").onclick = openSettings;
}
function nav(){
  const cur = (location.hash || "#overview").slice(1);
  document.getElementById("nav").innerHTML = VIEWS.map(([id,label]) =>
    '<button data-go="' + id + '"' + (id === cur ? ' class="on"' : "") + '>' + esc(label) + '</button>').join("");
}

function kpi(icon, color, label, value, extra){
  return '<div class="card kpi"><div class="ic" style="background:' + color + '22;color:' + color + '">' + icon + '</div><div><div class="l">' + label + '</div><div class="n">' + value + '</div>' + extra + '</div></div>';
}
function delta(n, suffix){
  if (n == null) return '<div class="delta flat">No earlier run</div>';
  const cls = n > 0 ? "up" : n < 0 ? "down" : "flat";
  const sign = n > 0 ? "+" : "";
  return '<div class="delta ' + cls + '">' + sign + n + suffix + '</div>';
}

function overview(){
  const s = svc(selected) || D.services[0];
  const tested = D.services.filter(x => x.tested).length;
  const healthyPct = D.service_total ? Math.round(100 * D.healthy_count / D.service_total) : 0;
  const dcls = (D.delta || 0) > 0 ? "up" : (D.delta || 0) < 0 ? "down" : "flat";
  const dsign = (D.delta || 0) > 0 ? "+" : "";
  let html = '<h1>Overview</h1><p class="sub">Monitor application health, run chaos experiments, and improve resilience with AI.</p>';
  html += '<div class="kpis">';
  html += kpi("&#128737;", "#e08a45", "Resilience Score", esc(D.score) + ' <span style="font-size:14px;color:var(--muted)">/ 100</span>',
    '<div class="delta ' + dcls + '">' + dsign + (D.delta == null ? "0" : D.delta) + ' vs previous run</div>');
  html += kpi("&#9632;", "#3ecf8e", "Confirmed healthy", D.healthy_count + " / " + D.service_total,
    '<div class="bar"><span style="width:' + healthyPct + '%"></span></div><div class="delta flat">' + tested + ' tested, ' + D.untested_count + ' not tested</div>');
  html += kpi("&#9888;", "#e85d4c", "Weaknesses found", D.weakness_count, delta(D.weak_delta, " vs previous run"));
  html += kpi("&#129514;", "#c47ad4", "Experiments run", D.n_experiments,
    '<div class="delta flat">' + D.n_runs + ' saved run(s)</div>');
  html += '</div>';
  html += '<div class="topgrid"><div class="card">' + mapCard() + '</div><div class="card">' + inspector(s) + '</div><div>' + sideCol() + '</div></div>';
  html += '<div class="midgrid"><div class="card">' + chartCard() + '</div><div class="card">' + suggestedCard() + '</div></div>';
  html += '<div class="foot">' + tipCard() + findingCard() + fixCard() + safetyCard() + '</div>';
  return html;
}

function mapCard(){
  const pos = {};
  D.services.forEach((s,i) => { pos[s.name] = s.pos || [80 + (i % 4) * 140, 50 + Math.floor(i / 4) * 90]; });
  const vb = "0 0 640 390";
  let edges = "";
  D.edges.forEach(e => {
    if (!pos[e.from] || !pos[e.to]) return;
    const [x1,y1] = pos[e.from], [x2,y2] = pos[e.to];
    edges += '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '" stroke="#5c5148" stroke-width="1.4" marker-end="url(#arr)"/>';
  });
  let nodes = "";
  D.services.forEach(s => {
    const [x,y] = pos[s.name];
    const c = sevColor(s.severity);
    const on = s.name === selected ? ' stroke="#fff" stroke-width="2"' : ' stroke="' + c + '" stroke-width="1.2"';
    nodes += '<g class="node" data-svc="' + esc(s.name) + '"><polygon points="' + hex(x,y,22) + '" fill="#1c1714"' + on + '/>' +
      '<circle cx="' + x + '" cy="' + y + '" r="5" fill="' + c + '"/>' +
      '<text x="' + x + '" y="' + (y + 36) + '" text-anchor="middle" fill="#f7f4f1" font-size="11">' + esc(s.name) + '</text></g>';
  });
  return '<div class="row"><h2>Microservice dependency map</h2></div>' +
    '<p class="muted" style="margin:0 0 6px">Click a service to see what the latest run measured. Grey means not tested yet.</p>' +
    '<svg class="mapsvg" viewBox="' + vb + '" role="img" aria-label="Dependency map">' +
    '<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8a7e74"/></marker></defs>' +
    edges + nodes + '</svg>' +
    '<div class="legend"><span><i class="dot" style="background:#3ecf8e"></i>Healthy</span>' +
    '<span><i class="dot" style="background:#e08a45"></i>Degraded</span>' +
    '<span><i class="dot" style="background:#e85d4c"></i>Unhealthy</span>' +
    '<span><i class="dot" style="background:#8a7e74"></i>Not tested</span></div>' +
    '<div class="hint">Arrows point from a caller to the service it calls. Colour is the worst result in the latest run.</div>';
}
function hex(x,y,r){
  const pts = [];
  for (let i = 0; i < 6; i++){
    const a = Math.PI / 6 + i * Math.PI / 3;
    pts.push((x + r * Math.cos(a)).toFixed(1) + "," + (y + r * Math.sin(a)).toFixed(1));
  }
  return pts.join(" ");
}
function inspector(s){
  if (!s) return "<h2>No services</h2>";
  const calls = (s.depends_on || []).join(", ") || "none";
  const callers = (s.called_by || []).join(", ") || "none";
  return '<div class="row"><div class="svc-name">' + esc(s.name) + '</div><span class="tag ' + (s.severity === "critical" ? "bad" : s.severity === "none" ? "ok" : s.tested ? "warn" : "mid") + '">' + sevLabel(s.severity) + '</span></div>' +
    '<p class="muted">' + esc(s.role) + '</p>' +
    '<p><b>Calls:</b> ' + esc(calls) + '</p><p><b>Called by:</b> ' + esc(callers) + '</p>' +
    '<div class="meta"><div><span class="muted">Replicas</span><b>' + esc(s.replicas) + ' in the manifest</b></div>' +
    '<div><span class="muted">Dependents</span><b>' + s.dependents + '</b></div>' +
    '<div><span class="muted">Latest score</span><b>' + (s.tested ? esc(s.score) : "not tested") + '</b></div>' +
    '<div><span class="muted">During the fault</span><b>' + (s.tested ? (pct(s.error_rate) + " errors, p95 " + ms(s.p95_ms)) : "n/a") + '</b></div></div>' +
    (s.tested ? '<button class="btn" data-go="lab">View this experiment</button>' : '<p class="hint">This service has not been targeted yet. See Fix Recommendations and the suggested experiments.</p>') +
    '<div class="hint">Replica count comes from the Kubernetes manifest, not a live pod listing. This run was ' + esc(D.env) + '.</div>';
}
function sideCol(){
  const sim = D.env === "simulated";
  let recent = D.experiments.map(e => {
    const oc = outcome(e);
    return '<div class="recent"><div><b>' + esc(e.action) + '</b><div class="muted">' + esc(e.service) + '</div></div>' +
      '<span class="tag ' + oc[1] + '">' + oc[0] + '</span></div>';
  }).join("");
  return '<div class="card"><div class="row"><h2 style="margin:0">Current run status</h2><span class="tag ' + (sim ? "warn" : "ok") + '">' + (sim ? "Simulated" : "Live") + '</span></div>' +
    '<p><b>Namespace</b><br><span class="muted">' + esc(D.namespace) + '</span></p>' +
    '<p><b>Decisions</b><br><span class="muted">' + esc(D.planner) + (D.model ? " (" + esc(D.model) + ")" : "") + '</span></p>' +
    '<p><b>Allowed faults</b><br><span class="muted">' + esc(D.allowlist.join(", ")) + '</span></p>' +
    '<p class="muted">' + (sim ? "These numbers are from the offline simulator, not a connected cluster." : "Measured against the connected cluster.") + '</p>' +
    '<div class="hint">ChaosPilot records the run mode on each results file. A simulated run cannot show a real Kubernetes version or Chaos Mesh status.</div></div>' +
    '<div class="card" style="margin-top:14px"><div class="row"><h2 style="margin:0">Recent experiments</h2><button class="btn ghost" data-go="lab" style="margin:0">View all</button></div>' + recent + '</div>';
}
function chartCard(){
  const pts = D.chart || [];
  if (pts.length < 2) return "<h2>Probe latency</h2><p class='muted'>Not enough samples to draw a chart.</p>";
  const w = 640, h = 220, l = 36, r = 10, t = 16, b = 28;
  const maxT = pts[pts.length - 1].t, maxL = Math.max(200, ...pts.map(p => p.lat));
  const x = v => l + (w - l - r) * (v / maxT);
  const y = v => t + (h - t - b) * (1 - v / maxL);
  let d = "", err = "";
  pts.forEach((p,i) => {
    d += (i ? "L" : "M") + x(p.t).toFixed(1) + "," + y(p.lat).toFixed(1) + " ";
    if (!p.ok) err += '<circle cx="' + x(p.t).toFixed(1) + '" cy="' + y(p.lat).toFixed(1) + '" r="2.2" fill="#e85d4c"/>';
  });
  let bands = "";
  (D.bands || []).forEach(bn => {
    if (bn.phase !== "during") return;
    const x1 = x(bn.start), x2 = x(bn.end);
    bands += '<rect x="' + x1.toFixed(1) + '" y="' + t + '" width="' + Math.max(0, x2 - x1).toFixed(1) + '" height="' + (h - t - b) + '" fill="#e08a4533"/>';
  });
  return '<h2>Probe latency in the latest run</h2><p class="muted" style="margin-top:0">Each point is one request. Purple bands are while a fault was injected. Red dots are failed requests. CPU is not measured by the probe.</p>' +
    '<svg viewBox="0 0 ' + w + ' ' + h + '" style="width:100%;height:auto">' + bands +
    '<line x1="' + l + '" y1="' + (h - b) + '" x2="' + (w - r) + '" y2="' + (h - b) + '" stroke="#433a33"/>' +
    '<polyline fill="none" stroke="#e08a45" stroke-width="2" points="' + pts.map(p => x(p.t).toFixed(1) + "," + y(p.lat).toFixed(1)).join(" ") + '"/>' + err +
    '<text x="' + l + '" y="12" fill="#b7aa9e" font-size="11">ms</text></svg>' +
    '<div class="hint">The line is request latency, not a p95 trend across days. Saved runs of this project repeated the same three experiments, so a day-by-day score chart would be flat.</div>';
}
function suggestedCard(){
  const rows = (D.suggested || []).map((s,i) =>
    '<div class="rec"><div class="num">' + (i + 1) + '</div><div style="flex:1"><b>' + esc(s.service) + '</b><div class="muted">' + esc(s.action) + ' · ' + esc(s.reason) + '</div></div>' +
    '<span class="tag ' + (s.risk === "High" ? "bad" : s.risk === "Low" ? "ok" : "warn") + '">' + esc(s.risk) + ' risk</span>' +
    '<button class="btn ghost" style="margin:0" data-cmd="' + esc(s.command) + '">How to run</button></div>').join("");
  return '<h2>Suggested next experiments</h2><p class="muted" style="margin-top:0">Services not targeted in the latest run, highest blast radius first. Risk uses replica count and how many services depend on it.</p>' +
    (rows || '<p class="muted">Every service in the map was already targeted.</p>') +
    '<div class="hint">The Run button in the design mock cannot inject a fault from the browser. Use the command in a terminal in the project folder.</div>';
}
function tipCard(){
  return '<div class="card tip"><h2>New to chaos engineering?</h2><p>Chaos engineering injects a controlled fault, watches errors and latency, then checks that the app recovers.</p><button class="btn" data-go="help" style="background:#f7f4f1;color:#2a1c14">Get started</button></div>';
}
function findingCard(){
  const e = D.experiments.slice().sort((a,b) => a.rank - b.rank)[0];
  if (!e) return '<div class="card"><h2>Latest finding</h2><p>No experiments.</p></div>';
  return '<div class="card"><div class="row"><h2 style="margin:0">Latest AI finding</h2><span class="tag bad">' + esc(e.severity) + '</span></div>' +
    '<p><b>' + esc(e.service) + '</b> · ' + esc(e.action) + '</p><p class="muted">' + esc(e.what) + '</p>' +
    '<button class="btn ghost" data-go="investigate">View full investigation</button>' +
    '<div class="hint">' + esc(D.summary_source) + '</div></div>';
}
function fixCard(){
  const f = D.fixes[0];
  if (!f) return '<div class="card"><h2>Top fix</h2><p class="muted">No fix recommended.</p></div>';
  return '<div class="card"><div class="row"><h2 style="margin:0">Top fix recommendation</h2><span class="tag warn">' + esc(f.effort) + '</span></div>' +
    '<p><b>' + esc(f.title) + '</b></p><p class="muted">' + esc(f.detail) + '</p>' +
    '<button class="btn ghost" data-go="fixes">View implementation guide</button></div>';
}
function safetyCard(){
  const bad = D.abort_count > 0 || D.stop_active;
  const items = [
    "Error-rate limit " + pct(D.limits.max_error_rate),
    "p95 limit " + (D.limits.p95_limit_ms || "?") + " ms",
    "Blast radius " + (D.limits.max_extra_unhealthy_pods || "?") + " extra pods",
    D.abort_count ? D.abort_count + " experiment(s) aborted by the guard" : "No aborts in saved runs"
  ];
  return '<div class="card"><div class="row"><h2 style="margin:0">Safety status</h2><span class="tag ' + (bad ? "warn" : "ok") + '">' + (D.stop_active ? "Stop switch on" : bad ? "Guard fired" : "Within limits") + '</span></div><ul>' +
    items.map(t => "<li>" + esc(t) + "</li>").join("") + "</ul></div>";
}

function servicesView(){
  const cards = D.services.map(s =>
    '<button class="card" data-svc="' + esc(s.name) + '" style="text-align:left;cursor:pointer">' +
    '<div class="row"><b>' + esc(s.name) + '</b><span class="tag ' + (s.severity === "critical" ? "bad" : s.tested ? "warn" : "mid") + '">' + sevLabel(s.severity) + '</span></div>' +
    '<p class="muted">' + esc(s.role) + '</p><p>' + s.replicas + ' replica(s) · ' + s.dependents + ' dependents</p></button>').join("");
  return '<h1>Service Explorer</h1><p class="sub">Every service from the dependency graph except the load generator.</p><div class="gridcards">' + cards + '</div><div class="card" style="margin-top:14px">' + inspector(svc(selected)) + '</div>';
}
function labView(){
  const blocks = D.experiments.map(e => {
    const oc = outcome(e);
    const phases = ["before","during","recovery","after"].map(p => {
      const m = (e.phases || {})[p] || {};
      return '<div><div class="muted">' + p + '</div><b>' + pct(m.error_rate) + '</b><div class="muted">p95 ' + ms(m.p95_ms) + '</div></div>';
    }).join("");
    return '<div class="card" id="' + esc(e.id) + '" style="margin-bottom:12px"><div class="row"><div><span class="tag ' + oc[1] + '">' + oc[0] + '</span> <b>' + esc(e.action) + ' on ' + esc(e.service) + '</b></div><b>' + esc(e.score) + '/100</b></div>' +
      '<p class="muted">Why it was chosen: ' + esc(e.rationale) + '</p><div class="phases">' + phases + '</div>' +
      '<p>' + esc(e.what) + '</p></div>';
  }).join("");
  return '<h1>Experiment Lab</h1><p class="sub">Latest run ' + esc(D.run_id) + '. Phase numbers are what the probe measured.</p>' + blocks;
}
function investigateView(){
  const blocks = D.experiments.map(e =>
    '<div class="card" style="margin-bottom:12px"><div class="row"><h2 style="margin:0">' + esc(e.service) + '</h2><span class="tag bad">' + esc(e.severity) + '</span></div>' +
    '<p><b>What happened.</b> ' + esc(e.what) + '</p><p><b>Why it matters.</b> ' + esc(e.why) + '</p><p><b>Likely cause.</b> ' + esc(e.cause) + '</p>' +
    '<p class="muted">Severity: ' + esc((e.reasons || []).join("; ")) + '</p></div>').join("");
  return '<h1>AI Investigation</h1><p class="sub">' + esc(D.summary_source) + '</p><div class="card" style="margin-bottom:12px"><p>' + esc(D.summary) + '</p></div>' + blocks;
}
function fixesView(){
  const blocks = D.fixes.map((f,i) =>
    '<div class="card" style="margin-bottom:12px"><div class="row"><b>' + (i + 1) + '. ' + esc(f.title) + '</b><span class="tag warn">' + esc(f.severity) + '</span></div>' +
    '<p class="muted">' + esc(f.detail) + '</p><p><b>Addresses:</b> ' + esc(f.addresses) + ' · <b>Effort:</b> ' + esc(f.effort) + ' · <b>Potential:</b> up to +' + f.gain + ' on the score</p>' +
    (f.added ? '<p class="hint" style="display:block">Suggested from measurements: the analyzer only writes a fix when the score is under 90.</p>' : '') +
    (f.snippet ? '<pre>' + esc(f.snippet) + '</pre>' : '') + '</div>').join("");
  return '<h1>Fix Recommendations</h1><p class="sub">Highest severity first. Snippets are starting points, not applied changes.</p>' + (blocks || '<div class="card">No fixes.</div>');
}
function historyView(){
  const rows = D.runs.map(r => '<tr><td>' + esc(r.run_id) + '</td><td>' + esc(r.env) + '</td><td>' + esc(r.planner) + '</td><td>' + r.n + '</td><td>' + r.aborts + '</td><td><b>' + esc(r.score) + '</b></td></tr>').join("");
  return '<h1>Reports & History</h1><p class="sub">Every saved run under runs/. The score is the mean of that run\'s experiments.</p><div class="card"><table><tr><th>Run</th><th>Environment</th><th>Decisions</th><th>Experiments</th><th>Aborts</th><th>Score</th></tr>' + rows + '</table></div>';
}
function helpView(){
  return '<h1>Help</h1><p class="sub">How this project produces the numbers on the Overview.</p>' +
    '<div class="card"><h2>What a run does</h2><ol><li>Map which service calls which.</li><li>Measure a baseline with no fault.</li><li>Inject one allowlisted fault at a time.</li><li>Probe the frontend for errors and latency.</li><li>Remove the fault and score recovery.</li></ol>' +
    '<p>The safety guard aborts a fault if the rolling error rate, p95 latency, or blast radius crosses the limit in config.yaml.</p>' +
    '<pre>python -m chaosai map\npython -m chaosai baseline --sim\npython -m chaosai agent --sim --rounds 3\npython -m chaosai dashboard\npython -m chaosai kill</pre>' +
    '<p class="muted">Never targeted: ' + esc((D.exclude || []).join(", ")) + '. Kill switch: create runs/STOP, press Ctrl+C, or run chaosai kill.</p></div>';
}

const PAGES = {overview, services: servicesView, lab: labView, investigate: investigateView, fixes: fixesView, history: historyView, help: helpView};
function render(){
  const id = (location.hash || "#overview").slice(1);
  const fn = PAGES[id] || overview;
  nav();
  document.getElementById("view").innerHTML = fn();
}
function openSettings(){
  const m = document.getElementById("modal");
  m.className = "modal show";
  m.innerHTML = '<div class="card"><h2>Limits enforced by code</h2><ul><li>Abort if rolling error rate exceeds ' + pct(D.limits.max_error_rate) + '</li>' +
    '<li>Abort if rolling p95 exceeds ' + esc(D.limits.p95_limit_ms) + ' ms</li>' +
    '<li>Abort if more than ' + esc(D.limits.max_extra_unhealthy_pods) + ' extra pods become unhealthy</li></ul>' +
    '<p class="muted">Run ' + esc(D.run_id) + '</p><button class="btn" id="close">Close</button></div>';
  document.getElementById("close").onclick = () => { m.className = "modal"; };
  m.onclick = (ev) => { if (ev.target === m) m.className = "modal"; };
}
document.body.addEventListener("click", (ev) => {
  const goBtn = ev.target.closest("[data-go]");
  if (goBtn){ go(goBtn.dataset.go); return; }
  const node = ev.target.closest("[data-svc]");
  if (node){ selected = node.dataset.svc; render(); return; }
  const cmd = ev.target.closest("[data-cmd]");
  if (cmd){ alert("From the project folder:\n\n" + cmd.dataset.cmd); }
});
window.addEventListener("hashchange", render);
header();
render();
</script>
</body>
</html>
"""


def render_page(data):
    blob = json_dumps(data)
    return PAGE.replace("__DATA__", blob)


def json_dumps(data):
    import json
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
