#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    REQUIRED_TASK_HEADINGS,
    ROOT,
    normalize_id,
    task_allowed_paths,
    task_section,
)


def validate_task_path(
    task_id: str,
    path: Path,
    *,
    accepted_statuses=("READY",),
) -> tuple[str, list[str], str]:
    if not path.exists():
        raise ValueError(f"{task_id} is not present at {path}")
    text = path.read_text(encoding="utf-8")
    missing = [heading for heading in REQUIRED_TASK_HEADINGS if heading not in text]
    if missing:
        raise ValueError("Missing task headings: " + ", ".join(missing))

    status = task_section(text, "Status").upper()
    if not any(accepted in status for accepted in accepted_statuses):
        raise ValueError("Task status must be one of: " + ", ".join(accepted_statuses))

    allowed = task_allowed_paths(text)
    if not allowed:
        raise ValueError("Allowed paths must contain at least one explicit path/glob")
    if any(
        any(marker in pattern.upper() for marker in ("REPLACE_WITH", "TBD", "..."))
        for pattern in allowed
    ):
        raise ValueError("Allowed paths still contain placeholder values")

    profile = task_section(text, "Worker profile").upper()
    if profile not in ("SMALL", "MEDIUM", "HIGH"):
        raise ValueError("Worker profile must be exactly SMALL, MEDIUM, or HIGH")

    decision = task_section(text, "Decision gate").upper()
    if any(marker in decision for marker in ("PENDING", "UNAPPROVED", "TBD")):
        raise ValueError("Task has an unresolved decision gate")
    return text, allowed, profile


def main() -> None:
    parser = argparse.ArgumentParser(prog="validate-task")
    parser.add_argument("task_id")
    parser.add_argument(
        "--folder",
        choices=("ready", "blocked"),
        default="ready",
        help="Validate a READY task or a BLOCKED task before --recheck.",
    )
    args = parser.parse_args()
    task_id = normalize_id(args.task_id)
    path = ROOT / "agent" / "tasks" / args.folder / f"{task_id}.md"
    statuses = ("READY",) if args.folder == "ready" else ("READY", "BLOCKED")
    try:
        _, allowed, _ = validate_task_path(task_id, path, accepted_statuses=statuses)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(f"VALID {task_id}: {len(allowed)} allowed path pattern(s)")


if __name__ == "__main__":
    main()
