"""Step 1: understand the app. Parse Kubernetes manifests into a service dependency graph."""
import re
from collections import deque

import yaml

ADDR = re.compile(r"^([a-z0-9][a-z0-9-]*):(\d+)$")


def _containers(deployment):
    spec = deployment.get("spec", {}).get("template", {}).get("spec", {})
    return (spec.get("containers") or []) + (spec.get("initContainers") or [])


def build_graph(manifest_path, overrides=None):
    with open(manifest_path) as f:
        docs = [d for d in yaml.safe_load_all(f) if d]
    deployments = [d for d in docs if d.get("kind") == "Deployment"]
    names = {d["metadata"]["name"] for d in deployments}

    nodes = {}
    for d in deployments:
        name = d["metadata"]["name"]
        labels = d.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {}) or {}
        nodes[name] = {
            "name": name,
            "app_label": labels.get("app", name),
            "replicas": d.get("spec", {}).get("replicas", 1),
            "depends_on": [],
            "depended_by": [],
        }

    edges = set()
    for d in deployments:
        src = d["metadata"]["name"]
        for c in _containers(d):
            for env in c.get("env") or []:
                m = ADDR.match(str(env.get("value", "")))
                if m and m.group(1) in names and m.group(1) != src:
                    edges.add((src, m.group(1), env["name"]))

    overrides = overrides or {}
    for pair in overrides.get("remove_edges", []):
        edges = {e for e in edges if (e[0], e[1]) != tuple(pair)}
    for src, dst in overrides.get("add_edges", []):
        if src in names and dst in names:
            edges.add((src, dst, "manual"))

    for src, dst, _ in edges:
        if dst not in nodes[src]["depends_on"]:
            nodes[src]["depends_on"].append(dst)
        if src not in nodes[dst]["depended_by"]:
            nodes[dst]["depended_by"].append(src)

    for n in nodes.values():
        n["depends_on"].sort()
        n["depended_by"].sort()
        n["transitive_dependents"] = len(_upstream(nodes, n["name"]))

    return {
        "nodes": sorted(nodes.values(), key=lambda n: n["name"]),
        "edges": [{"from": a, "to": b, "via": v} for a, b, v in sorted(edges)],
    }


def _upstream(nodes, start):
    """All services that directly or indirectly depend on `start`."""
    seen, queue = set(), deque([start])
    while queue:
        cur = queue.popleft()
        for parent in nodes[cur]["depended_by"]:
            if parent not in seen:
                seen.add(parent)
                queue.append(parent)
    return seen


def to_mermaid(graph):
    lines = ["graph LR"]
    for e in graph["edges"]:
        lines.append(f"  {e['from']} --> {e['to']}")
    return "\n".join(lines) + "\n"
