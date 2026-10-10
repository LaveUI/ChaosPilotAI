import os
import sys
import tempfile
import unittest
from datetime import datetime

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


if __name__ == "__main__":
    unittest.main()
