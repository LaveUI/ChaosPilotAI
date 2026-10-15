"""ChaosPilot AI: four-phase chaos experiment runner."""

import os
import time
from collections import deque

from . import chaos
from .guard import Guard


def percentile(values, fraction):
    if not values:
        return None

    values = sorted(values)
    index = int(fraction * (len(values) - 1))
    return round(values[index], 2)


def p95(values):
    return percentile(values, 0.95) or 0.0


def window_stats(window):
    if not window:
        return 0.0, 0.0

    errors = sum(not ok for ok, _ in window)
    successful = [ms for ok, ms in window if ok]

    return errors / len(window), p95(successful)


def phase_stats(samples):
    """Calculate metrics from [time, success, latency, phase]."""

    if not samples:
        return {
            "samples": 0,
            "error_rate": None,
            "p50_ms": None,
            "p95_ms": None,
            "successful_requests": 0,
            "failed_requests": 0,
        }

    successful = [
        float(s[2]) for s in samples if s[1]
    ]

    failed = sum(not bool(s[1]) for s in samples)

    return {
        "samples": len(samples),
        "error_rate": round(failed / len(samples), 4),
        "p50_ms": percentile(successful, 0.50),
        "p95_ms": percentile(successful, 0.95),
        "successful_requests": len(successful),
        "failed_requests": failed,
    }


def collect_phase(env, cfg, seconds, phase, origin, on_progress=None):
    """Collect probe samples for a fixed observation window."""

    samples = []
    end = env.now() + seconds

    while env.now() < end:
        ok, ms = env.probe()

        sample = [
            round(env.now() - origin, 2),
            int(ok),
            round(ms, 2),
            phase,
        ]
        samples.append(sample)
        if on_progress:
            on_progress({"phase": phase, "event": "sample", "sample": sample})

        env.sleep(cfg["probe_interval_s"])

    return samples


def measure_baseline(cfg, env, seconds):
    """Preserve the existing baseline CLI interface."""

    samples = collect_phase(
        env, cfg, seconds, "before", env.now()
    )

    stats = phase_stats(samples)

    return {
        "error_rate": stats["error_rate"] or 0.0,
        "p50_ms": stats["p50_ms"],
        "p95_ms": stats["p95_ms"] or 0.0,
        "samples": stats["samples"],
        "successful_requests": stats["successful_requests"],
        "failed_requests": stats["failed_requests"],
    }


def latency_change_pct(before, other):
    if before is None or other is None or before <= 0:
        return None

    return round((other - before) / before * 100, 2)


def run_experiment(exp, cfg, env, baseline, guard, run_dir, on_sample=None, on_progress=None):
    """Run Before -> During -> Recovery -> After.

    on_sample: optional callback, called about every `agent_review_every_samples` probes while the
    fault is active with the current readings. If it returns a reason string, the fault is rolled
    back early (an agent decision). The safety guard is always checked first and cannot be skipped."""

    path = chaos.write_manifest(exp, cfg, run_dir)

    interval = cfg["probe_interval_s"]
    safety = cfg["safety"]

    before_seconds = cfg.get("phase_before_seconds", 15)
    after_seconds = cfg.get("phase_after_seconds", 15)

    samples = []
    phase_samples = {
        "before": [],
        "during": [],
        "recovery": [],
        "after": [],
    }

    print(
        f"\n[{exp['id']}] {exp['action']} "
        f"on {exp['service']}"
    )

    # ---------------------------------------
    # PHASE 1: BEFORE
    # ---------------------------------------

    origin = env.now()

    print(f"  BEFORE: measuring for {before_seconds}s")
    if on_progress:
        on_progress({"phase": "before", "event": "started"})

    before = collect_phase(
        env, cfg, before_seconds, "before", origin, on_progress
    )

    phase_samples["before"] = before
    samples.extend(before)

    before_metrics = phase_stats(before)

    if not before_metrics["samples"]:
        raise RuntimeError("No baseline samples collected")

    if before_metrics["error_rate"] > 0.05:
        raise RuntimeError(
            "Pre-experiment baseline is unhealthy"
        )

    if before_metrics["p95_ms"] is None:
        raise RuntimeError(
            "No successful baseline requests"
        )

    experiment_baseline = {
        "error_rate": before_metrics["error_rate"],
        "p95_ms": before_metrics["p95_ms"],
    }

    # Use a fresh guard for this experiment.
    # This retains the session's manual stop path.
    local_guard = Guard(
        cfg,
        experiment_baseline,
        guard.stop_file,
    )

    # ---------------------------------------
    # PHASE 2: DURING
    # ---------------------------------------

    print("  DURING: injecting controlled failure")
    if on_progress:
        on_progress({"phase": "injecting", "event": "started"})

    window = deque(maxlen=safety["window"])

    base_unhealthy = env.unhealthy_count()
    extra = 0

    peak_err = 0.0
    peak_p95 = 0.0

    aborted = False
    reason = None
    abort_latency = None
    cleanup_confirmed = False
    agent_rollback = None
    review_every = max(1, int(cfg.get("agent_review_every_samples", 15)))

    injected_at = env.now() - origin
    fault_started = env.now()

    try:
        # Attempt cleanup even if apply partially succeeds.
        env.apply(exp, path)

        i = 0

        while env.now() - fault_started < exp["duration_s"]:

            ok, ms = env.probe()

            sample = [
                round(env.now() - origin, 2),
                int(ok),
                round(ms, 2),
                "chaos",
            ]

            samples.append(sample)
            phase_samples["during"].append(sample)
            window.append((ok, ms))

            if i % 3 == 0:
                extra = max(
                    0,
                    env.unhealthy_count() - base_unhealthy
                )

            i += 1

            if len(window) >= safety["min_samples"]:
                err, latency = window_stats(window)

                peak_err = max(peak_err, err)
                peak_p95 = max(peak_p95, latency)

                reason = local_guard.check(
                    err, latency, extra
                )

                if reason:
                    aborted = True
                    print(f"  SAFETY ABORT: {reason}")
                    if on_progress:
                        on_progress({
                            "phase": "during", "event": "safety_abort",
                            "error_rate": round(err, 3), "p95_ms": round(latency),
                            "extra_unhealthy_pods": extra, "warning": reason,
                        })
                    break

                if on_sample and i % review_every == 0:
                    agent_rollback = on_sample({
                        "elapsed_s": round(env.now() - fault_started, 1),
                        "planned_duration_s": exp["duration_s"],
                        "error_rate": round(err, 3),
                        "p95_ms": round(latency),
                        "extra_unhealthy_pods": extra,
                        "samples": len(phase_samples["during"]),
                    })
                    if agent_rollback:
                        agent_rollback = str(agent_rollback)[:400]
                        print(f"  AGENT ROLLBACK: {agent_rollback}")
                        break
            if on_progress:
                on_progress({
                    "phase": "during", "event": "sample",
                    "sample": sample,
                    "error_rate": round(window_stats(window)[0], 3) if window else None,
                    "p95_ms": round(window_stats(window)[1]) if window else None,
                    "extra_unhealthy_pods": extra,
                })

            env.sleep(interval)

    finally:
        print("  Removing injected fault...")
        if on_progress:
            on_progress({"phase": "cleanup_pending", "event": "started"})

        cleanup_start = time.perf_counter()

        cleanup_confirmed = env.delete(exp, path)
        if on_progress:
            on_progress({
                "phase": "cleanup_verified" if cleanup_confirmed else "cleanup_pending",
                "event": "finished",
                "cleanup_confirmed": cleanup_confirmed,
            })

        if aborted:
            abort_latency = (
                time.perf_counter() - cleanup_start
            )

        removed_at = env.now() - origin

        if cleanup_confirmed is False:
            print(
                "  WARNING: Fault cleanup not confirmed"
            )

    # ---------------------------------------
    # PHASE 3: RECOVERY
    # ---------------------------------------

    print("  RECOVERY: checking stabilization")
    if on_progress:
        on_progress({"phase": "recovery", "event": "started"})

    rec_start = env.now()
    streak = 0
    streak_start = None
    recovered = False

    latency_limit = max(
        experiment_baseline["p95_ms"] * 3,
        400,
    )

    while env.now() - rec_start < cfg["recovery_timeout_s"]:

        ok, ms = env.probe()

        sample = [
            round(env.now() - origin, 2),
            int(ok),
            round(ms, 2),
            "recovery",
        ]

        samples.append(sample)
        phase_samples["recovery"].append(sample)
        if on_progress:
            on_progress({"phase": "recovery", "event": "sample", "sample": sample})

        if ok and ms <= latency_limit:
            streak += 1

            if streak == 1:
                streak_start = env.now()

            if streak >= 5:
                recovered = True
                break
        else:
            streak = 0
            streak_start = None

        env.sleep(interval)

    recovery_s = (
        round(streak_start - rec_start, 2)
        if recovered else None
    )

    # ---------------------------------------
    # PHASE 4: AFTER
    # ---------------------------------------

    if recovered:
        print(
            f"  AFTER: measuring for {after_seconds}s"
        )

        after = collect_phase(
            env, cfg, after_seconds, "after", origin, on_progress
        )

        phase_samples["after"] = after
        samples.extend(after)

    else:
        print(
            "  AFTER: skipped because recovery "
            "was not confirmed"
        )

    # ---------------------------------------
    # ANALYSIS
    # ---------------------------------------
    if on_progress:
        on_progress({"phase": "analyzing", "event": "started"})

    phase_metrics = {
        name: phase_stats(values)
        for name, values in phase_samples.items()
    }

    during_metrics = phase_metrics["during"]
    after_metrics = phase_metrics["after"]

    before_p95 = before_metrics["p95_ms"]
    during_p95 = during_metrics["p95_ms"]
    after_p95 = after_metrics["p95_ms"]

    during_change = latency_change_pct(
        before_p95, during_p95
    )

    after_change = latency_change_pct(
        before_p95, after_p95
    )

    # Require post-recovery behavior close to baseline.
    recovered_to_baseline = (
        recovered
        and after_metrics["samples"] > 0
        and after_metrics["error_rate"] <= 0.05
        and after_p95 is not None
        and after_p95 <= before_p95 * 1.20
    )

    impact = {
        "latency_increase_pct": during_change,
        "after_latency_change_pct": after_change,
        "recovered_to_baseline": recovered_to_baseline,
        "recovery_verified": recovered,
    }

    events = {
        "fault_injected_at_s": round(injected_at, 2),
        "fault_removed_at_s": round(removed_at, 2),
        "experiment_ended_at_s": round(
            env.now() - origin, 2
        ),
    }

    print("\n  PHASE COMPARISON")

    for name, metrics in phase_metrics.items():
        print(
            f"  {name.upper():8} "
            f"errors={metrics['error_rate']} "
            f"p95={metrics['p95_ms']}ms "
            f"samples={metrics['samples']}"
        )

    print(
        "  Returned to baseline:",
        recovered_to_baseline,
    )

    # ---------------------------------------
    # RESULT: backward-compatible fields
    # ---------------------------------------

    result = {
        **{
            k: exp[k]
            for k in (
                "id",
                "service",
                "action",
                "duration_s",
                "rationale",
                "app_label",
            )
        },

        "aborted": aborted,
        "abort_reason": reason if aborted else None,
        "abort_latency_s": (
            round(abort_latency, 3)
            if abort_latency is not None else None
        ),

        "error_rate": during_metrics["error_rate"] or 0.0,
        "p95_ms": round(during_p95 or 0.0),

        "peak_error_rate": round(peak_err, 3),
        "peak_p95_ms": round(peak_p95),

        "recovered": recovered,
        "recovery_s": recovery_s,

        "samples": samples,

        "phase_metrics": phase_metrics,
        "phase_samples": phase_samples,
        "impact": impact,
        "events": events,
        "cleanup_confirmed": cleanup_confirmed,
        "agent_rollback": agent_rollback,
    }

    if on_progress:
        on_progress({"phase": "completed", "event": "finished", "cleanup_confirmed": cleanup_confirmed})

    return result


def run_plan(plan, cfg, env, baseline, run_dir, stop_file):
    """Execute all experiments using existing CLI interface."""

    guard = Guard(cfg, baseline, stop_file)

    if os.path.exists(stop_file):
        os.remove(stop_file)

    print(f"Safety limits: {guard.limits()}")

    done = []

    try:
        for exp in plan["experiments"]:

            done.append(
                run_experiment(
                    exp,
                    cfg,
                    env,
                    baseline,
                    guard,
                    run_dir,
                )
            )

            if os.path.exists(stop_file):
                print("Manual stop requested")
                break

            env.sleep(cfg["cooldown_s"])

    except KeyboardInterrupt:
        print("\nExperiment session interrupted")

    return done, guard.limits()