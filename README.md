# AI-driven chaos engineering for cloud-native resilience

An AI system that **plans** controlled failures for a cloud-native app, **injects** them with safety
limits, **observes** the impact, then **scores** resilience and **recommends fixes**. After a fix is
applied, it re-runs the same experiments to prove the score improved.

Built for the Bosch hackathon problem statement. Sample app: Google's Online Boutique (12 microservices).
Fault injection: Chaos Mesh. Works with or without an LLM key.

```
GitHub repo --1--> Dependency mapper --> Experiment planner (LLM, allowlist-validated)
                                                  | 2
                                                  v
  Safety guard <--metrics-- Telemetry <--4-- Sample app <--3-- Chaos Mesh (kind cluster)
       | abort                                                    ^
       +----------------------------------------------------------+
  Analyzer + scorer --5--> Report --> apply fix --> re-run --> score goes up
```
A full diagram is in `docs/architecture.html`.

## Quick start

**Try it in 30 seconds, no cluster needed** (offline simulator):
```bash
pip install pyyaml
./demo.sh --sim            # map, baseline, plan, run, fix, rerun
python3 -m unittest discover -s tests
```
Open the newest `runs/*/report.html`. A pre-generated example is in `docs/sample-report.html`.

**On a real cluster:**
```bash
./setup.sh                                          # kind + Online Boutique + Chaos Mesh
kubectl port-forward deployment/frontend 8080:8080  # separate terminal, keep running
./demo.sh                                           # full loop against the cluster
```

**Optional LLM planner** (otherwise a rule-based planner runs):
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 -m chaosai plan --n 4
```

## Commands

| Command | What it does | Slide milestone |
|---|---|---|
| `map` | Parses manifests into `graph.json` + `graph.mmd` (paste into mermaid.live) | Application mapping |
| `baseline` | Measures normal error rate and p95 latency | Monitoring baseline |
| `plan --n 3` | Chooses experiments and explains why | Plan experiments |
| `run` | Injects each fault with safety limits, scores, writes HTML report | First failure, safety controls |
| `fix` | Applies safe automatic fixes (scale to 2 replicas) from the last run | Recommend fixes |
| `rerun` | Re-runs the same plan and compares to the previous score | Verify the fix |
| `report` | Regenerates a report | Analyze and report |
| `kill` | Panic button: stops the session and deletes all chaosai experiments | Safety controls |

Add `--sim` before the command to use the simulator, for example `python3 -m chaosai --sim run`.

## Safety design

1. **Allowlist.** Only `pod-failure`, `network-delay` and `cpu-stress` exist in `chaos.py`. Anything else raises an error.
2. **LLM proposes, code disposes.** Every LLM suggestion is validated against the allowlist, the dependency graph and the exclusion list before it can run.
3. **Small blast radius.** One service per experiment, `mode: one` for pod and CPU faults, a fixed duration so Chaos Mesh also expires faults on its own, and `frontend`/`loadgenerator` are never targeted.
4. **Automatic abort** on rolling error rate, p95 latency, or number of newly unhealthy pods (`safety:` in `config.yaml`). The time taken to remove the fault is measured and shown in the report.
5. **Manual kill switch:** Ctrl+C, `python3 -m chaosai kill`, or `touch runs/STOP`. The fault is always deleted in a `finally` block.
6. To rehearse the abort for the demo, run with a low limit, for example set `max_error_rate: 0.05` in `config.yaml`.

## Resilience score

Each experiment scores 100 minus penalties; the overall score is the mean.

| Penalty | Max | Full penalty when |
|---|---|---|
| Errors | 40 | mean error rate during the fault is 50% or more |
| Latency | 25 | p95 is 10x the baseline p95 or more |
| Recovery | 25 | recovery takes 60s or more, or never happens |
| Safety abort | 10 | the guard had to stop the experiment |

Weaknesses are the experiments scoring below 90, ranked lowest first. Edit the constants at the top of
`chaosai/analyzer.py` to tune.

## Project layout

```
chaosai/
  mapper.py    manifests -> dependency graph
  planner.py   LLM + rule-based experiment planning, with validation
  chaos.py     allowlisted Chaos Mesh manifests
  guard.py     abort rules
  runner.py    inject, observe, recover
  analyzer.py  scoring + recommendations (+ optional LLM summary)
  report.py    self-contained HTML report
  env.py       KubeEnv (real) and SimEnv (offline simulator)
  cli.py       commands
tests/         11 unit tests (mapper, rendering, guard, scoring, planner, simulated run)
sample/        Online Boutique manifest used by `map` if the repo is not cloned
```

## Day-by-day

- **Day 1 checkpoint:** `./setup.sh`, then `map`, `baseline`, one `run` with a low `max_error_rate` to show the kill switch firing. Minimum: running app, dependency map, one safe injection with a working kill switch.
- **Day 2:** set `ANTHROPIC_API_KEY`, `plan`, `run`, `fix`, `rerun`, and show the before/after report.

## Troubleshooting

- **Baseline shows errors:** the port-forward is not running, or pods are not ready (`kubectl get pods`).
- **Chaos Mesh pods crash on kind:** check the containerd settings in `setup.sh`.
- **Network delay has no effect:** make sure the `chaos-daemon` pods are running in the `chaos-mesh` namespace.
- **Real-cluster behavior not matching:** the simulator is a toy model. Trust cluster numbers over simulated ones.
- Chaos Mesh manifests were written from its documented schema. If one is rejected, `kubectl apply --dry-run=server -f runs/<id>/<file>.yaml` shows why.

## Ideas to extend

Add more allowlisted actions (HTTP faults, IO delay), run OpenTelemetry/Prometheus queries in the guard instead of HTTP probes, auto-patch resource limits and probes (not just replicas), or schedule nightly runs in CI.
