"""Self-contained HTML report (no external assets) with before/after comparison."""
import html

CSS = """
:root{--bg:#f7f5fa;--ink:#201c2b;--muted:#6b6578;--card:#fff;--line:#d9d3e3;--pink:#d4146a;--teal:#00849e;--good:#1a7f4b;--warn:#b7791f;--bad:#c0262d}
@media(prefers-color-scheme:dark){:root{--bg:#15121c;--ink:#efeaf7;--muted:#a59db5;--card:#1f1b2a;--line:#3a3449;--pink:#ff4d97;--teal:#3cc3dc;--good:#4cc38a;--warn:#e0a84a;--bad:#ff6b6f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:960px;margin:0 auto;padding:28px 18px 60px}h1{font-size:28px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 10px}
.muted{color:var(--muted)}.hero{display:flex;gap:24px;align-items:center;flex-wrap:wrap;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px}
.big{font-size:56px;font-weight:700;line-height:1}.delta{font-size:20px;font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}
.row{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:baseline}
.pill{display:inline-block;padding:1px 9px;border-radius:99px;border:1px solid var(--line);font-size:12px}
.pill.abort{border-color:var(--pink);color:var(--pink)}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
.scroll{overflow-x:auto}svg{max-width:100%;height:auto}ul{margin:6px 0 0;padding-left:20px}
"""


def _color(score):
    return "var(--good)" if score >= 80 else "var(--warn)" if score >= 60 else "var(--bad)"


def timeline_svg(samples, w=560, h=96):
    if not samples:
        return ""
    tmax = max(s[0] for s in samples) or 1
    lmax = max(max(s[2] for s in samples), 1)
    x = lambda t: 8 + (w - 16) * t / tmax
    y = lambda ms: h - 14 - (h - 28) * min(ms, lmax) / lmax
    chaos_end = max((s[0] for s in samples if s[3] == "chaos"), default=0)
    pts = " ".join(f"{x(s[0]):.1f},{y(s[2]):.1f}" for s in samples if s[1])
    errs = "".join(f'<circle cx="{x(s[0]):.1f}" cy="{h - 8}" r="2.6" fill="var(--bad)"/>' for s in samples if not s[1])
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Latency and errors over time">'
            f'<rect x="{x(0):.1f}" y="2" width="{x(chaos_end) - x(0):.1f}" height="{h - 4}" fill="var(--pink)" opacity="0.10"/>'
            f'<polyline points="{pts}" fill="none" stroke="var(--teal)" stroke-width="1.6"/>{errs}'
            f'<text x="10" y="12" font-size="10" fill="var(--muted)">latency (max {lmax} ms); red dots = failed requests; shaded = fault active</text></svg>')


def render(results, graph, previous=None):
    e = html.escape
    score = results["resilience_score"]
    prev_score = previous["resilience_score"] if previous else None
    prev_by = {(p["service"], p["action"]): p for p in previous["experiments"]} if previous else {}

    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Resilience report {e(results['run_id'])}</title><style>{CSS}</style></head><body><main>",
             "<h1>Resilience report</h1>",
             f"<div class='muted'>Run {e(results['run_id'])} &middot; environment: {e(results['env'])} &middot; planner: {e(results['planner'])}</div>"]

    delta = ""
    if prev_score is not None:
        d = round(score - prev_score, 1)
        delta = f"<div class='delta' style='color:{'var(--good)' if d >= 0 else 'var(--bad)'}'>{'+' if d >= 0 else ''}{d} vs run {e(previous['run_id'])} ({prev_score})</div>"
    parts.append(f"<div class='hero' style='margin-top:16px'><div class='big' style='color:{_color(score)}'>{score}</div>"
                 f"<div><div><b>Resilience score</b> out of 100</div>{delta}"
                 f"<div class='muted'>Baseline: {results['baseline']['error_rate']:.1%} errors, p95 {results['baseline']['p95_ms']:.0f} ms</div></div></div>")
    if results.get("summary"):
        parts.append(f"<div class='card'><b>Summary</b><p>{e(results['summary'])}</p></div>")

    parts.append("<h2>Experiments, weakest first</h2><div class='scroll'><table><tr><th>Service</th><th>Fault</th><th>Score</th>"
                 "<th>Errors</th><th>p95</th><th>Recovery</th>" + ("<th>Before</th>" if previous else "") + "</tr>")
    for x in sorted(results["experiments"], key=lambda x: x["score"]):
        rec = f"{x['recovery_s']}s" if x["recovered"] else "none"
        before = ""
        if previous:
            p = prev_by.get((x["service"], x["action"]))
            before = f"<td>{p['score']}</td>" if p else "<td>-</td>"
        parts.append(f"<tr><td>{e(x['service'])}</td><td>{e(x['action'])}</td><td style='color:{_color(x['score'])}'><b>{x['score']}</b></td>"
                     f"<td>{x['error_rate']:.0%}</td><td>{x['p95_ms']} ms</td><td>{rec}</td>{before}</tr>")
    parts.append("</table></div>")

    parts.append("<h2>Details</h2>")
    for x in results["experiments"]:
        abort = f"<span class='pill abort'>aborted: {e(x['abort_reason'])}</span>" if x["aborted"] else ""
        parts.append(f"<div class='card'><div class='row'><b>{e(x['action'])} on {e(x['service'])}</b> {abort}"
                     f"<span style='color:{_color(x['score'])}'><b>{x['score']}</b>/100</span></div>"
                     f"<p class='muted' style='margin:4px 0 8px'>Why this test: {e(x['rationale'])}</p>"
                     f"{timeline_svg(x['samples'])}"
                     f"<div class='muted'>Penalties: errors -{x['breakdown']['errors']}, latency -{x['breakdown']['latency']}, "
                     f"recovery -{x['breakdown']['recovery']}, abort -{x['breakdown']['abort']}"
                     + (f". Kill switch removed the fault in {x['abort_latency_s']}s" if x["aborted"] else "") + "</div>")
        if x["recommendations"]:
            parts.append("<b>Recommended fixes</b><ul>" + "".join(
                f"<li><b>{e(r['title'])}</b>. {e(r['detail'])}</li>" for r in x["recommendations"]) + "</ul>")
        else:
            parts.append("<div style='color:var(--good)'>No action needed.</div>")
        parts.append("</div>")

    parts.append("<h2>Dependency map</h2><div class='scroll'><table><tr><th>Service</th><th>Calls</th><th>Called by</th><th>Replicas</th></tr>")
    for n in graph["nodes"]:
        parts.append(f"<tr><td>{e(n['name'])}</td><td>{e(', '.join(n['depends_on']) or '-')}</td>"
                     f"<td>{e(', '.join(n['depended_by']) or '-')}</td><td>{n['replicas']}</td></tr>")
    parts.append("</table></div></main></body></html>")
    return "".join(parts)
