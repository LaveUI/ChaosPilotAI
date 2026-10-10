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

    def cluster_diagnostics(self):
        deployments_result = _kubectl("get", "deployments", "-n", self.ns, "-o", "json")
        pods_result = _kubectl("get", "pods", "-n", self.ns, "-o", "json")
        events_result = _kubectl(
            "get", "events", "-n", self.ns, "--field-selector", "type=Warning", "-o", "json"
        )
        deployments = json.loads(deployments_result.stdout).get("items", [])
        pod_items = json.loads(pods_result.stdout).get("items", [])
        event_items = json.loads(events_result.stdout).get("items", [])

        deployment_data = {}
        for deployment in deployments:
            name = deployment["metadata"]["name"]
            status = deployment.get("status", {})
            spec = deployment.get("spec", {})
            deployment_data[name] = {
                "desired": spec.get("replicas", 1),
                "ready": status.get("readyReplicas", 0),
                "available": status.get("availableReplicas", 0),
            }

        pod_data = []
        unhealthy_pods = []
        for pod in pod_items:
            metadata = pod.get("metadata", {})
            status = pod.get("status", {})
            container_statuses = status.get("containerStatuses") or []
            ready = (
                status.get("phase") == "Running"
                and bool(container_statuses)
                and all(container.get("ready") for container in container_statuses)
            )
            item = {
                "name": metadata.get("name", ""),
                "app": (metadata.get("labels") or {}).get("app", ""),
                "phase": status.get("phase", "Unknown"),
                "ready": ready,
                "restarts": sum(container.get("restartCount", 0) for container in container_statuses),
                "container_states": [],
            }
            for container in container_statuses:
                state = container.get("state") or {}
                last_state = container.get("lastState") or {}
                waiting = state.get("waiting") or {}
                terminated = last_state.get("terminated") or {}
                if waiting.get("reason") or terminated.get("reason"):
                    item["container_states"].append({
                        "name": container.get("name", ""),
                        "waiting_reason": waiting.get("reason"),
                        "waiting_message": waiting.get("message"),
                        "last_termination_reason": terminated.get("reason"),
                        "last_termination_message": terminated.get("message"),
                        "exit_code": terminated.get("exitCode"),
                    })
            pod_data.append(item)
            if not ready:
                unhealthy_pods.append(item)

        warning_events = []
        for event in event_items:
            involved = event.get("involvedObject") or {}
            warning_events.append({
                "time": event.get("lastTimestamp") or event.get("eventTime") or event.get("metadata", {}).get("creationTimestamp"),
                "reason": event.get("reason", ""),
                "message": event.get("message", "")[:500],
                "object_kind": involved.get("kind", ""),
                "object_name": involved.get("name", ""),
                "count": event.get("count", 1),
            })
        warning_events.sort(key=lambda item: item["time"] or "", reverse=True)

        for pod in unhealthy_pods[:3]:
            log_result = _kubectl(
                "logs", pod["name"], "-n", self.ns, "--all-containers=true", "--tail=30", "--since=10m",
                check=False,
            )
            if log_result.returncode == 0 and log_result.stdout.strip():
                pod["recent_logs"] = log_result.stdout[-3000:]
            elif log_result.returncode != 0:
                pod["log_error"] = log_result.stderr.strip()[:500]

        return {
            "deployments": deployment_data,
            "pods": pod_data,
            "unhealthy_pods": unhealthy_pods,
            "warning_events": warning_events[:20],
        }

    def scale(self, service, replicas):
        _kubectl("scale", f"deployment/{service}", f"--replicas={replicas}", "-n", self.ns)
        result = _kubectl(
            "rollout", "status", f"deployment/{service}", "-n", self.ns, "--timeout=180s", check=False
        )
        if result.returncode != 0:
            raise RuntimeError(f"Rollout for {service} did not complete: {result.stderr.strip()}")


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
