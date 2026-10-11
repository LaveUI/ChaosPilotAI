import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chaosai import analyzer, chaos, config, dashboard, mapper, planner, report, runner  # noqa: E402
from chaosai.cli import _make_run_id  # noqa: E402
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


class DashboardTests(unittest.TestCase):
    base = {"error_rate": 0.0, "p95_ms": 100}

    def exp(self, **kw):
        x = {"id": "exp1", "service": "redis-cart", "action": "pod-failure", "score": 95, "error_rate": 0.0,
             "p95_ms": 110, "recovered": True, "recovery_s": 2, "aborted": False, "abort_reason": None,
             "rationale": "test", "breakdown": {"errors": 0, "latency": 0, "recovery": 0, "abort": 0},
             "samples": [], "recommendations": []}
        x.update(kw)
        return x

    def test_severity_levels(self):
        g = mapper.build_graph(MANIFEST)
        sev = lambda **kw: dashboard.severity(self.exp(**kw), g, self.base)[0]
        self.assertEqual(sev(aborted=True, error_rate=1.0, score=20), "critical")
        self.assertEqual(sev(service="adservice", aborted=True, error_rate=1.0, score=20), "high")
        self.assertEqual(sev(p95_ms=600, score=85), "high")
        self.assertEqual(sev(p95_ms=300, score=88), "medium")
        self.assertEqual(sev(impact={"recovered_to_baseline": False}), "medium")
        self.assertEqual(sev(), "none")

    def test_weakness_without_analyzer_fix_gets_one(self):
        g = mapper.build_graph(MANIFEST)
        x = self.exp(service="shippingservice", action="cpu-stress", p95_ms=380, score=90,
                     impact={"recovered_to_baseline": False})
        recs, added = dashboard.effective_recs(x, g, self.base, "medium")
        self.assertTrue(added)
        self.assertTrue(any("autoscaler" in r["title"] for r in recs))
        self.assertTrue(any("lingering" in r["title"] for r in recs))

    def test_all_failed_has_no_latency_ratio(self):
        x = self.exp(error_rate=1.0, p95_ms=0)
        self.assertIsNone(dashboard.latency_ratio(x, self.base))

    def test_render_has_every_section_without_ai(self):
        g = mapper.build_graph(MANIFEST)
        rec = {"title": "Run at least 2 replicas of redis-cart", "detail": "single point of failure",
               "auto_fix": {"type": "scale", "service": "redis-cart", "replicas": 2}}
        run = {"run_id": "r1", "env": "simulated", "planner": "rule-based", "resilience_score": 40.0,
               "baseline": self.base, "limits": {"max_error_rate": 0.5, "p95_limit_ms": 1500,
                                                 "max_extra_unhealthy_pods": 3},
               "experiments": [self.exp(aborted=True, error_rate=1.0, score=20, abort_reason="error rate",
                                        recommendations=[rec])]}
        pages = dashboard.render([run], g, config.load(None))
        self.assertEqual(list(pages), ["dashboard.html"])
        page = pages["dashboard.html"]
        for text in ("Resilience Command Center", "redis-cart", "Run at least 2 replicas of redis-cart",
                     "Generated from measurements", "Experiment Lab", "Fix Recommendations"):
            self.assertIn(text, page)
        self.assertNotIn("Coverage across all runs", page)
        self.assertNotIn("Resilience over time", page)


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
        ids = {_make_run_id() for _ in range(10)}
        self.assertEqual(len(ids), 10)


if __name__ == "__main__":
    unittest.main()
