import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chaosai import analyzer, chaos, config, mapper, planner, report, runner  # noqa: E402
from chaosai.env import SimEnv  # noqa: E402
from chaosai.guard import Guard  # noqa: E402

MANIFEST = os.path.join(ROOT, "sample", "kubernetes-manifests.yaml")


def cfg_in(tmp):
    cfg = config.load(None)
    cfg["runs_dir"] = tmp
    cfg["cooldown_s"] = 0
    return cfg


class MapperTests(unittest.TestCase):
    def setUp(self):
        self.g = mapper.build_graph(MANIFEST)
        self.nodes = {n["name"]: n for n in self.g["nodes"]}

    def test_finds_services_and_edges(self):
        self.assertEqual(len(self.nodes), 12)
        self.assertIn("productcatalogservice", self.nodes["frontend"]["depends_on"])
        self.assertIn("redis-cart", self.nodes["cartservice"]["depends_on"])
        self.assertIn("frontend", self.nodes["loadgenerator"]["depends_on"])

    def test_transitive_dependents(self):
        self.assertGreaterEqual(self.nodes["productcatalogservice"]["transitive_dependents"], 3)
        self.assertEqual(self.nodes["loadgenerator"]["transitive_dependents"], 0)

    def test_overrides(self):
        g = mapper.build_graph(MANIFEST, {"add_edges": [["adservice", "redis-cart"]],
                                          "remove_edges": [["frontend", "adservice"]]})
        n = {x["name"]: x for x in g["nodes"]}
        self.assertIn("redis-cart", n["adservice"]["depends_on"])
        self.assertNotIn("adservice", n["frontend"]["depends_on"])


class ChaosTests(unittest.TestCase):
    def test_render_each_allowed_action(self):
        cfg = config.load(None)
        kinds = {"pod-failure": "PodChaos", "network-delay": "NetworkChaos", "cpu-stress": "StressChaos"}
        for action, kind in kinds.items():
            m = chaos.render({"service": "cartservice", "app_label": "cartservice", "action": action,
                              "duration_s": 30}, cfg)
            self.assertEqual(m["kind"], kind)
            self.assertEqual(m["spec"]["duration"], "30s")

    def test_unknown_action_rejected(self):
        with self.assertRaises(ValueError):
            chaos.render({"service": "x", "app_label": "x", "action": "delete-namespace", "duration_s": 5},
                         config.load(None))


class GuardTests(unittest.TestCase):
    def test_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            stop = os.path.join(tmp, "STOP")
            g = Guard(config.load(None), {"p95_ms": 100}, stop)
            self.assertIsNone(g.check(0.1, 200, 0))
            self.assertIn("error rate", g.check(0.6, 200, 0))
            self.assertIn("p95", g.check(0.0, 5000, 0))
            self.assertIn("blast radius", g.check(0.0, 100, 9))
            open(stop, "w").close()
            self.assertIn("manual", g.check(0.0, 100, 0))


class ScoreTests(unittest.TestCase):
    base = {"p95_ms": 100}

    def res(self, **kw):
        r = {"error_rate": 0.0, "p95_ms": 100, "recovered": True, "recovery_s": 0, "aborted": False}
        r.update(kw)
        return r

    def test_perfect_and_worst(self):
        self.assertEqual(analyzer.score_result(self.res(), self.base)[0], 100.0)
        worst = self.res(error_rate=1, p95_ms=5000, recovered=False, recovery_s=None, aborted=True)
        self.assertEqual(analyzer.score_result(worst, self.base)[0], 0.0)

    def test_monotonic(self):
        s = lambda **kw: analyzer.score_result(self.res(**kw), self.base)[0]
        self.assertGreater(s(error_rate=0.1), s(error_rate=0.3))
        self.assertGreater(s(p95_ms=200), s(p95_ms=600))
        self.assertGreater(s(recovery_s=5), s(recovery_s=40))


class PlannerTests(unittest.TestCase):
    def test_heuristic_respects_rules(self):
        cfg = config.load(None)
        g = mapper.build_graph(MANIFEST)
        picks = planner.plan(g, cfg, [], 5)["experiments"]
        self.assertEqual(len(picks), 5)
        self.assertEqual(len({p["service"] for p in picks}), 5)
        for p in picks:
            self.assertNotIn(p["service"], cfg["exclude_services"])
            self.assertIn(p["action"], cfg["allowlist"])

    def test_llm_output_is_validated(self):
        cfg = config.load(None)
        g = mapper.build_graph(MANIFEST)
        raw = {"experiments": [
            {"service": "cartservice", "action": "pod-failure", "rationale": "ok"},
            {"service": "frontend", "action": "pod-failure", "rationale": "excluded"},
            {"service": "nope", "action": "pod-failure", "rationale": "unknown service"},
            {"service": "adservice", "action": "rm-rf", "rationale": "not allowed"}]}
        picks = planner._validate_llm(raw, g, cfg, 5)
        self.assertEqual([p["service"] for p in picks], ["cartservice"])

    def test_explicit_llm_requires_gemini(self):
        with patch("chaosai.planner.llm.available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Gemini is unavailable"):
                planner.plan(mapper.build_graph(MANIFEST), config.load(None), mode="llm")

    def test_explicit_rule_based_does_not_call_gemini(self):
        with patch("chaosai.planner.llm.available", side_effect=AssertionError("must not check Gemini")):
            result = planner.plan(mapper.build_graph(MANIFEST), config.load(None), mode="rule-based")
        self.assertEqual(result["planner"], "rule-based")


class ReportTests(unittest.TestCase):
    def test_report_labels_gemini_content_and_code_calculated_results(self):
        results = {
            "run_id": "test-run",
            "env": "simulated",
            "planner": "llm",
            "llm_model": "gemini-test",
            "resilience_score": 90,
            "baseline": {"error_rate": 0.0, "p95_ms": 100},
            "summary": "The service recovered after the test.",
            "experiments": [{
                "service": "cartservice",
                "action": "pod-failure",
                "score": 90,
                "error_rate": 0.0,
                "p95_ms": 110,
                "recovered": True,
                "recovery_s": 1,
                "aborted": False,
                "abort_reason": None,
                "abort_latency_s": None,
                "rationale": "Tests whether callers tolerate a pod outage.",
                "planner": "llm",
                "breakdown": {"errors": 0, "latency": 0, "recovery": 0, "abort": 0},
                "samples": [],
                "recommendations": [],
            }],
        }

        rendered = report.render(results, {"nodes": []})

        self.assertIn("Gemini model: gemini-test", rendered)
        self.assertIn("Gemini-generated summary", rendered)
        self.assertIn("Gemini planner rationale", rendered)
        self.assertIn("Probe measurements, resilience scores", rendered)


class SimulatedRunTests(unittest.TestCase):
    def run_one(self, replicas):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = cfg_in(tmp)
            g = mapper.build_graph(MANIFEST)
            env = SimEnv(cfg, g)
            env.replicas["productcatalogservice"] = replicas
            base = runner.measure_baseline(cfg, env, 30)
            plan = planner.plan(g, cfg, [], 1)
            exp = dict(plan["experiments"][0], service="productcatalogservice",
                       app_label="productcatalogservice", action="pod-failure")
            guard = Guard(cfg, base, os.path.join(tmp, "STOP"))
            r = runner.run_experiment(exp, cfg, env, base, guard, tmp)
            r["score"], _ = analyzer.score_result(r, base)
            return r

    def test_single_replica_aborts_and_fix_helps(self):
        before, after = self.run_one(1), self.run_one(2)
        self.assertTrue(before["aborted"])
        self.assertFalse(after["aborted"])
        self.assertGreater(after["score"], before["score"])

    def test_run_ids_are_unique(self):
        ids = {datetime.now().strftime("%Y%m%d-%H%M%S-%f") for _ in range(10)}
        self.assertEqual(len(ids), 10)


class LlmAgentLoopTests(unittest.TestCase):
    """All five agents in LLM mode, with the model replaced by a scripted fake."""

    def run_loop(self, fake, rounds=2):
        from unittest import mock
        from chaosai import agents, llm
        with tempfile.TemporaryDirectory() as tmp:
            cfg = cfg_in(tmp)
            g = mapper.build_graph(MANIFEST)
            env = SimEnv(cfg, g)
            base = runner.measure_baseline(cfg, env, 30)
            with mock.patch.object(llm, "available", return_value=True), \
                 mock.patch.object(llm, "ask_json", side_effect=fake), \
                 mock.patch.object(llm, "model_name", return_value="fake-model"):
                res = agents.run_agents(cfg, env, g, base, rounds, "t", os.path.join(tmp, "run"),
                                        os.path.join(tmp, "STOP"), planner_mode="llm")
                if res["experiments"]:
                    report.render(res, g, None)      # the report must render with the agent fields
                return res

    @staticmethod
    def scripted(picks, inject=True, duration=30, rollback=False, overrides=None):
        """Fake model. `picks` is one ranked list of (service, action) per planner call."""
        picks = [list(p) for p in picks]
        overrides = overrides or {}

        def fake(cfg, system, payload, max_tokens=1500):
            for key, answer in overrides.items():
                if key in system:
                    return answer
            if "observer agent" in system:
                return {"healthy": True, "summary": "All deployments are ready.", "concerns": []}
            if "planner agent" in system:
                ranked = picks.pop(0)
                return {"experiments": [{"service": s, "action": a, "rationale": "llm reason"} for s, a in ranked]}
            if "A fault you injected is" in system:
                return {"rollback": rollback, "reason": "impact is already clear"}
            if "injection agent" in system:
                return {"inject": inject, "duration_s": duration, "reason": "app is healthy"}
            if "analyst agent" in system:
                return {"diagnosis": "The service failed under the fault.", "severity": "high",
                        "fixes": [{"title": "Add a timeout", "detail": "Bound the wait."}]}
            if "reporting agent" in system:
                return {"overall": "Overall findings.", "score_explanation": "Mean of the scores.",
                        "ranked_weaknesses": [{"service": e["service"], "action": e["action"],
                                               "severity": "high", "why": "It broke."}
                                              for e in payload["experiments"]]
                        + [{"service": "made-up", "action": "pod-failure", "severity": "critical", "why": "x"}]}
            raise AssertionError("unexpected prompt: " + system[:60])
        return fake

    def test_all_five_agents_use_the_llm(self):
        res = self.run_loop(self.scripted([[("productcatalogservice", "network-delay"), ("adservice", "cpu-stress")],
                                           [("shippingservice", "cpu-stress")]]))
        self.assertEqual(res["agents"], {"observer": "llm", "planner": "llm", "injector": "llm",
                                         "analyst": "llm", "reporter": "llm"})
        first = res["experiments"][0]
        self.assertEqual(first["duration_s"], 30)
        self.assertEqual(first["observation"]["summary"], "All deployments are ready.")
        self.assertEqual(first["ai_diagnosis"], "The service failed under the fault.")
        self.assertEqual(first["recommendations"][0], {"title": "Add a timeout", "detail": "Bound the wait.",
                                                       "source": "llm"})
        self.assertIn("score", first)          # the score still comes from the fixed formula
        self.assertEqual(res["summary"], "Overall findings.")

    def test_planner_ranks_candidates_and_skips_tested_ones(self):
        same = [("productcatalogservice", "network-delay"), ("adservice", "cpu-stress")]
        res = self.run_loop(self.scripted([same, same]))
        ran = [(e["service"], e["action"]) for e in res["experiments"]]
        self.assertEqual(ran, same)             # round 2 moves to the second-ranked candidate
        ranked = res["experiments"][1]["ranked_candidates"]
        self.assertEqual([r["rank"] for r in ranked], [1, 2])
        self.assertTrue(ranked[0]["already_tested"])
        self.assertTrue(ranked[1]["chosen"])

    def test_reporter_ranking_only_contains_real_experiments(self):
        res = self.run_loop(self.scripted([[("productcatalogservice", "pod-failure")]]), rounds=1)
        ranked = res["ai_report"]["ranked_weaknesses"]
        self.assertEqual([(w["service"], w["action"]) for w in ranked], [("productcatalogservice", "pod-failure")])

    def test_injector_duration_is_clamped_to_the_limits(self):
        res = self.run_loop(self.scripted([[("shippingservice", "cpu-stress")]], duration=99999), rounds=1)
        self.assertEqual(res["experiments"][0]["duration_s"], 60)
        res = self.run_loop(self.scripted([[("shippingservice", "cpu-stress")]], duration=1), rounds=1)
        self.assertEqual(res["experiments"][0]["duration_s"], 15)

    def test_injector_can_decline_and_nothing_is_injected(self):
        res = self.run_loop(self.scripted([[("shippingservice", "cpu-stress")],
                                           [("currencyservice", "cpu-stress")]], inject=False))
        self.assertEqual(res["experiments"], [])
        self.assertEqual([r["outcome"] for r in res["rounds"]], ["declined", "declined"])

    def test_injector_can_roll_back_early(self):
        res = self.run_loop(self.scripted([[("shippingservice", "cpu-stress")]], duration=60, rollback=True),
                            rounds=1)
        exp = res["experiments"][0]
        self.assertEqual(exp["agent_rollback"], "impact is already clear")
        self.assertFalse(exp["aborted"])        # an agent rollback is not a safety abort
        self.assertLess(len(exp["phase_samples"]["during"]), 60)
        self.assertTrue(exp["cleanup_confirmed"])

    def test_safety_guard_still_aborts_when_the_agent_says_continue(self):
        res = self.run_loop(self.scripted([[("redis-cart", "pod-failure")]], rollback=False), rounds=1)
        self.assertTrue(res["experiments"][0]["aborted"])

    def test_llm_cannot_target_a_protected_service(self):
        with self.assertRaises(RuntimeError):
            self.run_loop(self.scripted([[("frontend", "pod-failure")]]), rounds=1)

    def test_bad_answers_fall_back_to_rules(self):
        bad = {"observer agent": {"x": 1}, "analyst agent": {"nonsense": True}, "reporting agent": {"y": 2}}
        res = self.run_loop(self.scripted([[("productcatalogservice", "pod-failure")]], overrides=bad), rounds=1)
        self.assertEqual(res["agents"]["observer"], "rule-based")
        self.assertEqual(res["agents"]["analyst"], "rule-based")
        self.assertEqual(res["agents"]["reporter"], "rule-based")
        self.assertTrue(res["experiments"][0]["recommendations"])
        self.assertTrue(res["ai_report"]["ranked_weaknesses"])

    def test_planner_failure_after_the_first_round_keeps_the_session(self):
        res = self.run_loop(self.scripted([[("shippingservice", "cpu-stress")], []]), rounds=2)
        self.assertEqual(len(res["experiments"]), 2)
        self.assertEqual(res["experiments"][1]["planner"], "rule-based")


class ObserverTests(unittest.TestCase):
    def test_simulated_diagnostics_show_the_failed_pod(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = cfg_in(tmp)
            env = SimEnv(cfg, mapper.build_graph(MANIFEST))
            self.assertEqual(env.cluster_diagnostics()["unhealthy_pods"], [])
            env.apply({"service": "redis-cart", "action": "pod-failure"}, None)
            diag = env.cluster_diagnostics()
            self.assertEqual(diag["deployments"]["redis-cart"]["ready"], 0)
            self.assertEqual(diag["unhealthy_pods"][0]["app"], "redis-cart")

    def test_rule_based_observer_flags_an_unready_deployment(self):
        from chaosai import agents
        with tempfile.TemporaryDirectory() as tmp:
            cfg = cfg_in(tmp)
            g = mapper.build_graph(MANIFEST)
            env = SimEnv(cfg, g)
            env.apply({"service": "adservice", "action": "pod-failure"}, None)
            obs = agents.ObserverAgent(cfg, env, g).observe()
            self.assertFalse(obs["healthy"])
            self.assertEqual(obs["concerns"], ["adservice"])


if __name__ == "__main__":
    unittest.main()