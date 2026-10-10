"""Self-contained HTML investigation dashboard for chaos experiment results."""
import html
import math

CSS = """
:root{color-scheme:dark;--bg:#0b1020;--surface:#111a2d;--surface-2:#172238;--ink:#e7edf8;--muted:#a8b5ca;--line:#293750;--blue:#79b3ff;--red:#fb7185;--amber:#f4b860;--green:#43d6b0;--teal:#78c8ef;--purple:#c3a6ff;--good:#43d6b0;--warn:#f4b860;--bad:#fb7185;--shadow:0 12px 28px #03071226}
@media(prefers-color-scheme:light){:root{color-scheme:light;--bg:#f3f6fb;--surface:#fff;--surface-2:#f7f9fc;--ink:#152238;--muted:#52627a;--line:#d9e1ec;--blue:#2563eb;--red:#c62845;--amber:#a15c00;--green:#087a59;--teal:#087fa5;--purple:#7042b6;--good:#087a59;--warn:#a15c00;--bad:#c62845;--shadow:0 8px 22px #26354a12}}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1440px;margin:0 auto;padding:36px 28px 72px}h1{font-size:clamp(26px,3vw,38px);letter-spacing:-.035em;line-height:1.12;margin:0 0 8px}h2{font-size:21px;letter-spacing:-.02em;margin:34px 0 14px}h3{font-size:16px;margin:20px 0 10px}h4{margin:0 0 8px}
p{margin:8px 0}.eyebrow,.kpi-label,.section-kicker{font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:700}
.muted{color:var(--muted)}.subtitle{font-size:15px;color:var(--muted);margin:0 0 20px}.meta-row{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 20px}.meta-chip{padding:6px 10px;border:1px solid var(--line);background:var(--surface);border-radius:8px;color:var(--muted);font-size:12px}.meta-chip b{color:var(--ink);font-weight:650}
.hero{display:grid;grid-template-columns:minmax(190px,.7fr) 1.3fr;gap:22px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:24px;box-shadow:var(--shadow)}
.score-block{display:flex;align-items:center;gap:17px}.big{font-size:clamp(54px,7vw,76px);font-weight:780;line-height:.95;letter-spacing:-.06em;font-variant-numeric:tabular-nums}.score-caption{font-size:14px;font-weight:700}.delta{font-size:14px;font-weight:700;margin-top:5px}
.kpi-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin:14px 0 20px}.kpi{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px;min-width:0}.kpi-value{font-size:25px;font-weight:750;line-height:1.1;margin-top:5px;font-variant-numeric:tabular-nums}.kpi-detail{font-size:11px;color:var(--muted);margin-top:3px}
.card,.panel{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px;margin:14px 0;box-shadow:var(--shadow)}.row{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center}
.pill{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:99px;border:1px solid var(--line);font-size:11px;color:var(--muted);font-weight:700}.pill.abort,.status-failed{border-color:color-mix(in srgb,var(--red) 45%,var(--line));color:var(--red);background:color-mix(in srgb,var(--red) 9%,transparent)}.status-ok{color:var(--green)}.status-warn{color:var(--amber)}.status-info{color:var(--blue)}
.summary{border-left:3px solid var(--purple);background:var(--surface);}.summary p{font-size:15px;max-width:1000px}.summary .evidence-note{font-size:12px;color:var(--muted);margin-top:12px}
.flow{display:flex;gap:0;align-items:center;flex-wrap:wrap;margin:8px 0 20px}.flow-step{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--muted);font-weight:650}.flow-num{width:22px;height:22px;border-radius:50%;display:grid;place-items:center;background:var(--surface-2);border:1px solid var(--line);color:var(--blue);font-size:11px}.flow-arrow{padding:0 10px;color:var(--muted)}
.findings-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.finding-card{background:var(--surface);border:1px solid var(--line);border-top:3px solid var(--severity);border-radius:13px;padding:17px;min-width:0}.finding-card h3{margin:10px 0 4px}.finding-top{display:flex;justify-content:space-between;align-items:center;gap:8px}.severity{color:var(--severity);font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.finding-score{font-size:23px;font-weight:750;font-variant-numeric:tabular-nums}.finding-metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0}.finding-metric{padding:8px;background:var(--surface-2);border-radius:8px}.finding-metric b{display:block;font-size:15px;font-variant-numeric:tabular-nums}.finding-note{font-size:12px;color:var(--muted)}
.grid-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.grid-three{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:10px 11px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:10px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);font-weight:750}tbody tr:last-child td{border-bottom:0}.scroll{overflow-x:auto}caption{text-align:left;color:var(--muted);padding:0 0 9px;font-size:12px}.rank{font-weight:800;color:var(--blue);font-variant-numeric:tabular-nums}
.score-track{height:7px;background:var(--line);border-radius:99px;overflow:hidden;min-width:80px}.score-fill{height:100%;border-radius:inherit}.comparison-chart{display:grid;gap:10px}.comparison-row{display:grid;grid-template-columns:minmax(120px,1fr) 2fr 42px;gap:10px;align-items:center;font-size:12px}.comparison-bars{display:grid;gap:4px}.comparison-bar{height:8px;border-radius:99px;background:var(--bar);min-width:2px}
.phase-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0}.phase-card{background:var(--surface-2);border:1px solid var(--line);border-top:3px solid var(--phase);border-radius:11px;padding:14px;min-width:0}.phase-card h4{margin:0 0 12px;text-transform:uppercase;letter-spacing:.09em;font-size:11px;color:var(--phase)}.phase-values{display:grid;grid-template-columns:1fr 1fr;gap:9px}.metric{font-size:15px;font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums}.metric-label{display:block;color:var(--muted);font-size:10px;font-weight:600}.phase-before{--phase:var(--blue)}.phase-during{--phase:var(--red)}.phase-recovery{--phase:var(--amber)}.phase-after{--phase:var(--green)}
.insight-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.insight{background:var(--surface-2);border:1px solid var(--line);border-radius:11px;padding:16px;min-width:0}.insight h3{margin:0 0 10px;font-size:15px}.insight p{font-size:13px}.conclusion{border-left:3px solid var(--teal);padding:12px 15px;background:var(--surface-2);border-radius:0 9px 9px 0}
.chart-legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:11px;margin:8px 2px 14px}.legend-item{display:flex;align-items:center;gap:6px}.swatch{width:9px;height:9px;border-radius:50%;background:var(--swatch)}.legend-marker{font-weight:800;color:var(--marker);font-size:15px;line-height:1}
svg.timeline{display:block;width:100%;height:auto;margin:8px 0 4px;background:var(--surface-2);border:1px solid var(--line);border-radius:10px}svg{max-width:100%;height:auto}
.experiment-heading{border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:12px}.experiment-heading h3{font-size:18px;margin:0}.audit-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.audit-item{padding:12px;background:var(--surface-2);border-radius:9px;min-width:0}.audit-item b{display:block;margin-top:3px;font-size:13px;overflow-wrap:anywhere}.recommendation{padding:12px 0;border-top:1px solid var(--line)}.recommendation:first-child{border-top:0}.recommendation h4{margin:0 0 5px}.recommendation p{font-size:12px;color:var(--muted)}
.agent-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.agent-panel{background:var(--surface-2);border:1px solid var(--line);border-radius:11px;padding:16px;min-width:0}.agent-panel h3{margin:0 0 8px}.provenance{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:99px;padding:3px 8px;display:inline-block}.reason-list{padding-left:18px}.round-label{display:inline-block;border-radius:6px;padding:3px 7px;background:var(--surface-2);color:var(--blue);font-size:11px;font-weight:700}
.empty-state{padding:18px;border:1px dashed var(--line);border-radius:10px;color:var(--muted)}details{margin:12px 0}summary{cursor:pointer;color:var(--blue);font-weight:700;padding:5px 0}details>div,details>p{margin-top:10px}ul{margin:7px 0 0;padding-left:20px}li{padding:4px 0}.section-head{display:flex;justify-content:space-between;align-items:end;gap:12px;flex-wrap:wrap;margin:30px 0 12px}.section-head h2{margin:0}.section-note{font-size:12px;color:var(--muted)}
@media(max-width:1100px){.kpi-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.findings-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.audit-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:740px){main{padding:24px 16px 48px}.hero{grid-template-columns:1fr}.phase-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.grid-two{grid-template-columns:1fr}.flow-arrow{padding:0 5px}}
@media(max-width:520px){main{padding:18px 12px 40px}.kpi-grid,.findings-grid,.phase-grid,.insight-grid,.grid-three,.audit-grid{grid-template-columns:1fr 1fr}.big{font-size:56px}.card,.panel{padding:15px}.flow{gap:7px}.flow-arrow{display:none}.flow-step{font-size:10px}.comparison-row{grid-template-columns:100px 1fr 35px}.phase-card{padding:11px}.metric{font-size:13px}}
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
    max_latency = max((r["latency"] for r in records if r["success"]), default=0)
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
            cx = x(record["time"])
            if record["success"]:
                cy = y(record["latency"])
                pieces.append(
                    f"<circle cx='{cx:.2f}' cy='{cy:.2f}' r='2.4' "
                    f"fill='{phase_colors[phase]}' opacity='.9'/>"
                )
            else:
                cy = bottom + 7
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
        successful = _number(data.get("successful_requests"))
        all_failed = has_samples and (
            successful == 0 or _number(data.get("error_rate")) == 1.0
        )
        p50 = _fmt_ms(data.get("p50_ms")) if has_samples and not all_failed else "N/A"
        p95 = _fmt_ms(data.get("p95_ms")) if has_samples and not all_failed else "N/A"
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
    max_latency = max(
        (record["latency"] for record in records if record["success"]),
        default=None,
    )
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





SEVERITY_COLOR = {"critical": "var(--red)", "high": "var(--red)", "medium": "var(--amber)",
                  "low": "var(--blue)", "none": "var(--green)"}


def agents_line(results):
    """One line saying which agents ran and whether each used the LLM."""
    agents = results.get("agents")
    if not agents:
        return ""
    order = ("observer", "planner", "injector", "analyst", "reporter")
    text = " &middot; ".join(f"{name}: {html.escape(str(agents[name]))}" for name in order if name in agents)
    orch = results.get("orchestrator")
    orch = f" &middot; orchestrated by: {html.escape(str(orch))}" if orch else ""
    return f"<div class='muted'>Agents &mdash; {text}{orch}</div>"


def score_bars(experiments):
    """Horizontal bar per experiment score (0-100), labelled with service, fault and value."""
    if not experiments:
        return ""
    rows = []
    for x in sorted(experiments, key=lambda x: x.get("score", 0)):
        score = float(x.get("score", 0) or 0)
        label = html.escape(f"{x.get('service')} · {x.get('action')}")
        rows.append(
            "<div style='display:grid;grid-template-columns:minmax(150px,34%) 1fr 52px;gap:10px;"
            "align-items:center;margin:7px 0'>"
            f"<div style='font-size:13px;overflow-wrap:anywhere'>{label}</div>"
            "<div style='background:var(--line);border-radius:6px;height:14px' role='img' "
            f"aria-label='{label}: score {score:.1f} out of 100'>"
            f"<div style='width:{max(1.0, min(100.0, score)):.1f}%;height:14px;border-radius:6px;"
            f"background:{_color(score)}'></div></div>"
            f"<div style='text-align:right;font-variant-numeric:tabular-nums'><b>{score:.1f}</b></div></div>"
        )
    return ("<h2>Score per experiment</h2><div class='card'>" + "".join(rows)
            + "<div class='muted' style='font-size:12px;margin-top:6px'>Scale 0 to 100. Higher is more resilient.</div></div>")


def severity_section(results):
    """Weaknesses ranked by severity, from the reporter agent."""
    rep = results.get("ai_report")
    if not rep:
        return ""
    who = "Gemini reporter agent" if rep.get("source") == "llm" else "Reporter agent (rule-based)"
    out = [f"<h2>Weaknesses ranked by severity</h2><div class='muted'>Ranked by: {who}</div>"]
    ranked = rep.get("ranked_weaknesses") or []
    if ranked:
        out.append("<div class='scroll'><table><tr><th>#</th><th>Severity</th><th>Service</th><th>Fault</th>"
                   "<th>Score</th><th>Why</th></tr>")
        for i, w in enumerate(ranked, 1):
            sev = str(w.get("severity") or "low")
            out.append(
                f"<tr><td>{i}</td>"
                f"<td><b style='color:{SEVERITY_COLOR.get(sev, 'var(--muted)')}'>{html.escape(sev)}</b></td>"
                f"<td>{html.escape(str(w.get('service')))}</td><td>{html.escape(str(w.get('action')))}</td>"
                f"<td>{html.escape(str(w.get('score')))}</td><td>{html.escape(str(w.get('why', '')))}</td></tr>"
            )
        out.append("</table></div>")
    else:
        out.append("<p style='color:var(--green)'>No weaknesses found in this session.</p>")
    if rep.get("score_explanation"):
        out.append(f"<p class='muted'><b>About the score:</b> {html.escape(str(rep['score_explanation']))}</p>")
    return "".join(out)


def round_context(x):
    """What the observer saw and how the planner ranked the candidates for this experiment."""
    out = []
    obs = x.get("observation")
    if obs:
        who = "Gemini observer agent" if obs.get("source") == "llm" else "Observer agent"
        state = "healthy" if obs.get("healthy") else "not healthy"
        out.append(f"<p class='muted' style='margin:4px 0'><b>{who}:</b> app {state} before the experiment. "
                   f"{html.escape(str(obs.get('summary', '')))}</p>")
    ranked = x.get("ranked_candidates") or []
    if ranked:
        rows = "".join(
            f"<tr><td>{r.get('rank')}</td><td>{html.escape(str(r.get('service')))}</td>"
            f"<td>{html.escape(str(r.get('action')))}</td>"
            f"<td>{'<b>chosen</b>' if r.get('chosen') else ('already tested' if r.get('already_tested') else '')}</td>"
            f"<td>{html.escape(str(r.get('rationale', '')))}</td></tr>"
            for r in ranked)
        out.append("<details style='margin:6px 0'><summary>Planner's ranked candidates for this round "
                   f"({len(ranked)})</summary><div class='scroll'><table><tr><th>Rank</th><th>Service</th>"
                   f"<th>Fault</th><th></th><th>Reason</th></tr>{rows}</table></div></details>")
    return "".join(out)


def _score_value(experiment):
    score = _number(experiment.get("score"))
    return score if score is not None else 0.0


def _ordered_experiments(experiments):
    return sorted(experiments, key=_score_value)


def _kpi(label, value, detail):
    return (
        f"<div class='kpi'><div class='kpi-label'>{html.escape(str(label))}</div>"
        f"<div class='kpi-value'>{html.escape(str(value))}</div>"
        f"<div class='kpi-detail'>{html.escape(str(detail))}</div></div>"
    )


def _summary_copy(results, experiments):
    if results.get("summary"):
        return (
            "<b>Recorded run summary</b>"
            f"<p>{html.escape(str(results['summary']))}</p>"
            + (
                f"<div class='evidence-note'>Recorded model: "
                f"{html.escape(str(results['summary_model']))}.</div>"
                if results.get("summary_model") else ""
            )
        )

    if not experiments:
        text = "This run contains no experiments to summarize."
    else:
        weakest = _ordered_experiments(experiments)[0]
        service = html.escape(str(weakest.get("service", "Unknown service")))
        action = html.escape(str(weakest.get("action", "fault")).replace("-", " "))
        score = _score_value(weakest)
        impact = _observed_impact(weakest, results.get("baseline") or {})
        text = (
            f"{len(experiments)} experiment(s) were recorded. The lowest-scoring result was "
            f"{service} under {action} ({score:.1f}/100)."
        )
        if impact["all_failed"]:
            text += " All measured requests failed during that fault observation."
        elif impact["error_increase_points"] is not None:
            text += (
                f" Its observed error rate changed by "
                f"{impact['error_increase_points']:+.1f} percentage points."
            )
        else:
            text += " Comparable successful-request measurements were not available."
        verified = sum(
            1 for experiment in experiments
            if (experiment.get("impact") or {}).get(
                "recovery_verified", experiment.get("recovered")
            ) is True
        )
        text += f" Recovery was recorded as verified for {verified} of {len(experiments)} experiment(s)."
    return (
        "<b>Evidence-based summary</b>"
        f"<p>{text}</p>"
        "<div class='evidence-note'>Generated from saved measurements and experiment fields; "
        "no analyst or reporter summary was saved for this run.</div>"
    )


def _finding_cards(experiments, baseline):
    if not experiments:
        return "<div class='empty-state'>No experiment findings were recorded.</div>"
    cards = []
    for experiment in _ordered_experiments(experiments)[:3]:
        score = _score_value(experiment)
        severity = experiment.get("ai_severity") or experiment.get("severity")
        severity_text = (
            f"{html.escape(str(severity)).upper()} severity"
            if severity else "Score-ranked"
        )
        color = (
            severity_color(str(severity).lower())
            if severity else "blue"
        )
        impact = _observed_impact(experiment, baseline)
        service = html.escape(str(experiment.get("service", "Unknown service")))
        action = html.escape(str(experiment.get("action", "Unknown fault")).replace("-", " "))
        metrics = []
        if impact["all_failed"]:
            metrics.append(("Requests failed", "100%"))
        elif impact["error_increase_points"] is not None:
            metrics.append(("Error-rate change", f"{impact['error_increase_points']:+.1f} pp"))
        if impact["latency_increase_pct"] is not None:
            metrics.append(("p95 change · successful probes", _fmt_pct(impact["latency_increase_pct"])))
        metrics.append(("Recovery", (
            f"{_number(experiment.get('recovery_s')):.1f} s"
            if _number(experiment.get("recovery_s")) is not None else "Not recorded"
        )))
        abort = (
            f"<p class='finding-note'><b>Guard action:</b> fault stopped — "
            f"{html.escape(str(experiment.get('abort_reason') or 'reason not recorded'))}.</p>"
            if experiment.get("aborted") else ""
        )
        details = (
            html.escape(str(experiment.get("ai_diagnosis")))
            if experiment.get("ai_diagnosis")
            else "Measured endpoint effect only; the saved run does not include a service-level diagnosis."
        )
        cards.append(
            f"<article class='finding-card' style='--severity:var(--{color})'>"
            f"<div class='finding-top'><span class='severity'>{severity_text}</span>"
            f"<span class='finding-score' style='color:var(--{color})'>{score:.1f}</span></div>"
            f"<h3>{service}</h3><div class='muted'>{action}</div>"
            "<div class='finding-metrics'>"
            + "".join(
                f"<div class='finding-metric'><span class='metric-label'>{html.escape(label)}</span>"
                f"<b>{html.escape(value)}</b></div>" for label, value in metrics
            )
            + f"</div><p class='finding-note'>{details}</p>{abort}"
            "<p class='finding-note'>p95 reflects successful probes only; failed requests are reported separately.</p>"
            "<p class='finding-note'>Dependency relationships indicate potential blast radius only; "
            "they do not prove dependent services failed.</p></article>"
        )
    return "<div class='findings-grid'>" + "".join(cards) + "</div>"


def severity_color(severity):
    return {"critical": "red", "high": "red", "medium": "amber", "low": "blue"}.get(severity, "blue")


def _recommendation_section(experiments):
    recommendations = []
    seen = set()
    for experiment in _ordered_experiments(experiments):
        for recommendation in experiment.get("recommendations") or []:
            title = str(recommendation.get("title") or "Recommendation")
            if title == "Safety limit stopped this experiment":
                continue
            key = (str(experiment.get("service")), title)
            if key in seen:
                continue
            seen.add(key)
            recommendations.append((experiment, recommendation))
    if not recommendations:
        return "<div class='empty-state'>No remediation recommendations were saved for this run.</div>"
    rows = []
    for rank, (experiment, recommendation) in enumerate(recommendations, 1):
        service = html.escape(str(experiment.get("service", "Unknown service")))
        title = html.escape(str(recommendation.get("title", "Recommendation")))
        detail = html.escape(str(recommendation.get("detail", "Details not recorded.")))
        source = recommendation.get("source") or experiment.get("analyst") or "rule-based"
        auto_fix = recommendation.get("auto_fix")
        applicability = (
            "Auto-fix candidate; not applied by this report."
            if auto_fix else "Manual engineering action; implementation not recorded."
        )
        rows.append(
            f"<div class='recommendation'><div class='row'><h4><span class='rank'>#{rank}</span> "
            f"{title}</h4><span class='pill'>{html.escape(str(source))}</span></div>"
            f"<p><b>{service}</b> · associated experiment score {_score_value(experiment):.1f}/100. "
            f"{detail}</p><p>{applicability}</p></div>"
        )
    return (
        "<div class='panel'>" + "".join(rows)
        + "<p class='muted'>Provisional order follows the associated experiment resilience score "
        "(lowest first). Cost, effort, confidence, and verified impact were not saved, so this is "
        "not a quantified remediation-priority model.</p></div>"
    )


def _fix_verification(experiments, previous):
    if not previous:
        return (
            "<div class='empty-state'><b>Verification pending.</b> No comparable previous run "
            "was provided. This report has no record that a recommended fix was applied, so it "
            "cannot verify remediation or claim a fix caused an outcome.</div>"
        )
    previous_experiments = {
        (item.get("service"), item.get("action")): item
        for item in previous.get("experiments") or []
    }
    rows = []
    comparable = 0
    for experiment in _ordered_experiments(experiments):
        prior = previous_experiments.get((experiment.get("service"), experiment.get("action")))
        if prior is None:
            continue
        comparable += 1
        current_score, prior_score = _score_value(experiment), _score_value(prior)
        delta = current_score - prior_score
        rows.append(
            f"<tr><td>{html.escape(str(experiment.get('service')))}</td>"
            f"<td>{html.escape(str(experiment.get('action')))}</td>"
            f"<td>{prior_score:.1f}</td><td>{current_score:.1f}</td>"
            f"<td class='{'status-ok' if delta > 0 else 'status-failed' if delta < 0 else 'muted'}'>"
            f"{delta:+.1f}</td></tr>"
        )
    if not comparable:
        return (
            "<div class='empty-state'>Verification pending. A previous run was provided, but "
            "there are no matching service-and-fault measurements to compare. No applied-fix "
            "record is available.</div>"
        )
    return (
        "<div class='panel'><div class='scroll'><table><thead><tr><th>Service</th><th>Fault</th>"
        "<th>Previous score</th><th>Current score</th><th>Change</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div><p class='muted'>These are comparable run scores, not proof that "
        "a remediation was applied or caused the difference. Fix verification requires an explicit "
        "change record and a controlled rerun.</p></div>"
    )


def _dependency_section(experiments, graph):
    nodes = {
        node.get("name"): node
        for node in (graph or {}).get("nodes") or []
        if isinstance(node, dict) and node.get("name")
    }
    if not experiments:
        return "<div class='empty-state'>No experiment targets to map.</div>"
    rows = []
    for experiment in _ordered_experiments(experiments):
        name = experiment.get("service")
        node = nodes.get(name) or {}
        callers = node.get("depended_by") or []
        callers_text = ", ".join(map(str, callers)) if callers else "None listed in the saved graph"
        transitive = node.get("transitive_dependents")
        rows.append(
            f"<tr><td><b>{html.escape(str(name or 'Unknown'))}</b></td>"
            f"<td>{html.escape(str(experiment.get('action', 'Unknown')))}</td>"
            f"<td>{html.escape(callers_text)}</td>"
            f"<td>{html.escape(str(transitive if transitive is not None else 'Not recorded'))}</td>"
            f"<td>{html.escape(str(node.get('replicas', 'Not recorded')))}</td></tr>"
        )
    return (
        "<div class='panel'><div class='scroll'><table><thead><tr><th>Fault target</th>"
        "<th>Fault</th><th>Direct dependents (potential callers)</th>"
        "<th>Transitive dependents</th><th>Replicas</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div><p class='muted'>The dependency mapper describes topology, not "
        "observed caller failures. This saved run does not contain route-level or per-caller "
        "measurements; business-journey impact is therefore not established.</p></div>"
    )


def _safety_section(results, experiments):
    limits = results.get("limits") or {}
    limit_items = [
        ("Maximum error-rate threshold", _fmt_rate(limits.get("max_error_rate"))),
        ("p95 threshold", _fmt_ms(limits.get("p95_limit_ms"))),
        ("Extra unhealthy-pod limit", limits.get("max_extra_unhealthy_pods", "Not recorded")),
    ]
    rows = []
    for experiment in experiments:
        abort_latency = _number(experiment.get("abort_latency_s"))
        abort_latency_text = f"{abort_latency:.2f} s" if abort_latency is not None else "Not recorded"
        rows.append(
            f"<tr><td>{html.escape(str(experiment.get('service', 'Unknown')))}</td>"
            f"<td>{html.escape(str(experiment.get('action', 'Unknown')))}</td>"
            f"<td>{'Triggered' if experiment.get('aborted') else 'Not triggered'}</td>"
            f"<td>{abort_latency_text}</td>"
            f"<td>{'Confirmed by runner' if experiment.get('cleanup_confirmed') is True else ('Not confirmed' if experiment.get('cleanup_confirmed') is False else 'Not recorded')}</td>"
            f"<td>{'Yes' if experiment.get('recovered') else 'No / not recorded'}</td></tr>"
        )
    return (
        "<div class='panel'><div class='audit-grid'>"
        + "".join(
            f"<div class='audit-item'><span class='metric-label'>{html.escape(str(label))}</span>"
            f"<b>{html.escape(str(value))}</b></div>" for label, value in limit_items
        )
        + "<div class='audit-item'><span class='metric-label'>Experiment environment</span>"
        f"<b>{html.escape(str(results.get('env', 'Not recorded')))}</b></div>"
        "<div class='audit-item'><span class='metric-label'>Policy evidence</span>"
        "<b>Rendered fault manifests and full allowlist were not saved in this result.</b></div>"
        "</div><div class='scroll' style='margin-top:15px'><table><thead><tr>"
        "<th>Target</th><th>Fault</th><th>Guard stop</th><th>Abort latency</th>"
        "<th>Cleanup signal</th><th>Recovery</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div><p class='muted'>“Cleanup confirmed” is the runner's recorded "
        "cleanup signal, not a general guarantee that the cluster is safe. Verify live workloads "
        "and fault resources before another production experiment.</p></div>"
    )


def _technical_appendix(results, graph, experiments):
    baseline = results.get("baseline") or {}
    agents = results.get("agents") or {}
    agent_text = ", ".join(
        f"{html.escape(str(name))}: {html.escape(str(value))}"
        for name, value in sorted(agents.items())
    ) if agents else "Agent-by-agent execution details not recorded"
    score_formula = (
        "Score = 100 − error penalty (up to 40) − latency penalty (up to 25) "
        "− recovery penalty (up to 25) − safety-abort penalty (10)."
    )
    score_details = (
        "Error reaches its full penalty at 50%; latency at 10× baseline p95; recovery at 60 seconds "
        "or when recovery fails. These are the code-defined scoring factors; the saved result's "
        "per-experiment breakdown is shown below."
    )
    experiment_rows = []
    for experiment in _ordered_experiments(experiments):
        breakdown = experiment.get("breakdown") or {}
        experiment_rows.append(
            f"<tr><td>{html.escape(str(experiment.get('id', 'Not recorded')))}</td>"
            f"<td>{html.escape(str(experiment.get('service', 'Unknown')))}</td>"
            f"<td>{html.escape(str(experiment.get('action', 'Unknown')))}</td>"
            f"<td>{_score_value(experiment):.1f}</td>"
            f"<td>{html.escape(str(breakdown.get('errors', 'N/A')))} / "
            f"{html.escape(str(breakdown.get('latency', 'N/A')))} / "
            f"{html.escape(str(breakdown.get('recovery', 'N/A')))} / "
            f"{html.escape(str(breakdown.get('abort', 'N/A')))}</td></tr>"
        )
    return (
        "<details class='panel'><summary>Technical appendix — measurement and scoring details</summary>"
        "<div class='audit-grid'>"
        f"<div class='audit-item'><span class='metric-label'>Run ID</span><b>{html.escape(str(results.get('run_id', 'Not recorded')))}</b></div>"
        f"<div class='audit-item'><span class='metric-label'>Planner</span><b>{html.escape(str(results.get('planner', 'Not recorded')))}</b></div>"
        f"<div class='audit-item'><span class='metric-label'>Model identifier</span><b>{html.escape(str(results.get('llm_model') or results.get('summary_model') or 'Not recorded'))}</b></div>"
        f"<div class='audit-item'><span class='metric-label'>Baseline sample count</span><b>{html.escape(str(baseline.get('samples', 'Not recorded')))}</b></div>"
        f"<div class='audit-item'><span class='metric-label'>Graph nodes</span><b>{len((graph or {}).get('nodes') or [])}</b></div>"
        f"<div class='audit-item'><span class='metric-label'>Recorded agent roles</span><b>{agent_text}</b></div>"
        "</div>"
        f"<p><b>Score model:</b> {score_formula}</p><p class='muted'>{score_details}</p>"
        "<p class='muted'>Penalty order below is errors / latency / recovery / abort. Missing saved "
        "breakdown values are shown as N/A rather than inferred.</p>"
        "<div class='scroll'><table><thead><tr><th>Experiment</th><th>Service</th><th>Fault</th>"
        "<th>Score</th><th>Penalty breakdown</th></tr></thead><tbody>"
        + "".join(experiment_rows)
        + "</tbody></table></div>"
        "<p class='muted'>The four phase cards show p50, p95, error rate, and phase sample count "
        "when recorded. The latency timeline plots successful probes; failed probes are marked at "
        "the chart baseline and are not treated as latency values.</p></details>"
    )


def _source_label(source):
    value = str(source or "").strip().lower()
    if value in {"llm", "gemini"}:
        return "Gemini"
    if value in {"mixed", "mixed gemini + fallback"}:
        return "Mixed Gemini + rule-based fallback"
    if value:
        return "Rule-based" if "rule" in value or "fallback" in value else str(source)
    return "Not recorded"


def _report_provenance(results):
    execution = results.get("llm_execution") or {}
    agents = results.get("agents") or {}
    calls = results.get("agent_calls") or []
    agent_workflow = bool(results.get("rounds") or results.get("orchestrator") or agents)
    sources = [
        _source_label(value)
        for value in agents.values()
    ] if isinstance(agents, dict) else []
    if execution.get("overall_source"):
        source = _source_label(execution["overall_source"])
    elif any(value.startswith("Mixed") for value in sources):
        source = "Mixed Gemini + rule-based fallback"
    elif any(value == "Gemini" for value in sources) and any(value == "Rule-based" for value in sources):
        source = "Mixed Gemini + rule-based fallback"
    elif sources and all(value == "Gemini" for value in sources):
        source = "Gemini-powered"
    elif sources:
        source = "Rule-based"
    elif any(experiment.get("planner") == "llm" for experiment in results.get("experiments") or []):
        source = "Gemini planner recorded; other agent provenance not recorded"
    elif results.get("planner") == "llm":
        source = "Gemini planner recorded; not a five-agent Gemini run"
    elif agent_workflow:
        source = "Agent execution source not fully recorded"
    else:
        source = "Planner/run source not recorded"

    gemini_calls = sum(1 for call in calls if call.get("gemini_used"))
    fallback_calls = sum(1 for call in calls if call.get("fallback_used"))
    return {
        "source": source,
        "environment": (
            "Offline simulator" if str(results.get("env", "")).lower() in {"sim", "simulated"}
            else str(results.get("env", "Not recorded"))
        ),
        "model": (
            results.get("requested_model") or results.get("llm_model")
            or results.get("summary_model") or "Not recorded"
        ),
        "orchestrator": results.get("orchestrator") or "Not recorded",
        "rounds": execution.get("rounds", len(results.get("rounds") or []) if results.get("rounds") else None),
        "experiments": execution.get("completed_experiments", len(results.get("experiments") or [])),
        "gemini_calls": gemini_calls if calls else None,
        "fallback_calls": fallback_calls if calls else None,
        "fallback_reason": execution.get("fallback_reason") or results.get("llm_fallback_reason"),
    }


def _agent_execution_section(results):
    provenance = _report_provenance(results)
    agent_status = results.get("agents") or {}
    cards = []
    for agent in ("observer", "planner", "injector", "analyst", "reporter"):
        status = _source_label(agent_status.get(agent))
        cards.append(
            f"<div class='audit-item'><span class='metric-label'>{html.escape(agent.title())} Agent</span>"
            f"<b>{html.escape(status)}</b></div>"
        )
    optional_counts = (
        f"{provenance['gemini_calls']} successful Gemini call(s)"
        if provenance["gemini_calls"] is not None else "Not recorded"
    )
    fallback_count = (
        f"{provenance['fallback_calls']} fallback decision(s)"
        if provenance["fallback_calls"] is not None else "Not recorded"
    )
    model_line = html.escape(str(provenance["model"]))
    fallback = (
        f"<p class='status-warn'><b>Fallback reason:</b> "
        f"{html.escape(str(provenance['fallback_reason']))}</p>"
        if provenance["fallback_reason"] else ""
    )
    calls = results.get("agent_calls") or []
    call_table = ""
    if calls:
        call_rows = []
        for call in calls:
            call_rows.append(
                f"<tr><td>{html.escape(str(call.get('agent', 'Not recorded')).title())}</td>"
                f"<td>{html.escape(str(call.get('model') or 'Not recorded'))}</td>"
                f"<td>{'Yes' if call.get('gemini_used') else 'No'}</td>"
                f"<td>{'Yes' if call.get('fallback_used') else 'No'}</td>"
                f"<td>{html.escape(str(call.get('retry_count', 0)))}</td>"
                f"<td>{html.escape(str(call.get('duration_s', 'Not recorded')))} s</td>"
                f"<td>{html.escape(str(call.get('fallback_reason') or '—'))}</td></tr>"
            )
        call_table = (
            "<details><summary>Per-decision Gemini and fallback provenance</summary>"
            "<div class='scroll'><table><thead><tr><th>Agent</th><th>Model</th><th>Gemini used</th>"
            "<th>Fallback</th><th>Retries</th><th>Duration</th><th>Fallback reason</th></tr></thead><tbody>"
            + "".join(call_rows) + "</tbody></table></div></details>"
        )
    return (
        "<section><div class='section-head'><h2>Agent execution overview</h2>"
        "<span class='section-note'>Execution source and orchestration metadata from this run</span></div>"
        "<div class='panel'><div class='audit-grid'>"
        f"<div class='audit-item'><span class='metric-label'>Decision provenance</span><b>{html.escape(provenance['source'])}</b></div>"
        f"<div class='audit-item'><span class='metric-label'>Execution environment</span><b>{html.escape(provenance['environment'])}</b></div>"
        f"<div class='audit-item'><span class='metric-label'>Requested / recorded model</span><b>{model_line}</b></div>"
        f"<div class='audit-item'><span class='metric-label'>Orchestrator</span><b>{html.escape(str(provenance['orchestrator']))}</b></div>"
        f"<div class='audit-item'><span class='metric-label'>Rounds</span><b>{html.escape(str(provenance['rounds'] if provenance['rounds'] is not None else 'Not recorded'))}</b></div>"
        f"<div class='audit-item'><span class='metric-label'>Completed experiments</span><b>{html.escape(str(provenance['experiments']))}</b></div>"
        f"<div class='audit-item'><span class='metric-label'>Gemini calls</span><b>{html.escape(optional_counts)}</b></div>"
        f"<div class='audit-item'><span class='metric-label'>Fallbacks</span><b>{html.escape(fallback_count)}</b></div>"
        + "".join(cards)
        + f"</div>{fallback}"
        + call_table
        + "<p class='muted'>Environment and decision provenance are independent: a Kubernetes run can "
        "be rule-based, mixed, or Gemini-powered. A model name alone does not prove that Gemini "
        "generated every agent decision.</p></div></section>"
    )


def _cluster_observation_html(snapshot):
    if not isinstance(snapshot, dict):
        return "<p class='muted'>Cluster-level pod and warning observations were not recorded.</p>"
    groups = (
        ("Unhealthy pods", snapshot.get("unhealthy_pods") or []),
        ("Pods with restarts", snapshot.get("pods_with_restarts") or []),
        ("Warnings", snapshot.get("warning_events") or []),
    )
    content = []
    for label, entries in groups:
        if entries:
            content.append(f"<p><b>{html.escape(label)}:</b> "
                           f"{html.escape('; '.join(str(item) for item in entries))}</p>")
        else:
            content.append(f"<p><b>{html.escape(label)}:</b> None recorded in this snapshot.</p>")
    not_ready = snapshot.get("deployments_not_ready") or {}
    content.append(
        "<p><b>Deployments not ready:</b> "
        + (
            html.escape(", ".join(map(str, not_ready.keys())))
            if not_ready else "None recorded."
        )
        + "</p>"
    )
    return "".join(content)


def _observer_planner_sections(results):
    rounds = results.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        return (
            "<section><div class='section-head'><h2>Observer &amp; Planner Agent</h2></div>"
            "<div class='empty-state'>Round observations and candidate rankings were not saved in "
            "this result; they cannot be reconstructed from experiment scores alone.</div></section>"
        )
    cards = []
    for entry in rounds:
        round_number = entry.get("round", "Not recorded")
        observation = entry.get("observation") or {}
        observed_by = _source_label(observation.get("source"))
        concerns = observation.get("concerns") or []
        probes = observation.get("probes") or []
        probe_summary = (
            f"{sum(1 for probe in probes if probe.get('ok'))}/{len(probes)} probes succeeded"
            if probes else "Probe detail not recorded"
        )
        ranked = entry.get("ranked_candidates") or []
        if ranked:
            candidate_rows = []
            for candidate in ranked:
                candidate_rows.append(
                    f"<tr><td>{html.escape(str(candidate.get('rank', 'N/A')))}</td>"
                    f"<td>{html.escape(str(candidate.get('service', 'Unknown')))}</td>"
                    f"<td>{html.escape(str(candidate.get('action', 'Unknown')))}</td>"
                    f"<td>{'<b>Selected</b>' if candidate.get('chosen') else ''}</td>"
                    f"<td>{html.escape(str(candidate.get('rationale', 'Not recorded')))}</td></tr>"
                )
            ranked_html = (
                "<div class='scroll'><table><thead><tr><th>Rank</th><th>Service</th><th>Fault</th>"
                "<th>Decision</th><th>Rationale</th></tr></thead><tbody>"
                + "".join(candidate_rows) + "</tbody></table></div>"
            )
        else:
            ranked_html = "<p class='muted'>Ranked candidate list not recorded for this round.</p>"
        planner_source = _source_label((entry.get("planner_provenance") or {}).get("source"))
        planner_reason = (entry.get("planner_provenance") or {}).get("fallback_reason")
        observation_text = html.escape(str(observation.get("summary", "Observation not recorded.")))
        concern_text = html.escape(", ".join(map(str, concerns)) or "None recorded")
        cards.append(
            f"<article class='agent-panel'><div class='row'><h3>Round {html.escape(str(round_number))}</h3>"
            "<span class='provenance'>Observer: " + html.escape(observed_by) + "</span></div>"
            f"<p><b>Health:</b> {html.escape(str(observation.get('healthy', 'Not recorded')))} · "
            f"{html.escape(probe_summary)}</p><p><b>Summary:</b> {observation_text}</p>"
            f"<p><b>Unhealthy service concerns:</b> {concern_text}</p>"
            + _cluster_observation_html(observation.get("cluster"))
            + f"<p><b>Planner source:</b> {html.escape(planner_source)}</p>"
            + (f"<p class='status-warn'><b>Planner fallback:</b> {html.escape(str(planner_reason))}</p>"
               if planner_reason else "")
            + ranked_html
            + "</article>"
        )
    return (
        "<section><div class='section-head'><h2>Observer &amp; Planner Agent</h2>"
        "<span class='section-note'>Health evidence and ranked candidate choices by round</span></div>"
        "<div class='agent-grid'>" + "".join(cards) + "</div></section>"
    )


def _reporter_section(results):
    report_data = results.get("ai_report")
    if not isinstance(report_data, dict):
        fallback = results.get("weaknesses") or []
        rows = "".join(
            f"<tr><td>{index}</td><td>Not recorded</td>"
            f"<td>{html.escape(str(item.get('service', 'Unknown')))}</td>"
            f"<td>{html.escape(str(item.get('action', 'Unknown')))}</td>"
            f"<td>{html.escape(str(item.get('score', 'N/A')))}</td>"
            "<td>Reporter explanation not saved.</td></tr>"
            for index, item in enumerate(fallback, 1)
        )
        table = (
            "<div class='scroll'><table><thead><tr><th>Rank</th><th>Severity</th><th>Service</th>"
            "<th>Fault</th><th>Score</th><th>Reporter explanation</th></tr></thead><tbody>"
            + rows + "</tbody></table></div>"
            if rows else "<div class='empty-state'>Reporter Agent output and a fallback weakness list were not saved.</div>"
        )
        return (
            "<section><div class='section-head'><h2>Reporter Agent</h2></div>"
            "<div class='panel'><p class='muted'>Reporter summary and score explanation were not "
            "saved. The table below, if present, uses code-calculated weakness data and is not "
            "a Gemini Reporter output.</p>" + table + "</div></section>"
        )
    ranked = report_data.get("ranked_weaknesses") or []
    rows = []
    for index, item in enumerate(ranked, 1):
        rows.append(
            f"<tr><td>{index}</td><td>{html.escape(str(item.get('severity', 'Not recorded')))}</td>"
            f"<td>{html.escape(str(item.get('service', 'Unknown')))}</td>"
            f"<td>{html.escape(str(item.get('action', 'Unknown')))}</td>"
            f"<td>{html.escape(str(item.get('score', 'N/A')))}</td>"
            f"<td>{html.escape(str(item.get('why', 'Not recorded')))}</td></tr>"
        )
    source = _source_label(report_data.get("source"))
    overall = report_data.get("overall")
    score_explanation = report_data.get("score_explanation")
    return (
        "<section><div class='section-head'><h2>Reporter Agent</h2>"
        f"<span class='provenance'>{html.escape(source)}</span></div><div class='panel'>"
        "<h3>Overall investigation summary</h3>"
        + (
            f"<p>{html.escape(str(overall))}</p>"
            if overall else "<p class='muted'>No Reporter overall summary was saved.</p>"
        )
        + "<h3>Weaknesses Ranked by Severity</h3>"
        + (
            "<div class='scroll'><table><thead><tr><th>Rank</th><th>Severity</th><th>Service</th>"
            "<th>Fault type</th><th>Resilience score</th><th>Reporter explanation</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></div>"
            if rows else "<p class='muted'>No ranked weakness entries were saved.</p>"
        )
        + "<h3>Resilience score explanation</h3>"
        + (
            f"<p>{html.escape(str(score_explanation))}</p>"
            if score_explanation else "<p class='muted'>No Reporter score explanation was saved.</p>"
        )
        + "</div></section>"
    )


def _injector_decision_section(experiment, limits, round_decision=None):
    decision = experiment.get("injector_decision") or round_decision
    if not isinstance(decision, dict):
        decision = {}
    approval = decision.get("approved")
    decision_text = (
        "Approved" if approval is True else "Rejected" if approval is False else
        "Fault ran; preflight decision metadata not recorded"
    )
    source = _source_label(decision.get("source"))
    requested = decision.get("requested_duration_s", experiment.get("duration_s"))
    events = experiment.get("events") or {}
    injected = _number(events.get("fault_injected_at_s"))
    removed = _number(events.get("fault_removed_at_s"))
    actual = decision.get("actual_duration_s")
    if injected is not None and removed is not None:
        actual = max(0.0, removed - injected)
    actual_text = f"{_number(actual):.1f} s" if _number(actual) is not None else "Not recorded"
    reason = decision.get("reason") or experiment.get("injector_reason")
    rollback = experiment.get("agent_rollback")
    cleanup = (
        "Confirmed by runner" if experiment.get("cleanup_confirmed") is True else
        "Not confirmed" if experiment.get("cleanup_confirmed") is False else "Not recorded"
    )
    abort_reason = experiment.get("abort_reason")
    threshold_text = (
        f"error ≤ {_fmt_rate(limits.get('max_error_rate'))}; "
        f"p95 ≤ {_fmt_ms(limits.get('p95_limit_ms'))}; "
        f"extra unhealthy pods ≤ {html.escape(str(limits.get('max_extra_unhealthy_pods', 'N/A')))}"
    )
    fallback = decision.get("fallback_reason")
    return (
        "<div class='agent-panel'><h3>Injector Agent decision</h3>"
        f"<p><b>{html.escape(decision_text)}</b> · {html.escape(source)}</p>"
        f"<p><b>Reason:</b> {html.escape(str(reason or 'Decision reasoning not recorded.'))}</p>"
        f"<p><b>Requested duration:</b> {html.escape(str(requested if requested is not None else 'N/A'))} s · "
        f"<b>Actual fault duration:</b> {actual_text}</p>"
        f"<p><b>Safety thresholds:</b> {threshold_text}</p>"
        f"<p><b>Early rollback:</b> {html.escape(str(rollback or 'No early rollback recorded'))}</p>"
        f"<p><b>Automatic abort:</b> {html.escape(str(abort_reason or 'Not triggered'))}</p>"
        f"<p><b>Cleanup verification:</b> {html.escape(cleanup)}</p>"
        + (f"<p class='status-warn'><b>Fallback:</b> {html.escape(str(fallback))}</p>" if fallback else "")
        + "</div>"
    )


def _round_for_experiment(experiment, rounds):
    experiment_id = str(experiment.get("id", ""))
    for entry in rounds if isinstance(rounds, list) else []:
        ranked = entry.get("ranked_candidates") or []
        if any(
            candidate.get("chosen")
            and candidate.get("service") == experiment.get("service")
            and candidate.get("action") == experiment.get("action")
            for candidate in ranked
        ):
            return entry
        if experiment_id.startswith("exp") and str(entry.get("round")) == experiment_id[3:]:
            return entry
    return None


def render(results, graph, previous=None):
    e = html.escape
    experiments = results.get("experiments") or []
    baseline = results.get("baseline") or {}
    score = _number(results.get("resilience_score"))
    score_text = f"{score:.1f}" if score is not None else "N/A"
    run_id = str(results.get("run_id", "Unknown run"))
    env = str(results.get("env", "Not recorded"))
    planner_name = str(results.get("planner", "Not recorded"))
    weak_count = sum(1 for experiment in experiments if _score_value(experiment) < 90)
    abort_count = sum(1 for experiment in experiments if experiment.get("aborted"))
    recovered_count = sum(
        1 for experiment in experiments
        if (experiment.get("impact") or {}).get("recovery_verified", experiment.get("recovered")) is True
    )
    recommendation_count = sum(
        1
        for experiment in experiments
        for item in experiment.get("recommendations") or []
        if item.get("title") != "Safety limit stopped this experiment"
    )
    app_label = "Mapped microservice application"
    model = results.get("llm_model") or results.get("summary_model")
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>ChaosPilot AI — Resilience Intelligence Report — {e(run_id)}</title>"
        f"<style>{CSS}</style></head><body><main>",
        "<div class='eyebrow'>ChaosPilot AI · Cloud-native resilience intelligence</div>"
        "<h1>Resilience intelligence report</h1>"
        "<p class='subtitle'>A measured view of fault response, recovery, and follow-up actions.</p>"
        "<div class='meta-row'>"
        f"<span class='meta-chip'><b>Run</b> {e(run_id)}</span>"
        f"<span class='meta-chip'><b>Environment</b> {e(env)}</span>"
        f"<span class='meta-chip'><b>Planner</b> {e(planner_name)}</span>"
        f"<span class='meta-chip'><b>Scope</b> {e(app_label)}</span>"
        + (f"<span class='meta-chip'><b>Model recorded</b> {e(str(model))}</span>" if model else "")
        + "</div>",
    ]

    delta_html = ""
    previous_score = _number((previous or {}).get("resilience_score"))
    if score is not None and previous_score is not None:
        delta = score - previous_score
        delta_html = (
            f"<div class='delta' style='color:var(--{'good' if delta >= 0 else 'bad'})'>"
            f"{delta:+.1f} vs previous run — score comparison only</div>"
        )
    baseline_text = (
        f"Baseline: {_fmt_rate(baseline.get('error_rate'))} errors · "
        f"p50 {_fmt_ms(baseline.get('p50_ms'))} · p95 {_fmt_ms(baseline.get('p95_ms'))} · "
        f"{e(str(baseline.get('samples', 'N/A')))} probes"
    )
    parts.append(
        "<section class='hero' aria-label='Executive summary'>"
        f"<div class='score-block'><div class='big' style='color:{_color(score if score is not None else 0)}'>{score_text}</div>"
        f"<div><div class='score-caption'>Resilience score</div><div class='muted'>out of 100</div>{delta_html}</div></div>"
        f"<div><div class='section-kicker'>Run at a glance</div><p>{e(baseline_text)}</p>"
        "<p class='muted'>Higher scores indicate greater resilience in the tested scenarios. "
        "The aggregate score is not a production availability SLO.</p></div></section>"
    )
    parts.append(
        "<section class='kpi-grid' aria-label='Run key performance indicators'>"
        + _kpi("Experiments", len(experiments), "saved fault scenarios")
        + _kpi("Weak findings", weak_count, "score below 90")
        + _kpi("Safety stops", abort_count, "guard-triggered aborts")
        + _kpi("Recoveries", f"{recovered_count}/{len(experiments)}", "recorded as verified")
        + _kpi("Recommendations", recommendation_count, "saved follow-up actions")
        + _kpi("Baseline probes", baseline.get("samples", "N/A"), "before fault injection")
        + "</section>"
    )

    parts.append(f"<section class='panel summary'>{_summary_copy(results, experiments)}</section>")
    parts.append(
        "<div class='flow' aria-label='Experiment lifecycle'>"
        "<span class='flow-step'><span class='flow-num'>1</span>Baseline</span><span class='flow-arrow' aria-hidden='true'>→</span>"
        "<span class='flow-step'><span class='flow-num'>2</span>Inject fault</span><span class='flow-arrow' aria-hidden='true'>→</span>"
        "<span class='flow-step'><span class='flow-num'>3</span>Observe impact</span><span class='flow-arrow' aria-hidden='true'>→</span>"
        "<span class='flow-step'><span class='flow-num'>4</span>Recover &amp; verify</span></div>"
    )

    parts.append(
        "<section><div class='section-head'><h2>Top measured findings</h2>"
        "<span class='section-note'>Ranked by measured resilience score · recorded severity shown only when available</span></div>"
        + _finding_cards(experiments, baseline) + "</section>"
    )
    parts.append(_agent_execution_section(results))
    parts.append(_observer_planner_sections(results))
    parts.append(_reporter_section(results))

    parts.append(
        "<section><div class='section-head'><h2>Recommended next actions</h2>"
        "<span class='section-note'>Transparent provisional order; not a fix-impact score</span></div>"
        + _recommendation_section(experiments) + "</section>"
    )
    parts.append(
        "<section><div class='section-head'><h2>Fix verification</h2>"
        "<span class='section-note'>A score comparison alone does not establish causality</span></div>"
        + _fix_verification(experiments, previous) + "</section>"
    )
    parts.append(
        "<section><div class='section-head'><h2>Dependency &amp; blast-radius context</h2>"
        "<span class='section-note'>Topology is potential impact, not observed failure</span></div>"
        + _dependency_section(experiments, graph) + "</section>"
    )
    parts.append(
        "<section><div class='section-head'><h2>Safety audit</h2>"
        "<span class='section-note'>Recorded thresholds, stop behavior, and cleanup signals</span></div>"
        + _safety_section(results, experiments) + "</section>"
    )

    parts.append("<section><div class='section-head'><h2>Experiment details</h2>"
                 "<span class='section-note'>Four measured phases, probe timeline, and recovery</span></div>")
    for experiment in experiments:
        round_entry = _round_for_experiment(experiment, results.get("rounds"))
        service = e(str(experiment.get("service", "Unknown service")))
        action_raw = str(experiment.get("action", "Unknown fault"))
        action = e(action_raw.replace("-", " ").title())
        score_value = _score_value(experiment)
        planner_source = experiment.get("planner", planner_name)
        rationale_label = "Recorded planner rationale" if planner_source else "Experiment rationale"
        abort = (
            f"<span class='pill abort'>Safety guard stopped the fault: "
            f"{e(str(experiment.get('abort_reason') or 'reason unavailable'))}</span>"
            if experiment.get("aborted") else ""
        )
        parts.append(
            "<article class='card'><div class='experiment-heading row'>"
            f"<div><h3>{action} · {service}</h3>"
            f"<span class='muted'>Experiment {e(str(experiment.get('id', 'not recorded')))} · "
            f"requested duration {e(str(experiment.get('duration_s', 'N/A')))} s</span></div>"
            f"<div class='row'>{abort}<span class='pill'>Score {score_value:.1f}/100</span></div></div>"
            f"{round_context(experiment)}"
            f"<p class='muted'><b>{rationale_label}:</b> "
            f"{e(str(experiment.get('rationale', 'Not recorded.')))}</p>"
            + _injector_decision_section(
                experiment, results.get("limits") or {},
                (round_entry or {}).get("injector_decision"),
            )
            + (
                f"<p><b>Recorded analyst diagnosis:</b> "
                f"{e(str(experiment.get('ai_diagnosis')))}"
                + (f" <span class='pill'>{e(str(experiment.get('ai_severity')))} severity</span>"
                   if experiment.get("ai_severity") else "")
                + "</p>"
                if experiment.get("ai_diagnosis") else ""
            )
            + (
                "<div class='agent-panel'><h3>Analyst Agent evidence &amp; hypotheses</h3>"
                + (
                    "<p><b>Root-cause hypotheses:</b></p><ul class='reason-list'>"
                    + "".join(f"<li>{e(str(item))}</li>" for item in experiment["root_cause_hypotheses"])
                    + "</ul>"
                    if experiment.get("root_cause_hypotheses") else
                    "<p class='muted'>No root-cause hypotheses were recorded.</p>"
                )
                + (
                    "<p><b>Evidence:</b></p><ul class='reason-list'>"
                    + "".join(f"<li>{e(str(item))}</li>" for item in experiment["analyst_evidence"])
                    + "</ul>"
                    if experiment.get("analyst_evidence") else
                    "<p class='muted'>No separate analyst evidence list was recorded; use the measured phase data below.</p>"
                )
                + f"<p><b>Analyst source:</b> {e(str((experiment.get('agent_provenance') or {}).get('analyst', {}).get('source', experiment.get('analyst', 'Not recorded'))))}</p>"
                "</div>"
            )
            + timeline_svg(
                experiment.get("samples"), events=experiment.get("events"),
                phase_samples=experiment.get("phase_samples")
            )
            + "<div class='chart-legend' aria-label='Timeline legend'>"
            "<span class='legend-item'><span class='swatch' style='--swatch:var(--blue)'></span>Before</span>"
            "<span class='legend-item'><span class='swatch' style='--swatch:var(--red)'></span>During fault</span>"
            "<span class='legend-item'><span class='swatch' style='--swatch:var(--amber)'></span>Recovery</span>"
            "<span class='legend-item'><span class='swatch' style='--swatch:var(--green)'></span>After</span>"
            "<span class='legend-item'><span class='legend-marker' style='--marker:var(--red)'>×</span>Failed probe</span>"
            "<span class='legend-item'><span class='legend-marker' style='--marker:var(--muted)'>┆</span>Fault boundary</span>"
            "</div>"
            "<div class='section-head'><h3>Four-phase measurements</h3>"
            "<span class='section-note'>Latency percentiles use successful requests only</span></div>"
            + phase_comparison(
                experiment.get("phase_metrics"), experiment.get("phase_samples"),
                experiment.get("recovery_s")
            )
            + "<div class='insight-grid'>"
            + impact_section(experiment, baseline)
            + recovery_section(experiment)
            + "</div><h3>Measured conclusion</h3>"
            + experiment_conclusion(experiment, baseline)
            + "<details><summary>Experiment actions and score breakdown</summary>"
            f"<p class='muted'>Recorded score penalties (errors / latency / recovery / abort): "
            f"{e(str((experiment.get('breakdown') or {}).get('errors', 'N/A')))} / "
            f"{e(str((experiment.get('breakdown') or {}).get('latency', 'N/A')))} / "
            f"{e(str((experiment.get('breakdown') or {}).get('recovery', 'N/A')))} / "
            f"{e(str((experiment.get('breakdown') or {}).get('abort', 'N/A')))}.</p>"
            + (
                f"<p>Guard abort latency: {_number(experiment.get('abort_latency_s')):.2f} s.</p>"
                if _number(experiment.get("abort_latency_s")) is not None else ""
            )
            + (
                "<h4>Recorded recommendations for this experiment</h4>"
                + "".join(
                    f"<div class='recommendation'><b>{e(str(item.get('title', 'Recommendation')))}</b>"
                    f"<p>{e(str(item.get('detail', '')))}</p></div>"
                    for item in experiment.get("recommendations") or []
                    if item.get("title") != "Safety limit stopped this experiment"
                )
                if any(
                    item.get("title") != "Safety limit stopped this experiment"
                    for item in experiment.get("recommendations") or []
                ) else
                "<p class='muted'>No recommendations were saved for this experiment.</p>"
            )
            + "</details></article>"
        )
    parts.append("</section>")
    parts.append(_technical_appendix(results, graph, experiments))
    parts.append(
        "<footer class='muted' style='margin-top:28px;border-top:1px solid var(--line);padding-top:14px'>"
        "ChaosPilot AI · Self-contained report · No external fonts, scripts, or network assets</footer>"
        "</main></body></html>"
    )
    return "".join(parts)