#!/usr/bin/env python3
"""Select a deterministic Codex model route and inspect current task metadata."""

import argparse
import json
import os
import re
import uuid
from pathlib import Path


MODELS = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
RUNTIME_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")
THREAD_ID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
MODEL_ALIASES = {
    "gpt-5.6": "gpt-5.6-sol",
    "gpt-5.6 sol": "gpt-5.6-sol",
    "gpt5.6": "gpt-5.6-sol",
    "gpt5.6 sol": "gpt-5.6-sol",
    "sol": "gpt-5.6-sol",
    "gpt-5.6-sol": "gpt-5.6-sol",
    "terra": "gpt-5.6-terra",
    "gpt-5.6 terra": "gpt-5.6-terra",
    "gpt5.6 terra": "gpt-5.6-terra",
    "gpt-5.6-terra": "gpt-5.6-terra",
    "luna": "gpt-5.6-luna",
    "gpt-5.6 luna": "gpt-5.6-luna",
    "gpt5.6 luna": "gpt-5.6-luna",
    "gpt-5.6-luna": "gpt-5.6-luna",
}
EFFORT_ALIASES = {
    "low": "low", "medium": "medium", "high": "high", "xhigh": "xhigh",
    "very high": "xhigh", "very-high": "xhigh",
    "extra high": "xhigh", "extra-high": "xhigh",
}


def normalize_model(value):
    if value is None:
        return None
    normalized = MODEL_ALIASES.get(value.strip().lower())
    if normalized is None:
        raise ValueError(f"unsupported model: {value}")
    return normalized


def normalize_effort(value):
    if value is None:
        return None
    normalized = EFFORT_ALIASES.get(value.strip().lower())
    if normalized is None:
        raise ValueError(f"unsupported effort: {value}")
    return normalized


def unavailable_current(thread_id=None, reason="metadata-unavailable"):
    return {
        "status": "unavailable",
        "thread_id": thread_id,
        "model": None,
        "effort": None,
        "source": None,
        "reason": reason,
    }


def detect_current_route(sessions_root=None, environ=None):
    environ = os.environ if environ is None else environ
    thread_id = environ.get("CODEX_THREAD_ID")
    if not thread_id or not THREAD_ID_RE.fullmatch(thread_id):
        return unavailable_current(reason="CODEX_THREAD_ID-unavailable")

    if sessions_root is None:
        codex_home = Path(environ.get("CODEX_HOME", Path.home() / ".codex"))
        sessions_root = codex_home / "sessions"
    else:
        sessions_root = Path(sessions_root)

    try:
        candidates = list(sessions_root.glob(f"*/*/*/*{thread_id}*.jsonl"))
        if not candidates:
            candidates = list(sessions_root.rglob(f"*{thread_id}*.jsonl"))
    except OSError:
        return unavailable_current(thread_id, "sessions-unreadable")
    if not candidates:
        return unavailable_current(thread_id, "session-not-found")

    verified = []
    try:
        for session in candidates:
            session_id = None
            latest = None
            latest_source = None
            with session.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not any(marker in line for marker in (
                        '"type":"session_meta"', '"type": "session_meta"',
                        '"thread_settings_applied"',
                        '"type":"turn_context"', '"type": "turn_context"',
                    )):
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = item.get("payload", {})
                    if item.get("type") == "session_meta":
                        session_id = payload.get("id") or payload.get("session_id")
                        continue
                    if item.get("type") == "event_msg" and payload.get("type") == "thread_settings_applied":
                        settings = payload.get("thread_settings", {})
                        model = settings.get("model")
                        effort = settings.get("reasoning_effort")
                        source = "thread_settings_applied"
                    elif item.get("type") == "turn_context":
                        collaboration = payload.get("collaboration_mode", {}).get("settings", {})
                        model = payload.get("model") or collaboration.get("model")
                        effort = payload.get("effort") or collaboration.get("reasoning_effort")
                        source = "turn_context"
                    else:
                        continue
                    if isinstance(model, str) and isinstance(effort, str):
                        latest = (model, effort)
                        latest_source = source
            if session_id == thread_id and latest is not None:
                verified.append((session.stat().st_mtime_ns, latest, latest_source))
    except OSError:
        return unavailable_current(thread_id, "session-unreadable")

    if not verified:
        return unavailable_current(thread_id, "verified-settings-not-found")
    _, latest, latest_source = max(verified, key=lambda item: item[0])
    return {
        "status": "verified",
        "thread_id": thread_id,
        "model": latest[0],
        "effort": latest[1],
        "source": f"local-session-metadata:{latest_source}",
        "reason": None,
    }


def recommended_route(mode, task_kind, risk, size, report_model=None, report_effort=None):
    if mode == "apply" and (report_model is not None or report_effort is not None):
        if report_model is None or report_effort is None:
            raise ValueError("report route requires both model and effort")
        return report_model, report_effort, "report"

    if mode in ("assess", "retune"):
        if risk == "high" or task_kind == "complex":
            return "gpt-5.6-sol", "high", "adaptive-default"
        if risk == "low" and task_kind == "mechanical":
            return "gpt-5.6-sol", "low", "adaptive-default"
        return "gpt-5.6-sol", "medium", "default"

    if risk == "high" or task_kind == "complex":
        return "gpt-5.6-sol", "high", "deterministic-fallback"
    if task_kind == "mechanical":
        effort = "medium" if size == "large" else "low"
        return "gpt-5.6-luna", effort, "deterministic-fallback"
    effort = "high" if size == "large" else "medium"
    return "gpt-5.6-terra", effort, "deterministic-fallback"


def select_route(
    mode,
    task_kind="ordinary",
    risk="normal",
    size="normal",
    model_override=None,
    effort_override=None,
    report_model=None,
    report_effort=None,
    current=None,
):
    report_model = normalize_model(report_model)
    report_effort = normalize_effort(report_effort)
    target_model, target_effort, source = recommended_route(
        mode, task_kind, risk, size, report_model, report_effort
    )

    explicit_override = model_override is not None or effort_override is not None
    if model_override is not None:
        target_model = normalize_model(model_override)
    if effort_override is not None:
        target_effort = normalize_effort(effort_override)
    if explicit_override:
        source = "user-override"

    current = current or unavailable_current()
    execution_model, execution_effort = target_model, target_effort
    tiny_fast_path = (
        mode == "apply" and task_kind == "mechanical" and size == "tiny"
        and risk != "high" and not explicit_override
    )
    if tiny_fast_path:
        dispatch = "local"
        execution_model = current.get("model") or "current-route"
        execution_effort = current.get("effort") or "keep"
        reason = "tiny-task-switch-cost"
    elif current.get("status") == "verified" and (
        current.get("model"), current.get("effort")
    ) == (target_model, target_effort):
        dispatch = "local"
        reason = "route-already-matched"
    elif current.get("status") == "verified" and current.get("thread_id"):
        dispatch = "same-task-switch"
        reason = source
    else:
        dispatch = "selectable-subagent-or-local"
        reason = "original-route-unavailable"

    restore_required = dispatch == "same-task-switch"
    return {
        "route_id": str(uuid.uuid4()),
        "mode": mode,
        "recommended": {"model": target_model, "effort": target_effort, "source": source},
        "execution": {
            "model": execution_model,
            "effort": execution_effort,
            "dispatch": dispatch,
            "reason": reason,
        },
        "current": current,
        "restore_required": restore_required,
        "explicit_override": explicit_override,
    }


def parser():
    root = argparse.ArgumentParser()
    root.add_argument("--inspect-current", action="store_true")
    root.add_argument("--sessions-root", type=Path)
    root.add_argument("--no-runtime-detection", action="store_true")
    root.add_argument("--current-model")
    root.add_argument("--current-effort", choices=RUNTIME_EFFORTS)
    root.add_argument("--mode", choices=("apply", "assess", "retune"))
    root.add_argument("--task-kind", choices=("mechanical", "ordinary", "complex"), default="ordinary")
    root.add_argument("--risk", choices=("low", "normal", "high"), default="normal")
    root.add_argument("--size", choices=("tiny", "normal", "large"), default="normal")
    root.add_argument("--model")
    root.add_argument("--effort")
    root.add_argument("--report-model")
    root.add_argument("--report-effort")
    return root


def main():
    args = parser().parse_args()
    if (args.current_model is None) != (args.current_effort is None):
        raise SystemExit("--current-model and --current-effort must be supplied together")
    if args.current_model is not None:
        current = {
            "status": "verified",
            "thread_id": os.environ.get("CODEX_THREAD_ID", "test-thread"),
            "model": args.current_model,
            "effort": args.current_effort,
            "source": "explicit-runtime-input",
            "reason": None,
        }
    elif args.no_runtime_detection:
        current = unavailable_current()
    else:
        current = detect_current_route(args.sessions_root)
    if args.inspect_current:
        print(json.dumps(current, ensure_ascii=False, sort_keys=True))
        return
    if args.mode is None:
        raise SystemExit("--mode is required unless --inspect-current is used")
    try:
        route = select_route(
            args.mode,
            args.task_kind,
            args.risk,
            args.size,
            args.model,
            args.effort,
            args.report_model,
            args.report_effort,
            current,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(route, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
