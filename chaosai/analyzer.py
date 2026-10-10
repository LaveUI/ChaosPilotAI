"""Step 5: score resilience, rank weaknesses, recommend fixes."""
from . import llm

# Score = 100 minus penalties (documented in README):
#   errors      up to 40  (mean error rate during the fault, 50% or more = full penalty)
#   latency     up to 25  (p95 vs baseline p95, 10x or more = full penalty)
#   recovery    up to 25  (seconds to recover, 60s or more / never = full penalty)
#   abort       10        (safety limit had to stop the experiment)
ERR_FULL, LAT_FULL_RATIO, REC_FULL_S, ABORT_PENALTY = 0.5, 10.0, 60.0, 10.0


def score_result(r, baseline):
    err_pen = 40 * min(1.0, r["error_rate"] / ERR_FULL)
    base = max(baseline["p95_ms"], 1.0)
    ratio = (r["p95_ms"] / base) if r["p95_ms"] else LAT_FULL_RATIO
    lat_pen = 25 * min(1.0, max(0.0, ratio - 1) / (LAT_FULL_RATIO - 1))
    rec_pen = 25.0 if not r["recovered"] else 25 * min(1.0, (r["recovery_s"] or 0) / REC_FULL_S)
    abort_pen = ABORT_PENALTY if r["aborted"] else 0.0
    total = max(0.0, 100 - err_pen - lat_pen - rec_pen - abort_pen)
    return round(total, 1), {"errors": round(err_pen, 1), "latency": round(lat_pen, 1),
                             "recovery": round(rec_pen, 1), "abort": abort_pen}


def recommend(r, node, baseline):
    """Rule-based fixes. `auto_fix` entries are safe changes the CLI can apply and re-test."""
    svc, act = r["service"], r["action"]
    callers = ", ".join(node["depended_by"]) or "its callers"
    ratio = (r["p95_ms"] / max(baseline["p95_ms"], 1)) if r["p95_ms"] else LAT_FULL_RATIO
    recs = []
    if act == "pod-failure" and r["error_rate"] > 0.1:
        if node["replicas"] < 2:
            recs.append({"title": f"Run at least 2 replicas of {svc}",
                         "detail": f"{svc} is a single point of failure: losing its pod caused {r['error_rate']:.0%} errors. "
                                   f"Add a PodDisruptionBudget as well.",
                         "auto_fix": {"type": "scale", "service": svc, "replicas": 2}})
        recs.append({"title": f"Add retries with backoff in {callers}",
                     "detail": "Callers should tolerate a brief outage instead of failing the whole request."})
    if act == "network-delay" and ratio > 2:
        recs.append({"title": f"Set client timeouts and a circuit breaker for calls to {svc}",
                     "detail": f"p95 latency rose {ratio:.1f}x. Bound how long {callers} wait, and consider caching responses."})
    if act == "cpu-stress" and (ratio > 2 or r["error_rate"] > 0.1):
        if node["replicas"] < 2:
            recs.append({"title": f"Scale {svc} and set CPU requests/limits with an autoscaler",
                         "detail": f"CPU pressure raised p95 latency {ratio:.1f}x on a single replica.",
                         "auto_fix": {"type": "scale", "service": svc, "replicas": 2}})
        else:
            recs.append({"title": f"Set CPU requests/limits and a HorizontalPodAutoscaler on {svc}",
                         "detail": "Let the cluster add capacity under load."})
    if not r["recovered"] or (r["recovery_s"] or 0) > 30:
        recs.append({"title": f"Add readiness and liveness probes to {svc}",
                     "detail": f"Recovery took {r['recovery_s'] if r['recovered'] else 'longer than the timeout'}s. "
                               f"Probes let Kubernetes route around and restart it faster."})
    if r["aborted"]:
        recs.append({"title": "Safety limit stopped this experiment",
                     "detail": f"Reason: {r['abort_reason']}. Fix the weakness, then re-run to see the full effect."})
    return recs


def analyze(results, graph, baseline, cfg):
    nodes = {n["name"]: n for n in graph["nodes"]}
    for r in results["experiments"]:
        r["score"], r["breakdown"] = score_result(r, baseline)
        r["recommendations"] = recommend(r, nodes[r["service"]], baseline) if r["score"] < 90 else []
    exps = results["experiments"]
    results["resilience_score"] = round(sum(e["score"] for e in exps) / len(exps), 1) if exps else None
    results["weaknesses"] = [{"service": e["service"], "action": e["action"], "score": e["score"]}
                             for e in sorted(exps, key=lambda e: e["score"]) if e["score"] < 90]
    results["summary"] = _summary(results, cfg)
    return results


def _summary(results, cfg):
    if not llm.available(cfg) or not results["experiments"]:
        return None
    slim = [{k: e[k] for k in ("service", "action", "score", "error_rate", "p95_ms", "recovery_s",
                               "aborted", "abort_reason", "breakdown")} for e in results["experiments"]]
    system = ('You are an SRE writing a short resilience summary for a chaos-engineering run. '
              'Respond with ONLY JSON: {"summary":"<3-4 plain sentences: what broke, why it matters, what to fix first>"}.')
    try:
        return llm.ask_json(cfg, system, {"resilience_score": results["resilience_score"], "experiments": slim},
                            max_tokens=400).get("summary")
    except Exception:
        return None
