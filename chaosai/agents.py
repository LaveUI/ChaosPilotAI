"""Agent loop: three agents take turns and learn from each round.

  PlannerAgent   decides WHICH failure to try next, using the dependency map and
                 what earlier experiments showed.
  InjectorAgent  checks it is safe, injects the failure and watches it. The Guard
                 (plain code, not AI) can abort it at any moment.
  AnalystAgent   scores the result, says what it means and recommends fixes.

The loop is Planner -> Injector -> Analyst -> back to the Planner with the new result.
With GEMINI_API_KEY set, the Planner asks the LLM; without it, it uses the
transparent rules below. Either way every choice is validated against the allowlist.
"""
import os

from . import analyzer, llm, planner, runner
from .chaos import ACTION_LABELS
from .guard import Guard

WEAK_BELOW = 50          # a service scoring under this is a confirmed weakness
RESILIENT_FROM = 90      # same threshold the analyzer uses
# Data stores must not be "fixed" by blindly adding replicas: copies would not share data.
STATEFUL_HINTS = ("redis", "postgres", "mysql", "mongo", "kafka")


def _nodes(graph):
    return {n["name"]: n for n in graph["nodes"]}


class PlannerAgent:
    """Decides the next experiment. One decision per round, so it can react to results."""

    def __init__(self, graph, cfg, mode="auto"):
        self.graph, self.cfg = graph, cfg
        if mode not in {"auto", "llm", "rule-based"}:
            raise ValueError(f"Unknown planner mode: {mode}")
        if mode == "llm" and not llm.available(cfg):
            raise RuntimeError("LLM planner selected, but Gemini is unavailable. Set GEMINI_API_KEY and install google-genai.")
        self.mode = "llm" if mode == "llm" or (mode == "auto" and llm.available(cfg)) else "rule-based"

    def decide(self, history):
        tested = {(h["service"], h["action"]) for h in history}
        if self.mode == "llm":
            p = planner.plan(self.graph, self.cfg, history, 1, mode="llm")
            exps = p["experiments"]
            if p["planner"] == "llm" and exps and (exps[0]["service"], exps[0]["action"]) not in tested:
                exp = exps[0]
                exp["planner"] = "llm"
                exp["llm_model"] = p["llm_model"]
                return exp
            if self.mode == "llm":
                print("  [Planner agent] Gemini returned no new experiment; stopping.")
                return None
            print("  [Planner agent] LLM gave no new experiment; using the rules for this round.")
        exp = self._decide_by_rules(history, tested)
        if exp:
            exp["planner"] = "rule-based"
        return exp

    def _decide_by_rules(self, history, tested):
        tried_actions = {h["action"] for h in history}
        times_hit, weak = {}, set()
        for h in history:
            times_hit[h["service"]] = times_hit.get(h["service"], 0) + 1
            if h["score"] < WEAK_BELOW:
                weak.add(h["service"])

        best = None
        for node in self.graph["nodes"]:
            name = node["name"]
            if name in self.cfg["exclude_services"]:
                continue
            for action in self.cfg["allowlist"]:
                if (name, action) in tested:
                    continue
                score = 3 * node["transitive_dependents"]          # how much of the app relies on it
                score += 4 if node["replicas"] < 2 else 0          # single point of failure
                score += 5 if action not in tried_actions else 0   # learn about a new failure type
                score -= 3 * times_hit.get(name, 0)                # spread out over services
                score -= 6 if name in weak else 0                  # weakness already confirmed: move on
                if best is None or (score, name, action) > best[0]:
                    best = ((score, name, action), node, action)
        if best is None:
            return None
        _, node, action = best
        return planner._finalize(
            [{"service": node["name"], "action": action, "rationale": self._why(node, action, history, weak)}],
            self.graph, self.cfg)[0]

    @staticmethod
    def _why(node, action, history, weak):
        label = ACTION_LABELS[action]
        why = (f"{node['name']} has {node['transitive_dependents']} service(s) relying on it and runs "
               f"{node['replicas']} replica(s).")
        if not history:
            return why + f" First round, so start with the highest-risk service and a {label}."
        if action not in {h["action"] for h in history}:
            why += f" No {label} has been tried yet, so this round tests a new kind of failure."
        last = history[-1]
        why += (f" Last round: {ACTION_LABELS[last['action']]} on {last['service']} scored {last['score']}"
                + (" and was aborted by the guard" if last["aborted"] else "") + ".")
        if weak and node["name"] not in weak:
            why += f" {', '.join(sorted(weak))} already confirmed weak, so the agent moves on."
        return why


class InjectorAgent:
    """Injects one experiment. Refuses if the choice is not allowed or the app is already unhealthy."""

    def __init__(self, cfg, env, baseline, guard, run_dir):
        self.cfg, self.env, self.baseline, self.guard, self.run_dir = cfg, env, baseline, guard, run_dir

    def preflight(self, exp):
        """Return a reason to refuse, or None if it is safe to inject."""
        if exp["action"] not in self.cfg["allowlist"]:
            return f"action {exp['action']} is not on the allowlist"
        if exp["service"] in self.cfg["exclude_services"]:
            return f"{exp['service']} is a protected service"
        failed = 0
        for _ in range(3):
            ok, _ms = self.env.probe()
            failed += 0 if ok else 1
            self.env.sleep(self.cfg["probe_interval_s"])
        if failed == 3:
            return "the app is not healthy right now (3 of 3 probes failed)"
        return None

    def act(self, exp):
        reason = self.preflight(exp)
        if reason:
            print(f"  [Injector agent] refused: {reason}.")
            return None
        return runner.run_experiment(exp, self.cfg, self.env, self.baseline, self.guard, self.run_dir)


class AnalystAgent:
    """Scores one result, explains it and recommends fixes."""

    def __init__(self, graph, baseline):
        self.nodes, self.baseline = _nodes(graph), baseline

    def explain(self, result):
        result["score"], result["breakdown"] = analyzer.score_result(result, self.baseline)
        recs = []
        if result["score"] < RESILIENT_FROM:
            recs = analyzer.recommend(result, self.nodes[result["service"]], self.baseline)
        for rec in recs:
            fx = rec.get("auto_fix")
            if fx and any(h in fx["service"] for h in STATEFUL_HINTS):
                del rec["auto_fix"]
                rec["detail"] += (" This is a data store: extra replicas only help once replication is set up, "
                                  "so this fix is not applied automatically.")
        result["recommendations"] = recs

        if result["score"] >= RESILIENT_FROM:
            verdict = "resilient"
        elif result["score"] >= WEAK_BELOW:
            verdict = "degraded"
        else:
            verdict = "weak"
        b = result["breakdown"]
        print(f"  [Analyst agent] {result['service']} is {verdict}: score {result['score']}/100 "
              f"(errors -{b['errors']}, latency -{b['latency']}, recovery -{b['recovery']}, abort -{b['abort']})")
        for rec in recs:
            print(f"      fix: {rec['title']}")
        return result


def run_agents(cfg, env, graph, baseline, rounds, run_id, run_dir, stop_file, planner_mode="auto"):
    """Run the Planner -> Injector -> Analyst loop and return a results dict shaped like `run` produces."""
    guard = Guard(cfg, baseline, stop_file)
    if os.path.exists(stop_file):
        os.remove(stop_file)
    planner_agent = PlannerAgent(graph, cfg, planner_mode)
    injector_agent = InjectorAgent(cfg, env, baseline, guard, run_dir)
    analyst_agent = AnalystAgent(graph, baseline)
    print(f"Agents: planner ({planner_agent.mode}), injector, analyst. Safety limits: {guard.limits()}")

    history, chosen, done = [], [], []
    try:
        for i in range(1, rounds + 1):
            print(f"\n=== Round {i} of {rounds} ===")
            exp = planner_agent.decide(history)
            if exp is None:
                print("  [Planner agent] nothing new left to test; stopping.")
                break
            exp["id"] = f"exp{i}"
            print(f"  [Planner agent] chose {ACTION_LABELS[exp['action']]} on {exp['service']}")

            result = injector_agent.act(exp)
            if result is None:
                break
            analyst_agent.explain(result)
            chosen.append(exp)
            done.append(result)
            history.append({k: result[k] for k in ("service", "action", "score", "error_rate", "p95_ms",
                                                   "recovery_s", "aborted")})
            if os.path.exists(stop_file):
                print("Manual stop file found; ending the session.")
                break
            env.sleep(cfg["cooldown_s"])
    except KeyboardInterrupt:
        print("\nInterrupted: experiment removed, session ended early.")

    sources = {exp["planner"] for exp in chosen}
    planner_label = "agents (" + ", ".join(sorted(sources)) + ")"
    llm_model = next((exp["llm_model"] for exp in chosen if exp.get("llm_model")), None)
    plan = {"planner": planner_label, "llm_model": llm_model, "experiments": chosen}
    results = {"run_id": run_id, "env": env.name, "planner": plan["planner"], "llm_model": llm_model,
               "baseline": baseline,
               "limits": guard.limits(), "plan": plan, "experiments": done, "compare_to": None}
    results["resilience_score"] = round(sum(e["score"] for e in done) / len(done), 1) if done else None
    results["weaknesses"] = [{"service": e["service"], "action": e["action"], "score": e["score"]}
                             for e in sorted(done, key=lambda e: e["score"]) if e["score"] < RESILIENT_FROM]
    results["summary"] = analyzer._summary(results, cfg)
    return results