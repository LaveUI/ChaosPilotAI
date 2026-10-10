"""Steps 3 and 4: inject controlled failures, observe behavior, recover."""
import os
import time
from collections import deque

from . import chaos
from .guard import Guard


def p95(values):
    if not values:
        return 0.0
    s = sorted(values)
    return s[int(0.95 * (len(s) - 1))]


def window_stats(window):
    errs = sum(1 for ok, _ in window if not ok)
    return errs / len(window), p95([ms for ok, ms in window if ok])


def measure_baseline(cfg, env, seconds):
    samples, end = [], env.now() + seconds
    while env.now() < end:
        samples.append(env.probe())
        env.sleep(cfg["probe_interval_s"])
    err, p = window_stats(samples)
    return {"error_rate": err, "p95_ms": p, "samples": len(samples)}


def run_experiment(exp, cfg, env, baseline, guard, run_dir):
    path = chaos.write_manifest(exp, cfg, run_dir)
    interval, s = cfg["probe_interval_s"], cfg["safety"]
    window, samples = deque(maxlen=s["window"]), []
    peak_err = peak_p95 = 0.0
    base_unhealthy, extra, i = env.unhealthy_count(), 0, 0
    aborted, reason, abort_latency = False, None, None

    print(f"\n[{exp['id']}] {exp['action']} on {exp['service']} for {exp['duration_s']}s")
    print(f"  why: {exp['rationale']}")
    t0 = env.now()
    env.apply(exp, path)
    try:
        while env.now() - t0 < exp["duration_s"]:
            ok, ms = env.probe()
            samples.append([round(env.now() - t0, 1), int(ok), round(ms), "chaos"])
            window.append((ok, ms))
            if i % 3 == 0:
                extra = max(0, env.unhealthy_count() - base_unhealthy)
            i += 1
            if len(window) >= s["min_samples"]:
                err, p = window_stats(window)
                peak_err, peak_p95 = max(peak_err, err), max(peak_p95, p)
                if i % 5 == 0:
                    print(f"  t={env.now() - t0:5.1f}s  error {err:4.0%}  p95 {p:6.0f} ms  extra unhealthy pods {extra}")
                reason = guard.check(err, p, extra)
                if reason:
                    t = time.perf_counter()
                    env.delete(exp, path)
                    abort_latency = time.perf_counter() - t
                    aborted = True
                    print(f"  ABORT: {reason}. Experiment removed in {abort_latency:.2f}s.")
                    break
            env.sleep(interval)
    finally:
        env.delete(exp, path)  # idempotent; also covers Ctrl+C and crashes

    # Recovery: 5 healthy probes in a row
    rec_start, streak, streak_start, recovered = env.now(), 0, None, False
    lat_ok = max(baseline["p95_ms"] * 3, 400)
    while env.now() - rec_start < cfg["recovery_timeout_s"]:
        ok, ms = env.probe()
        samples.append([round(env.now() - t0, 1), int(ok), round(ms), "recovery"])
        if ok and ms <= lat_ok:
            streak += 1
            streak_start = streak_start if streak > 1 else env.now()
            if streak >= 5:
                recovered = True
                break
        else:
            streak, streak_start = 0, None
        env.sleep(interval)
    recovery_s = round(streak_start - rec_start, 1) if recovered else None
    print(f"  recovery: {'%.1fs' % recovery_s if recovered else 'did not recover within timeout'}")

    chaos_s = [x for x in samples if x[3] == "chaos"]
    errs = sum(1 for x in chaos_s if not x[1])
    return {
        **{k: exp[k] for k in ("id", "service", "action", "duration_s", "rationale", "app_label")},
        "aborted": aborted, "abort_reason": reason if aborted else None,
        "abort_latency_s": round(abort_latency, 3) if abort_latency is not None else None,
        "error_rate": round(errs / len(chaos_s), 3) if chaos_s else 0.0,
        "p95_ms": round(p95([x[2] for x in chaos_s if x[1]])),
        "peak_error_rate": round(peak_err, 3), "peak_p95_ms": round(peak_p95),
        "recovered": recovered, "recovery_s": recovery_s,
        "samples": samples,
    }


def run_plan(plan, cfg, env, baseline, run_dir, stop_file):
    guard = Guard(cfg, baseline, stop_file)
    if os.path.exists(stop_file):
        os.remove(stop_file)
    print(f"Safety limits: {guard.limits()}")
    done = []
    try:
        for exp in plan["experiments"]:
            done.append(run_experiment(exp, cfg, env, baseline, guard, run_dir))
            if os.path.exists(stop_file):
                print("Manual stop file found; ending the session.")
                break
            env.sleep(cfg["cooldown_s"])
    except KeyboardInterrupt:
        print("\nInterrupted: experiment removed, session ended early.")
    return done, guard.limits()
