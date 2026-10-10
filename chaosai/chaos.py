"""Step 3: turn an approved experiment into a Chaos Mesh manifest. Only allowlisted actions exist here."""
import os

import yaml

ACTION_LABELS = {
    "pod-failure": "pod failure",
    "network-delay": "network delay",
    "cpu-stress": "CPU stress",
}


def manifest_name(exp):
    return f"chaosai-{exp['action']}-{exp['service']}"[:60].rstrip("-")


def render(exp, cfg):
    ns = cfg["namespace"]
    meta = {
        "name": manifest_name(exp),
        "namespace": ns,
        "labels": {"app.kubernetes.io/managed-by": "chaosai"},
    }
    selector = {"namespaces": [ns], "labelSelectors": {"app": exp["app_label"]}}
    duration = f"{int(exp['duration_s'])}s"
    c = cfg["chaos"]

    if exp["action"] == "pod-failure":
        return {"apiVersion": "chaos-mesh.org/v1alpha1", "kind": "PodChaos", "metadata": meta,
                "spec": {"action": "pod-failure", "mode": "one", "duration": duration, "selector": selector}}
    if exp["action"] == "network-delay":
        return {"apiVersion": "chaos-mesh.org/v1alpha1", "kind": "NetworkChaos", "metadata": meta,
                "spec": {"action": "delay", "mode": "all", "duration": duration, "selector": selector,
                         "delay": {"latency": c["network_latency"], "jitter": c["network_jitter"],
                                   "correlation": "50"}}}
    if exp["action"] == "cpu-stress":
        return {"apiVersion": "chaos-mesh.org/v1alpha1", "kind": "StressChaos", "metadata": meta,
                "spec": {"mode": "one", "duration": duration, "selector": selector,
                         "stressors": {"cpu": {"workers": c["cpu_workers"], "load": c["cpu_load"]}}}}
    raise ValueError(f"action not allowed: {exp['action']}")


def write_manifest(exp, cfg, run_dir):
    os.makedirs(run_dir, exist_ok=True)
    path = os.path.join(run_dir, f"{manifest_name(exp)}.yaml")
    with open(path, "w") as f:
        yaml.safe_dump(render(exp, cfg), f, sort_keys=False)
    return path
