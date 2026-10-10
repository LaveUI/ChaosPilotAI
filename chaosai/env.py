"""Environments: KubeEnv talks to a real cluster; SimEnv is a fast offline simulator
(useful for development, tests, and as a demo fallback if the cluster misbehaves)."""
import json
import os
import random
import subprocess
import time
import urllib.request


def _kubectl(*args, check=True):
    return subprocess.run(["kubectl", *args], capture_output=True, text=True, check=check)


class KubeEnv:
    name = "kubernetes"

    def __init__(self, cfg):
        self.cfg = cfg
        self.ns = cfg["namespace"]
        self._i = 0

    def now(self):
        return time.time()

    def sleep(self, s):
        time.sleep(max(0.0, s))

    def probe(self):
        urls = self.cfg["target_urls"]
        url = urls[self._i % len(urls)]
        self._i += 1
        start = time.time()
        try:
            with urllib.request.urlopen(url, timeout=self.cfg["probe_timeout_s"]) as r:
                r.read(512)
                ok = 200 <= r.status < 400
        except Exception:
            ok = False
        return ok, (time.time() - start) * 1000

    def apply(self, exp, path):
        _kubectl("apply", "-f", path)

    def delete(self, exp, path):
        r = _kubectl("delete", "-f", path, "--ignore-not-found", check=False)
        if r.returncode != 0:
            print(f"  WARNING: kubectl delete failed: {r.stderr.strip()}")
        return r.returncode == 0

    def delete_all_chaos(self):
        r = _kubectl("delete", "podchaos,networkchaos,stresschaos", "-n", self.ns,
                     "-l", "app.kubernetes.io/managed-by=chaosai", "--ignore-not-found", check=False)
        return r.stdout + r.stderr

    def unhealthy_count(self):
        r = _kubectl("get", "pods", "-n", self.ns, "-o", "json", check=False)
        if r.returncode != 0:
            return 0
        bad = 0
        for p in json.loads(r.stdout)["items"]:
            st = p.get("status", {})
            cs = st.get("containerStatuses") or []
            if not (st.get("phase") == "Running" and cs and all(c.get("ready") for c in cs)):
                bad += 1
        return bad

    def scale(self, service, replicas):
        _kubectl("scale", f"deployment/{service}", f"--replicas={replicas}", "-n", self.ns)
        _kubectl("rollout", "status", f"deployment/{service}", "-n", self.ns, "--timeout=180s", check=False)


class SimEnv:
    """Deterministic toy model: single-replica services hurt more; 2+ replicas absorb faults."""
    name = "simulated"

    def __init__(self, cfg, graph, seed=7):
        self.cfg = cfg
        self.rng = random.Random(seed)
        self.t = 0.0
        self.active = None
        self.last = None
        self.recover_until = 0.0
        self.state_file = os.path.join(cfg["runs_dir"], "sim_state.json")
        self.replicas = {n["name"]: n.get("replicas", 1) for n in graph["nodes"]}
        self.dependents = {n["name"]: n.get("transitive_dependents", 0) for n in graph["nodes"]}
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                self.replicas.update(json.load(f))

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s

    def apply(self, exp, path):
        self.active = exp

    def delete(self, exp, path):
        if self.active:
            self.last = self.active
            self.active = None
            spof = self.replicas.get(self.last["service"], 1) < 2
            self.recover_until = self.t + (20 if spof else 3)
        return True

    def delete_all_chaos(self):
        self.active = None
        return "simulated: nothing to delete"

    def unhealthy_count(self):
        return 1 if self.active and self.active["action"] == "pod-failure" else 0

    def scale(self, service, replicas):
        self.replicas[service] = replicas
        os.makedirs(self.cfg["runs_dir"], exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.replicas, f)

    def probe(self):
        err, extra = 0.01, 0.0
        exp, recovering = self.active, False
        if exp is None and self.t < self.recover_until:
            exp, recovering = self.last, True
        if exp:
            svc, act = exp["service"], exp["action"]
            spof = self.replicas.get(svc, 1) < 2
            crit = min(1.0, 0.25 + 0.25 * self.dependents.get(svc, 0))
            if act == "pod-failure":
                err += (0.9 * crit) if spof else 0.04
            elif act == "network-delay":
                extra += (700 if spof else 150) * crit
                err += (0.05 * crit) if spof else 0.0
            elif act == "cpu-stress":
                extra += (400 if spof else 60) * crit
            if recovering:
                err, extra = err * 0.5, extra * 0.5
        ok = self.rng.random() >= min(err, 1.0)
        ms = max(20.0, self.rng.gauss(120, 15)) + extra
        if not ok:
            ms = 50 + extra
        return ok, ms


def make_env(cfg, graph=None, sim=False):
    if sim:
        if graph is None:
            raise SystemExit("Simulation needs graph.json. Run `python -m chaosai map` first.")
        return SimEnv(cfg, graph)
    return KubeEnv(cfg)
