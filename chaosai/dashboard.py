"""Resilience command center: one HTML app built from every run in runs/.

Measurements, severities and scores are calculated here. Gemini, when available, only
writes the plain-language summary and per-experiment explanations.
"""
import glob
import json
import os
from collections import deque

from . import llm
from .report import _number

SEVERITY_ORDER = ["critical", "high", "medium", "low", "none"]
SEVERITY_LABEL = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low", "none": "Resilient"}
SEVERITY_COLOR = {"critical": "#fb7185", "high": "#fb923c", "medium": "#f4b860", "low": "#69a9ff",
                  "none": "#43d6b0", "untested": "#4b5873"}
WEAK_BELOW, RESILIENT_FROM = 50, 90
# Traffic sources are not real dependents when measuring blast radius
NON_SERVICES = {"loadgenerator"}



# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_runs(runs_dir):
    runs = []
    for path in sorted(glob.glob(os.path.join(runs_dir, "*", "results.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                r = json.load(f)
        except (OSError, ValueError):
            continue
        if r.get("experiments"):
            runs.append(r)
    runs.sort(key=lambda r: r.get("run_id", ""))
    return runs


# ---------------------------------------------------------------------------
# Analysis (all calculated from measurements, no AI)
# ---------------------------------------------------------------------------

def _nodes(graph):
    return {n["name"]: n for n in (graph or {}).get("nodes", [])}


def upstream(graph, service):
    """Every service that directly or indirectly depends on `service`."""
    nodes = _nodes(graph)
    seen, queue = set(), deque([service])
    while queue:
        for parent in nodes.get(queue.popleft(), {}).get("depended_by", []):
            if parent not in seen:
                seen.add(parent)
                queue.append(parent)
    return sorted(seen - NON_SERVICES)


def all_failed(exp):
    during = (exp.get("phase_metrics") or {}).get("during") or {}
    if during.get("samples"):
        return during.get("successful_requests") == 0
    return (_number(exp.get("error_rate")) or 0) >= 0.999


def latency_ratio(exp, baseline):
    """p95 during the fault divided by p95 before it. None when it cannot be calculated."""
    if all_failed(exp):
        return None
    pm = exp.get("phase_metrics") or {}
    before = _number((pm.get("before") or {}).get("p95_ms"))
    during = _number((pm.get("during") or {}).get("p95_ms"))
    if before and during:
        return during / before
    p95, base = _number(exp.get("p95_ms")), _number((baseline or {}).get("p95_ms"))
    return p95 / base if p95 and base else None


def back_to_baseline(exp):
    return (exp.get("impact") or {}).get("recovered_to_baseline")


def severity(exp, graph, baseline):
    """Return (level, reasons). Levels: critical, high, medium, low, none."""
    dependents = len(upstream(graph, exp.get("service")))
    err = _number(exp.get("error_rate")) or 0.0
    ratio = latency_ratio(exp, baseline)
    rec_s = _number(exp.get("recovery_s"))
    recovered = bool(exp.get("recovered"))
    back = back_to_baseline(exp)
    score = _number(exp.get("score")) or 0.0
    reasons = []

    if exp.get("aborted"):
        reasons.append("the safety guard had to abort it")
    if err >= 0.5:
        reasons.append(f"{err:.0%} of requests failed")
    if not recovered:
        reasons.append("the app did not recover within the timeout")
    if reasons:
        if dependents >= 3:
            reasons.append(f"{dependents} services depend on it")
            return "critical", reasons
        return "high", reasons

    if err >= 0.10:
        reasons.append(f"{err:.0%} of requests failed")
    if ratio is not None and ratio >= 5:
        reasons.append(f"p95 latency rose {ratio:.1f}x")
    if rec_s is not None and rec_s > 30:
        reasons.append(f"recovery took {rec_s:.0f}s")
    if reasons:
        return "high", reasons

    if ratio is not None and ratio >= 2:
        reasons.append(f"p95 latency rose {ratio:.1f}x")
    if back is False:
        reasons.append("latency did not return to baseline afterwards")
    if err >= 0.05:
        reasons.append(f"{err:.0%} of requests failed")
    if reasons:
        return "medium", reasons

    if score < RESILIENT_FROM:
        return "low", [f"score {score:.0f}/100 is below {RESILIENT_FROM}"]
    return "none", ["no meaningful impact measured"]


def confidence(exp):
    during = (exp.get("phase_metrics") or {}).get("during") or {}
    n = during.get("samples")
    if n is None:
        n = sum(1 for s in exp.get("samples") or [] if len(s) > 3 and s[3] in ("chaos", "during"))
    if n >= 30:
        return "high", n
    if n >= 10:
        return "medium", n
    return "low", n


def verdict(score):
    return "resilient" if score >= RESILIENT_FROM else "degraded" if score >= WEAK_BELOW else "weak"


def explain(exp, graph, baseline):
    """Measurement-based explanation used when Gemini is not available."""
    svc, act = exp.get("service", "?"), str(exp.get("action", "fault")).replace("-", " ")
    node = _nodes(graph).get(svc, {})
    ups = upstream(graph, svc)
    err = _number(exp.get("error_rate")) or 0.0
    ratio = latency_ratio(exp, baseline)

    if all_failed(exp):
        what = f"During the {act}, every request failed."
    elif ratio is not None:
        what = f"During the {act}, {err:.0%} of requests failed and p95 latency was {ratio:.1f}x the level before the fault."
    else:
        what = f"During the {act}, {err:.0%} of requests failed."
    if exp.get("aborted"):
        what += f" The safety guard stopped it early ({exp.get('abort_reason')})."
    if exp.get("recovered"):
        what += f" Requests succeeded again {exp.get('recovery_s')}s after the fault was removed"
        back = back_to_baseline(exp)
        what += (", and latency returned to normal." if back is True else
                 ", but latency had not returned to normal by the end." if back is False else ".")
    else:
        what += " The app did not recover within the timeout."

    why = (f"{svc} runs {node.get('replicas', '?')} replica(s) and {len(ups)} service(s) depend on it"
           + (f" ({', '.join(ups)})." if ups else "."))

    if act == "pod failure":
        cause = ("With a single replica there is nothing to fail over to, so callers see errors until the pod is back."
                 if node.get("replicas", 1) < 2 else
                 "Other replicas should absorb the loss; remaining errors point to slow failover or missing retries in callers.")
    elif act == "network delay":
        cause = ("Callers wait for the slow responses instead of timing out, so the delay spreads up the call chain"
                 + (f" to {', '.join(ups)}." if ups else "."))
    elif act == "cpu stress":
        cause = "The pod has no spare CPU or autoscaling, so requests queue behind the extra load."
    else:
        cause = "See the measurements below."
    return {"what": what, "why": why, "cause": cause, "source": "measurements"}


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def _effort(title):
    t = title.lower()
    if "replica" in t or t.startswith("scale") or "probe" in t:
        return "Low"
    if "autoscaler" in t or "requests/limits" in t:
        return "Medium"
    return "Medium (code change)"


def _snippet(title, svc):
    t = title.lower()
    if "replica" in t or (t.startswith("scale") and "autoscaler" in t):
        return (f"kubectl scale deployment/{svc} --replicas=2\n---\n"
                f"apiVersion: policy/v1\nkind: PodDisruptionBudget\nmetadata:\n  name: {svc}-pdb\n"
                f"spec:\n  minAvailable: 1\n  selector:\n    matchLabels:\n      app: {svc}")
    if "autoscaler" in t:
        return f"kubectl autoscale deployment/{svc} --cpu-percent=70 --min=2 --max=5"
    if "probe" in t:
        return ("readinessProbe:\n  periodSeconds: 5\n  failureThreshold: 2\n"
                "livenessProbe:\n  periodSeconds: 10\n  failureThreshold: 3")
    if "timeout" in t or "circuit breaker" in t:
        return (f"// Go caller of {svc}: bound every call\n"
                "ctx, cancel := context.WithTimeout(ctx, 500*time.Millisecond)\ndefer cancel()")
    if "retries" in t:
        return ('// gRPC retry policy in the client service config\n'
                '{"methodConfig":[{"name":[{}],"retryPolicy":{"maxAttempts":3,"initialBackoff":"0.1s",'
                '"maxBackoff":"1s","backoffMultiplier":2,"retryableStatusCodes":["UNAVAILABLE"]}}]}')
    return None


def effective_recs(exp, graph, baseline, level):
    """The analyzer's recommendations, or rule-based ones when it gave none for a real weakness
    (it only recommends below a score of 90). Returns (recs, added_by_dashboard)."""
    recs = list(exp.get("recommendations") or [])
    if recs or level == "none":
        return recs, False
    svc, act = exp.get("service", "?"), exp.get("action")
    single = _nodes(graph).get(svc, {}).get("replicas", 1) < 2
    ratio = latency_ratio(exp, baseline)
    callers = ", ".join(upstream(graph, svc)) or "its callers"
    if act == "cpu-stress":
        recs.append({"title": f"Scale {svc} and set CPU requests/limits with an autoscaler" if single
                     else f"Set CPU requests/limits and a HorizontalPodAutoscaler on {svc}",
                     "detail": f"CPU pressure raised p95 latency {ratio:.1f}x." if ratio else "CPU pressure slowed requests."})
    elif act == "network-delay":
        recs.append({"title": f"Set client timeouts and a circuit breaker for calls to {svc}",
                     "detail": f"Bound how long {callers} wait for {svc}."})
    elif act == "pod-failure":
        recs.append({"title": f"Run at least 2 replicas of {svc}" if single else f"Add retries with backoff in {callers}",
                     "detail": "Callers should keep working while one pod is replaced."})
    if back_to_baseline(exp) is False:
        recs.append({"title": f"Investigate lingering slowness after faults on {svc}",
                     "detail": "Requests succeeded again, but latency had not returned to normal by the end of the "
                               "observation. Check for cold caches, connection pools or queues draining slowly."})
    return recs, True


def aggregate_fixes(run, graph, baseline):
    exps = run["experiments"]
    n = len(exps) or 1
    fixes = {}
    for exp in exps:
        level, _ = severity(exp, graph, baseline)
        recs, added = effective_recs(exp, graph, baseline, level)
        for rec in recs:
            title = rec.get("title", "")
            if title.lower().startswith("safety limit"):
                continue
            f = fixes.setdefault(title, {"title": title, "detail": rec.get("detail", ""), "links": [],
                                         "auto": bool(rec.get("auto_fix")), "service": exp.get("service"),
                                         "gain": 0.0, "rank": len(SEVERITY_ORDER), "added": added})
            f["links"].append((exp.get("service"), exp.get("action"), level))
            f["gain"] += (100 - (_number(exp.get("score")) or 0)) / n
            f["rank"] = min(f["rank"], SEVERITY_ORDER.index(level))
            f["auto"] = f["auto"] or bool(rec.get("auto_fix"))
    out = list(fixes.values())
    for f in out:
        f["effort"] = "Low (automatic)" if f["auto"] else _effort(f["title"])
        f["snippet"] = _snippet(f["title"], f["service"])
    effort_rank = {"Low (automatic)": 0, "Low": 1, "Medium": 2, "Medium (code change)": 3}
    out.sort(key=lambda f: (f["rank"], -f["gain"], effort_rank.get(f["effort"], 4)))
    return out


# ---------------------------------------------------------------------------
# Optional Gemini explanations
# ---------------------------------------------------------------------------

AI_SYSTEM = """You are an SRE explaining chaos-engineering results for a microservice app to a mixed audience.
You get measured results; never invent numbers. Respond with ONLY JSON:
{"summary":"<4-5 plain sentences: overall resilience, the most severe weakness and why it matters, what to fix first>",
 "experiments":{"<id>":{"what":"<what happened, 1-2 sentences>","why":"<why it matters for users and dependent services>",
 "cause":"<most likely root cause in the architecture or code>"}}}"""


def ai_insights(run, graph, baseline, cfg):
    if not llm.available(cfg):
        return None
    slim = []
    for e in run["experiments"]:
        level, reasons = severity(e, graph, baseline)
        slim.append({"id": e.get("id"), "service": e.get("service"), "action": e.get("action"),
                     "score": e.get("score"), "severity": level, "severity_reasons": reasons,
                     "error_rate": e.get("error_rate"), "latency_ratio": latency_ratio(e, baseline),
                     "aborted": e.get("aborted"), "recovered": e.get("recovered"),
                     "recovery_s": e.get("recovery_s"), "back_to_baseline": back_to_baseline(e),
                     "depended_on_by": upstream(graph, e.get("service")),
                     "replicas": _nodes(graph).get(e.get("service"), {}).get("replicas"),
                     "recommendations": [r.get("title") for r in e.get("recommendations") or []]})
    try:
        out = llm.ask_json(cfg, AI_SYSTEM, {"resilience_score": run.get("resilience_score"),
                                            "environment": run.get("env"), "experiments": slim}, max_tokens=2000)
    except Exception as exc:  # network, auth or parse errors: fall back to measurement-based text
        print(f"Gemini explanations unavailable ({exc.__class__.__name__}); using measurement-based text.")
        return None
    return {"summary": out.get("summary"), "experiments": out.get("experiments") or {},
            "model": llm.model_name(cfg)}


def template_summary(run, ranked, fixes):
    score = run.get("resilience_score")
    n = len(run["experiments"])
    counts = {lvl: sum(1 for _, l, _ in ranked if l == lvl) for lvl in SEVERITY_ORDER}
    serious = counts["critical"] + counts["high"]
    text = f"The app scored {score}/100 across {n} experiment(s)."
    if ranked:
        exp, level, reasons = ranked[0]
        text += (f" The most severe weakness is {exp['action'].replace('-', ' ')} on {exp['service']} "
                 f"({SEVERITY_LABEL[level]}): {', '.join(reasons)}.")
    text += (f" {serious} finding(s) are critical or high." if serious else " No critical or high findings.")
    if fixes:
        text += f" Fix first: {fixes[0]['title']}."
    return text


# ---------------------------------------------------------------------------
# Command center
# ---------------------------------------------------------------------------

ROLES = {
    "frontend": "Web UI. It calls the other shop services.",
    "adservice": "Returns ads for the shop.",
    "cartservice": "Stores the shopping cart.",
    "checkoutservice": "Places the order and calls payment, shipping, currency, and email.",
    "currencyservice": "Converts product prices.",
    "emailservice": "Sends the order confirmation.",
    "paymentservice": "Charges the card.",
    "productcatalogservice": "Lists products.",
    "recommendationservice": "Suggests other products.",
    "shippingservice": "Calculates the shipping quote.",
    "redis-cart": "Stores cart data for cartservice.",
}
POSITIONS = {
    "frontend": [240, 48],
    "adservice": [70, 130],
    "recommendationservice": [400, 70],
    "checkoutservice": [250, 170],
    "productcatalogservice": [120, 230],
    "currencyservice": [40, 320],
    "cartservice": [190, 330],
    "paymentservice": [430, 175],
    "emailservice": [540, 240],
    "shippingservice": [330, 330],
    "redis-cart": [560, 330],
}
OLD_PAGES = (
    "dashboard-summary.html", "dashboard-weaknesses.html", "dashboard-fixes.html",
    "dashboard-map.html", "dashboard-experiments.html", "dashboard-scores.html",
    "dashboard-safety.html", "dashboard-log.html",
)


def _samples(exp):
    out = []
    for s in exp.get("samples") or []:
        if len(s) >= 3:
            out.append([round(float(s[0]), 2), 1 if s[1] else 0, round(float(s[2]), 1),
                        s[3] if len(s) > 3 else ""])
    return out


def pack(runs, graph, cfg, ai=None, stop_active=False):
    latest = runs[-1]
    by_id = {r["run_id"]: r for r in runs}
    previous = by_id.get(latest.get("compare_to")) or (runs[-2] if len(runs) > 1 else None)
    baseline = latest.get("baseline") or {}
    exps = latest["experiments"]
    assessed = [(x, *severity(x, graph, baseline)) for x in exps]
    ranked = sorted([a for a in assessed if a[1] != "none"],
                    key=lambda a: (SEVERITY_ORDER.index(a[1]), _number(a[0].get("score")) or 0))
    fixes = aggregate_fixes(latest, graph, baseline)
    worst = {}
    by_service = {}
    for x, level, reasons in assessed:
        by_service[x["service"]] = (x, level, reasons)
        cur = worst.get(x["service"])
        if cur is None or SEVERITY_ORDER.index(level) < SEVERITY_ORDER.index(cur):
            worst[x["service"]] = level
    ai_exps = (ai or {}).get("experiments") or {}
    summary = (ai or {}).get("summary") or template_summary(latest, ranked, fixes)
    summary_source = (f"Gemini-generated ({ai.get('model')})" if ai and ai.get("summary")
                      else "Generated from measurements (set GEMINI_API_KEY for an AI-written summary)")
    nodes = _nodes(graph)
    services = []
    for name, node in sorted(nodes.items()):
        if name in NON_SERVICES:
            continue
        hit = by_service.get(name)
        level = worst.get(name, "untested")
        p95 = None
        err = None
        score = None
        action = None
        if hit:
            x = hit[0]
            action = x.get("action")
            score = x.get("score")
            err = x.get("error_rate")
            p95 = None if all_failed(x) else x.get("p95_ms")
        services.append({
            "name": name,
            "replicas": node.get("replicas", 1),
            "depends_on": [d for d in node.get("depends_on", []) if d not in NON_SERVICES],
            "called_by": upstream(graph, name),
            "dependents": len(upstream(graph, name)),
            "severity": level,
            "tested": name in worst,
            "score": score,
            "action": action,
            "error_rate": err,
            "p95_ms": p95,
            "role": ROLES.get(name, "Service in the dependency graph."),
            "pos": POSITIONS.get(name),
        })
    edges = [{"from": e["from"], "to": e["to"]} for e in graph.get("edges", [])
             if e["from"] not in NON_SERVICES and e["to"] not in NON_SERVICES]
    experiments = []
    chart, bands, t_off = [], [], 0.0
    for x, level, reasons in sorted(assessed, key=lambda a: SEVERITY_ORDER.index(a[1])):
        text = explain(x, graph, baseline)
        extra = ai_exps.get(str(x.get("id"))) or {}
        recs, added = effective_recs(x, graph, baseline, level)
        samples = _samples(x)
        experiments.append({
            "id": x.get("id"),
            "service": x.get("service"),
            "action": x.get("action"),
            "score": x.get("score"),
            "severity": level,
            "rank": SEVERITY_ORDER.index(level),
            "reasons": reasons,
            "error_rate": x.get("error_rate"),
            "p95_ms": None if all_failed(x) else x.get("p95_ms"),
            "aborted": bool(x.get("aborted")),
            "abort_reason": x.get("abort_reason"),
            "recovered": bool(x.get("recovered")),
            "recovery_s": x.get("recovery_s"),
            "back_to_baseline": back_to_baseline(x),
            "rationale": x.get("rationale") or "",
            "what": extra.get("what") or text["what"],
            "why": extra.get("why") or text["why"],
            "cause": extra.get("cause") or text["cause"],
            "phases": x.get("phase_metrics") or {},
            "recommendations": [{"title": r.get("title", ""), "detail": r.get("detail", ""),
                                 "snippet": _snippet(r.get("title", ""), x.get("service"))} for r in recs],
            "added": added,
        })
        if samples:
            span = samples[-1][0] - samples[0][0]
            during = [s for s in samples if s[3] == "during"]
            if during:
                bands.append({"start": round(t_off + during[0][0] - samples[0][0], 2),
                              "end": round(t_off + during[-1][0] - samples[0][0], 2), "phase": "during"})
            step = max(1, len(samples) // 80)
            for s in samples[::step]:
                chart.append({"t": round(t_off + s[0] - samples[0][0], 2), "ok": s[1], "lat": s[2], "phase": s[3]})
            t_off += span + 8
    tested = {x.get("service") for x in exps}
    suggested = []
    for name, node in nodes.items():
        if name in NON_SERVICES or name in (cfg.get("exclude_services") or []) or name in tested:
            continue
        deps = len(upstream(graph, name))
        single = node.get("replicas", 1) < 2
        action = "pod-failure" if single else "network-delay"
        risk = "High" if deps >= 3 or (single and deps >= 2) else "Medium" if deps >= 1 else "Low"
        suggested.append({
            "service": name, "action": action, "dependents": deps, "risk": risk,
            "reason": f"{deps} service(s) depend on it" + (" and it has a single replica" if single else ""),
            "command": ("python -m chaosai agent --sim --rounds 1" if latest.get("env") == "simulated"
                        else "python -m chaosai agent --rounds 1"),
        })
    suggested.sort(key=lambda s: (-s["dependents"], s["service"]))
    prev_score = previous.get("resilience_score") if previous else None
    score = latest.get("resilience_score")
    delta = None if prev_score is None or score is None else round(score - prev_score, 1)
    prev_weak = None
    if previous:
        prev_base = previous.get("baseline") or {}
        prev_weak = sum(1 for x in previous["experiments"] if severity(x, graph, prev_base)[0] != "none")
    weak_delta = None if prev_weak is None else len(ranked) - prev_weak
    fix_out = []
    for f in fixes:
        level = SEVERITY_ORDER[f["rank"]] if f["rank"] < len(SEVERITY_ORDER) else "low"
        fix_out.append({
            "title": f["title"], "detail": f["detail"], "effort": f["effort"],
            "gain": round(f["gain"], 1), "snippet": f.get("snippet") or "",
            "severity": level, "added": f["added"],
            "addresses": ", ".join(f"{s} ({a})" for s, a, _lvl in f["links"]),
        })
    healthy = sum(1 for s in services if s["severity"] == "none")
    untested = sum(1 for s in services if not s["tested"])
    abort_count = sum(1 for r in runs for x in r["experiments"] if x.get("aborted"))
    unconfirmed = sum(1 for r in runs for x in r["experiments"] if x.get("cleanup_confirmed") is False)
    limits = latest.get("limits") or {}
    return {
        "env": latest.get("env") or "simulated",
        "namespace": cfg.get("namespace") or "default",
        "run_id": latest.get("run_id"),
        "planner": str(latest.get("planner") or "rule-based"),
        "model": (ai or {}).get("model") or latest.get("llm_model"),
        "score": score,
        "delta": delta,
        "weak_delta": weak_delta,
        "n_experiments": len(exps),
        "n_runs": len(runs),
        "weakness_count": len(ranked),
        "service_total": len(services),
        "healthy_count": healthy,
        "untested_count": untested,
        "summary": summary,
        "summary_source": summary_source,
        "allowlist": list(cfg.get("allowlist") or []),
        "exclude": list(cfg.get("exclude_services") or []),
        "limits": {
            "max_error_rate": limits.get("max_error_rate"),
            "p95_limit_ms": limits.get("p95_limit_ms"),
            "max_extra_unhealthy_pods": limits.get("max_extra_unhealthy_pods"),
        },
        "stop_active": bool(stop_active),
        "abort_count": abort_count,
        "unconfirmed_cleanups": unconfirmed,
        "services": services,
        "edges": edges,
        "experiments": experiments,
        "fixes": fix_out,
        "suggested": suggested[:3],
        "chart": chart,
        "bands": bands,
        "runs": [{
            "run_id": r.get("run_id"), "env": r.get("env"), "planner": str(r.get("planner")),
            "score": r.get("resilience_score"), "n": len(r.get("experiments") or []),
            "aborts": sum(1 for x in r.get("experiments") or [] if x.get("aborted")),
        } for r in reversed(runs)],
    }


def render(runs, graph, cfg, ai=None, stop_active=False, stem="dashboard"):
    if not runs:
        raise ValueError("No runs with results found.")
    from .command_center import render_page
    return {_filename_for(stem): render_page(pack(runs, graph, cfg, ai, stop_active))}


def _filename_for(stem):
    return f"{stem}.html" if stem else "dashboard.html"


def build(cfg, graph, out_path, use_ai=True):
    runs = load_runs(cfg["runs_dir"])
    if not runs:
        raise SystemExit(f"No runs with results in {cfg['runs_dir']}/. Run `python -m chaosai agent` or `run` first.")
    latest = runs[-1]
    ai = ai_insights(latest, graph, latest.get("baseline") or {}, cfg) if use_ai else None
    stem = os.path.splitext(os.path.basename(out_path))[0] or "dashboard"
    pages = render(runs, graph, cfg, ai, os.path.exists(os.path.join(cfg["runs_dir"], "STOP")), stem)
    folder = os.path.dirname(out_path) or "."
    os.makedirs(folder, exist_ok=True)
    for name in OLD_PAGES:
        old = os.path.join(folder, name)
        if os.path.isfile(old):
            os.remove(old)
    target = os.path.join(folder, _filename_for(stem))
    with open(target, "w", encoding="utf-8") as f:
        f.write(pages[_filename_for(stem)])
    return target, len(runs), ai is not None
