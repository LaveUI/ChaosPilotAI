"""Self-contained HTML investigation dashboard for chaos experiment results."""
import html
import math

CSS = """
:root{color-scheme:dark;--bg:#0b1020;--surface:#111a2d;--surface-2:#172238;--ink:#e7edf8;--muted:#9aa9c2;--line:#293750;--blue:#69a9ff;--red:#fb7185;--amber:#f4b860;--green:#43d6b0;--teal:#69c4e8;--good:#43d6b0;--warn:#f4b860;--bad:#fb7185}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1280px;margin:0 auto;padding:32px 24px 64px}h1{font-size:30px;letter-spacing:-.03em;margin:0 0 4px}h2{font-size:19px;letter-spacing:-.01em;margin:30px 0 12px}h3{font-size:15px;margin:22px 0 10px}
.muted{color:var(--muted)}.hero{display:flex;gap:24px;align-items:center;flex-wrap:wrap;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:24px}
.big{font-size:62px;font-weight:750;line-height:1;letter-spacing:-.05em}.delta{font-size:18px;font-weight:650}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:20px;margin:14px 0;box-shadow:0 8px 24px #03071226}
.row{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:baseline}
.pill{display:inline-block;padding:3px 10px;border-radius:99px;border:1px solid var(--line);font-size:12px;color:var(--muted)}
.pill.abort,.status-failed{border-color:#713746;color:var(--red);background:#fb718514}.status-ok{color:var(--green)}.status-warn{color:var(--amber)}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);font-weight:650}
.scroll{overflow-x:auto}svg.timeline{display:block;width:100%;height:auto;margin:12px 0 4px;background:#0d1526;border:1px solid var(--line);border-radius:10px}ul{margin:7px 0 0;padding-left:20px}li{padding:3px 0}
.section-title{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.phase-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0}
.phase-card{background:var(--surface-2);border:1px solid var(--line);border-top:3px solid var(--phase);border-radius:11px;padding:14px;min-width:0}
.phase-card h4{margin:0 0 12px;text-transform:uppercase;letter-spacing:.08em;font-size:11px;color:var(--phase)}
.phase-values{display:grid;grid-template-columns:1fr 1fr;gap:8px}.metric{font-size:16px;font-weight:650;white-space:nowrap}.metric-label{display:block;color:var(--muted);font-size:11px;font-weight:500}
.phase-before{--phase:var(--blue)}.phase-during{--phase:var(--red)}.phase-recovery{--phase:var(--amber)}.phase-after{--phase:var(--green)}
.insight-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.insight{background:var(--surface-2);border:1px solid var(--line);border-radius:10px;padding:15px}.insight h4{margin:0 0 8px;font-size:13px}.insight p{margin:5px 0}.conclusion{border-left:3px solid var(--teal);padding:10px 14px;background:#69c4e80c;border-radius:0 8px 8px 0}
.chart-legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin:8px 4px}.legend-item{display:flex;align-items:center;gap:6px}.swatch{width:9px;height:9px;border-radius:50%;background:var(--swatch)}
.legend-marker{font-weight:800;color:var(--marker);font-size:15px;line-height:1}
@media(max-width:850px){main{padding:24px 16px 48px}.phase-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:520px){main{padding:18px 12px 40px}.phase-grid,.insight-grid{grid-template-columns:1fr}.big{font-size:52px}.card{padding:15px}}
"""


def _color(score):
    return "var(--good)" if score >= 80 else "var(--warn)" if score >= 60 else "var(--bad)"


PHASES = (
    ("before", "Before", "phase-before"),
    ("during", "During", "phase-during"),
    ("recovery", "Recovery", "phase-recovery"),
    ("after", "After", "phase-after"),
)


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _fmt_ms(value):
    number = _number(value)
    return "N/A" if number is None else f"{number:.1f} ms"


def _fmt_pct(value):
    number = _number(value)
    return "N/A" if number is None else f"{number:.1f}%"


def _fmt_rate(value):
    number = _number(value)
    return "N/A" if number is None else f"{number:.1%}"


def _phase_records(phase_samples, samples):
    records = []
    if isinstance(phase_samples, dict):
        for phase, phase_values in phase_samples.items():
            if isinstance(phase_values, list):
                records.extend(_sample_record(sample, phase) for sample in phase_values)
    if not records and isinstance(samples, list):
        records = [_sample_record(sample) for sample in samples]
    return [record for record in records if record is not None]


def _sample_record(sample, phase=None):
    if not isinstance(sample, (list, tuple)) or len(sample) < 3:
        return None
    timestamp, success, latency = (_number(sample[0]), sample[1], _number(sample[2]))
    if timestamp is None or latency is None:
        return None
    sample_phase = phase or (sample[3] if len(sample) > 3 else "during")
    if sample_phase == "chaos":
        sample_phase = "during"
    return {
        "time": timestamp,
        "success": bool(success),
        "latency": latency,
        "phase": sample_phase if sample_phase in {p[0] for p in PHASES} else "during",
    }


def timeline_svg(samples, w=900, h=320, events=None, phase_samples=None):
    """Render stored samples and event boundaries as an offline SVG timeline."""
    records = _phase_records(phase_samples, samples)
    if not records:
        return "<p class='muted'>Timeline data unavailable for this experiment.</p>"

    events = events if isinstance(events, dict) else {}
    injected = _number(events.get("fault_injected_at_s"))
    removed = _number(events.get("fault_removed_at_s"))
    after_start = min((r["time"] for r in records if r["phase"] == "after"), default=None)
    times = [r["time"] for r in records]
    times.extend(value for value in (injected, removed) if value is not None)
    tmin, tmax = min(0.0, min(times)), max(times)
    if tmax <= tmin:
        tmax = tmin + 1

    left, right, top, bottom = 58, w - 20, 24, h - 55
    plot_width, plot_height = right - left, bottom - top
    max_latency = max((r["latency"] for r in records), default=0)
    y_max = max(1.0, math.ceil(max_latency / 50) * 50)
    x = lambda value: left + plot_width * (value - tmin) / (tmax - tmin)
    y = lambda value: bottom - plot_height * value / y_max

    def phase_start(phase):
        return min((r["time"] for r in records if r["phase"] == phase), default=None)

    def phase_end(phase):
        return max((r["time"] for r in records if r["phase"] == phase), default=None)

    bounds = {
        "before": (phase_start("before"), injected if injected is not None else phase_end("before")),
        "during": (injected if injected is not None else phase_start("during"),
                   removed if removed is not None else phase_end("during")),
        "recovery": (removed if removed is not None else phase_start("recovery"),
                     after_start if after_start is not None else phase_end("recovery")),
        "after": (after_start, phase_end("after")),
    }
    phase_colors = {
        "before": "var(--blue)", "during": "var(--red)",
        "recovery": "var(--amber)", "after": "var(--green)",
    }

    pieces = [
        f"<svg class='timeline' viewBox='0 0 {w} {h}' role='img' "
        "aria-label='Request latency over elapsed experiment time'>",
        "<title>Experiment latency timeline</title>",
        "<desc>Measured request latency by experiment phase, with failed requests and fault boundaries.</desc>",
    ]
    for phase, (start, end) in bounds.items():
        if start is not None and end is not None and end >= start:
            pieces.append(
                f"<rect x='{x(start):.2f}' y='{top}' width='{max(0, x(end)-x(start)):.2f}' "
                f"height='{plot_height}' fill='{phase_colors[phase]}' opacity='.075'/>"
            )

    for tick in range(5):
        value = y_max * tick / 4
        yy = y(value)
        pieces.append(
            f"<line x1='{left}' y1='{yy:.2f}' x2='{right}' y2='{yy:.2f}' "
            "stroke='#293750' stroke-width='1'/>"
            f"<text x='{left-9}' y='{yy+4:.2f}' text-anchor='end' "
            "font-size='11' fill='#9aa9c2'>"
            f"{value:.0f}</text>"
        )
        time_value = tmin + (tmax - tmin) * tick / 4
        xx = x(time_value)
        pieces.append(
            f"<text x='{xx:.2f}' y='{bottom+20}' text-anchor='middle' "
            "font-size='11' fill='#9aa9c2'>"
            f"{time_value:.0f}</text>"
        )

    pieces.extend([
        f"<line x1='{left}' y1='{top}' x2='{left}' y2='{bottom}' stroke='#71819b'/>",
        f"<line x1='{left}' y1='{bottom}' x2='{right}' y2='{bottom}' stroke='#71819b'/>",
        f"<text x='16' y='{(top+bottom)/2:.1f}' transform='rotate(-90 16 {(top+bottom)/2:.1f})' "
        "font-size='11' fill='#c3cee0'>Latency (ms)</text>",
        f"<text x='{(left+right)/2:.1f}' y='{h-10}' text-anchor='middle' "
        "font-size='11' fill='#c3cee0'>Elapsed time (s)</text>",
    ])

    for phase, _, _ in PHASES:
        phase_records = sorted((r for r in records if r["phase"] == phase), key=lambda r: r["time"])
        successful = [r for r in phase_records if r["success"]]
        if len(successful) > 1:
            points = " ".join(f"{x(r['time']):.2f},{y(r['latency']):.2f}" for r in successful)
            pieces.append(
                f"<polyline points='{points}' fill='none' stroke='{phase_colors[phase]}' "
                "stroke-width='2' stroke-linejoin='round' stroke-linecap='round'/>"
            )
        for record in phase_records:
            cx, cy = x(record["time"]), y(record["latency"])
            if record["success"]:
                pieces.append(
                    f"<circle cx='{cx:.2f}' cy='{cy:.2f}' r='2.4' "
                    f"fill='{phase_colors[phase]}' opacity='.9'/>"
                )
            else:
                pieces.append(
                    f"<path d='M {cx-3:.2f} {cy-3:.2f} L {cx+3:.2f} {cy+3:.2f} "
                    f"M {cx+3:.2f} {cy-3:.2f} L {cx-3:.2f} {cy+3:.2f}' "
                    "stroke='#fb7185' stroke-width='1.8'/>"
                )

    for value, label, anchor, offset in (
        (injected, "Fault injected", "end", -5),
        (removed, "Fault removed", "start", 5),
    ):
        if value is not None:
            xx = x(value)
            label_x = min(max(xx + offset, left + 4), right - 4)
            pieces.append(
                f"<line x1='{xx:.2f}' y1='{top}' x2='{xx:.2f}' y2='{bottom}' "
                "stroke='#f8fafc' stroke-width='1.2' stroke-dasharray='4 4'/>"
                f"<text x='{label_x:.2f}' y='{top+12}' text-anchor='{anchor}' "
                "font-size='10' fill='#f8fafc'>"
                f"{label}</text>"
            )
    pieces.append("</svg>")
    return "".join(pieces)


def phase_comparison(phase_metrics, phase_samples=None, recovery_s=None):
    """Render four phase cards without treating missing measurements as zero."""
    phase_metrics = phase_metrics if isinstance(phase_metrics, dict) else {}
    phase_samples = phase_samples if isinstance(phase_samples, dict) else {}
    cards = []
    for key, label, css_class in PHASES:
        data = phase_metrics.get(key) or {}
        measured = data.get("samples")
        if measured is None:
            measured = len(phase_samples.get(key, []))
        has_samples = bool(measured)
        p50 = _fmt_ms(data.get("p50_ms")) if has_samples else "N/A"
        p95 = _fmt_ms(data.get("p95_ms")) if has_samples else "N/A"
        error = _fmt_rate(data.get("error_rate")) if has_samples else "N/A"
        if key == "recovery":
            duration = f"{_number(recovery_s):.1f} s" if _number(recovery_s) is not None else "Not verified"
            tail = f"<div><span class='metric-label'>Recovery duration</span><span class='metric'>{duration}</span></div>"
        else:
            count = f"{int(measured)}" if has_samples else "N/A"
            tail = f"<div><span class='metric-label'>Samples</span><span class='metric'>{count}</span></div>"
        cards.append(
            f"<section class='phase-card {css_class}' aria-label='{label} phase metrics'>"
            f"<h4>{label}</h4><div class='phase-values'>"
            f"<div><span class='metric-label'>p50 latency</span><span class='metric'>{p50}</span></div>"
            f"<div><span class='metric-label'>p95 latency</span><span class='metric'>{p95}</span></div>"
            f"<div><span class='metric-label'>Error rate</span><span class='metric'>{error}</span></div>"
            f"{tail}</div></section>"
        )
    return "<div class='phase-grid'>" + "".join(cards) + "</div>"


def _latency_delta(before, during):
    before, during = _number(before), _number(during)
    if before is None or during is None or before <= 0:
        return None
    return (during - before) / before * 100


def _observed_impact(experiment, baseline):
    phases = experiment.get("phase_metrics") or {}
    before = phases.get("before") or {}
    during = phases.get("during") or {}
    impact = experiment.get("impact") or {}

    if phases:
        latency_increase = impact.get("latency_increase_pct")
        if latency_increase is None:
            latency_increase = _latency_delta(before.get("p95_ms"), during.get("p95_ms"))
        error_before, error_during = before.get("error_rate"), during.get("error_rate")
        sample_count = _number(during.get("samples"))
        successful_count = _number(during.get("successful_requests"))
        all_failed = (
            sample_count not in (None, 0)
            and (
                successful_count == 0
                or _number(during.get("error_rate")) == 1.0
            )
        )
    else:
        latency_increase = _latency_delta(baseline.get("p95_ms"), experiment.get("p95_ms"))
        error_before, error_during = baseline.get("error_rate"), experiment.get("error_rate")
        all_failed = _number(error_during) == 1.0

    records = _phase_records(experiment.get("phase_samples"), experiment.get("samples"))
    max_latency = max((record["latency"] for record in records), default=None)
    error_diff = None
    if _number(error_before) is not None and _number(error_during) is not None:
        error_diff = (_number(error_during) - _number(error_before)) * 100
    return {
        "latency_increase_pct": _number(latency_increase),
        "error_increase_points": error_diff,
        "max_latency_ms": max_latency,
        "all_failed": all_failed,
        "successful_during": _number(during.get("successful_requests")) if phases else None,
    }


def impact_section(experiment, baseline):
    impact = _observed_impact(experiment, baseline)
    abort_reason = experiment.get("abort_reason")
    abort_status = (
        f"<span class='status-failed'>Yes</span> — {html.escape(str(abort_reason or 'reason unavailable'))}"
        if experiment.get("aborted")
        else "<span class='status-ok'>No</span>"
    )
    if impact["all_failed"]:
        latency_statement = "Latency degradation cannot be calculated because all requests failed during the fault."
    elif impact["latency_increase_pct"] is not None:
        latency_statement = (
            f"{html.escape(str(experiment.get('action', 'Fault')).replace('-', ' ').title())} "
            f"increased p95 latency by {impact['latency_increase_pct']:.2f}% "
            "compared with the pre-experiment baseline."
        )
    else:
        latency_statement = "p95 latency change is N/A because comparable successful measurements are unavailable."

    if impact["error_increase_points"] is None:
        error_change = "N/A"
    else:
        error_change = f"{impact['error_increase_points']:+.1f} percentage points"
    return (
        "<div class='insight'><h3>Observed Impact</h3>"
        f"<p class='muted'>{latency_statement}</p>"
        f"<p><b>p95 latency change:</b> {_fmt_pct(impact['latency_increase_pct'])}</p>"
        f"<p><b>Error-rate change:</b> {error_change}</p>"
        f"<p><b>Maximum observed latency:</b> {_fmt_ms(impact['max_latency_ms'])}</p>"
        f"<p><b>Safety guard aborted:</b> {abort_status}</p></div>"
    )


def recovery_section(experiment):
    phases = experiment.get("phase_metrics") or {}
    recovery = phases.get("recovery") or {}
    before, after = phases.get("before") or {}, phases.get("after") or {}
    impact = experiment.get("impact") or {}
    recovery_samples = _number(recovery.get("samples"))

    if not phases or (
        recovery_samples in (None, 0)
        and "recovery_verified" not in impact
    ):
        status = "Recovery data unavailable"
        status_class = "status-warn"
    else:
        verified = impact.get("recovery_verified", experiment.get("recovered"))
        restored = impact.get("recovered_to_baseline")
        if verified is False:
            status, status_class = "Recovery not verified", "status-failed"
        elif verified is True and restored is True:
            status, status_class = "Recovery verified and baseline restored", "status-ok"
        elif verified is True and restored is False:
            status, status_class = "Recovery verified; baseline not restored", "status-warn"
        elif verified is True:
            status, status_class = "Recovery verified; baseline restoration unavailable", "status-warn"
        else:
            status, status_class = "Recovery not verified", "status-failed"

    recovery_time = _number(experiment.get("recovery_s"))
    after_change = _number(impact.get("after_latency_change_pct"))
    if after_change is None:
        after_change = _latency_delta(before.get("p95_ms"), after.get("p95_ms"))
    recovery_time_text = f"{recovery_time:.1f} s" if recovery_time is not None else "N/A"
    change_text = _fmt_pct(after_change)
    return (
        "<div class='insight'><h3>Recovery Assessment</h3>"
        f"<p class='{status_class}'><b>{status}</b></p>"
        f"<p><b>Recovery time:</b> {recovery_time_text}</p>"
        f"<p><b>Before p95 / error rate:</b> {_fmt_ms(before.get('p95_ms'))} / {_fmt_rate(before.get('error_rate'))}</p>"
        f"<p><b>After p95 / error rate:</b> {_fmt_ms(after.get('p95_ms'))} / {_fmt_rate(after.get('error_rate'))}</p>"
        f"<p><b>Before-to-after p95 difference:</b> {change_text}</p></div>"
    )


def experiment_conclusion(experiment, baseline):
    impact = _observed_impact(experiment, baseline)
    service = html.escape(str(experiment.get("service", "Unknown service")))
    action = html.escape(str(experiment.get("action", "fault")).replace("-", " "))
    metrics = experiment.get("phase_metrics") or {}
    after = metrics.get("after") or {}
    recovery = experiment.get("impact") or {}
    if impact["all_failed"]:
        sentence = (
            f"{service} had complete request failure during the {action} observation window; "
            "latency degradation could not be calculated because there were no successful requests."
        )
    elif impact["latency_increase_pct"] is not None:
        sentence = (
            f"{service} experienced a {impact['latency_increase_pct']:.1f}% increase in p95 latency "
            f"during {action}."
        )
    else:
        sentence = f"{service} was tested with {action}; comparable phase latency measurements are unavailable."

    if recovery.get("recovery_verified", experiment.get("recovered")) is True:
        if recovery.get("recovered_to_baseline") is True:
            sentence += " Recovery was verified and post-recovery measurements returned to baseline."
        elif recovery.get("recovered_to_baseline") is False:
            sentence += " Recovery was verified, but post-recovery measurements did not return to baseline."
        elif after.get("samples"):
            sentence += " Recovery was verified; baseline restoration was not recorded."
        else:
            sentence += " Recovery was verified, but post-recovery measurements are unavailable."
    else:
        sentence += " Recovery was not verified in the recorded observation window."
    return f"<p class='conclusion'>{sentence}</p>"




def render(results, graph, previous=None):
    e = html.escape
    score = results["resilience_score"]

    prev_score = (
        previous["resilience_score"] if previous else None
    )

    prev_by = (
        {
            (p["service"], p["action"]): p
            for p in previous["experiments"]
        }
        if previous else {}
    )

    parts = [
        "<!doctype html><html lang='en'>"
        "<head><meta charset='utf-8'>"
        "<meta name='viewport' "
        "content='width=device-width,initial-scale=1'>"
        f"<title>Resilience report {e(results['run_id'])}</title>"
        f"<style>{CSS}</style></head><body><main>",

        "<h1>Resilience report</h1>",

        f"<div class='muted'>"
        f"Run {e(results['run_id'])} &middot; "
        f"environment: {e(results['env'])} &middot; "
        f"planner: {e(results['planner'])}"
        f"</div>"
    ]

    # ---------------------------------------
    # Overall resilience score
    # ---------------------------------------

    delta = ""

    if prev_score is not None:
        d = round(score - prev_score, 1)
        delta_color = (
            "var(--good)" if d >= 0 else "var(--bad)"
        )

        delta = (
            f"<div class='delta' style='color:{delta_color}'>"
            f"{'+' if d >= 0 else ''}{d} "
            f"vs run {e(previous['run_id'])} "
            f"({prev_score})"
            f"</div>"
        )

    parts.append(
        f"<div class='hero' style='margin-top:16px'>"
        f"<div class='big' style='color:{_color(score)}'>"
        f"{score}</div>"
        f"<div>"
        f"<div><b>Resilience score</b> out of 100</div>"
        f"{delta}"
        f"<div class='muted'>"
        f"Baseline: "
        f"{results['baseline']['error_rate']:.1%} errors, "
        f"p95 {results['baseline']['p95_ms']:.0f} ms"
        f"</div></div></div>"
    )

    if results.get("summary"):
        parts.append(
            f"<div class='card'>"
            f"<b>Summary</b>"
            f"<p>{e(results['summary'])}</p>"
            f"</div>"
        )

    # ---------------------------------------
    # Experiments overview table
    # ---------------------------------------

    parts.append(
        "<h2>Experiments, weakest first</h2>"
        "<div class='scroll'>"
        "<table>"
        "<tr>"
        "<th>Service</th>"
        "<th>Fault</th>"
        "<th>Score</th>"
        "<th>Errors</th>"
        "<th>p95</th>"
        "<th>Recovery</th>"
        + ("<th>Before</th>" if previous else "")
        + "</tr>"
    )

    for x in sorted(results["experiments"], key=lambda item: item.get("score", 0)):
        rec = (
            f"{x.get('recovery_s')}s"
            if x.get("recovered")
            else "none"
        )

        before = ""

        if previous:
            p = prev_by.get(
                (x["service"], x["action"])
            )
            before = (
                f"<td>{p['score']}</td>"
                if p else "<td>-</td>"
            )

        parts.append(
            f"<tr>"
            f"<td>{e(str(x.get('service', 'Unknown')))}</td>"
            f"<td>{e(str(x.get('action', 'Unknown')))}</td>"
            f"<td style='color:{_color(x.get('score', 0))}'>"
            f"<b>{x.get('score', 'N/A')}</b></td>"
            f"<td>{_fmt_rate(x.get('error_rate'))}</td>"
            f"<td>{_fmt_ms(x.get('p95_ms'))}</td>"
            f"<td>{rec}</td>"
            f"{before}"
            f"</tr>"
        )

    parts.append("</table></div>")

    # ---------------------------------------
    # Detailed experiment analysis
    # ---------------------------------------

    parts.append("<h2>Details</h2>")

    for x in results["experiments"]:
        service = e(str(x.get("service", "Unknown service")))
        action = e(str(x.get("action", "Unknown fault")))
        abort = (
            f"<span class='pill abort'>"
            f"safety abort: {e(str(x.get('abort_reason') or 'reason unavailable'))}"
            f"</span>"
            if x.get("aborted") else ""
        )

        parts.append(
            f"<div class='card'>"

            f"<div class='row'>"
            f"<b>{action} on {service}</b>"
            f"{abort}"
            f"<span style='color:{_color(x.get('score', 0))}'>"
            f"<b>{x.get('score', 'N/A')}</b>/100"
            f"</span>"
            f"</div>"

            f"<p class='muted' "
            f"style='margin:4px 0 8px'>"
            f"Why this test: {e(str(x.get('rationale', 'Rationale unavailable.')))}"
            f"</p>"

            f"{timeline_svg(x.get('samples'), events=x.get('events'), phase_samples=x.get('phase_samples'))}"
            "<div class='chart-legend' aria-label='Timeline legend'>"
            "<span class='legend-item'><span class='swatch' style='--swatch:var(--blue)'></span>Before</span>"
            "<span class='legend-item'><span class='swatch' style='--swatch:var(--red)'></span>During fault</span>"
            "<span class='legend-item'><span class='swatch' style='--swatch:var(--amber)'></span>Recovery</span>"
            "<span class='legend-item'><span class='swatch' style='--swatch:var(--green)'></span>After</span>"
            "<span class='legend-item'><span class='legend-marker' style='--marker:var(--red)'>×</span>Failed request</span>"
            "<span class='legend-item'><span class='legend-marker' style='--marker:#f8fafc'>┆</span>Fault inject / remove</span>"
            "</div>"

            f"<div class='muted'>"
            f"Penalties: "
            f"errors -{(x.get('breakdown') or {}).get('errors', 'N/A')}, "
            f"latency -{(x.get('breakdown') or {}).get('latency', 'N/A')}, "
            f"recovery -{(x.get('breakdown') or {}).get('recovery', 'N/A')}, "
            f"abort -{(x.get('breakdown') or {}).get('abort', 'N/A')}"
            + (
                f". Kill switch removed the fault in "
                f"{x.get('abort_latency_s')}s"
                if x.get("aborted") and x.get("abort_latency_s") is not None else ""
            )
            + "</div>"
        )

        parts.append("<div class='section-title'><h3>Four-phase measurements</h3>"
                     "<span class='muted'>Latencies use successful requests only</span></div>")
        parts.append(phase_comparison(
            x.get("phase_metrics"), x.get("phase_samples"), x.get("recovery_s")
        ))
        parts.append("<h3>Investigation</h3><div class='insight-grid'>")
        parts.append(impact_section(x, results.get("baseline") or {}))
        parts.append(recovery_section(x))
        parts.append("</div>")
        parts.append("<h3>Conclusion</h3>")
        parts.append(experiment_conclusion(x, results.get("baseline") or {}))

        # -----------------------------------
        # Recommended fixes
        # -----------------------------------

        if x.get("recommendations"):
            parts.append(
                "<b>Recommended fixes</b><ul>"
                + "".join(
                    f"<li>"
                    f"<b>{e(str(r.get('title', 'Recommendation')))}</b>. "
                    f"{e(str(r.get('detail', '')))}"
                    f"</li>"
                    for r in x["recommendations"]
                )
                + "</ul>"
            )
        else:
            parts.append(
                "<div style='color:var(--good)'>"
                "No action needed."
                "</div>"
            )

        parts.append("</div>")

    # ---------------------------------------
    # Dependency map
    # ---------------------------------------

    parts.append(
        "<h2>Dependency map</h2>"
        "<div class='scroll'>"
        "<table>"
        "<tr>"
        "<th>Service</th>"
        "<th>Calls</th>"
        "<th>Called by</th>"
        "<th>Replicas</th>"
        "</tr>"
    )

    for n in graph["nodes"]:
        parts.append(
            f"<tr>"
            f"<td>{e(n['name'])}</td>"
            f"<td>{e(', '.join(n['depends_on']) or '-')}</td>"
            f"<td>{e(', '.join(n['depended_by']) or '-')}</td>"
            f"<td>{n['replicas']}</td>"
            f"</tr>"
        )

    parts.append(
        "</table></div>"
        "</main></body></html>"
    )

    return "".join(parts)
