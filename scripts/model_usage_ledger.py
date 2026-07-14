#!/usr/bin/env python3
"""Safely append, aggregate, and render the model-routing usage ledger."""

import argparse
import fcntl
import json
import math
import os
import statistics
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
MODES = ("assess", "query", "record", "retune")
OUTCOMES = ("completed", "failed", "escalated", "reworked", "cancelled")
SOURCES = ("user-confirmed", "task-metadata")
USAGE_START = "<!-- MODEL_USAGE_START -->"
USAGE_END = "<!-- MODEL_USAGE_END -->"


def now():
    return datetime.now(timezone.utc).isoformat()


def load_lines(text, source):
    events, warnings = [], []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("event is not an object")
            events.append(event)
        except (json.JSONDecodeError, ValueError) as exc:
            warnings.append(f"skipped malformed event at {source}:{number}: {exc}")
    return events, warnings


def read_events(path):
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        text = handle.read()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return load_lines(text, path)


def append_event(path, event):
    path.parent.mkdir(parents=True, exist_ok=True)
    event.setdefault("event_id", str(uuid.uuid4()))
    event.setdefault("timestamp", now())
    encoded = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        existing_text = handle.read()
        existing, _ = load_lines(existing_text, path)
        if any(item.get("event_id") == event["event_id"] for item in existing):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return False
        handle.seek(0, os.SEEK_END)
        if existing_text and not existing_text.endswith("\n"):
            handle.write("\n")
        handle.write(encoded + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return True


def proportions(counter):
    total = sum(counter.values())
    return {
        "total": total,
        "items": {
            key: {"count": count, "percent": round(count * 100 / total, 1)}
            for key, count in sorted(counter.items())
        } if total else {},
    }


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def route_performance(executions):
    groups = defaultdict(list)
    for event in executions:
        key = " | ".join((
            event.get("task_class", "unknown"),
            event.get("model", "unknown"),
            event.get("effort", "unknown"),
        ))
        groups[key].append(event)
    result = {}
    for key, items in sorted(groups.items()):
        outcomes = Counter(item.get("outcome", "unknown") for item in items)
        attempts = sum(value for name, value in outcomes.items() if name != "cancelled")
        completed = outcomes.get("completed", 0)
        pressure = sum(outcomes.get(name, 0) for name in ("failed", "escalated", "reworked"))
        durations = [item["duration_seconds"] for item in items if item.get("duration_seconds") is not None]
        if attempts >= 5 and pressure / attempts >= 0.4:
            signal = "raise_candidate"
        elif attempts >= 10 and completed / attempts >= 0.9 and pressure == 0:
            signal = "lower_candidate"
        elif attempts < 5:
            signal = "insufficient_sample"
        else:
            signal = "hold"
        result[key] = {
            "attempts": attempts,
            "outcomes": dict(sorted(outcomes.items())),
            "success_rate": round(completed * 100 / attempts, 1) if attempts else None,
            "pressure_rate": round(pressure * 100 / attempts, 1) if attempts else None,
            "duration_median_seconds": round(statistics.median(durations), 1) if durations else None,
            "duration_p75_seconds": round(percentile(durations, 0.75), 1) if durations else None,
            "retune_signal": signal,
        }
    return result


def build_summary(events, warnings):
    executions = [item for item in events if item.get("event") == "execution"]
    attempts = [item for item in executions if item.get("outcome") != "cancelled"]
    actual_models = Counter(item.get("model", "unknown") for item in attempts)
    model_effort = Counter(
        f"{item.get('model', 'unknown')} | {item.get('effort', 'unknown')}" for item in attempts
    )
    analyses = Counter(
        item.get("analysis_model", "unknown")
        for item in events if item.get("event") == "skill_run"
    )
    latest = next((item for item in reversed(events) if item.get("event") == "allocation"), None)
    return {
        "actual_execution": proportions(actual_models),
        "model_effort_usage": proportions(model_effort),
        "analysis_runs": proportions(analyses),
        "recommended_allocation": latest,
        "route_performance": route_performance(executions),
        "actual_sample": "insufficient" if not attempts else ("early" if len(attempts) < 5 else "established"),
        "warnings": warnings,
    }


def markdown_table(view, first_header):
    rows = [f"| {first_header} | Count | Percent |", "|---|---:|---:|"]
    for name, values in view["items"].items():
        safe_name = str(name).replace("|", "\\|")
        rows.append(f"| {safe_name} | {values['count']} | {values['percent']}% |")
    if not view["items"]:
        rows.append("| Insufficient observed data | 0 | — |")
    return "\n".join(rows)


def render_markdown(summary):
    sample = summary["actual_sample"]
    lines = [
        USAGE_START,
        f"_Observed sample: **{sample}**. Actual use counts non-cancelled execution attempts._",
        "",
        "### Actual execution by model",
        "",
        markdown_table(summary["actual_execution"], "Model"),
        "",
        "### Actual execution by model and effort",
        "",
        markdown_table(summary["model_effort_usage"], "Model and effort"),
        "",
        "### Router analysis runs",
        "",
        markdown_table(summary["analysis_runs"], "Analysis model"),
        "",
        "### Latest recommended allocation",
        "",
    ]
    allocation = summary.get("recommended_allocation")
    if allocation:
        lines.extend([
            f"Basis: `{allocation.get('basis', 'unknown')}`",
            "",
            "| Model | Recommended share |",
            "|---|---:|",
        ])
        for model, percent in sorted(allocation.get("allocation", {}).items()):
            lines.append(f"| {model} | {percent:g}% |")
    else:
        lines.append("No recommended allocation has been recorded.")
    signals = [
        (route, values["retune_signal"])
        for route, values in summary["route_performance"].items()
        if values["retune_signal"] in ("raise_candidate", "lower_candidate")
    ]
    lines.extend(["", "### Retuning signals", ""])
    if signals:
        lines.extend(f"- `{route}`: `{signal}`" for route, signal in signals)
    else:
        lines.append("No route currently meets the automatic retuning evidence threshold.")
    if summary["warnings"]:
        lines.extend(["", f"Ledger warnings: {len(summary['warnings'])} malformed event(s) skipped."])
    lines.append(USAGE_END)
    return "\n".join(lines)


def update_report(path, block):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        text = handle.read()
        starts, ends = text.count(USAGE_START), text.count(USAGE_END)
        if starts != ends or starts > 1:
            raise SystemExit("report has unmatched or duplicate model-usage markers")
        if starts == 1:
            before = text.split(USAGE_START, 1)[0].rstrip()
            after = text.split(USAGE_END, 1)[1].lstrip("\n")
            updated = before + "\n\n" + block + ("\n\n" + after if after else "\n")
        else:
            heading = "# Codex model routing report\n" if not text.strip() else text.rstrip()
            updated = heading + "\n\n## Usage proportions\n\n" + block + "\n"
        handle.seek(0)
        handle.truncate()
        handle.write(updated)
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def record(args):
    required = {
        "skill_run": ("mode", "analysis_model", "effort"),
        "execution": ("model", "effort", "task_class", "outcome", "source"),
    }[args.event]
    missing = [key for key in required if getattr(args, key, None) is None]
    if missing:
        raise SystemExit(f"{args.event} requires: {', '.join(missing)}")
    if args.duration_seconds is not None and (not math.isfinite(args.duration_seconds) or args.duration_seconds < 0):
        raise SystemExit("duration must be finite and non-negative")
    event = {"event": args.event}
    for key in ("event_id", "task_id", "mode", "analysis_model", "model", "effort",
                "task_class", "outcome", "source", "fallback_from", "fallback_to",
                "fallback_reason"):
        value = getattr(args, key, None)
        if value is not None:
            event[key] = value
    if args.duration_seconds is not None:
        event["duration_seconds"] = args.duration_seconds
    print(json.dumps({"appended": append_event(args.ledger, event), "event_id": event.get("event_id")}, ensure_ascii=False))


def allocation(args):
    try:
        values = json.loads(args.values)
        numeric = {str(key): float(value) for key, value in values.items()}
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
        raise SystemExit(f"--values must be a JSON object with numeric percentages: {exc}") from exc
    if not numeric or any(not math.isfinite(value) or value < 0 for value in numeric.values()):
        raise SystemExit("allocation percentages must be finite and non-negative")
    if abs(sum(numeric.values()) - 100) > 0.01:
        raise SystemExit("allocation percentages must total 100")
    event = {"event": "allocation", "basis": args.basis, "allocation": numeric}
    if args.event_id:
        event["event_id"] = args.event_id
    print(json.dumps({"appended": append_event(args.ledger, event), "event_id": event.get("event_id")}, ensure_ascii=False))


def summarize(args):
    events, warnings = read_events(args.ledger)
    summary = build_summary(events, warnings)
    if args.format == "markdown":
        print(render_markdown(summary))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def render(args):
    events, warnings = read_events(args.ledger)
    update_report(args.report, render_markdown(build_summary(events, warnings)))
    print(args.report)


def parser():
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    rec = commands.add_parser("record")
    rec.add_argument("--ledger", type=Path, required=True)
    rec.add_argument("--event", choices=("skill_run", "execution"), required=True)
    rec.add_argument("--event-id")
    rec.add_argument("--task-id")
    rec.add_argument("--mode", choices=MODES)
    rec.add_argument("--analysis-model")
    rec.add_argument("--model")
    rec.add_argument("--effort", choices=EFFORTS)
    rec.add_argument("--task-class")
    rec.add_argument("--outcome", choices=OUTCOMES)
    rec.add_argument("--source", choices=SOURCES)
    rec.add_argument("--fallback-from")
    rec.add_argument("--fallback-to")
    rec.add_argument("--fallback-reason")
    rec.add_argument("--duration-seconds", type=float)
    rec.set_defaults(func=record)
    alloc = commands.add_parser("allocation")
    alloc.add_argument("--ledger", type=Path, required=True)
    alloc.add_argument("--values", required=True, help='JSON object such as {"Sol":30,"Terra":50,"Luna":20}')
    alloc.add_argument("--basis", choices=("heuristic", "observed", "mixed"), default="heuristic")
    alloc.add_argument("--event-id")
    alloc.set_defaults(func=allocation)
    report = commands.add_parser("summary")
    report.add_argument("--ledger", type=Path, required=True)
    report.add_argument("--format", choices=("json", "markdown"), default="json")
    report.set_defaults(func=summarize)
    renderer = commands.add_parser("render")
    renderer.add_argument("--ledger", type=Path, required=True)
    renderer.add_argument("--report", type=Path, required=True)
    renderer.set_defaults(func=render)
    return root


if __name__ == "__main__":
    arguments = parser().parse_args()
    arguments.func(arguments)
