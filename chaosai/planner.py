"""Step 2: plan experiments intelligently. The LLM proposes, the code disposes:
every suggestion is validated against the allowlist and the dependency graph."""
from . import llm
from .chaos import ACTION_LABELS

SYSTEM = """You are the planner agent in a chaos-engineering system for a Kubernetes microservice app.
Rank the most informative failure experiments to run next, best first. Use the dependency graph:
prefer services many others depend on and single-replica services (single points of failure).
Use the observation of the live system: do not target a service that is already unhealthy.
Use already_tested: prefer failure types and services not yet tested, and build on what earlier rounds showed.
Respond with ONLY a JSON object: {"experiments":[{"service":"<name>","action":"<allowed action>","rationale":"<one or two sentences>"}]}.
Return `count` experiments in ranked order. Use only services from graph.nodes and only actions from
allowlist. Never pick excluded services. One experiment per service."""

def _by_name(graph):
    return {n["name"]: n for n in graph["nodes"]}


def _finalize(picks, graph, cfg):
    nodes = _by_name(graph)
    out = []
    for i, p in enumerate(picks, 1):
        node = nodes[p["service"]]
        out.append({
            "id": f"exp{i}",
            "service": p["service"],
            "app_label": node["app_label"],
            "action": p["action"],
            "duration_s": cfg["experiment_duration_s"],
            "rationale": p["rationale"],
        })
    return out


def heuristic_plan(graph, cfg, history, n):
    tested = {(h["service"], h["action"]) for h in history}
    scored = []
    for node in graph["nodes"]:
        if node["name"] in cfg["exclude_services"]:
            continue
        dep = node["transitive_dependents"]
        spof = node["replicas"] < 2
        for action in cfg["allowlist"]:
            score = 3 * dep + (4 if spof else 0)
            if action == "pod-failure" and spof:
                score += 3
            if action == "network-delay" and dep >= 2:
                score += 2
            if action == "cpu-stress" and spof:
                score += 1
            if (node["name"], action) in tested:
                score -= 100
            scored.append((score, node["name"], action, dep, spof))
    picks, seen, used = [], set(), {}
    while len(picks) < n:
        # Greedy: highest score, with a penalty for repeating a fault type so the plan covers more ground
        best = None
        for score, name, action, dep, spof in scored:
            if name in seen or score < -50:
                continue
            adj = score - 4 * used.get(action, 0)
            if best is None or (adj, name) > (best[0], best[1]):
                best = (adj, name, action, dep, spof)
        if best is None:
            break
        _, name, action, dep, spof = best
        seen.add(name)
        used[action] = used.get(action, 0) + 1
        why = (f"{name} is depended on by {dep} service(s) and runs {'a single replica' if spof else 'multiple replicas'}; "
               f"a {ACTION_LABELS[action]} shows how much the app relies on it.")
        picks.append({"service": name, "action": action, "rationale": why})
    return picks


def _validate_llm(raw, graph, cfg, n, requested_experiment=None):
    nodes = _by_name(graph)
    picks, seen = [], set()
    for e in raw.get("experiments", []):
        svc, act = e.get("service"), e.get("action")
        requested_matches = (
            requested_experiment is None
            or (svc, act) == (requested_experiment["service"], requested_experiment["action"])
        )
        if (requested_matches and svc in nodes and svc not in cfg["exclude_services"]
                and act in cfg["allowlist"] and svc not in seen):
            seen.add(svc)
            picks.append({"service": svc, "action": act, "rationale": str(e.get("rationale", ""))[:400]})
    return picks[:n]


def plan(graph, cfg, history=None, n=3, mode="auto", observation=None, llm_metadata=None,
         requested_experiment=None):
    if mode not in {"auto", "llm", "rule-based"}:
        raise ValueError(f"Unknown planner mode: {mode}")
    history = history or []
    use_llm = mode == "llm" or (mode == "auto" and llm.available(cfg))
    if mode == "llm" and not llm.available(cfg):
        raise RuntimeError("LLM planner selected, but Gemini is unavailable. Set GEMINI_API_KEY and install google-genai.")
    if use_llm:
        try:
            payload = {"graph": graph, "allowlist": cfg["allowlist"], "excluded": cfg["exclude_services"],
                       "already_tested": history, "count": n}
            if requested_experiment:
                payload["requested_experiment"] = {
                    "service": requested_experiment["service"],
                    "action": requested_experiment["action"],
                    "instruction": "Only propose this exact service and fault type.",
                }
            if observation:
                payload["observation"] = observation
            picks = _validate_llm(
                llm.ask_json(
                    cfg, SYSTEM, payload, schema=llm.PLANNER_SCHEMA, metadata=llm_metadata
                ),
                graph, cfg, n, requested_experiment,
            )
            if picks:
                return {"planner": "llm", "llm_model": llm.model_name(cfg),
                        "experiments": _finalize(picks, graph, cfg)}
            if mode == "llm":
                raise RuntimeError("Gemini returned no valid experiments.")
            print("LLM returned no valid experiments; using rule-based planner.")
        except Exception as exc:
            if mode == "llm":
                raise RuntimeError(f"LLM planner failed ({exc.__class__.__name__}): {exc}") from exc
            print(f"LLM planner failed ({exc.__class__.__name__}); using rule-based planner.")
    if requested_experiment:
        service, action = requested_experiment["service"], requested_experiment["action"]
        nodes = _by_name(graph)
        if service not in nodes or service in cfg["exclude_services"] or action not in cfg["allowlist"]:
            raise ValueError("Requested experiment is not allowed by the service graph and configured safety policy.")
        picks = [{"service": service, "action": action,
                  "rationale": "Operator-selected experiment, validated against the dependency map and allowlist."}]
    else:
        picks = heuristic_plan(graph, cfg, history, n)
    return {"planner": "rule-based", "experiments": _finalize(picks, graph, cfg)}