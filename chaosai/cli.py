import argparse
import json
import os
import time
import uuid
from datetime import datetime

from . import analyzer, config, mapper, planner, report, runner
from .chaos import ACTION_LABELS
from .env import make_env


def _make_run_id():
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{uuid.uuid4().hex[:8]}"


def _load(path, what):
    if not os.path.exists(path):
        raise SystemExit(f"Missing {path}. {what}")
    with open(path) as f:
        return json.load(f)


def _save(path, data):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _latest_id(cfg):
    p = os.path.join(cfg["runs_dir"], "latest.txt")
    return open(p).read().strip() if os.path.exists(p) else None


def _results_path(cfg, run_id):
    return os.path.join(cfg["runs_dir"], run_id, "results.json")


def _graph(cfg):
    return _load(cfg["graph_file"], "Run `python -m chaosai map` first.")


def _baseline(cfg):
    return _load(cfg["baseline_file"], "Run `python -m chaosai baseline` first.")


def cmd_map(a, cfg):
    path = cfg["manifest_path"]
    if not os.path.exists(path):
        print(f"{path} not found; using sample/kubernetes-manifests.yaml")
        path = "sample/kubernetes-manifests.yaml"
    graph = mapper.build_graph(path, cfg["graph_overrides"])
    _save(cfg["graph_file"], graph)
    with open("graph.mmd", "w", encoding="utf-8") as f:
        f.write(mapper.to_mermaid(graph))
    sim_state = os.path.join(cfg["runs_dir"], "sim_state.json")
    if os.path.exists(sim_state):
        os.remove(sim_state)
    print(f"Mapped {len(graph['nodes'])} services and {len(graph['edges'])} dependencies -> {cfg['graph_file']}, graph.mmd")
    for n in sorted(graph["nodes"], key=lambda n: -n["transitive_dependents"]):
        print(f"  {n['name']:<24} called by {len(n['depended_by'])} directly, {n['transitive_dependents']} overall; replicas={n['replicas']}")


def cmd_baseline(a, cfg):
    graph = _graph(cfg) if a.sim else None
    env = make_env(cfg, graph, a.sim)
    secs = a.seconds or cfg["baseline_seconds"]
    print(f"Measuring baseline for {secs}s ({env.name})...")
    base = runner.measure_baseline(cfg, env, secs)
    _save(cfg["baseline_file"], base)
    print(f"Baseline: error rate {base['error_rate']:.1%}, p95 {base['p95_ms']:.0f} ms ({base['samples']} probes)")
    if base["error_rate"] > 0.05:
        print("WARNING: baseline already has errors. Is the port-forward running and the app healthy?")


def cmd_plan(a, cfg):
    graph = _graph(cfg)
    history = []
    latest = _latest_id(cfg)
    if latest and a.avoid_tested:
        history = [{"service": e["service"], "action": e["action"]}
                   for e in _load(_results_path(cfg, latest), "")["experiments"]]
    try:
        p = planner.plan(graph, cfg, history, a.n, mode=a.planner)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    _save(cfg["plan_file"], p)
    print(f"Plan from {p['planner']} planner -> {cfg['plan_file']}")
    for e in p["experiments"]:
        print(f"  {e['id']}: {ACTION_LABELS[e['action']]} on {e['service']}\n      why: {e['rationale']}")


def _execute(cfg, sim, plan, compare_to=None):
    graph, baseline = _graph(cfg), _baseline(cfg)
    env = make_env(cfg, graph, sim)
    run_id = _make_run_id()
    run_dir = os.path.join(cfg["runs_dir"], run_id)
    done, limits = runner.run_plan(plan, cfg, env, baseline, run_dir, os.path.join(cfg["runs_dir"], "STOP"))
    results = {"run_id": run_id, "env": env.name, "planner": plan["planner"],
               "llm_model": plan.get("llm_model"), "baseline": baseline,
               "limits": limits, "plan": plan, "experiments": done, "compare_to": compare_to}
    if not done:
        raise SystemExit("No experiments completed.")
    analyzer.analyze(results, graph, baseline, cfg)
    _save(os.path.join(run_dir, "results.json"), results)
    previous = _load(_results_path(cfg, compare_to), "") if compare_to else None
    with open(os.path.join(run_dir, "report.html"), "w", encoding="utf-8") as f:
        f.write(report.render(results, graph, previous))
    with open(os.path.join(cfg["runs_dir"], "latest.txt"), "w", encoding="utf-8") as f:
        f.write(run_id)
    print(f"\nResilience score: {results['resilience_score']}/100"
          + (f" (was {previous['resilience_score']})" if previous else ""))
    for w in results["weaknesses"]:
        print(f"  weak: {w['action']} on {w['service']} scored {w['score']}")
    print(f"Report: {os.path.join(run_dir, 'report.html')}")
    return results


def cmd_run(a, cfg):
    plan = _load(a.plan or cfg["plan_file"], "Run `python -m chaosai plan` first.")
    _execute(cfg, a.sim, plan, a.compare_to)


def cmd_fix(a, cfg):
    latest = _latest_id(cfg)
    if not latest:
        raise SystemExit("No runs yet. Run `python -m chaosai run` first.")
    results = _load(_results_path(cfg, latest), "")
    env = make_env(cfg, _graph(cfg), a.sim)
    fixes, seen = [], set()
    for e in results["experiments"]:
        for r in e["recommendations"]:
            fx = r.get("auto_fix")
            if fx and (fx["service"], fx["replicas"]) not in seen:
                seen.add((fx["service"], fx["replicas"]))
                fixes.append((r["title"], fx))
    if not fixes:
        print("No automatic fixes available. Apply the recommendations in the report manually, then `rerun`.")
        return
    for title, fx in fixes:
        print(f"Applying: {title}  (scale {fx['service']} to {fx['replicas']})")
        env.scale(fx["service"], fx["replicas"])
    print("Done. Now run `python -m chaosai rerun` to verify.")


def cmd_rerun(a, cfg):
    latest = _latest_id(cfg)
    if not latest:
        raise SystemExit("No runs yet. Run `python -m chaosai run` first.")
    prev = _load(_results_path(cfg, latest), "")
    _execute(cfg, a.sim, prev["plan"], compare_to=latest)


def cmd_report(a, cfg):
    run_id = a.run or _latest_id(cfg)
    results = _load(_results_path(cfg, run_id), "")
    prev = _load(_results_path(cfg, results["compare_to"]), "") if results.get("compare_to") else None
    out = os.path.join(cfg["runs_dir"], run_id, "report.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(report.render(results, _graph(cfg), prev))
    print(f"Wrote {out}")

def cmd_agent(a, cfg):
    from . import agents
    graph, baseline = _graph(cfg), _baseline(cfg)
    env = make_env(cfg, graph, a.sim)
    run_id = _make_run_id()
    run_dir = os.path.join(cfg["runs_dir"], run_id)
    try:
        results = agents.run_agents(cfg, env, graph, baseline, a.rounds, run_id, run_dir,
                                    os.path.join(cfg["runs_dir"], "STOP"), planner_mode=a.planner)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    if not results["experiments"]:
        raise SystemExit("No experiments completed.")
    _save(os.path.join(run_dir, "results.json"), results)
    with open(os.path.join(run_dir, "report.html"), "w", encoding="utf-8") as f:
        f.write(report.render(results, graph, None))
    with open(os.path.join(cfg["runs_dir"], "latest.txt"), "w", encoding="utf-8") as f:
        f.write(run_id)
    print(f"\nResilience score: {results['resilience_score']}/100")
    for w in results["weaknesses"]:
        print(f"  weak: {w['action']} on {w['service']} scored {w['score']}")
    print(f"Report: {os.path.join(run_dir, 'report.html')}")

def cmd_dashboard(a, cfg):
    from . import dashboard
    out = a.out or os.path.join(cfg["runs_dir"], "dashboard.html")
    path, n, used_ai = dashboard.build(cfg, _graph(cfg), out, use_ai=not a.no_ai)
    print(f"Dashboard built from {n} run(s)" + (" with Gemini explanations" if used_ai else "") + f": {path}")


def cmd_kill(a, cfg):
    os.makedirs(cfg["runs_dir"], exist_ok=True)
    with open(os.path.join(cfg["runs_dir"], "STOP"), "w", encoding="utf-8"):
        pass
    print("STOP file created: a running session will abort at its next check.")
    graph = _graph(cfg) if a.sim else None
    print(make_env(cfg, graph, a.sim).delete_all_chaos().strip() or "No chaosai experiments were active.")


def main(argv=None):
    p = argparse.ArgumentParser(prog="chaosai", description="AI-driven chaos engineering")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--sim", action="store_true", help="use the offline simulator instead of a real cluster")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("map", help="build the dependency graph from manifests")
    b = sub.add_parser("baseline", help="measure normal error rate and latency")
    b.add_argument("--seconds", type=int)
    pl = sub.add_parser("plan", help="choose experiments (LLM if configured, else rule-based)")
    pl.add_argument("--n", type=int, default=3)
    pl.add_argument("--planner", choices=("auto", "llm", "rule-based"), default="auto",
                    help="planner selection (default: auto, using Gemini when available)")
    pl.add_argument("--avoid-tested", action="store_true", help="deprioritize pairs from the latest run")
    r = sub.add_parser("run", help="run a plan with safety limits, then score and report")
    r.add_argument("--plan")
    r.add_argument("--compare-to", help="run id to compare against")
    sub.add_parser("fix", help="apply the safe automatic fixes from the latest run")
    sub.add_parser("rerun", help="re-run the latest plan and compare scores")
    rp = sub.add_parser("report", help="regenerate an HTML report")
    rp.add_argument("--run")
    ag = sub.add_parser("agent", help="agent loop: plan, inject and analyze one experiment per round")
    ag.add_argument("--rounds", type=int, default=3)
    ag.add_argument("--planner", choices=("auto", "llm", "rule-based"), default="auto",
                    help="planner selection (default: auto, using Gemini when available)")
    db = sub.add_parser("dashboard", help="build one dashboard from every run: findings, severity, fixes, score")
    db.add_argument("--out", help="output file (default: runs/dashboard.html)")
    db.add_argument("--no-ai", action="store_true", help="skip Gemini explanations even if a key is set")
    sub.add_parser("kill", help="panic button: stop and remove all chaosai experiments")
    a = p.parse_args(argv)
    cfg = config.load(a.config)
    {"map": cmd_map, "baseline": cmd_baseline, "plan": cmd_plan, "run": cmd_run, "fix": cmd_fix,
     "rerun": cmd_rerun, "report": cmd_report, "agent": cmd_agent, "dashboard": cmd_dashboard,
     "kill": cmd_kill}[a.cmd](a, cfg)
