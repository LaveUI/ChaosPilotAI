"""Local-first web control panel for ChaosPilot AI."""

import json
import os
import threading
import time
from collections import deque
from contextlib import redirect_stdout
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import TextIOBase
from urllib.parse import urlsplit

from . import agents, analyzer, chaos, config as config_module, mapper, report, runner
from .env import make_env
from .guard import Guard


AGENT_NAMES = ("observer", "planner", "injector", "analyst", "reporter")
MAX_EVENTS = 100
STATEFUL_HINTS = ("redis", "postgres", "mysql", "mongo", "kafka")


class OperationStopped(Exception):
    """A dashboard operation was cancelled through its explicit stop control."""


def validate_experiment(payload, graph, cfg):
    """Validate a dashboard-requested experiment against the same configured boundaries."""
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    service = payload.get("service")
    action = payload.get("action")
    duration = payload.get("duration_s")
    if not isinstance(service, str) or not isinstance(action, str):
        raise ValueError("Choose a service and fault type.")
    nodes = {node["name"]: node for node in graph["nodes"]}
    if service not in nodes:
        raise ValueError("Select a service in the dependency map.")
    if service in cfg["exclude_services"]:
        raise ValueError(f"{service} is protected by exclude_services.")
    if action not in cfg["allowlist"] or action not in chaos.ACTION_LABELS:
        raise ValueError("Select a fault type from the configured allowlist.")
    maximum = int(cfg["experiment_duration_s"])
    if isinstance(duration, bool) or not isinstance(duration, int) or not 15 <= duration <= maximum:
        raise ValueError(f"Duration must be an integer between 15 and {maximum} seconds.")
    return {
        "id": "exp1",
        "service": service,
        "app_label": nodes[service]["app_label"],
        "action": action,
        "duration_s": duration,
        "rationale": "Manually selected from the ChaosPilot dashboard.",
    }


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as source:
            return json.load(source)
    except FileNotFoundError:
        return None


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as output:
        json.dump(data, output, indent=2)
    os.replace(temporary, path)


class _DashboardLog(TextIOBase):
    def __init__(self, runtime):
        self.runtime = runtime
        self.buffer = ""

    def write(self, text):
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
                self.runtime.add_log(line.strip())
        return len(text)

    def flush(self):
        if self.buffer.strip():
            self.runtime.add_log(self.buffer.strip())
        self.buffer = ""


class DashboardRuntime:
    def __init__(self, cfg, sim=False):
        self.cfg = cfg
        self.sim = sim
        self.graph = _read_json(cfg["graph_file"])
        if self.graph is None:
            manifest = cfg["manifest_path"]
            if not os.path.exists(manifest):
                manifest = "sample/kubernetes-manifests.yaml"
            self.graph = mapper.build_graph(manifest, cfg["graph_overrides"])
        self.env = make_env(cfg, self.graph, sim=sim)
        self.lock = threading.RLock()
        self.job_thread = None
        self.job = {
            "state": "idle", "operation": None, "agent": None, "phase": "Ready",
            "run_id": None, "started_at": None, "finished_at": None, "error": None,
        }
        self.events = deque(maxlen=MAX_EVENTS)
        self.metrics_samples = deque(maxlen=60)
        self.last_diagnostics = None
        self.last_diagnostics_at = 0.0
        self.diagnostics_error = None

    def add_log(self, line):
        with self.lock:
            self.events.append({"time": datetime.now().astimezone().isoformat(timespec="seconds"), "message": line})
            lower = line.lower()
            if "observer agent" in lower:
                self.job["agent"] = "observer"
            elif "planner agent" in lower:
                self.job["agent"] = "planner"
            elif "injector agent" in lower or "injecting" in lower or "fault" in lower:
                self.job["agent"] = "injector"
            elif "analyst agent" in lower:
                self.job["agent"] = "analyst"
            elif "reporter agent" in lower or "reporter" in lower:
                self.job["agent"] = "reporter"
            if "before:" in lower:
                self.job["phase"] = "Measuring baseline"
            elif "during:" in lower or "injecting controlled failure" in lower:
                self.job["phase"] = "Fault injection"
            elif "recovery:" in lower:
                self.job["phase"] = "Recovery"
            elif "analysis" in lower or "analyst agent" in lower:
                self.job["phase"] = "Analysis"
            elif "report" in lower:
                self.job["phase"] = "Wrapping up"
            elif "safety abort" in lower or "manual stop" in lower:
                self.job["phase"] = "Stopping safely"

    def _start(self, operation, run_id, function):
        with self.lock:
            if self.job["state"] in {"running", "stopping"}:
                raise RuntimeError("An operation is already running.")
            self.events.clear()
            self.job = {
                "state": "running", "operation": operation, "agent": None,
                "phase": "Starting", "run_id": run_id,
                "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "finished_at": None, "error": None,
            }
            stop_file = os.path.join(self.cfg["runs_dir"], "STOP")
            if os.path.exists(stop_file):
                os.remove(stop_file)

        def execute():
            log = _DashboardLog(self)
            try:
                with redirect_stdout(log):
                    result = function(log)
                    log.flush()
                with self.lock:
                    self.job["state"] = "completed"
                    self.job["phase"] = "Complete"
                    self.job["agent"] = None
                self.add_log("Operation completed.")
            except OperationStopped as exc:
                log.flush()
                with self.lock:
                    self.job["state"] = "stopped"
                    self.job["phase"] = "Stopped safely"
                    self.job["error"] = None
                    self.job["agent"] = None
                self.add_log(str(exc))
            except Exception as exc:
                log.flush()
                with self.lock:
                    self.job["state"] = "failed"
                    self.job["phase"] = "Needs attention"
                    self.job["error"] = f"{exc.__class__.__name__}: {exc}"
                    self.job["agent"] = None
                self.add_log(f"Operation failed: {exc.__class__.__name__}: {exc}")
            finally:
                with self.lock:
                    self.job["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")

        self.job_thread = threading.Thread(target=execute, name="chaospilot-dashboard-job", daemon=True)
        self.job_thread.start()

    def start_baseline(self, seconds):
        if isinstance(seconds, bool) or not isinstance(seconds, int) or not 5 <= seconds <= 300:
            raise ValueError("Baseline duration must be between 5 and 300 seconds.")

        def measure(_log):
            stop_file = os.path.join(self.cfg["runs_dir"], "STOP")
            try:
                base = runner.measure_baseline(self.cfg, self.env, seconds, stop_file)
            except RuntimeError as exc:
                if os.path.exists(stop_file):
                    raise OperationStopped("Baseline measurement stopped safely; no new baseline was saved.") from exc
                raise
            _save_json(self.cfg["baseline_file"], base)
            self.add_log(
                f"Baseline saved: {base['error_rate']:.1%} errors, "
                f"p95 {base['p95_ms']:.0f} ms over {base['samples']} probes."
            )
            return base

        self._start("baseline", f"baseline-{int(time.time())}", measure)

    def start_experiment(self, payload):
        exp = validate_experiment(payload, self.graph, self.cfg)
        baseline = _read_json(self.cfg["baseline_file"])
        if baseline is None:
            raise RuntimeError("Measure a baseline before running a fault experiment.")
        if baseline.get("p95_ms") is None:
            raise RuntimeError("Saved baseline has no successful latency samples; measure it again.")
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        run_dir = os.path.join(self.cfg["runs_dir"], run_id)

        def run_manual(_log):
            guard = Guard(self.cfg, baseline, os.path.join(self.cfg["runs_dir"], "STOP"))
            self.add_log(f"Manual experiment: {exp['action']} on {exp['service']}.")
            result = runner.run_experiment(exp, self.cfg, self.env, baseline, guard, run_dir)
            results = {
                "run_id": run_id, "env": self.env.name, "planner": "dashboard manual selection",
                "baseline": baseline, "limits": guard.limits(), "plan": {"experiments": [exp]},
                "experiments": [result], "compare_to": None,
            }
            analyzer.analyze(results, self.graph, baseline, self.cfg)
            self._save_run(results, run_dir)
            return results

        self._start("manual experiment", run_id, run_manual)

    def start_agents(self, rounds, planner_mode):
        if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= 10:
            raise ValueError("Agent rounds must be between 1 and 10.")
        if not isinstance(planner_mode, str) or planner_mode not in {"auto", "llm", "local", "rule-based"}:
            raise ValueError("Choose auto, Gemini, local Ollama, or rule-based agent mode.")
        baseline = _read_json(self.cfg["baseline_file"])
        if baseline is None:
            raise RuntimeError("Measure a baseline before starting the agents.")
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        run_dir = os.path.join(self.cfg["runs_dir"], run_id)

        def run_agent(_log):
            results = agents.run_agents(
                self.cfg, self.env, self.graph, baseline, rounds, run_id, run_dir,
                os.path.join(self.cfg["runs_dir"], "STOP"), planner_mode=planner_mode,
                clear_stop=False,
            )
            self._save_run(results, run_dir)
            return results

        self._start("agent run", run_id, run_agent)

    def start_fix(self):
        fixes = self._collect_safe_fixes(self._latest_result())
        if not fixes:
            raise RuntimeError("The latest run has no safe automatic fixes to apply.")
        run_id = f"fix-{int(time.time())}"

        def apply(_log):
            for title, fix in fixes:
                self.add_log(f"Applying: {title} (scale {fix['service']} to {fix['replicas']})")
                self.env.scale(fix["service"], fix["replicas"])
            self.add_log("Safe fixes applied. Start another agent run to verify the changes.")

        self._start("apply safe fixes", run_id, apply)

    def _save_run(self, results, run_dir):
        os.makedirs(run_dir, exist_ok=True)
        _save_json(os.path.join(run_dir, "results.json"), results)
        with open(os.path.join(run_dir, "report.html"), "w", encoding="utf-8") as output:
            output.write(report.render(results, self.graph))
        with open(os.path.join(self.cfg["runs_dir"], "latest.txt"), "w", encoding="utf-8") as output:
            output.write(results["run_id"])
        self.add_log(f"Run saved: {results['run_id']}; resilience score {results.get('resilience_score', 'N/A')}.")

    def stop(self):
        stop_file = os.path.join(self.cfg["runs_dir"], "STOP")
        os.makedirs(self.cfg["runs_dir"], exist_ok=True)
        with open(stop_file, "w", encoding="utf-8"):
            pass
        with self.lock:
            if self.job["state"] == "running":
                self.job["state"] = "stopping"
                self.job["phase"] = "Stopping safely"
                self.job["agent"] = "injector"
        self.add_log("Stop requested. Safety guard will remove the active fault.")

    def panic(self):
        self.stop()
        output = self.env.delete_all_chaos()
        self.add_log("Emergency cleanup requested; ChaosPilot-managed faults were deleted.")
        return output.strip()

    def state(self):
        now = time.monotonic()
        with self.lock:
            if self.last_diagnostics_at == 0 or now - self.last_diagnostics_at >= 10:
                try:
                    self.last_diagnostics = self.env.cluster_diagnostics()
                    self.last_diagnostics_at = now
                    self.diagnostics_error = None
                except Exception as exc:
                    self.last_diagnostics = None
                    self.last_diagnostics_at = now
                    self.diagnostics_error = f"{exc.__class__.__name__}: {exc}"
            diagnostics = self.last_diagnostics
            diagnostics_error = self.diagnostics_error

        ok, latency = self.env.probe()
        sample = {"at": time.time(), "ok": bool(ok), "latency_ms": round(latency, 2)}
        with self.lock:
            self.metrics_samples.append(sample)
            recent = list(self.metrics_samples)
            events = list(self.events)
            job = dict(self.job)
        successful = sorted(row["latency_ms"] for row in recent if row["ok"])
        p95_value = successful[min(len(successful) - 1, int(0.95 * (len(successful) - 1)))] if successful else None
        baseline = _read_json(self.cfg["baseline_file"])
        deployments = (diagnostics or {}).get("deployments", {})
        pods = (diagnostics or {}).get("pods", [])
        unhealthy = (diagnostics or {}).get("unhealthy_pods", [])
        warnings = (diagnostics or {}).get("warning_events", [])
        service_data = []
        for node in self.graph["nodes"]:
            dep = deployments.get(node["name"])
            svc_pods = [pod for pod in pods if pod.get("app") == node["name"]]
            service_data.append({
                **node,
                "desired": dep.get("desired") if dep else node.get("replicas"),
                "ready": dep.get("ready") if dep else None,
                "pod_count": len(svc_pods),
                "unhealthy": sum(not pod.get("ready", False) for pod in svc_pods),
                "status": (
                    "unknown" if diagnostics is None else
                    "degraded" if not dep or dep.get("ready", 0) < dep.get("desired", 0) else "healthy"
                ),
            })
        limits = Guard(self.cfg, baseline or {"p95_ms": 0}, os.path.join(self.cfg["runs_dir"], "STOP")).limits()
        return {
            "environment": self.env.name,
            "mode": "simulated" if self.sim else "live Kubernetes",
            "actions": [
                {"id": action, "label": chaos.ACTION_LABELS[action]}
                for action in self.cfg["allowlist"] if action in chaos.ACTION_LABELS
            ],
            "protected_services": list(self.cfg["exclude_services"]),
            "max_duration_s": int(self.cfg["experiment_duration_s"]),
            "baseline_seconds": int(self.cfg["baseline_seconds"]),
            "connected": diagnostics is not None and bool(ok),
            "diagnostics_error": diagnostics_error,
            "probe": sample,
            "metrics": {
                "error_rate": round(sum(not row["ok"] for row in recent) / len(recent), 4) if recent else None,
                "p95_ms": p95_value,
                "samples": len(recent),
                "baseline": baseline,
                "deployments_ready": sum(
                    dep.get("ready", 0) >= dep.get("desired", 0) for dep in deployments.values()
                ) if diagnostics else None,
                "deployments_total": len(deployments) if diagnostics else None,
                "unhealthy_pods": len(unhealthy) if diagnostics else None,
                "warning_events": len(warnings) if diagnostics else None,
            },
            "limits": limits,
            "services": service_data,
            "events": events[-MAX_EVENTS:],
            "job": job,
            "agents": [{"name": name, "state": "active" if job["agent"] == name else "waiting"} for name in AGENT_NAMES],
            "recent_runs": self._recent_runs(),
            "latest_findings": self._latest_findings(),
            "safe_fixes_available": self._safe_fixes_available(),
        }

    def _latest_result(self):
        latest_path = os.path.join(self.cfg["runs_dir"], "latest.txt")
        try:
            with open(latest_path, encoding="utf-8") as source:
                run_id = source.read().strip()
            return _read_json(os.path.join(self.cfg["runs_dir"], run_id, "results.json"))
        except OSError:
            return None

    def _safe_fixes_available(self):
        results = self._latest_result()
        return bool(self._collect_safe_fixes(results)) if isinstance(results, dict) else False

    def _collect_safe_fixes(self, results):
        if not isinstance(results, dict):
            return []
        nodes = {node["name"]: node for node in self.graph["nodes"]}
        max_replicas = self.cfg["local_agent"]["max_replicas"]
        fixes, seen = [], set()
        for experiment in results.get("experiments", []):
            for recommendation in experiment.get("recommendations", []):
                fix = recommendation.get("auto_fix") if isinstance(recommendation, dict) else None
                if not isinstance(fix, dict) or fix.get("type") != "scale":
                    continue
                service, replicas = fix.get("service"), fix.get("replicas")
                node = nodes.get(service) if isinstance(service, str) else None
                if (not node or service in self.cfg["exclude_services"]
                        or any(hint in service.lower() for hint in STATEFUL_HINTS)
                        or isinstance(replicas, bool) or not isinstance(replicas, int)
                        or not node["replicas"] < replicas <= max_replicas
                        or (service, replicas) in seen):
                    continue
                seen.add((service, replicas))
                fixes.append((recommendation.get("title", f"Scale {service}"), {
                    "service": service, "replicas": replicas,
                }))
        return fixes

    def _latest_findings(self):
        results = self._latest_result()
        if not isinstance(results, dict):
            return None
        run_id = results.get("run_id", "unknown")
        findings = []
        for experiment in results.get("experiments", []):
            recommendations = experiment.get("recommendations") or []
            findings.append({
                "service": experiment.get("service"),
                "action": chaos.ACTION_LABELS.get(experiment.get("action"), experiment.get("action")),
                "score": experiment.get("score"),
                "severity": experiment.get("severity") or ("weakness" if (experiment.get("score") or 0) < 90 else "resilient"),
                "error_rate": experiment.get("error_rate"),
                "p95_ms": experiment.get("p95_ms"),
                "recovered": experiment.get("recovered"),
                "diagnosis": experiment.get("ai_diagnosis") or (
                    recommendations[0].get("detail") if recommendations else None
                ),
            })
        return {
            "run_id": run_id,
            "summary": results.get("summary") or (results.get("ai_report") or {}).get("overall"),
            "resilience_score": results.get("resilience_score"),
            "experiments": findings,
        }

    def _recent_runs(self):
        runs = []
        root = self.cfg["runs_dir"]
        try:
            entries = sorted(os.listdir(root), reverse=True)
        except FileNotFoundError:
            return runs
        for run_id in entries:
            path = os.path.join(root, run_id, "results.json")
            if not os.path.isfile(path):
                continue
            try:
                result = _read_json(path)
                runs.append({
                    "run_id": run_id, "environment": result.get("env"),
                    "score": result.get("resilience_score"),
                    "experiments": len(result.get("experiments", [])),
                    "planner": result.get("planner"),
                })
                if len(runs) == 8:
                    break
            except (OSError, ValueError, TypeError):
                continue
        return runs


def _loopback_host(host):
    try:
        return host in {"localhost", "127.0.0.1", "::1"}
    except TypeError:
        return False


def _same_origin(origin, host_header):
    try:
        parsed = urlsplit(origin)
        request_host = urlsplit("//" + host_header).hostname
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname is not None
            and request_host is not None
            and parsed.hostname.casefold() == request_host.casefold()
        )
    except ValueError:
        return False


class DashboardHandler(BaseHTTPRequestHandler):
    runtime = None
    page = ""
    public_sim = False
    public_action_lock = threading.Lock()
    public_last_action = {}

    def log_message(self, fmt, *args):
        return

    def _host_is_local(self):
        try:
            parsed = urlsplit("//" + self.headers.get("Host", ""))
            return _loopback_host(parsed.hostname) and parsed.port in (None, self.server.server_port)
        except ValueError:
            return False

    def _host_is_allowed(self):
        if not self.public_sim:
            return self._host_is_local()
        try:
            return bool(urlsplit("//" + self.headers.get("Host", "")).hostname)
        except ValueError:
            return False

    def _origin_is_allowed(self, origin):
        try:
            parsed = urlsplit(origin)
            if self.public_sim:
                return _same_origin(origin, self.headers.get("Host", ""))
            return (
                parsed.scheme == "http"
                and _loopback_host(parsed.hostname)
                and parsed.port in (None, self.server.server_port)
            )
        except ValueError:
            return False

    def _send(self, status, body, content_type="application/json; charset=utf-8", headers=()):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(encoded)

    def _json(self, status, value):
        self._send(status, json.dumps(value, separators=(",", ":")))

    def _read_body(self):
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Content-Type must be application/json.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length header.") from exc
        if length <= 0 or length > 16_384:
            raise ValueError("Request body must be between 1 and 16384 bytes.")
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Request body must be valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def _authorized_request(self):
        if not self._host_is_allowed():
            self._json(403, {"error": "Dashboard request host is not allowed."})
            return False
        origin = self.headers.get("Origin")
        if origin and not self._origin_is_allowed(origin):
            self._json(403, {"error": "Cross-origin requests are not allowed."})
            return False
        return True

    def do_GET(self):
        if not self._authorized_request():
            return
        if self.path == "/healthz":
            self._json(200, {"ok": True})
        elif self.path == "/":
            self._send(200, self.page, "text/html; charset=utf-8")
        elif self.path == "/api/state":
            try:
                self._json(200, self.runtime.state())
            except Exception as exc:
                self._json(503, {"error": f"Unable to collect dashboard state: {exc.__class__.__name__}: {exc}"})
        else:
            self._json(404, {"error": "Not found."})

    def do_POST(self):
        if not self._authorized_request():
            return
        try:
            payload = self._read_body()
            if self.public_sim and self.path == "/api/agents":
                requested_rounds = payload.get("rounds")
                if isinstance(requested_rounds, bool) or not isinstance(requested_rounds, int):
                    raise ValueError("Agent rounds must be an integer between 1 and 3 in public simulator mode.")
                payload["rounds"] = min(requested_rounds, 3)
                payload["planner_mode"] = "rule-based"
            if self.path == "/api/baseline":
                self.runtime.start_baseline(payload.get("seconds"))
            elif self.path == "/api/experiment":
                self.runtime.start_experiment(payload)
            elif self.path == "/api/agents":
                self.runtime.start_agents(payload.get("rounds"), payload.get("planner_mode"))
            elif self.path == "/api/fix":
                self.runtime.start_fix()
            elif self.path == "/api/stop":
                self.runtime.stop()
            elif self.path == "/api/panic":
                cleanup = self.runtime.panic()
                self._json(200, {"ok": True, "cleanup": cleanup})
                return
            else:
                self._json(404, {"error": "Not found."})
                return
            self._json(202, {"ok": True, "job": self.runtime.state()["job"]})
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except RuntimeError as exc:
            self._json(409, {"error": str(exc)})
        except Exception as exc:
            self._json(500, {"error": f"{exc.__class__.__name__}: {exc}"})


def serve(cfg, sim=False, port=8765, public_sim=False):
    if public_sim and not sim:
        raise ValueError("Public dashboard mode is simulation-only. Pass --sim.")
    runtime = DashboardRuntime(cfg, sim=sim)
    page_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(page_path, encoding="utf-8") as source:
        DashboardHandler.page = source.read()
    DashboardHandler.runtime = runtime
    DashboardHandler.public_sim = public_sim
    with DashboardHandler.public_action_lock:
        DashboardHandler.public_last_action.clear()
    host = "0.0.0.0" if public_sim else "127.0.0.1"
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"ChaosPilot dashboard: http://127.0.0.1:{port} ({runtime.env.name})")
    if public_sim:
        print("Public dashboard is simulation-only; no real cluster controls are enabled.")
    else:
        print("Local-only control surface; do not expose this port to the public internet.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Run the local ChaosPilot control dashboard.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--sim", action="store_true", help="use the offline simulator")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--public-sim", action="store_true", help="serve the simulator publicly without login; requires simulation mode")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    serve(config_module.load(args.config), sim=args.sim, port=args.port, public_sim=args.public_sim)


if __name__ == "__main__":
    main()
