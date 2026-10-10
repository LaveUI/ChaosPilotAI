"""Agent loop: five agents take turns and learn from each round.

  ObserverAgent  watches the whole app (probes, deployments, pods, events, logs) and reports its state.
  PlannerAgent   ranks the candidate experiments from the dependency map, the observation and earlier
                 results, and picks the next one.
  InjectorAgent  decides WHETHER to inject now and for how long, injects through Chaos Mesh, reviews the
                 readings while the fault is active and can roll it back early.
  AnalystAgent   scores the result, diagnoses what happened and recommends fixes.
  ReporterAgent  ranks all weaknesses by severity and explains the overall resilience score.

Each round is Observer -> Planner -> Injector -> Analyst, and the result feeds the next round.
The Reporter runs once at the end. The agents are the nodes of a LangGraph state graph (see
run_agents); without LangGraph installed, the same nodes run in a plain Python loop.

In LLM mode (GEMINI_API_KEY set) every agent asks the model for its decision. Every answer is
validated in code before it is used: the allowlist, the protected services, the duration limits,
the safety guard and the score formula cannot be changed by the model. Without a key, or when a
model answer is unusable, the agent falls back to the transparent rules below.
"""
import os
from typing import Any, TypedDict

from . import analyzer, llm, planner, runner
from .chaos import ACTION_LABELS
from .guard import Guard

WEAK_BELOW = 50          # a service scoring under this is a confirmed weakness
RESILIENT_FROM = 90      # same threshold the analyzer uses
MIN_DURATION_S = 15
SETTLE_S = 30            # wait before retrying when the app is not yet healthy enough to test
RANKED_CANDIDATES = 5    # how many ranked experiments the planner proposes each round
# Data stores must not be "fixed" by blindly adding replicas: copies would not share data.
STATEFUL_HINTS = ("redis", "postgres", "mysql", "mongo", "kafka")
SEVERITIES = ("critical", "high", "medium", "low", "none")

OBSERVER_SYSTEM = """You are the observer agent in a chaos-engineering system for a Kubernetes app.
You get HTTP probe results and a snapshot of the cluster: deployments, unhealthy pods, restart counts,
warning events and recent logs. Say whether the application is healthy enough to run an experiment on,
and name any services that already look unhealthy. Use only the data given.
Respond with ONLY JSON: {"healthy": true or false, "summary": "<one or two sentences>",
"concerns": ["<service name>", ...]}. concerns must be service names taken from the input."""

INJECTOR_SYSTEM = """You are the injection agent in a chaos-engineering system for a Kubernetes app.
The planner chose an experiment. Decide whether it is safe and useful to inject it now, and for how long.
Inject only if the pre-flight probes and the observation show the app is healthy enough to measure a clear effect.
Choose a longer duration for faults whose effect builds up slowly (network delay, CPU stress) and a
shorter one when earlier rounds show the app fails fast.
Respond with ONLY JSON: {"inject": true or false, "duration_s": <integer seconds>, "reason": "<one or two sentences>"}.
duration_s must be between min_duration_s and max_duration_s from the input."""

ROLLBACK_SYSTEM = """You are the injection agent in a chaos-engineering system. A fault you injected is
active right now. You get the latest readings and the safety limits. Decide whether to keep the fault
running or roll it back now. Roll back when the impact is already clearly demonstrated and continuing
would only cause more damage, or when the readings are heading toward the safety limits. Continue when
more observation time is needed to see the effect.
Respond with ONLY JSON: {"rollback": true or false, "reason": "<one sentence>"}."""

ANALYST_SYSTEM = """You are the analyst agent (an SRE) in a chaos-engineering system for a Kubernetes app.
You get the measurements of ONE experiment, the dependency information of the target service, what the
observer saw in the cluster while the fault was active, and the resilience score that the system calculated.
Explain what the failure revealed and recommend fixes.
Rules: use only the numbers given, never invent measurements. Tie every fix to the evidence. Be specific
about which service should change. If the target is a data store, do not recommend simply adding replicas
without replication. If the experiment showed no impact, say so and return an empty fixes list.
Respond with ONLY JSON: {"diagnosis": "<two or three sentences>", "severity": "critical|high|medium|low|none",
"fixes": [{"title": "<short imperative>", "detail": "<why this fix, tied to the evidence>"}]}. At most 4 fixes."""

REPORTER_SYSTEM = """You are the reporting agent in a chaos-engineering system for a Kubernetes app.
You get every experiment of one session with its measurements, calculated score, diagnosis and severity,
plus the overall resilience score (the mean of the experiment scores, calculated by the system).
Write the session findings. Rank the weaknesses from most to least severe, considering how much of the
application each one affects. Explain what the overall score means. Use only the data given.
Respond with ONLY JSON: {"overall": "<three or four sentences: what broke, why it matters, what to fix first>",
"ranked_weaknesses": [{"service": "<name>", "action": "<fault>", "severity": "critical|high|medium|low",
"why": "<one sentence>"}], "score_explanation": "<one or two sentences>"}.
Include only experiments that revealed a weakness, using their exact service and action values."""


def _nodes(graph):
    return {n["name"]: n for n in graph["nodes"]}


def _severity_from_score(score):
    if score < 40:
        return "critical"
    if score < 60:
        return "high"
    if score < 80:
        return "medium"
    if score < RESILIENT_FROM:
        return "low"
    return "none"


def _compact_cluster(diag, limit=5):
    """Trim a cluster_diagnostics() snapshot so it is small enough to send to the model."""
    if not diag:
        return None
    deployments = diag.get("deployments", {})
    pods = diag.get("pods", [])
    return {
        "deployments_total": len(deployments),
        "deployments_not_ready": {n: d for n, d in deployments.items() if d["ready"] < d["desired"]},
        "unhealthy_pods": [{k: p.get(k) for k in ("name", "app", "phase", "restarts", "container_states",
                                                  "recent_logs", "log_error") if p.get(k) not in (None, [], "")}
                           for p in diag.get("unhealthy_pods", [])[:limit]],
        "pods_with_restarts": sorted(({"app": p.get("app"), "restarts": p.get("restarts", 0)}
                                      for p in pods if p.get("restarts", 0) > 0),
                                     key=lambda x: -x["restarts"])[:limit],
        "warning_events": [{k: ev.get(k) for k in ("reason", "message", "object_kind", "object_name", "count")}
                           for ev in diag.get("warning_events", [])[:limit]],
    }


class ObserverAgent:
    """Watches the whole application and reports whether it is healthy."""

    def __init__(self, cfg, env, graph, use_llm=False):
        self.cfg, self.env, self.use_llm = cfg, env, use_llm
        self.services = {n["name"] for n in graph["nodes"]}

    def snapshot(self):
        """Raw facts: three probes plus the cluster state (if the environment can provide it)."""
        probes = []
        for _ in range(3):
            ok, ms = self.env.probe()
            probes.append({"ok": bool(ok), "latency_ms": round(ms)})
            self.env.sleep(self.cfg["probe_interval_s"])
        cluster = None
        diagnostics = getattr(self.env, "cluster_diagnostics", None)
        if diagnostics:
            try:
                cluster = _compact_cluster(diagnostics())
            except Exception as exc:        # kubectl hiccup: observe with probes only
                print(f"  [Observer agent] cluster snapshot failed ({exc.__class__.__name__}); using probes only.")
        return {"probes": probes, "cluster": cluster}

    def _by_rules(self, snap):
        failed = sum(1 for p in snap["probes"] if not p["ok"])
        cluster = snap["cluster"] or {}
        not_ready = sorted(cluster.get("deployments_not_ready", {}))
        healthy = failed == 0 and not not_ready
        parts = [f"{3 - failed} of 3 probes succeeded"]
        if snap["cluster"] is not None:
            total = cluster.get("deployments_total", 0)
            parts.append(f"{total - len(not_ready)} of {total} deployments ready")
            if not_ready:
                parts.append("not ready: " + ", ".join(not_ready))
            if cluster.get("warning_events"):
                parts.append(f"{len(cluster['warning_events'])} recent warning event(s)")
        return {"healthy": healthy, "summary": "; ".join(parts) + ".",
                "concerns": [s for s in not_ready if s in self.services], "source": "rule-based"}

    def observe(self):
        snap = self.snapshot()
        obs = self._by_rules(snap)
        if self.use_llm:
            try:
                raw = llm.ask_json(self.cfg, OBSERVER_SYSTEM, snap, max_tokens=400)
                summary = str(raw.get("summary", "")).strip()[:500]
                if not isinstance(raw.get("healthy"), bool) or not summary:
                    raise ValueError("incomplete observation")
                concerns = [c for c in (raw.get("concerns") or []) if isinstance(c, str) and c in self.services]
                obs = {"healthy": raw["healthy"], "summary": summary, "concerns": concerns[:6], "source": "llm"}
            except Exception as exc:
                print(f"  [Observer agent] LLM observation failed ({exc.__class__.__name__}); using the rules.")
        obs["probes"] = snap["probes"]
        print(f"  [Observer agent] ({obs['source']}) {'healthy' if obs['healthy'] else 'NOT healthy'}: {obs['summary']}")
        return obs


class PlannerAgent:
    """Ranks candidate experiments and picks the next one. One decision per round, so it can react to results."""

    def __init__(self, graph, cfg, mode="auto"):
        self.graph, self.cfg = graph, cfg
        if mode not in {"auto", "llm", "rule-based"}:
            raise ValueError(f"Unknown planner mode: {mode}")
        if mode == "llm" and not llm.available(cfg):
            raise RuntimeError("LLM planner selected, but Gemini is unavailable. Set GEMINI_API_KEY and install google-genai.")
        self.mode = "llm" if mode == "llm" or (mode == "auto" and llm.available(cfg)) else "rule-based"
        self.avoid = set()        # (service, action) pairs the injector declined
        self.last_ranked = []     # the ranked candidates of the latest decision, for the report

    def decide(self, history, observation=None):
        tested = {(h["service"], h["action"]) for h in history} | self.avoid
        obs = {k: observation[k] for k in ("healthy", "summary", "concerns")} if observation else None
        if self.mode == "llm":
            try:
                p = planner.plan(self.graph, self.cfg, history, RANKED_CANDIDATES, mode="llm", observation=obs)
            except RuntimeError as exc:
                if not history and not self.avoid:
                    raise                      # first decision: fail loudly (bad key, bad model name)
                print(f"  [Planner agent] {exc}")
                p = {"planner": "failed", "experiments": []}   # later rounds: keep the session alive
            ranked = p["experiments"] if p["planner"] == "llm" else []
            chosen = next((x for x in ranked if (x["service"], x["action"]) not in tested), None)
            if chosen:
                chosen["planner"], chosen["llm_model"] = "llm", p["llm_model"]
                self._remember(ranked, chosen, tested)
                return chosen
            print("  [Planner agent] Gemini proposed nothing new; using the rules for this round.")
        chosen = self._decide_by_rules(history, tested, observation)
        if chosen:
            chosen["planner"] = "rule-based"
        return chosen

    def _remember(self, ranked, chosen, tested):
        self.last_ranked = [{"rank": i, "service": x["service"], "action": x["action"],
                             "rationale": x["rationale"], "chosen": x is chosen,
                             "already_tested": (x["service"], x["action"]) in tested}
                            for i, x in enumerate(ranked, 1)]

    def _decide_by_rules(self, history, tested, observation=None):
        tried_actions = {h["action"] for h in history}
        concerns = set((observation or {}).get("concerns", []))
        times_hit, weak = {}, set()
        for h in history:
            times_hit[h["service"]] = times_hit.get(h["service"], 0) + 1
            if h["score"] < WEAK_BELOW:
                weak.add(h["service"])

        scored = []
        for node in self.graph["nodes"]:
            name = node["name"]
            if name in self.cfg["exclude_services"] or name in concerns:   # never test an already-unhealthy service
                continue
            for action in self.cfg["allowlist"]:
                if (name, action) in tested:
                    continue
                score = 3 * node["transitive_dependents"]          # how much of the app relies on it
                score += 4 if node["replicas"] < 2 else 0          # single point of failure
                score += 5 if action not in tried_actions else 0   # learn about a new failure type
                score -= 3 * times_hit.get(name, 0)                # spread out over services
                score -= 6 if name in weak else 0                  # weakness already confirmed: move on
                scored.append(((score, name, action), node, action))
        if not scored:
            self.last_ranked = []
            return None
        scored.sort(key=lambda x: x[0], reverse=True)
        top, seen = [], set()
        for _key, node, action in scored:                          # one candidate per service, like the LLM plan
            if node["name"] not in seen:
                seen.add(node["name"])
                top.append((node, action))
            if len(top) == RANKED_CANDIDATES:
                break
        picks = [{"service": node["name"], "action": action, "rationale": self._why(node, action, history, weak)}
                 for node, action in top]
        ranked = planner._finalize(picks, self.graph, self.cfg)
        self._remember(ranked, ranked[0], tested)
        return ranked[0]

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
    """Decides whether to inject and for how long, injects, and can roll the fault back early.

    Hard checks (allowlist, protected services, app health) are code. In LLM mode the model then makes
    the go/no-go, duration and rollback decisions, and the code clamps them to the configured limits.
    The safety guard is checked on every probe, before the agent is asked, and cannot be overridden."""

    def __init__(self, cfg, env, baseline, guard, run_dir, use_llm=False):
        self.cfg, self.env, self.baseline, self.guard, self.run_dir = cfg, env, baseline, guard, run_dir
        self.use_llm = use_llm
        self.fault_snapshot = None      # cluster state captured while the fault is active
        self._current = None

    def preflight(self, exp, observation=None):
        """Return (reason to refuse or None, pre-flight probe readings)."""
        if exp["action"] not in self.cfg["allowlist"]:
            return f"action {exp['action']} is not on the allowlist", []
        if exp["service"] in self.cfg["exclude_services"]:
            return f"{exp['service']} is a protected service", []
        probes = (observation or {}).get("probes")
        if not probes:
            probes = []
            for _ in range(3):
                ok, ms = self.env.probe()
                probes.append({"ok": bool(ok), "latency_ms": round(ms)})
                self.env.sleep(self.cfg["probe_interval_s"])
        if not any(p["ok"] for p in probes):
            return "the app is not healthy right now (3 of 3 probes failed)", probes
        return None, probes

    def _decide(self, exp, probes, history, observation):
        """Ask the LLM for go/no-go and duration. Returns (inject, duration_s, reason, source)."""
        max_d = int(exp["duration_s"])
        min_d = min(MIN_DURATION_S, max_d)
        if not self.use_llm:
            return True, max_d, "pre-flight checks passed", "rule-based"
        payload = {"experiment": {k: exp[k] for k in ("service", "action", "rationale")},
                   "preflight_probes": probes, "baseline": self.baseline, "safety_limits": self.guard.limits(),
                   "observation": {k: observation[k] for k in ("healthy", "summary", "concerns")} if observation else None,
                   "earlier_rounds": history, "min_duration_s": min_d, "max_duration_s": max_d}
        try:
            raw = llm.ask_json(self.cfg, INJECTOR_SYSTEM, payload, max_tokens=400)
            inject = raw.get("inject")
            duration = raw.get("duration_s")
            if not isinstance(inject, bool):
                raise ValueError("missing inject decision")
            if not isinstance(duration, (int, float)) or isinstance(duration, bool):
                duration = max_d
            duration = int(min(max_d, max(min_d, duration)))     # code enforces the limits
            return inject, duration, str(raw.get("reason", ""))[:400], "llm"
        except Exception as exc:
            print(f"  [Injector agent] LLM decision failed ({exc.__class__.__name__}); using the default duration.")
            return True, max_d, "pre-flight checks passed", "rule-based"

    def review(self, readings):
        """Called by the runner while the fault is active. Return a reason to roll back now, or None."""
        if self.fault_snapshot is None:                 # observe the cluster once while it is under the fault
            diagnostics = getattr(self.env, "cluster_diagnostics", None)
            if diagnostics:
                try:
                    self.fault_snapshot = _compact_cluster(diagnostics())
                except Exception:
                    self.fault_snapshot = None
        if not self.use_llm:
            return None                                  # rule-based mode: only the safety guard stops a fault
        payload = {"experiment": {k: self._current[k] for k in ("service", "action")},
                   "readings": readings, "baseline": self.baseline, "safety_limits": self.guard.limits()}
        try:
            raw = llm.ask_json(self.cfg, ROLLBACK_SYSTEM, payload, max_tokens=200)
            if raw.get("rollback") is True:
                return str(raw.get("reason", "")).strip()[:300] or "the agent decided to roll back"
        except Exception as exc:
            print(f"  [Injector agent] rollback review failed ({exc.__class__.__name__}); continuing under the safety guard.")
        return None

    def act(self, exp, history=(), observation=None):
        """Return the experiment result, or None if refused (hard check) or "declined" (agent's choice)."""
        refusal, probes = self.preflight(exp, observation)
        if refusal:
            print(f"  [Injector agent] refused: {refusal}.")
            return None
        inject, duration, reason, source = self._decide(exp, probes, list(history), observation)
        if not inject:
            print(f"  [Injector agent] ({source}) declined to inject: {reason}")
            return "declined"
        exp["duration_s"] = duration
        exp["injector"], exp["injector_reason"] = source, reason
        print(f"  [Injector agent] ({source}) injecting for {duration}s: {reason}")
        self._current, self.fault_snapshot = exp, None
        result = None
        for attempt in (1, 2):
            try:
                result = runner.run_experiment(exp, self.cfg, self.env, self.baseline, self.guard, self.run_dir,
                                               on_sample=self.review)
                break
            except RuntimeError as exc:
                # The runner refuses to start when its own pre-experiment reading is unhealthy.
                # Nothing has been injected at that point, so wait once and retry instead of crashing.
                if attempt == 1:
                    print(f"  [Injector agent] not injected: {exc}. Waiting {SETTLE_S}s for the app to settle.")
                    self.env.sleep(SETTLE_S)
                else:
                    print(f"  [Injector agent] skipped this round: {exc}.")
                    return "declined"
        result["injector"], result["injector_reason"] = source, reason
        result["fault_observation"] = self.fault_snapshot
        if result.get("agent_rollback"):
            print(f"  [Injector agent] ({source}) rolled the fault back early: {result['agent_rollback']}")
        return result


class AnalystAgent:
    """Scores one result (fixed formula), then diagnoses it and recommends fixes."""

    def __init__(self, graph, baseline, cfg=None, use_llm=False):
        self.nodes, self.baseline = _nodes(graph), baseline
        self.cfg, self.use_llm = cfg, bool(use_llm and cfg)

    def _rule_fixes(self, result):
        recs = []
        if result["score"] < RESILIENT_FROM:
            recs = analyzer.recommend(result, self.nodes[result["service"]], self.baseline)
        for rec in recs:
            rec["source"] = "rule-based"
            fx = rec.get("auto_fix")
            if fx and any(h in fx["service"] for h in STATEFUL_HINTS):
                del rec["auto_fix"]
                rec["detail"] += (" This is a data store: extra replicas only help once replication is set up, "
                                  "so this fix is not applied automatically.")
        return recs

    def _llm_fixes(self, result, rule_recs):
        """Ask the LLM for a diagnosis and fixes. Returns (diagnosis, severity, fixes) or None on failure."""
        node = self.nodes[result["service"]]
        payload = {
            "experiment": {k: result.get(k) for k in ("service", "action", "duration_s", "aborted", "abort_reason",
                                                      "agent_rollback", "error_rate", "p95_ms", "peak_error_rate",
                                                      "peak_p95_ms", "recovered", "recovery_s")},
            "phase_metrics": result.get("phase_metrics"),
            "impact": result.get("impact"),
            "cluster_during_fault": result.get("fault_observation"),
            "baseline": self.baseline,
            "calculated_score": result["score"], "score_penalties": result["breakdown"],
            "target_service": {"replicas": node["replicas"], "calls": node["depends_on"],
                               "called_by": node["depended_by"],
                               "services_relying_on_it": node["transitive_dependents"],
                               "is_data_store": any(h in node["name"] for h in STATEFUL_HINTS)},
            "rule_based_suggestions": [r["title"] for r in rule_recs],
        }
        try:
            raw = llm.ask_json(self.cfg, ANALYST_SYSTEM, payload, max_tokens=900)
            diagnosis = str(raw.get("diagnosis", "")).strip()[:800]
            if not diagnosis:
                raise ValueError("empty diagnosis")
            severity = str(raw.get("severity", "")).lower()
            if severity not in SEVERITIES:
                severity = None
            fixes = []
            for f in (raw.get("fixes") or [])[:4]:
                if isinstance(f, dict) and str(f.get("title", "")).strip():
                    fixes.append({"title": str(f["title"]).strip().rstrip(".")[:160],
                                  "detail": str(f.get("detail", "")).strip()[:600], "source": "llm"})
            return diagnosis, severity, fixes
        except Exception as exc:
            print(f"  [Analyst agent] LLM analysis failed ({exc.__class__.__name__}); using the rule-based fixes.")
            return None

    def explain(self, result):
        result["score"], result["breakdown"] = analyzer.score_result(result, self.baseline)
        rule_recs = self._rule_fixes(result)
        result["analyst"], result["recommendations"] = "rule-based", rule_recs
        result["severity"] = _severity_from_score(result["score"])
        if self.use_llm:
            answer = self._llm_fixes(result, rule_recs)
            if answer:
                diagnosis, severity, fixes = answer
                # keep rule-based entries that carry a safe automatic fix, so `fix` and `rerun` still work
                keep = [r for r in rule_recs if r.get("auto_fix")]
                result.update({"analyst": "llm", "analyst_model": llm.model_name(self.cfg),
                               "ai_diagnosis": diagnosis, "ai_severity": severity,
                               "severity": severity or result["severity"],
                               "recommendations": fixes + keep})

        if result["score"] >= RESILIENT_FROM:
            verdict = "resilient"
        elif result["score"] >= WEAK_BELOW:
            verdict = "degraded"
        else:
            verdict = "weak"
        b = result["breakdown"]
        print(f"  [Analyst agent] ({result['analyst']}) {result['service']} is {verdict}: score {result['score']}/100, "
              f"severity {result['severity']} "
              f"(errors -{b['errors']}, latency -{b['latency']}, recovery -{b['recovery']}, abort -{b['abort']})")
        if result.get("ai_diagnosis"):
            print(f"      diagnosis: {result['ai_diagnosis']}")
        for rec in result["recommendations"]:
            print(f"      fix ({rec.get('source', 'rule-based')}): {rec['title']}")
        return result


class ReporterAgent:
    """Ranks all weaknesses by severity and explains the overall score."""

    def __init__(self, cfg, use_llm=False):
        self.cfg, self.use_llm = cfg, use_llm

    @staticmethod
    def _by_rules(done, overall_score):
        order = {s: i for i, s in enumerate(SEVERITIES)}
        weak = sorted((e for e in done if e["score"] < RESILIENT_FROM),
                      key=lambda e: (order.get(e.get("severity"), 9), e["score"]))
        ranked = [{"service": e["service"], "action": e["action"], "severity": e.get("severity") or "low",
                   "score": e["score"],
                   "why": f"Scored {e['score']}/100 with {e['error_rate']:.0%} errors during the fault."}
                  for e in weak]
        return {"overall": None, "ranked_weaknesses": ranked, "source": "rule-based",
                "score_explanation": (f"{overall_score}/100 is the mean of {len(done)} experiment score(s); each starts "
                                      "at 100 and loses points for errors, latency, recovery time and safety aborts.")}

    def summarise(self, done, overall_score):
        report = self._by_rules(done, overall_score)
        if self.use_llm and done:
            slim = [{k: e.get(k) for k in ("service", "action", "score", "severity", "error_rate", "p95_ms",
                                           "recovery_s", "aborted", "abort_reason", "agent_rollback",
                                           "breakdown", "ai_diagnosis")} for e in done]
            try:
                raw = llm.ask_json(self.cfg, REPORTER_SYSTEM,
                                   {"resilience_score": overall_score, "experiments": slim}, max_tokens=900)
                overall = str(raw.get("overall", "")).strip()[:1200]
                if not overall:
                    raise ValueError("empty report")
                by_pair = {(e["service"], e["action"]): e for e in done}
                ranked = []
                for w in raw.get("ranked_weaknesses") or []:
                    pair = (w.get("service"), w.get("action")) if isinstance(w, dict) else None
                    if pair in by_pair and pair not in {(r["service"], r["action"]) for r in ranked}:
                        sev = str(w.get("severity", "")).lower()
                        ranked.append({"service": pair[0], "action": pair[1], "score": by_pair[pair]["score"],
                                       "severity": sev if sev in SEVERITIES else by_pair[pair].get("severity"),
                                       "why": str(w.get("why", "")).strip()[:400]})
                report = {"overall": overall, "ranked_weaknesses": ranked or report["ranked_weaknesses"],
                          "score_explanation": str(raw.get("score_explanation", "")).strip()[:500]
                          or report["score_explanation"],
                          "source": "llm", "model": llm.model_name(self.cfg)}
            except Exception as exc:
                print(f"[Reporter agent] LLM report failed ({exc.__class__.__name__}); using the rule-based ranking.")
        print(f"\n[Reporter agent] ({report['source']}) weaknesses by severity:")
        for i, w in enumerate(report["ranked_weaknesses"], 1):
            print(f"  {i}. {w['severity']}: {ACTION_LABELS.get(w['action'], w['action'])} on {w['service']} "
                  f"(score {w['score']})")
        if not report["ranked_weaknesses"]:
            print("  none found in this session")
        return report


class AgentState(TypedDict, total=False):
    """State passed between the agent nodes of the graph."""
    round: int          # current round number
    observation: Any    # what the Observer reported this round
    exp: Any            # the experiment the Planner chose
    result: Any         # the measured result of that experiment
    outcome: str        # what the last node did; the routing reads this


def _build_graph(lg, nodes, after_planner, after_injector, after_analyst):
    """Wire the five agent nodes into a LangGraph StateGraph and compile it."""
    builder = lg.StateGraph(AgentState)
    for name, fn in nodes.items():
        builder.add_node(name, fn)
    builder.add_edge(lg.START, "observer")
    builder.add_edge("observer", "planner")
    builder.add_conditional_edges("planner", after_planner, ["injector", "reporter"])
    builder.add_conditional_edges("injector", after_injector, ["analyst", "observer", "reporter"])
    builder.add_conditional_edges("analyst", after_analyst, ["observer", "reporter"])
    builder.add_edge("reporter", lg.END)
    return builder.compile()


def _langgraph():
    """Return the langgraph.graph module, or None if LangGraph is not installed."""
    try:
        from langgraph import graph
        return graph
    except ImportError:
        return None


def run_agents(cfg, env, graph, baseline, rounds, run_id, run_dir, stop_file, planner_mode="auto"):
    """Run the agent graph: Observer -> Planner -> Injector -> Analyst, repeated, then the Reporter.

    The five agents are nodes of a LangGraph StateGraph. If LangGraph is not installed, the same
    nodes and the same routing run in a plain Python loop. Returns a results dict shaped like the
    one `run` produces, with the agents' decisions added."""
    guard = Guard(cfg, baseline, stop_file)
    if os.path.exists(stop_file):
        os.remove(stop_file)
    planner_agent = PlannerAgent(graph, cfg, planner_mode)
    use_llm = planner_agent.mode == "llm"
    observer_agent = ObserverAgent(cfg, env, graph, use_llm)
    injector_agent = InjectorAgent(cfg, env, baseline, guard, run_dir, use_llm)
    analyst_agent = AnalystAgent(graph, baseline, cfg, use_llm)
    reporter_agent = ReporterAgent(cfg, use_llm)
    mode = planner_agent.mode
    lg = _langgraph()
    orchestrator = "LangGraph state graph" if lg else "Python loop (LangGraph not installed)"
    print(f"Agents ({mode}): observer, planner, injector, analyst, reporter. Orchestrator: {orchestrator}.")
    print(f"Safety limits: {guard.limits()}")

    # Session memory shared by all nodes. It lives outside the graph state so that a Ctrl+C
    # (the manual kill switch) still leaves everything collected so far for the report.
    history, chosen, done, round_log = [], [], [], []
    final = {}

    # ---------------- nodes: each returns the keys of the state it changes ----------------
    def observer_node(state):
        i = state.get("round", 0) + 1
        print(f"\n=== Round {i} of {rounds} ===")
        return {"round": i, "observation": observer_agent.observe(), "outcome": "observed"}

    def planner_node(state):
        observation = state["observation"]
        exp = planner_agent.decide(history, observation)
        if exp is None:
            print("  [Planner agent] nothing new left to test; stopping.")
            return {"exp": None, "outcome": "nothing_left"}
        exp["id"] = f"exp{state['round']}"
        ranked = planner_agent.last_ranked
        print(f"  [Planner agent] ({exp['planner']}) ranked {len(ranked)} candidate(s), "
              f"chose {ACTION_LABELS[exp['action']]} on {exp['service']}")
        for r in ranked:
            print(f"      {r['rank']}. {ACTION_LABELS.get(r['action'], r['action'])} on {r['service']}"
                  + ("  <- chosen" if r["chosen"] else "") + ("  (already tested)" if r["already_tested"] else ""))
        round_log.append({"round": state["round"],
                          "observation": {k: observation[k] for k in ("healthy", "summary", "concerns", "source")},
                          "ranked_candidates": ranked, "outcome": "ran"})
        return {"exp": exp, "outcome": "planned"}

    def injector_node(state):
        exp = state["exp"]
        result = injector_agent.act(exp, history, state["observation"])
        if result is None:
            round_log[-1]["outcome"] = "refused"
            return {"result": None, "outcome": "refused"}
        if result == "declined":
            round_log[-1]["outcome"] = "declined"
            planner_agent.avoid.add((exp["service"], exp["action"]))
            return {"result": None, "outcome": "declined"}
        result["observation"] = round_log[-1]["observation"]
        result["ranked_candidates"] = round_log[-1]["ranked_candidates"]
        result["planner"] = exp["planner"]
        return {"result": result, "outcome": "ran"}

    def analyst_node(state):
        result, exp = state["result"], state["exp"]
        analyst_agent.explain(result)
        chosen.append(exp)
        done.append(result)
        entry = {k: result[k] for k in ("service", "action", "score", "error_rate", "p95_ms",
                                        "recovery_s", "aborted")}
        if result.get("ai_diagnosis"):
            entry["diagnosis"] = result["ai_diagnosis"]
        history.append(entry)
        if os.path.exists(stop_file):
            print("Manual stop file found; ending the session.")
            return {"outcome": "stopped"}
        env.sleep(cfg["cooldown_s"])
        return {"outcome": "analysed"}

    def reporter_node(state):
        final.update(_finish(cfg, env, baseline, guard, planner_agent, reporter_agent, run_id,
                             chosen, done, round_log, orchestrator))
        return {"outcome": "reported"}

    # ---------------- routing: which node runs next ----------------
    def after_planner(state):
        return "injector" if state["outcome"] == "planned" else "reporter"

    def after_injector(state):
        if state["outcome"] == "ran":
            return "analyst"
        if state["outcome"] == "declined" and state["round"] < rounds:
            return "observer"
        return "reporter"

    def after_analyst(state):
        return "observer" if state["outcome"] == "analysed" and state["round"] < rounds else "reporter"

    nodes = {"observer": observer_node, "planner": planner_node, "injector": injector_node,
             "analyst": analyst_node, "reporter": reporter_node}

    try:
        if lg:
            app = _build_graph(lg, nodes, after_planner, after_injector, after_analyst)
            app.invoke({"round": 0}, {"recursion_limit": 5 * rounds + 10})
        else:
            state, node = {"round": 0}, "observer"
            routes = {"observer": lambda s: "planner", "planner": after_planner, "injector": after_injector,
                      "analyst": after_analyst, "reporter": lambda s: None}
            while node:
                state.update(nodes[node](state))
                node = routes[node](state)
    except KeyboardInterrupt:
        print("\nInterrupted: experiment removed, session ended early.")
    if not final:                      # interrupted before the reporter ran
        reporter_node({})
    return final


def agent_graph_mermaid():
    """Mermaid text of the agent graph, for the architecture page. Needs LangGraph installed."""
    lg = _langgraph()
    if not lg:
        return None
    names = ("observer", "planner", "injector", "analyst", "reporter")
    app = _build_graph(lg, {name: (lambda state: {}) for name in names},
                       lambda s: "injector", lambda s: "analyst", lambda s: "observer")
    return app.get_graph().draw_mermaid()


def _finish(cfg, env, baseline, guard, planner_agent, reporter_agent, run_id, chosen, done, round_log, orchestrator):
    """Reporter step: build the final results dict."""
    sources = {exp["planner"] for exp in chosen}
    planner_label = "agents (" + ", ".join(sorted(sources)) + ")"
    llm_model = next((exp["llm_model"] for exp in chosen if exp.get("llm_model")), None)
    plan = {"planner": planner_label, "llm_model": llm_model, "experiments": chosen}
    results = {"run_id": run_id, "env": env.name, "planner": plan["planner"], "llm_model": llm_model,
               "baseline": baseline, "rounds": round_log, "orchestrator": orchestrator,
               "limits": guard.limits(), "plan": plan, "experiments": done, "compare_to": None}
    results["resilience_score"] = round(sum(e["score"] for e in done) / len(done), 1) if done else None
    results["weaknesses"] = [{"service": e["service"], "action": e["action"], "score": e["score"]}
                             for e in sorted(done, key=lambda e: e["score"]) if e["score"] < RESILIENT_FROM]
    ai_report = reporter_agent.summarise(done, results["resilience_score"]) if done else None
    results["ai_report"] = ai_report
    results["summary"] = ai_report["overall"] if ai_report else None
    if ai_report and ai_report.get("model"):
        results["summary_model"] = ai_report["model"]

    def used(key):
        return "llm" if any(e.get(key) == "llm" for e in done) else "rule-based"
    results["agents"] = {
        "observer": "llm" if any(r["observation"]["source"] == "llm" for r in round_log) else "rule-based",
        "planner": "llm" if "llm" in sources else "rule-based",
        "injector": used("injector"), "analyst": used("analyst"),
        "reporter": (ai_report or {}).get("source", "rule-based"),
    }
    return results