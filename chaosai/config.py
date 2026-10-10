import copy
import os

import yaml

DEFAULTS = {
    "namespace": "default",
    "manifest_path": "microservices-demo/release/kubernetes-manifests.yaml",
    "target_urls": [
        "http://localhost:8080/",
        "http://localhost:8080/product/OLJCESPC7Z",
        "http://localhost:8080/cart",
    ],
    "probe_interval_s": 1.0,
    "probe_timeout_s": 3.0,
    "baseline_seconds": 60,
    "experiment_duration_s": 60,
    "recovery_timeout_s": 120,
    "cooldown_s": 10,
    "allowlist": ["pod-failure", "network-delay", "cpu-stress"],
    "exclude_services": ["loadgenerator", "frontend"],
    "safety": {
        "max_error_rate": 0.5,
        "p95_factor": 5.0,
        "min_p95_ms": 1500,
        "max_extra_unhealthy_pods": 3,
        "window": 10,
        "min_samples": 5,
    },
    "chaos": {
        "network_latency": "500ms",
        "network_jitter": "50ms",
        "cpu_workers": 2,
        "cpu_load": 90,
    },
    "llm": {"enabled": True, "model": "gemini-3.8-flash"},
    "graph_overrides": {"add_edges": [], "remove_edges": []},
    "runs_dir": "runs",
    "graph_file": "graph.json",
    "baseline_file": "baseline.json",
    "plan_file": "plan.json",
}


def _merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path="config.yaml"):
    user = {}
    if path and os.path.exists(path):
        with open(path) as f:
            user = yaml.safe_load(f) or {}
    return _merge(DEFAULTS, user)
