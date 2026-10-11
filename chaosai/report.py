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
.chart-panel h3{margin:0 0 12px}.bar-row{display:grid;grid-template-columns:minmax(130px,36%) 1fr 54px;gap:10px;align-items:center;margin:9px 0;font-size:12.5px}.bar-label{overflow-wrap:anywhere}.bar-track{height:16px;background:var(--line);border-radius:5px;overflow:hidden}.bar-track.stacked{display:flex;gap:2px;background:var(--surface-2)}.bar-fill{height:100%;border-radius:5px}.bar-seg{height:100%;border-radius:3px;font-size:10px;line-height:16px;text-align:center;color:var(--bg);font-weight:800;overflow:hidden}.bar-value{text-align:right;font-weight:750;font-variant-numeric:tabular-nums}
.rank-row{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.rank-chip{border:1px solid var(--line);border-radius:7px;padding:4px 9px;font-size:12px;background:var(--surface);color:var(--muted)}.rank-chip.chosen{border-color:var(--blue);color:var(--ink);font-weight:700}code{font-size:12px;background:var(--surface-2);border:1px solid var(--line);border-radius:5px;padding:1px 5px}
.sev-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:2px 0 6px}.sev-chip{border:1px solid var(--line);border-left:4px solid var(--severity);border-radius:7px;padding:5px 11px;background:var(--surface);font-size:12px;text-transform:capitalize}.sev-chip b{font-size:15px;margin-right:3px}
svg.depmap{display:block;width:100%;height:auto;margin:0 0 6px}
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


def _latency_phrase(change_pct):
    """Say the p95 change the right way round; a negative change is not an 'increase'."""
    if change_pct >= 0:
        return f"raised p95 latency by {change_pct:.1f}%"
    return (f"left p95 latency of the successful requests {abs(change_pct):.1f}% lower "
            "(failed requests have no latency and are counted as errors)")


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
            + _latency_phrase(impact["latency_increase_pct"])
            + " compared with the phase before the fault."
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
        change = impact["latency_increase_pct"]
        sentence = (
            f"{service}: p95 latency of successful requests was {abs(change):.1f}% "
            f"{'higher' if change >= 0 else 'lower'} during {action}."
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


PENALTY_PARTS = (
    ("errors", "Errors", "var(--red)"),
    ("latency", "Latency", "var(--amber)"),
    ("recovery", "Recovery", "var(--purple)"),
    ("abort", "Safety abort", "var(--teal)"),
)
SEVERITY_ORDER = ("critical", "high", "medium", "low", "none")


def _experiment_label(experiment):
    return f"{experiment.get('service', 'Unknown')} · {experiment.get('action', 'fault')}"


def _severity_of(experiment):
    value = experiment.get("ai_severity") or experiment.get("severity")
    return str(value).lower() if value else None


def _fully_recovered(experiment):
    """Recovered AND back to the pre-fault baseline (when that was measured)."""
    impact = experiment.get("impact") or {}
    if impact.get("recovery_verified", experiment.get("recovered")) is not True:
        return False
    return impact.get("recovered_to_baseline") is not False


def _first_sentence(text, limit=240):
    text = " ".join(str(text).split())
    cut = text.find(". ")
    short = text if cut < 0 else text[:cut + 1]
    return short if len(short) <= limit else short[:limit - 1].rstrip() + "…"


def score_bars(experiments):
    """One horizontal bar per experiment: resilience score 0-100, weakest first."""
    rows = []
    for x in _ordered_experiments(experiments):
        score = _score_value(x)
        label = html.escape(_experiment_label(x))
        rows.append(
            f"<div class='bar-row'><div class='bar-label'>{label}</div>"
            f"<div class='bar-track' role='img' aria-label='{label}: score {score:.1f} out of 100'>"
            f"<div class='bar-fill' style='width:{max(1.0, min(100.0, score)):.1f}%;background:{_color(score)}'></div></div>"
            f"<div class='bar-value'>{score:.1f}</div></div>"
        )
    return "".join(rows)


def penalty_bars(experiments):
    """Stacked bar per experiment: how many of the 100 points each cause took away."""
    rows = []
    for x in _ordered_experiments(experiments):
        breakdown = x.get("breakdown") or {}
        label = html.escape(_experiment_label(x))
        segments, lost, spoken = [], 0.0, []
        for key, name, color in PENALTY_PARTS:
            value = _number(breakdown.get(key)) or 0.0
            if value <= 0:
                continue
            lost += value
            spoken.append(f"{name} {value:.1f}")
            inside = f"{value:.0f}" if value >= 6 else ""
            segments.append(
                f"<div class='bar-seg' style='width:{min(100.0, value):.1f}%;background:{color}' "
                f"title='{name}: -{value:.1f}'>{inside}</div>"
            )
        aria = f"{label}: {', '.join(spoken) if spoken else 'no points lost'}"
        rows.append(
            f"<div class='bar-row'><div class='bar-label'>{label}</div>"
            f"<div class='bar-track stacked' role='img' aria-label='{aria}'>{''.join(segments)}</div>"
            f"<div class='bar-value'>{'-' + format(lost, '.1f') if lost else '0'}</div></div>"
        )
    legend = "".join(
        f"<span class='legend-item'><span class='swatch' style='--swatch:{color}'></span>{name}</span>"
        for _, name, color in PENALTY_PARTS
    )
    return "".join(rows) + f"<div class='chart-legend' style='margin-bottom:0'>{legend}</div>"


def severity_strip(experiments):
    """How many findings fall in each severity band (only when the analyst recorded severities)."""
    counts = {}
    for x in experiments:
        severity = _severity_of(x)
        if severity:
            counts[severity] = counts.get(severity, 0) + 1
    if not counts:
        return ""
    chips = "".join(
        f"<span class='sev-chip' style='--severity:{SEVERITY_COLOR.get(name, 'var(--muted)')}'>"
        f"<b>{counts[name]}</b> {html.escape(name)}</span>"
        for name in SEVERITY_ORDER if name in counts
    )
    return f"<div class='sev-row'><span class='metric-label'>Findings by severity</span>{chips}</div>"


def _overview_charts(experiments):
    if not experiments:
        return ""
    return (
        "<section><div class='section-head'><h2>Results at a glance</h2>"
        "<span class='section-note'>Weakest experiment first</span></div>"
        "<div class='grid-two'>"
        "<div class='panel chart-panel'><h3>Resilience score per experiment</h3>"
        + score_bars(experiments)
        + "<p class='section-note'>Scale 0 to 100. Higher is more resilient.</p></div>"
        "<div class='panel chart-panel'><h3>Points lost, by cause</h3>"
        + penalty_bars(experiments)
        + "</div></div>" + severity_strip(experiments) + "</section>"
    )


def _graph_layers(nodes):
    """Column for each service: 0 for services nobody calls, then one step per dependency hop."""
    depth = {}

    def visit(name, trail=()):
        if name in depth:
            return depth[name]
        callers = [c for c in (nodes[name].get("depended_by") or []) if c in nodes and c not in trail]
        depth[name] = 1 + max((visit(c, trail + (name,)) for c in callers), default=-1)
        return depth[name]

    for name in nodes:
        visit(name)
    return depth


def dependency_graph_svg(graph, experiments):
    """The dependency map as a left-to-right diagram, with the tested services highlighted."""
    nodes = {
        n.get("name"): n for n in (graph or {}).get("nodes") or []
        if isinstance(n, dict) and n.get("name")
    }
    if not nodes:
        return ""
    tested = {}
    for x in experiments:
        name = x.get("service")
        if name in nodes and (name not in tested or _score_value(x) < _score_value(tested[name])):
            tested[name] = x
    depth = _graph_layers(nodes)
    columns = {}
    for name in sorted(nodes):
        columns.setdefault(depth[name], []).append(name)
    box_w, box_h, gap_y, pad = 176, 38, 14, 16
    width = 980
    tallest = max(len(names) for names in columns.values())
    height = pad * 2 + tallest * box_h + (tallest - 1) * gap_y
    span = max(1, max(columns))
    position = {}
    for column, names in columns.items():
        x = pad + column * (width - 2 * pad - box_w) / span
        block = len(names) * box_h + (len(names) - 1) * gap_y
        top = (height - block) / 2
        for row, name in enumerate(names):
            position[name] = (x, top + row * (box_h + gap_y))
    out = [
        f"<svg class='depmap' viewBox='0 0 {width} {height:.0f}' role='img' "
        "aria-label='Service dependency map with tested services highlighted'>"
        "<title>Service dependency map</title>"
    ]
    for name, node in sorted(nodes.items()):
        for target in node.get("depends_on") or []:
            if target not in position:
                continue
            x1, y1 = position[name][0] + box_w, position[name][1] + box_h / 2
            x2, y2 = position[target][0], position[target][1] + box_h / 2
            hit = tested.get(target)
            stroke = _color(_score_value(hit)) if hit else "var(--muted)"
            mid = (x1 + x2) / 2
            out.append(
                f"<path d='M {x1:.1f} {y1:.1f} C {mid:.1f} {y1:.1f}, {mid:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}' "
                f"fill='none' stroke='{stroke}' stroke-width='{1.8 if hit else 1}' "
                f"opacity='{0.9 if hit else 0.4}'></path>"
            )
    for name, (x, y) in position.items():
        hit = tested.get(name)
        stroke = _color(_score_value(hit)) if hit else "var(--line)"
        out.append(
            f"<rect x='{x:.1f}' y='{y:.1f}' width='{box_w}' height='{box_h}' rx='8' "
            f"fill='var(--surface-2)' stroke='{stroke}' stroke-width='{2.2 if hit else 1}'></rect>"
        )
        label = html.escape(str(name))
        if hit:
            detail = html.escape(f"{hit.get('action', 'fault')} · score {_score_value(hit):.1f}")
            out.append(
                f"<text x='{x + 10:.1f}' y='{y + 16:.1f}' font-size='11.5' font-weight='700' "
                f"fill='var(--ink)'>{label}</text>"
                f"<text x='{x + 10:.1f}' y='{y + 30:.1f}' font-size='10.5' fill='{stroke}'>{detail}</text>"
            )
        else:
            out.append(
                f"<text x='{x + 10:.1f}' y='{y + 23:.1f}' font-size='11.5' fill='var(--ink)'>{label}</text>"
            )
    out.append("</svg>")
    return (
        "".join(out)
        + "<p class='section-note'>Arrows run from a caller (left) to the service it depends on (right). "
        "Outlined services were tested in this run; coloured arrows are their direct callers.</p>"
    )


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
        full = sum(1 for experiment in experiments if _fully_recovered(experiment))
        text += f" {full} of {len(experiments)} experiment(s) recovered fully, back to the pre-fault baseline."
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
            html.escape(_first_sentence(experiment.get("ai_diagnosis")))
            if experiment.get("ai_diagnosis")
            else "Measured effect at the shop frontend; no analyst diagnosis was saved for this run."
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
            + f"</div><p class='finding-note'>{details}</p>{abort}</article>"
        )
    return "<div class='findings-grid'>" + "".join(cards) + "</div>"


def severity_color(severity):
    return {"critical": "red", "high": "red", "medium": "amber", "low": "blue"}.get(severity, "blue")


def _collect_recommendations(experiments):
    """Every distinct fix once, weakest experiment first.

    When the analyst agent already recommends more replicas, the rule-based "run 2 replicas" entry
    says the same thing, so the two are merged: the agent's wording stays and keeps the auto-fix.
    """
    collected, seen = [], set()
    for experiment in _ordered_experiments(experiments):
        items = [
            dict(item) for item in experiment.get("recommendations") or []
            if isinstance(item, dict) and item.get("title") != "Safety limit stopped this experiment"
        ]
        agent_replica_fix = next(
            (item for item in items
             if str(item.get("source", "")).lower() == "llm"
             and "replica" in f"{item.get('title', '')} {item.get('detail', '')}".lower()),
            None,
        )
        for item in items:
            auto_fix = item.get("auto_fix") or {}
            same_fix = auto_fix.get("type") == "scale" or "replica" in str(item.get("title", "")).lower()
            if (agent_replica_fix is not None and item is not agent_replica_fix and same_fix
                    and str(item.get("source", "rule-based")).lower() != "llm"):
                if auto_fix:
                    agent_replica_fix.setdefault("auto_fix", auto_fix)
                elif "data store" in str(item.get("detail", "")).lower():
                    agent_replica_fix["detail"] = (
                        f"{agent_replica_fix.get('detail', '')} This is a data store: extra replicas "
                        "only help once replication is set up, so it is not applied automatically."
                    ).strip()
                continue
            key = (str(experiment.get("service")), str(item.get("title") or "Recommendation"))
            if key in seen:
                continue
            seen.add(key)
            collected.append((experiment, item))
    return collected


def _recommendation_section(experiments):
    recommendations = _collect_recommendations(experiments)
    if not recommendations:
        return "<div class='empty-state'>No remediation recommendations were saved for this run.</div>"
    rows = []
    for rank, (experiment, recommendation) in enumerate(recommendations, 1):
        service = html.escape(str(experiment.get("service", "Unknown service")))
        action = html.escape(str(experiment.get("action", "fault")))
        title = html.escape(str(recommendation.get("title", "Recommendation")))
        detail = html.escape(str(recommendation.get("detail", "Details not recorded.")))
        source = _source_label(recommendation.get("source") or experiment.get("analyst") or "rule-based")
        applicability = (
            "<span class='pill status-ok'>auto-fix available: chaosai fix</span>"
            if recommendation.get("auto_fix") else "<span class='pill'>manual change</span>"
        )
        rows.append(
            f"<div class='recommendation'><div class='row'><h4><span class='rank'>#{rank}</span> "
            f"{title}</h4><span class='row'>{applicability}<span class='pill'>{html.escape(source)}</span></span></div>"
            f"<p><b>{service}</b> · found by {action} (score {_score_value(experiment):.1f}/100). {detail}</p></div>"
        )
    return (
        "<div class='panel'>" + "".join(rows)
        + "<p class='section-note'>Ordered by the score of the experiment that exposed the weakness, "
        "lowest first.</p></div>"
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
    table = (
        "<div class='scroll'><table><thead><tr><th>Fault target</th>"
        "<th>Fault</th><th>Direct dependents (potential callers)</th>"
        "<th>Transitive dependents</th><th>Replicas</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )
    diagram = dependency_graph_svg(graph, experiments)
    if diagram:
        table = f"<details><summary>Dependents and replicas of each tested service</summary>{table}</details>"
    return "<div class='panel'>" + diagram + table + "</div>"


def _safety_section(results, experiments):
    limits = results.get("limits") or {}
    limit_items = [
        ("Abort above error rate", _fmt_rate(limits.get("max_error_rate"))),
        ("Abort above p95", _fmt_ms(limits.get("p95_limit_ms"))),
        ("Abort above extra unhealthy pods", limits.get("max_extra_unhealthy_pods", "Not recorded")),
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
            f"<td>{'Yes' if _fully_recovered(experiment) else ('Partial: baseline not restored' if experiment.get('recovered') else 'No / not recorded')}</td></tr>"
        )
    return (
        "<div class='panel'><div class='meta-row' style='margin:0 0 6px'>"
        + "".join(
            f"<span class='meta-chip'><b>{html.escape(str(label))}</b> {html.escape(str(value))}</span>"
            for label, value in limit_items
        )
        + f"<span class='meta-chip'><b>Environment</b> {html.escape(str(results.get('env', 'Not recorded')))}</span>"
        "</div><div class='scroll'><table><thead><tr>"
        "<th>Target</th><th>Fault</th><th>Guard stop</th><th>Abort latency</th>"
        "<th>Cleanup signal</th><th>Recovery</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div><p class='section-note'>Cleanup signal: the runner deleted the fault "
        "and saw the delete succeed.</p></div>"
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
        "<p><b>How to read this report</b></p><ul>"
        "<li>Probes go to the shop frontend. Latency percentiles use successful requests only; "
        "failed requests are counted as errors and drawn as × on the timeline.</li>"
        "<li>The dependency map shows which services could be affected (blast radius). Failures of "
        "individual callers are not measured separately.</li>"
        "<li>Scores, penalties, error rates and recovery times are calculated by code from the "
        "probes. Agent text (rationale, diagnosis, fixes, severity) is labelled with its source.</li>"
        "<li>The resilience score describes these experiments only; it is not an availability SLO.</li>"
        "</ul></details>"
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
    optional_counts = (
        f"{provenance['gemini_calls']} successful"
        if provenance["gemini_calls"] is not None else "Not recorded"
    )
    fallback_count = (
        f"{provenance['fallback_calls']}"
        if provenance["fallback_calls"] is not None else "Not recorded"
    )
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
    def chip(label, value):
        return f"<span class='meta-chip'><b>{html.escape(label)}</b> {html.escape(str(value))}</span>"

    rounds_text = provenance["rounds"] if provenance["rounds"] is not None else "not recorded"
    run_chips = (
        chip("Decisions", provenance["source"])
        + chip("Orchestrator", provenance["orchestrator"])
        + chip("Model", provenance["model"])
        + chip("Rounds", rounds_text)
        + chip("Experiments", provenance["experiments"])
        + chip("Gemini calls", optional_counts)
        + chip("Fallbacks", fallback_count)
    )
    agent_chips = "".join(
        chip(agent.title(), _source_label(agent_status.get(agent)))
        for agent in ("observer", "planner", "injector", "analyst", "reporter")
    )
    return (
        "<section><div class='section-head'><h2>Agent execution overview</h2>"
        "<span class='section-note'>Who made the decisions in this run</span></div>"
        f"<div class='panel'><div class='meta-row' style='margin:0 0 8px'>{run_chips}</div>"
        f"<div class='meta-row' style='margin:0'>{agent_chips}</div>{fallback}"
        + call_table
        + "</div></section>"
    )


def _cluster_observation_html(snapshot):
    if not isinstance(snapshot, dict):
        return "<p class='muted'>Cluster-level pod and warning observations were not recorded.</p>"
    groups = (
        ("Unhealthy pods", snapshot.get("unhealthy_pods") or []),
        ("Pods with restarts", snapshot.get("pods_with_restarts") or []),
        ("Warnings", snapshot.get("warning_events") or []),
        ("Deployments not ready", list((snapshot.get("deployments_not_ready") or {}).keys())),
    )
    content = [
        f"<p><b>{html.escape(label)}:</b> {html.escape('; '.join(str(item) for item in entries))}</p>"
        for label, entries in groups if entries
    ]
    if not content:
        return ("<p><b>Cluster:</b> no unhealthy pods, restarts, warning events or unready "
                "deployments in this snapshot.</p>")
    return "".join(content)


def _health_text(healthy):
    if healthy is True:
        return "<span class='status-ok'>Healthy</span>"
    if healthy is False:
        return "<span class='status-failed'>Not healthy</span>"
    return "Not recorded"


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
            candidate_rows, ranking, chosen_reason = [], [], ""
            for candidate in ranked:
                name = html.escape(f"{candidate.get('service', 'Unknown')} · {candidate.get('action', 'Unknown')}")
                rank = html.escape(str(candidate.get("rank", "?")))
                if candidate.get("chosen"):
                    ranking.append(f"<span class='rank-chip chosen'>{rank}. {name} — selected</span>")
                    chosen_reason = html.escape(str(candidate.get("rationale", "")))
                elif candidate.get("already_tested"):
                    ranking.append(f"<span class='rank-chip'>{rank}. {name} (already tested)</span>")
                else:
                    ranking.append(f"<span class='rank-chip'>{rank}. {name}</span>")
                candidate_rows.append(
                    f"<tr><td>{rank}</td>"
                    f"<td>{html.escape(str(candidate.get('service', 'Unknown')))}</td>"
                    f"<td>{html.escape(str(candidate.get('action', 'Unknown')))}</td>"
                    f"<td>{'<b>Selected</b>' if candidate.get('chosen') else ('Already tested' if candidate.get('already_tested') else '')}</td>"
                    f"<td>{html.escape(str(candidate.get('rationale', 'Not recorded')))}</td></tr>"
                )
            ranked_html = (
                f"<div class='rank-row'>{''.join(ranking)}</div>"
                + (f"<p><b>Why this one:</b> {chosen_reason}</p>" if chosen_reason else "")
                + f"<details><summary>Reason for every candidate ({len(ranked)})</summary>"
                "<div class='scroll'><table><thead><tr><th>Rank</th><th>Service</th><th>Fault</th>"
                "<th>Decision</th><th>Rationale</th></tr></thead><tbody>"
                + "".join(candidate_rows) + "</tbody></table></div></details>"
            )
        else:
            ranked_html = "<p class='muted'>Ranked candidate list not recorded for this round.</p>"
        planner_source = _source_label((entry.get("planner_provenance") or {}).get("source"))
        planner_reason = (entry.get("planner_provenance") or {}).get("fallback_reason")
        observation_text = html.escape(str(observation.get("summary", "Observation not recorded.")))
        concern_text = html.escape(", ".join(map(str, concerns)) or "None recorded")
        cards.append(
            f"<article class='agent-panel'><div class='row'><h3>Round {html.escape(str(round_number))}</h3>"
            "<span class='row'><span class='provenance'>Observer: " + html.escape(observed_by) + "</span>"
            "<span class='provenance'>Planner: " + html.escape(planner_source) + "</span></span></div>"
            f"<p><b>Observed:</b> {_health_text(observation.get('healthy'))} · "
            f"{html.escape(probe_summary)}. {observation_text}</p>"
            + (f"<p><b>Services of concern:</b> {concern_text}</p>" if concerns else "")
            + _cluster_observation_html(observation.get("cluster"))
            + (f"<p class='status-warn'><b>Planner fallback:</b> {html.escape(str(planner_reason))}</p>"
               if planner_reason else "")
            + ranked_html
            + "</article>"
        )
    return (
        "<section><div class='section-head'><h2>Observer &amp; Planner Agent</h2>"
        "<span class='section-note'>What was observed and how the experiments were ranked, by round</span></div>"
        "<div class='agent-grid' style='grid-template-columns:1fr'>" + "".join(cards) + "</div></section>"
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
            f"<tr><td>{index}</td><td><b style='color:{SEVERITY_COLOR.get(str(item.get('severity', '')).lower(), 'var(--muted)')}'>"
            f"{html.escape(str(item.get('severity', 'Not recorded')))}</b></td>"
            f"<td>{html.escape(str(item.get('service', 'Unknown')))}</td>"
            f"<td>{html.escape(str(item.get('action', 'Unknown')))}</td>"
            f"<td>{html.escape(str(item.get('score', 'N/A')))}</td>"
            f"<td>{html.escape(str(item.get('why', 'Not recorded')))}</td></tr>"
        )
    source = _source_label(report_data.get("source"))
    overall = report_data.get("overall")
    score_explanation = report_data.get("score_explanation")
    shown_at_top = " ".join(str(results.get("summary") or "").split())
    if overall and " ".join(str(overall).split()) == shown_at_top:
        overall_html = ""        # already printed in the summary panel at the top of the report
    elif overall:
        overall_html = f"<h3>Overall investigation summary</h3><p>{html.escape(str(overall))}</p>"
    else:
        overall_html = ""
    return (
        "<section><div class='section-head'><h2>Reporter Agent</h2>"
        f"<span class='provenance'>{html.escape(source)}</span></div><div class='panel'>"
        + overall_html
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
    planned = _number(decision.get("requested_duration_s"))
    approved = _number(decision.get("actual_duration_s"))
    if approved is None or approval is False:
        approved = _number(experiment.get("duration_s")) if approval is not False else None
    events = experiment.get("events") or {}
    injected = _number(events.get("fault_injected_at_s"))
    removed = _number(events.get("fault_removed_at_s"))
    active = max(0.0, removed - injected) if injected is not None and removed is not None else None
    stopped_early = (
        " (stopped early)" if active is not None and approved and active < approved - 1 else ""
    )
    duration_parts = []
    if planned is not None:
        duration_parts.append(f"<b>Planned:</b> {planned:.0f} s")
    if approved is not None:
        duration_parts.append(f"<b>Approved by injector:</b> {approved:.0f} s")
    duration_parts.append(
        f"<b>Fault actually active:</b> {active:.1f} s{stopped_early}" if active is not None
        else "<b>Fault actually active:</b> not recorded"
    )
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
        f"<p>{' · '.join(duration_parts)}</p>"
        f"<p><b>Safety thresholds:</b> {threshold_text}</p>"
        f"<p><b>Rollback by the agent:</b> {html.escape(str(rollback or 'not needed'))} · "
        f"<b>Abort by the safety guard:</b> {html.escape(str(abort_reason or 'not triggered'))} · "
        f"<b>Cleanup:</b> {html.escape(cleanup.lower())}</p>"
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
    recovered_count = sum(1 for experiment in experiments if _fully_recovered(experiment))
    recommendation_count = len(_collect_recommendations(experiments))
    has_rounds = isinstance(results.get("rounds"), list) and bool(results.get("rounds"))
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
        + _kpi("Weaknesses found", weak_count, "experiments scoring below 90")
        + _kpi("Safety stops", abort_count, "guard-triggered aborts")
        + _kpi("Full recoveries", f"{recovered_count}/{len(experiments)}", "recovered and back to baseline")
        + _kpi("Recommendations", recommendation_count, "distinct follow-up actions")
        + _kpi("Baseline probes", baseline.get("samples", "N/A"), "before fault injection")
        + "</section>"
    )

    parts.append(f"<section class='panel summary'>{_summary_copy(results, experiments)}</section>")
    parts.append(_overview_charts(experiments))
    parts.append(
        "<section><div class='section-head'><h2>Top measured findings</h2>"
        "<span class='section-note'>Ranked by measured resilience score, weakest first</span></div>"
        + _finding_cards(experiments, baseline) + "</section>"
    )
    parts.append(_agent_execution_section(results))
    parts.append(_observer_planner_sections(results))
    parts.append(_reporter_section(results))

    parts.append(
        "<section><div class='section-head'><h2>Recommended next actions</h2>"
        "<span class='section-note'>Fixes proposed by the analyst agent and the built-in rules</span></div>"
        + _recommendation_section(experiments) + "</section>"
    )
    if previous:
        parts.append(
            "<section><div class='section-head'><h2>Fix verification</h2>"
            "<span class='section-note'>Same experiments, before and after the fix</span></div>"
            + _fix_verification(experiments, previous) + "</section>"
        )
    else:
        parts.append(
            "<p class='section-note'><b>Verification pending.</b> No fix has been re-tested yet, so this "
            "report cannot verify remediation. Run <code>chaosai fix</code> and then "
            "<code>chaosai rerun</code> to add the before/after comparison.</p>"
        )
    parts.append(
        "<section><div class='section-head'><h2>Dependency &amp; blast-radius context</h2>"
        "<span class='section-note'>Who depends on each tested service (potential impact)</span></div>"
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
            f"fault duration set to {e(str(experiment.get('duration_s', 'N/A')))} s</span></div>"
            f"<div class='row'>{abort}<span class='pill'>Score {score_value:.1f}/100</span></div></div>"
            f"{'' if has_rounds else round_context(experiment)}"
            + ("" if has_rounds else
               f"<p class='muted'><b>{rationale_label}:</b> "
               f"{e(str(experiment.get('rationale', 'Not recorded.')))}</p>")
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
            + ("" if not (experiment.get("root_cause_hypotheses") or experiment.get("analyst_evidence")) else (
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
                + f"<p><b>Analyst source:</b> {e(_source_label((experiment.get('agent_provenance') or {}).get('analyst', {}).get('source', experiment.get('analyst'))))}</p>"
                "</div>"
            ))
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
            + experiment_conclusion(experiment, baseline)
            + "<details><summary>Measurements: four phases, impact, recovery and score breakdown</summary>"
            + phase_comparison(
                experiment.get("phase_metrics"), experiment.get("phase_samples"),
                experiment.get("recovery_s")
            )
            + "<div class='insight-grid'>"
            + impact_section(experiment, baseline)
            + recovery_section(experiment)
            + "</div>"
            f"<p class='muted'>Recorded score penalties (errors / latency / recovery / abort): "
            f"{e(str((experiment.get('breakdown') or {}).get('errors', 'N/A')))} / "
            f"{e(str((experiment.get('breakdown') or {}).get('latency', 'N/A')))} / "
            f"{e(str((experiment.get('breakdown') or {}).get('recovery', 'N/A')))} / "
            f"{e(str((experiment.get('breakdown') or {}).get('abort', 'N/A')))}.</p>"
            + (
                f"<p>Guard abort latency: {_number(experiment.get('abort_latency_s')):.2f} s.</p>"
                if _number(experiment.get("abort_latency_s")) is not None else ""
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