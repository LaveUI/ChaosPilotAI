"""Local, approval-gated diagnosis of application incidents using Ollama."""
import ipaddress
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime, timezone

from . import runner

STATEFUL_HINTS = ("redis", "postgres", "mysql", "mongo", "kafka")
PROTECTED_SERVICES = {"frontend", "loadgenerator"}
SYSTEM_PROMPT = """You are a local SRE assistant diagnosing a Kubernetes application incident.
Use only the supplied dependency map and collected probes, Kubernetes status, events, and logs.
Do not claim certainty beyond the evidence. Do not invent telemetry or suggest destructive actions.
Respond as JSON with this shape:
{"diagnosis":"short explanation","likely_cause":"evidence-based likely cause","confidence":0.0,
 "fix":{"action":"scale","service":"deployment name","replicas":2,"rationale":"why this may help"}}
If scaling is not clearly appropriate, return fix with action "none", service "", replicas 0,
and explain why in rationale. Scaling is the only fix that can be offered for approval."""


def _loopback_ollama_endpoint(base_url):
    parsed = urllib.parse.urlsplit(base_url)
    host = parsed.hostname
    if parsed.scheme != "http" or not host or parsed.username or parsed.password:
        raise ValueError("Ollama URL must be a plain HTTP URL on localhost.")
    try:
        local = host.lower() == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = False
    if not local or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Ollama URL must point to a local loopback address, such as http://127.0.0.1:11434.")
    return base_url.rstrip("/") + "/api/chat"


def ask_ollama(cfg, context):
    settings = cfg["local_agent"]
    endpoint = _loopback_ollama_endpoint(settings["ollama_url"])
    payload = {
        "model": settings["model"],
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context)},
        ],
        "options": {"temperature": 0.1},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings["ollama_timeout_s"]) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Ollama returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not reach local Ollama at {settings['ollama_url']}: {exc.reason}. "
            f"Start Ollama and pull model {settings['model']}."
        ) from exc
    try:
        return json.loads(body["message"]["content"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Ollama returned a response that was not valid diagnosis JSON.") from exc


def incident_metrics(samples, baseline, cfg):
    stats = runner.phase_stats([[0, int(ok), ms, "monitor"] for ok, ms in samples])
    if not stats["samples"]:
        return stats, []

    settings = cfg["local_agent"]
    reasons = []
    enough_samples = stats["samples"] >= settings["min_samples"]
    if enough_samples and stats["error_rate"] >= settings["error_rate_threshold"]:
        reasons.append(
            f"probe error rate is {stats['error_rate']:.0%} "
            f"(threshold {settings['error_rate_threshold']:.0%})"
        )
    latency_limit = max(
        settings["min_p95_ms"],
        baseline["p95_ms"] * settings["p95_factor"],
    )
    if enough_samples and stats["p95_ms"] is not None and stats["p95_ms"] > latency_limit:
        reasons.append(f"probe p95 is {stats['p95_ms']:.0f} ms (limit {latency_limit:.0f} ms)")
    return stats, reasons


def validate_diagnosis(raw, graph, snapshot, cfg, affected_services):
    if not isinstance(raw, dict):
        raise ValueError("Ollama diagnosis must be a JSON object.")
    diagnosis = {
        "diagnosis": str(raw.get("diagnosis", "No diagnosis provided."))[:1000],
        "likely_cause": str(raw.get("likely_cause", "No likely cause provided."))[:1000],
        "confidence": None,
        "fix": None,
    }
    confidence = raw.get("confidence")
    if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and math.isfinite(confidence):
        diagnosis["confidence"] = round(min(1.0, max(0.0, float(confidence))), 2)

    fix = raw.get("fix")
    if not isinstance(fix, dict) or fix.get("action") != "scale":
        diagnosis["fix_rationale"] = (
            str((fix or {}).get("rationale", "No safe scale-up recommendation was made."))[:1000]
            if isinstance(fix, dict) else "No safe scale-up recommendation was made."
        )
        return diagnosis

    service = fix.get("service")
    graph_services = {node["name"] for node in graph["nodes"]}
    deployment = snapshot["deployments"].get(service) if isinstance(service, str) else None
    current_replicas = deployment["desired"] if deployment else 0
    replicas = fix.get("replicas")
    maximum = cfg["local_agent"]["max_replicas"]
    allowed = (
        isinstance(service, str)
        and service in graph_services
        and service in affected_services
        and service not in PROTECTED_SERVICES
        and service not in cfg["exclude_services"]
        and not any(hint in service.lower() for hint in STATEFUL_HINTS)
        and deployment is not None
        and isinstance(replicas, int)
        and not isinstance(replicas, bool)
        and current_replicas < replicas <= maximum
    )
    if not allowed:
        diagnosis["fix_rationale"] = (
            "The proposed scale action was not offered: it must target an affected, known, stateless "
            f"deployment and stay within {maximum} replicas."
        )
        return diagnosis

    diagnosis["fix"] = {
        "action": "scale",
        "service": service,
        "from_replicas": current_replicas,
        "replicas": replicas,
        "rationale": str(fix.get("rationale", ""))[:1000],
    }
    return diagnosis


class LocalMonitorAgent:
    def __init__(self, cfg, graph, env, baseline, input_fn=input, diagnose_fn=ask_ollama):
        self.cfg = cfg
        self.graph = graph
        self.env = env
        self.baseline = baseline
        self.input_fn = input_fn
        self.diagnose_fn = diagnose_fn
        self.samples = deque(maxlen=cfg["local_agent"]["window_samples"])
        self.active_incident = False
        self.healthy_streak = 0
        self.run_dir = os.path.join(cfg["runs_dir"], "monitor")

    def _context(self, stats, reasons, snapshot, affected_services):
        return {
            "incident_reasons": reasons,
            "probe_window": stats,
            "baseline": self.baseline,
            "dependency_map": self.graph,
            "affected_services": sorted(affected_services),
            "cluster": snapshot,
        }

    def _save_incident(self, record):
        os.makedirs(self.run_dir, exist_ok=True)
        path = os.path.join(self.run_dir, "incidents.jsonl")
        with open(path, "a") as output:
            output.write(json.dumps(record, sort_keys=True) + "\n")

    def _incident(self, stats, reasons, snapshot):
        unhealthy_services = {
            pod["app"] for pod in snapshot["unhealthy_pods"] if pod.get("app")
        }
        unhealthy_services.update(
            name for name, state in snapshot["deployments"].items()
            if state["ready"] < state["desired"]
        )
        affected_services = unhealthy_services.intersection(
            node["name"] for node in self.graph["nodes"]
        )
        if reasons:
            affected_services.update(
                event["object_name"]
                for event in snapshot["warning_events"]
                if event["object_kind"] in {"Pod", "Deployment"}
                and event["object_name"] in {node["name"] for node in self.graph["nodes"]}
            )

        context = self._context(stats, reasons, snapshot, affected_services)
        raw = self.diagnose_fn(self.cfg, context)
        diagnosis = validate_diagnosis(raw, self.graph, snapshot, self.cfg, affected_services)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reasons": reasons,
            "metrics": stats,
            "affected_services": sorted(affected_services),
            "diagnosis": diagnosis,
            "approved": False,
            "applied": False,
        }

        print(f"\nIncident detected: {'; '.join(reasons)}")
        print(f"Diagnosis: {diagnosis['diagnosis']}")
        print(f"Likely cause: {diagnosis['likely_cause']}")
        if diagnosis["confidence"] is not None:
            print(f"Local model confidence: {diagnosis['confidence']:.0%} (estimate, not a calibrated probability)")
        if diagnosis["fix"]:
            fix = diagnosis["fix"]
            print(f"Proposed fix: scale {fix['service']} from {fix['from_replicas']} to {fix['replicas']} replicas.")
            print(f"Reason: {fix['rationale']}")
            approval = self.input_fn("Apply this scale-up? Type 'yes' to approve: ").strip().lower()
            if approval == "yes":
                record["approved"] = True
                try:
                    self.env.scale(fix["service"], fix["replicas"])
                    record["applied"] = True
                    print("Scale-up completed; continuing to monitor for recovery.")
                except Exception as exc:
                    record["apply_error"] = f"{exc.__class__.__name__}: {exc}"
                    self._save_incident(record)
                    raise
            else:
                print("No change applied.")
        else:
            print(f"No approved-action candidate. {diagnosis['fix_rationale']}")

        self._save_incident(record)
        return record

    def poll(self):
        ok, latency = self.env.probe()
        self.samples.append((ok, latency))
        snapshot = self.env.cluster_diagnostics()
        stats, reasons = incident_metrics(list(self.samples), self.baseline, self.cfg)
        for name, deployment in snapshot["deployments"].items():
            if deployment["ready"] < deployment["desired"]:
                reasons.append(
                    f"deployment {name} has {deployment['ready']}/{deployment['desired']} ready replicas"
                )
        for pod in snapshot["unhealthy_pods"]:
            if not pod.get("app") and pod["phase"] != "Running":
                reasons.append(f"pod {pod['name']} is {pod['phase']}")

        if reasons:
            self.healthy_streak = 0
            if not self.active_incident:
                self.active_incident = True
                self._incident(stats, reasons, snapshot)
            else:
                print(f"Incident ongoing: {'; '.join(reasons)}")
        elif len(self.samples) == self.samples.maxlen:
            self.healthy_streak += 1
            if self.active_incident and self.healthy_streak >= self.cfg["local_agent"]["recovery_samples"]:
                self.active_incident = False
                self.healthy_streak = 0
                print("Incident resolved: probes and Kubernetes workload health returned to normal.")
            elif not self.active_incident:
                print(
                    f"Healthy: error rate {stats['error_rate']:.0%}, "
                    f"p95 {stats['p95_ms'] if stats['p95_ms'] is not None else 0:.0f} ms; "
                    f"{len(snapshot['deployments'])} deployments checked."
                )

    def run(self):
        settings = self.cfg["local_agent"]
        print(
            f"Local monitor active: Ollama {settings['model']} at {settings['ollama_url']}; "
            f"poll interval {settings['interval_s']}s. No changes are made without your approval. "
            "Press Ctrl+C to stop."
        )
        while True:
            self.poll()
            self.env.sleep(settings["interval_s"])
