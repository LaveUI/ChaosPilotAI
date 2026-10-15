"""Local dashboard API for the existing ChaosPilot CLI and saved run data."""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT)
if sys_path not in os.sys.path:
    os.sys.path.insert(0, sys_path)

from chaosai import agents, config, mapper, report, runner
from chaosai.env import KubeEnv, SimEnv
from chaosai.guard import Guard


CFG = config.load(str(ROOT / "config.yaml"))
ACTION_TYPES = Literal["pod-failure", "network-delay", "cpu-stress"]
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,100}$")


class ExperimentPreviewRequest(BaseModel):
    service: str = Field(min_length=1, max_length=100)
    action: ACTION_TYPES
    duration_s: int = Field(ge=15, le=300)
    environment: Literal["simulated", "kubernetes"] = "simulated"


class ExperimentStartRequest(ExperimentPreviewRequest):
    planner_mode: Literal["auto", "llm", "rule-based"] = "auto"
    confirm_real_experiment: bool = False


class ExperimentStartResponse(BaseModel):
    run_id: str
    status: str
    message: str


class ExperimentStopResponse(BaseModel):
    status: str
    message: str
    cleanup_confirmed: bool | None


_run_lock = threading.RLock()
_active_run: dict[str, Any] | None = None

app = FastAPI(title="ChaosPilot AI Dashboard API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def api_root() -> dict[str, str]:
    return {
        "name": "ChaosPilot AI Dashboard API",
        "status": "ok",
        "docs": "/docs",
        "health": "/api/health",
    }


def _configured_path(key: str) -> Path:
    path = Path(CFG[key])
    return path if path.is_absolute() else ROOT / path


def _read_json(path: Path, *, required: bool = False) -> dict[str, Any] | None:
    if not path.is_file():
        if required:
            raise HTTPException(status_code=503, detail=f"Required project data is missing: {path.name}.")
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=500, detail=f"{path.name} must contain a JSON object.")
    return value


def _graph() -> dict[str, Any]:
    saved = _read_json(_configured_path("graph_file"))
    if saved is not None:
        return saved
    manifest = Path(CFG["manifest_path"])
    if not manifest.is_absolute():
        manifest = ROOT / manifest
    if not manifest.is_file():
        manifest = ROOT / "sample" / "kubernetes-manifests.yaml"
    if not manifest.is_file():
        raise HTTPException(status_code=503, detail="No dependency graph or Kubernetes manifest is available.")
    try:
        return mapper.build_graph(str(manifest), CFG["graph_overrides"])
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not build the service dependency map: {exc}") from exc


def _run_files() -> list[Path]:
    runs_dir = _configured_path("runs_dir")
    if not runs_dir.is_dir():
        return []
    return sorted(
        runs_dir.glob("*/results.json"),
        key=lambda path: path.parent.name,
        reverse=True,
    )


def _all_results() -> list[dict[str, Any]]:
    results = []
    for path in _run_files():
        result = _read_json(path)
        if result is not None:
            result.setdefault("run_id", path.parent.name)
            results.append(result)
    return results


def _latest_result(environment: str | None = None) -> dict[str, Any] | None:
    for result in _all_results():
        if environment is None or result.get("env") == environment:
            return result
    return None


def _run_id(value: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(value):
        raise HTTPException(status_code=400, detail="Invalid run identifier.")
    return value


def _run_dir(run_id: str) -> Path:
    return _configured_path("runs_dir") / _run_id(run_id)


def _snapshot(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not result:
        return None
    for round_result in reversed(result.get("rounds") or []):
        observation = round_result.get("observation") or {}
        if observation.get("cluster"):
            return observation["cluster"]
    for experiment in reversed(result.get("experiments") or []):
        observation = experiment.get("observation") or {}
        if observation.get("cluster"):
            return observation["cluster"]
        if experiment.get("fault_observation"):
            return experiment["fault_observation"]
    return None


def _service_status(name: str, snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return "unknown"
    deployment = (snapshot.get("deployments") or {}).get(name)
    if not deployment:
        return "unknown"
    ready = deployment.get("ready")
    desired = deployment.get("desired")
    if not isinstance(ready, int) or not isinstance(desired, int):
        return "unknown"
    if ready == 0:
        return "failed"
    if ready < desired:
        return "degraded"
    return "healthy"


def _live_snapshot() -> dict[str, Any]:
    try:
        return KubeEnv(CFG).cluster_diagnostics()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="kubectl is not installed or is not on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise HTTPException(status_code=503, detail=f"Kubernetes diagnostics failed: {detail}") from exc


def _services(
    snapshot: dict[str, Any] | None,
    result: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    graph = _graph()
    latest = result
    latest_by_service: dict[str, dict[str, Any]] = {}
    for experiment in (latest or {}).get("experiments") or []:
        latest_by_service[experiment["service"]] = experiment
    services = []
    for node in graph["nodes"]:
        experiment = latest_by_service.get(node["name"])
        deployment = (snapshot or {}).get("deployments", {}).get(node["name"], {})
        services.append({
            **node,
            "status": _service_status(node["name"], snapshot),
            "ready_replicas": deployment.get("ready"),
            "desired_replicas": deployment.get("desired", node.get("replicas")),
            "latest_experiment": experiment,
        })
    return services


def _validate_experiment(request: ExperimentPreviewRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    graph = _graph()
    node = next((item for item in graph["nodes"] if item["name"] == request.service), None)
    if node is None:
        raise HTTPException(status_code=422, detail=f"Unknown service: {request.service}.")
    if request.service in CFG["exclude_services"]:
        raise HTTPException(status_code=422, detail=f"{request.service} is protected by the configured policy.")
    if request.action not in CFG["allowlist"]:
        raise HTTPException(status_code=422, detail=f"{request.action} is not on the configured fault allowlist.")
    if request.duration_s > int(CFG["experiment_duration_s"]):
        raise HTTPException(
            status_code=422,
            detail=f"Duration exceeds the configured maximum of {CFG['experiment_duration_s']} seconds.",
        )
    return graph, node


def _context_status() -> dict[str, Any]:
    approved = os.environ.get("CHAOSAI_APPROVED_CONTEXT")
    try:
        result = subprocess.run(
            ["kubectl", "config", "current-context"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except FileNotFoundError:
        return {"available": False, "current": None, "approved": approved, "matches": False}
    except subprocess.CalledProcessError as exc:
        return {"available": False, "current": None, "approved": approved, "matches": False,
                "error": (exc.stderr or exc.stdout or str(exc)).strip()}
    except subprocess.TimeoutExpired:
        return {"available": False, "current": None, "approved": approved, "matches": False,
                "error": "kubectl context lookup timed out."}
    current = result.stdout.strip()
    return {"available": bool(current), "current": current or None, "approved": approved,
            "matches": bool(approved and current == approved)}


def _overview_data(demo: bool) -> dict[str, Any]:
    if demo:
        result = _latest_result("simulated")
        snapshot = _snapshot(result)
        source = "saved simulation" if result else "no saved simulation"
        environment = "simulated"
    else:
        result = _latest_result("kubernetes")
        snapshot = _live_snapshot()
        source = "live Kubernetes diagnostics"
        environment = "kubernetes"
    services = _services(snapshot, result)
    known = [service for service in services if service["status"] != "unknown"]
    experiments = (result or {}).get("experiments") or []
    safety = Guard(CFG, (result or {}).get("baseline") or
                   _read_json(_configured_path("baseline_file")) or {"p95_ms": 0}, "").limits()
    rounds = (result or {}).get("rounds") or []
    last_round = rounds[-1] if rounds else {}
    suggestions = (result or {}).get("plan", {}).get("experiments") or last_round.get("ranked_candidates") or []
    weaknesses = (result or {}).get("weaknesses") or []
    weakness_details = []
    for weakness in weaknesses:
        experiment = next(
            (
                item for item in experiments
                if item.get("service") == weakness.get("service")
                and item.get("action") == weakness.get("action")
            ),
            {},
        )
        weakness_details.append({
            **weakness,
            "severity": experiment.get("severity"),
            "error_rate": experiment.get("error_rate"),
            "p95_ms": experiment.get("p95_ms"),
            "recovered": experiment.get("recovered"),
            "recommendations": experiment.get("recommendations") or [],
        })
    return {
        "data_available": bool(snapshot or result),
        "environment": environment,
        "source": source,
        "run_id": (result or {}).get("run_id"),
        "resilience_score": (result or {}).get("resilience_score"),
        "services_total": len(services),
        "healthy_services": sum(service["status"] == "healthy" for service in known) if known else None,
        "health_known": bool(known),
        "weaknesses": len(weaknesses),
        "weakness_details": weakness_details,
        "experiments_completed": len(experiments),
        "active_experiment": _active_snapshot(),
        "safety": safety,
        "cleanup_confirmed": (
            (experiments[-1].get("cleanup_confirmed") if experiments else None)
        ),
        "services": services,
        "recent_experiments": experiments[-6:][::-1],
        "suggested_experiments": suggestions[:5],
        "snapshot": snapshot,
    }


def _active_snapshot() -> dict[str, Any] | None:
    with _run_lock:
        if not _active_run:
            return None
        return {key: _active_run.get(key) for key in (
            "run_id", "status", "phase", "service", "action", "environment",
            "started_at", "cleanup_confirmed", "error",
        )}


def _update_active(update: dict[str, Any]) -> None:
    with _run_lock:
        if _active_run is None:
            return
        _active_run.update(update)
        _active_run.setdefault("timeline", []).append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **update,
        })


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/overview")
def overview(demo: bool = Query(default=True)) -> dict[str, Any]:
    return _overview_data(demo)


@app.get("/api/services")
def list_services(demo: bool = Query(default=True)) -> dict[str, Any]:
    snapshot = _snapshot(_latest_result("simulated")) if demo else _live_snapshot()
    return {"environment": "simulated" if demo else "kubernetes",
            "services": _services(snapshot, _latest_result("simulated" if demo else "kubernetes")),
            "edges": _graph()["edges"]}


@app.get("/api/services/{service}")
def service_detail(service: str, demo: bool = Query(default=True)) -> dict[str, Any]:
    payload = list_services(demo)
    found = next((item for item in payload["services"] if item["name"] == service), None)
    if found is None:
        raise HTTPException(status_code=404, detail=f"Service not found: {service}.")
    return found


@app.get("/api/experiments")
def list_experiments() -> dict[str, Any]:
    entries = []
    for result in _all_results():
        for experiment in result.get("experiments") or []:
            entries.append({**experiment, "run_id": result["run_id"], "environment": result.get("env"),
                            "planner": result.get("planner"), "llm_execution": result.get("llm_execution")})
    return {"experiments": entries}


@app.get("/api/experiments/status")
def experiment_status() -> dict[str, Any]:
    snapshot = _active_snapshot()
    if not snapshot:
        return {"active": False, "run": None, "timeline": []}
    with _run_lock:
        return {"active": snapshot["status"] in {"queued", "running", "stopping", "cleanup_pending"},
                "run": snapshot, "timeline": list(_active_run.get("timeline") or []),
                "progress": _active_run.get("sample_metrics")}


@app.get("/api/experiments/{experiment_id}")
def experiment_detail(experiment_id: str) -> dict[str, Any]:
    for result in _all_results():
        for experiment in result.get("experiments") or []:
            if experiment.get("id") == experiment_id:
                return {**experiment, "run_id": result["run_id"], "environment": result.get("env")}
    raise HTTPException(status_code=404, detail=f"Experiment not found: {experiment_id}.")


@app.post("/api/experiments/preview")
def preview_experiment(request: ExperimentPreviewRequest) -> dict[str, Any]:
    graph, node = _validate_experiment(request)
    baseline = _read_json(_configured_path("baseline_file"))
    context = _context_status() if request.environment == "kubernetes" else None
    label = {
        "pod-failure": "Chaos Mesh terminates one matching pod; Kubernetes should replace it.",
        "network-delay": "Chaos Mesh adds the configured latency and jitter to matching service traffic.",
        "cpu-stress": "Chaos Mesh applies the configured CPU load to one matching pod.",
    }[request.action]
    return {
        "validated": True,
        "environment": request.environment,
        "simulation_notice": "This uses the local simulator; it does not contact Kubernetes."
        if request.environment == "simulated" else None,
        "service": request.service,
        "action": request.action,
        "duration_s": request.duration_s,
        "fault_explanation": label,
        "direct_dependents": node["depended_by"],
        "transitive_dependents": node["transitive_dependents"],
        "blast_radius": f"{node['transitive_dependents']} service(s) depend on this service directly or indirectly.",
        "safety_thresholds": Guard(CFG, baseline or {"p95_ms": 0}, "").limits(),
        "max_duration_s": int(CFG["experiment_duration_s"]),
        "rollback_plan": "Safety guard/manual stop requests rollback; the runner then verifies fault cleanup.",
        "cleanup_status": "Not started",
        "context": context,
        "real_run_allowed": bool(context and context["matches"]),
        "gemini_key_available": bool(os.environ.get("GEMINI_API_KEY")),
        "planner_note": "The agent planner will be constrained to this exact service and fault. Any model proposal is validated; a mismatch falls back to the validated operator selection.",
        "warning": "A real run injects a fault into the selected Kubernetes service."
        if request.environment == "kubernetes" else None,
    }


def _save_results(run_dir: Path, result: dict[str, Any], graph: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "results.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    (run_dir / "report.html").write_text(report.render(result, graph, None), encoding="utf-8")
    latest_file = _configured_path("runs_dir") / "latest.txt"
    latest_file.parent.mkdir(parents=True, exist_ok=True)
    latest_file.write_text(result["run_id"], encoding="utf-8")


def _run_worker(request: ExperimentStartRequest, run_id: str, run_dir: Path, stop_file: Path) -> None:
    try:
        graph = _graph()
        cfg = copy.deepcopy(CFG)
        cfg["runs_dir"] = str(_configured_path("runs_dir"))
        cfg["experiment_duration_s"] = request.duration_s
        env = SimEnv(cfg, graph) if request.environment == "simulated" else KubeEnv(cfg)
        baseline = _read_json(_configured_path("baseline_file"))
        if request.environment == "simulated":
            baseline = runner.measure_baseline(cfg, env, 5)
        if not baseline:
            raise RuntimeError("No saved baseline is available. Measure a baseline before a real test.")
        _update_active({"status": "running", "phase": "preparing"})
        result = agents.run_agents(
            cfg, env, graph, baseline, 1, run_id, str(run_dir), str(stop_file),
            planner_mode=request.planner_mode,
            requested_experiment={"service": request.service, "action": request.action},
            preserve_stop_file=True,
            progress_callback=lambda event: _update_active({
                **event,
                "phase": event.get("phase", "running"),
                "status": "stopping" if stop_file.exists() else "running",
                "sample_metrics": {
                    key: event.get(key) for key in (
                        "error_rate", "p95_ms", "extra_unhealthy_pods", "sample",
                    ) if event.get(key) is not None
                } if event.get("event") == "sample" else None,
            }),
        )
        if not result.get("experiments"):
            if stop_file.exists():
                _update_active({"status": "stopped", "phase": "stopped", "cleanup_confirmed": True})
                return
            raise RuntimeError("The agent workflow did not complete an experiment; see API logs for details.")
        _save_results(run_dir, result, graph)
        experiment = (result.get("experiments") or [None])[-1]
        terminal_status = (
            "cleanup_pending" if experiment and not experiment.get("cleanup_confirmed")
            else "aborted" if experiment and experiment.get("aborted")
            else "completed"
        )
        _update_active({
            "status": terminal_status,
            "phase": "completed" if terminal_status in {"completed", "aborted"} else "cleanup_pending",
            "cleanup_confirmed": experiment.get("cleanup_confirmed") if experiment else None,
            "result": result,
            "report_url": f"/api/runs/{run_id}/report",
        })
    except Exception as exc:
        _update_active({"status": "failed", "phase": "failed", "error": f"{exc.__class__.__name__}: {exc}"})


@app.post("/api/experiments/start", response_model=ExperimentStartResponse, status_code=202)
def start_experiment(request: ExperimentStartRequest) -> ExperimentStartResponse:
    global _active_run
    _graph, _node = _validate_experiment(request)
    if request.environment == "kubernetes":
        if not request.confirm_real_experiment:
            raise HTTPException(status_code=409, detail="Explicit real-cluster confirmation is required.")
        context = _context_status()
        if not context["matches"]:
            raise HTTPException(
                status_code=403,
                detail="Live experiments are locked: set CHAOSAI_APPROVED_CONTEXT to the current kubectl context and retry.",
            )
        if not _configured_path("baseline_file").is_file():
            raise HTTPException(status_code=503, detail="Measure and save a live baseline before starting an experiment.")
    elif not request.confirm_real_experiment:
        raise HTTPException(status_code=409, detail="Confirm the experiment preview before starting.")

    with _run_lock:
        if _active_run and _active_run.get("status") in {
            "queued", "running", "stopping", "cleanup_pending",
        }:
            raise HTTPException(status_code=409, detail="Another experiment is active or awaiting cleanup.")
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        run_dir = _configured_path("runs_dir") / run_id
        stop_file = run_dir / "STOP"
        _active_run = {
            "run_id": run_id,
            "status": "queued",
            "phase": "queued",
            "service": request.service,
            "action": request.action,
            "environment": request.environment,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "cleanup_confirmed": None,
            "timeline": [],
            "stop_file": str(stop_file),
        }
        thread = threading.Thread(
            target=_run_worker, args=(request, run_id, run_dir, stop_file),
            name=f"chaospilot-{run_id}", daemon=True,
        )
        thread.start()
    return ExperimentStartResponse(run_id=run_id, status="queued", message="Experiment accepted and queued.")


@app.post("/api/experiments/stop", response_model=ExperimentStopResponse)
def stop_experiment() -> ExperimentStopResponse:
    with _run_lock:
        if not _active_run or _active_run.get("status") not in {"queued", "running", "stopping"}:
            raise HTTPException(status_code=409, detail="There is no active experiment to stop.")
        Path(_active_run["stop_file"]).parent.mkdir(parents=True, exist_ok=True)
        Path(_active_run["stop_file"]).touch()
        _active_run["status"] = "stopping"
        _active_run["phase"] = "stopping"
        _active_run.setdefault("timeline", []).append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "stopping",
            "event": "manual_stop_requested",
        })
        cleanup = _active_run.get("cleanup_confirmed")
    return ExperimentStopResponse(
        status="stopping",
        message="Stop requested. The runner will verify cleanup; do not assume the fault is removed until status confirms it.",
        cleanup_confirmed=cleanup,
    )


@app.get("/api/agents/status")
def agent_status() -> dict[str, Any]:
    with _run_lock:
        current = dict(_active_run) if _active_run else None
    result = (current or {}).get("result") or _latest_result()
    calls = (result or {}).get("agent_calls") or []
    agents_by_name = (result or {}).get("agents") or {}
    timeline = (current or {}).get("timeline") or []
    return {
        "run_id": (result or {}).get("run_id") or (current or {}).get("run_id"),
        "status": (current or {}).get("status", "idle"),
        "agents": [
            {"name": name, "status": agents_by_name.get(name, "not recorded"),
             "calls": [call for call in calls if call.get("agent") == name]}
            for name in ("observer", "planner", "injector", "analyst", "reporter")
        ],
        "timeline": timeline or (result or {}).get("rounds") or [],
        "provenance": (result or {}).get("llm_execution"),
        "finding": (result or {}).get("ai_report"),
    }


@app.get("/api/findings")
def findings() -> dict[str, Any]:
    result = _latest_result()
    if not result:
        return {"run_id": None, "findings": [], "data_available": False}
    items = []
    ai_report = result.get("ai_report")
    if ai_report and ai_report.get("overall"):
        items.append({"type": "session_summary", "text": ai_report["overall"],
                      "source": ai_report.get("source", "not recorded")})
    for experiment in result.get("experiments") or []:
        if experiment.get("ai_diagnosis"):
            items.append({
                "type": "diagnosis", "service": experiment["service"], "action": experiment["action"],
                "text": experiment["ai_diagnosis"], "severity": experiment.get("severity"),
                "evidence": experiment.get("evidence") or [],
                "source": (experiment.get("analyst") or experiment.get("agent_provenance") or {}).get("source"),
            })
    return {"run_id": result["run_id"], "findings": items, "data_available": bool(items)}


@app.get("/api/recommendations")
def recommendations() -> dict[str, Any]:
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, None: 4}
    rows = []
    for result in _all_results():
        for experiment in result.get("experiments") or []:
            for item in experiment.get("recommendations") or []:
                rows.append({
                    **item,
                    "service": experiment["service"],
                    "action": experiment["action"],
                    "score": experiment.get("score"),
                    "severity": experiment.get("severity"),
                    "run_id": result["run_id"],
                    "environment": result.get("env"),
                })
    rows.sort(key=lambda row: (
        severity_rank.get(row.get("severity"), 4),
        row["score"] if isinstance(row.get("score"), (int, float)) else 101,
        row["run_id"],
    ))
    return {"recommendations": rows, "data_available": bool(rows)}


@app.get("/api/runs")
def list_runs(query: str | None = None) -> dict[str, Any]:
    needle = (query or "").casefold()
    results = _all_results()
    rows = []
    for result in results:
        row = {key: result.get(key) for key in (
            "run_id", "env", "planner", "llm_model", "resilience_score", "weaknesses", "llm_execution",
        )}
        row["experiment_count"] = len(result.get("experiments") or [])
        row["report_available"] = (_run_dir(result["run_id"]) / "report.html").is_file()
        if not needle or needle in json.dumps(row, ensure_ascii=True).casefold():
            rows.append(row)
    return {"runs": rows, "data_available": bool(rows)}


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    path = _run_dir(run_id) / "results.json"
    result = _read_json(path)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}.")
    return result


@app.get("/api/runs/{run_id}/report", response_class=HTMLResponse)
def run_report(run_id: str, download: bool = False) -> HTMLResponse:
    report_path = _run_dir(run_id) / "report.html"
    if report_path.is_file():
        try:
            body = report_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Could not read report: {exc}") from exc
    else:
        result = _read_json(report_path.parent / "results.json")
        if result is None:
            raise HTTPException(status_code=404, detail=f"HTML report not found for run {run_id}.")
        body = report.render(result, _graph(), None)
    disposition = "attachment" if download else "inline"
    return HTMLResponse(
        body,
        headers={"Content-Disposition": f'{disposition}; filename="{run_id}-report.html"'},
    )
