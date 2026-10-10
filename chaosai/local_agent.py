"""Local Ollama monitor for manually injected application faults."""
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
SYSTEM_PROMPT = """Diagnose this Kubernetes application incident from supplied evidence only.
Return JSON: {"diagnosis":"...","likely_cause":"...","confidence":0.0,
"fix":{"action":"scale" or "none","service":"deployment name","replicas":2,"rationale":"..."}}
Do not invent evidence or recommend destructive actions. Scaling an affected, stateless app
deployment is the only fix that may be offered for human approval. Prefer action none if unsure."""


def _endpoint(base_url):
    parsed = urllib.parse.urlsplit(base_url)
    try:
        loopback = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname).is_loopback
    except (ValueError, TypeError):
        loopback = False
    if (parsed.scheme != "http" or not loopback or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("Ollama must use a local loopback URL, e.g. http://127.0.0.1:11434.")
    return base_url.rstrip("/") + "/api/chat"


def diagnose(cfg, context):
    settings = cfg["local_agent"]
    payload = {
        "model": settings["model"],
        "stream": False,
        "format": "json",
        "keep_alive": settings["keep_alive"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context)},
        ],
        "options": {
            "temperature": 0.1,
            "num_ctx": settings["num_ctx"],
            "num_predict": settings["num_predict"],
        },
    }
    request = urllib.request.Request(
        _endpoint(settings["ollama_url"]),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings["ollama_timeout_s"]) as response:
            body = json.loads(response.read().decode())
        return json.loads(body["message"]["content"])
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach local Ollama: {exc.reason}. Start Ollama and pull {settings['model']}.") from exc
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Ollama did not return valid JSON diagnosis.") from exc


class LocalMonitorAgent:
    def __init__(self, cfg, graph, env, baseline, input_fn=input, diagnose_fn=diagnose):
        self.cfg, self.graph, self.env, self.baseline = cfg, graph, env, baseline
        self.input_fn, self.diagnose_fn = input_fn, diagnose_fn
        self.samples = deque(maxlen=cfg["local_agent"]["window_samples"])
        self.incident_active = False
        self.healthy_after = 0
        self.incident_services = set()
        self.log_path = os.path.join(cfg["runs_dir"], "monitor", "incidents.jsonl")

    def _check(self):
        settings = self.cfg["local_agent"]
        stats = runner.phase_stats([[0, int(ok), latency, "monitor"] for ok, latency in self.samples])
        reasons = []
        enough = stats["samples"] >= settings["min_samples"]
        if enough and stats["error_rate"] >= settings["error_rate_threshold"]:
            reasons.append(f"HTTP probe error rate {stats['error_rate']:.0%} reached threshold {settings['error_rate_threshold']:.0%}")
        latency_limit = max(settings["min_p95_ms"], self.baseline["p95_ms"] * settings["p95_factor"])
        if enough and stats["p95_ms"] is not None and stats["p95_ms"] > latency_limit:
            reasons.append(f"HTTP probe p95 {stats['p95_ms']:.0f} ms exceeded {latency_limit:.0f} ms")
        snapshot = self.env.cluster_diagnostics()
        names = {node["name"] for node in self.graph["nodes"]}
        self.incident_services = {
            pod.get("app") for pod in snapshot["unhealthy_pods"]
            if pod.get("app") in names
        }
        for name, deployment in snapshot["deployments"].items():
            if deployment["ready"] < deployment["desired"]:
                reasons.append(f"deployment {name} has {deployment['ready']}/{deployment['desired']} ready replicas")
                if name in names:
                    self.incident_services.add(name)
        for pod in snapshot["unhealthy_pods"]:
            if pod.get("app") in names and pod["app"] not in self.incident_services:
                self.incident_services.add(pod["app"])
        return stats, reasons, snapshot

    def _validated_fix(self, raw, snapshot):
        fix = raw.get("fix") if isinstance(raw, dict) else None
        if not isinstance(fix, dict) or fix.get("action") != "scale":
            return None
        service = fix.get("service")
        replicas = fix.get("replicas")
        deployment = snapshot["deployments"].get(service) if isinstance(service, str) else None
        graph_names = {node["name"] for node in self.graph["nodes"]}
        if (not isinstance(service, str) or service not in graph_names or service not in self.incident_services
                or service in self.cfg["exclude_services"]
                or any(hint in service.lower() for hint in STATEFUL_HINTS)
                or not deployment or isinstance(replicas, bool) or not isinstance(replicas, int)
                or not deployment["desired"] < replicas <= self.cfg["local_agent"]["max_replicas"]):
            return None
        return {
            "service": service,
            "from_replicas": deployment["desired"],
            "replicas": replicas,
            "rationale": str(fix.get("rationale", ""))[:1000],
        }

    def _record(self, record):
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "a") as output:
            output.write(json.dumps(record, sort_keys=True) + "\n")

    def poll(self):
        self.samples.append(self.env.probe())
        stats, reasons, snapshot = self._check()
        if reasons:
            self.healthy_after = 0
            if self.incident_active:
                print(f"Incident ongoing: {'; '.join(reasons)}")
                return
            context = {
                "dependency_map": self.graph,
                "baseline": self.baseline,
                "probe_window": stats,
                "incident_reasons": reasons,
                "cluster": snapshot,
            }
            print(f"\nIncident detected. Asking local Ollama model {self.cfg['local_agent']['model']} to diagnose...")
            started = time.monotonic()
            result = self.diagnose_fn(self.cfg, context)
            diagnosis_seconds = round(time.monotonic() - started, 2)
            if not isinstance(result, dict):
                raise RuntimeError("Ollama diagnosis must be a JSON object.")
            confidence = result.get("confidence")
            if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and math.isfinite(confidence):
                confidence = min(1.0, max(0.0, confidence))
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reasons": reasons,
                "metrics": stats,
                "diagnosis": str(result.get("diagnosis", "No diagnosis provided."))[:1000],
                "likely_cause": str(result.get("likely_cause", "No cause provided."))[:1000],
                "confidence": confidence,
                "diagnosis_seconds": diagnosis_seconds,
                "approved": False,
                "applied": False,
            }
            self.incident_active = True
            print(f"Incident: {'; '.join(reasons)}")
            print(f"Diagnosis completed in {diagnosis_seconds:.1f}s.")
            print(f"Diagnosis: {record['diagnosis']}")
            print(f"Likely cause: {record['likely_cause']}")
            if confidence is not None:
                print(f"Local model confidence: {confidence:.0%} (estimate, not calibrated)")
            fix = self._validated_fix(result, snapshot)
            if fix:
                print(f"Proposed fix: scale {fix['service']} from {fix['from_replicas']} to {fix['replicas']} replicas.")
                print(f"Reason: {fix['rationale']}")
                record["proposed_fix"] = fix
                if self.input_fn("Apply this scale-up? Type 'yes' to approve: ").strip().lower() == "yes":
                    record["approved"] = True
                    self.env.scale(fix["service"], fix["replicas"])
                    record["applied"] = True
                    print("Scale-up completed; monitoring continues.")
                else:
                    print("No change applied.")
            else:
                print("No safe scale-up candidate; no changes were made.")
            self._record(record)
        elif self.incident_active:
            self.healthy_after += 1
            if self.healthy_after >= self.cfg["local_agent"]["recovery_samples"]:
                self.incident_active = False
                self.healthy_after = 0
                print("Incident resolved: probes and deployment health are back within normal limits.")
        elif len(self.samples) == self.samples.maxlen:
            print(f"Healthy: probe errors {stats['error_rate']:.0%}; p95 {stats['p95_ms'] or 0:.0f} ms.")

    def run(self):
        settings = self.cfg["local_agent"]
        print(f"Local monitor active: Ollama {settings['model']} at {settings['ollama_url']}; Ctrl+C stops it.")
        while True:
            self.poll()
            self.env.sleep(settings["interval_s"])
