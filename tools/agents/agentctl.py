#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from common import ROOT, find_task_locations, normalize_id
from routing import load_registry, schedule_workers
from usage_ledger import UsageLedger
from validate_task import validate_task_path


GITIGNORE_ENTRIES = (
    ".agent-worker/",
    ".claude/settings.local.json",
    "*.agent-worker.log",
    "__pycache__/",
    "*.pyc",
)

GENERIC_PROJECT_FILES = {
    "agent/STATE.md": """# Project State

## Project
- Name: TBD
- Repository type: existing project
- Lifecycle: audit

## Current objective
Audit the existing codebase before creating implementation tasks.

## Active task
None.

## Pending human decisions
See `agent/decisions/PENDING.md`.

## Resume instruction
Reconcile this file with the live task folders and latest reports before continuing.
""",
    "agent/decisions/PENDING.md": "# Pending Human Decisions\n\nNone.\n",
    "agent/product/VISION.md": "# Product Vision\n\nTBD — derive from the existing project and user input.\n",
    "agent/product/PRD.md": "# Product Requirements Document\n\nTBD — audit before changing behavior.\n",
    "agent/product/SCOPE.md": "# Product Scope\n\nTBD — preserve existing behavior until approved.\n",
    "agent/product/NON_FUNCTIONAL.md": "# Non-Functional Requirements\n\nTBD.\n",
    "agent/design/SOURCES.md": "# Design Sources\n\nRecord existing design files, screenshots, and links here.\n",
    "agent/discovery/CODEBASE_AUDIT.md": "# Codebase Audit\n\nNot started.\n",
    "agent/discovery/TECH_DEBT.md": "# Technical Debt\n\nNot assessed.\n",
    "agent/architecture/ARCHITECTURE.md": "# Architecture\n\nTBD — document current reality before target architecture.\n",
    "agent/planning/ROADMAP.md": "# Roadmap\n\nTBD.\n",
    "agent/planning/MILESTONES.md": "# Milestones\n\nTBD.\n",
    "agent/history/CHANGELOG_AI.md": "# AI Change History\n\n",
    "agent/tasks/INDEX.md": "# Task Index\n\nNo tasks yet.\n",
}

EMPTY_PROJECT_DIRECTORIES = (
    "agent/decisions/approved",
    "agent/tasks/backlog",
    "agent/tasks/ready",
    "agent/tasks/active",
    "agent/tasks/review",
    "agent/tasks/blocked",
    "agent/tasks/done",
    "agent/tasks/archive",
    "agent/reports/implementation",
    "agent/reports/review",
    "agent/reports/qa",
)

POTENTIAL_SECRET = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|auth[_-]?token|secret|password)"
    r"\s*[:=]\s*[\"']?[A-Za-z0-9_./+\-=]{12,}"
)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _executable(name: str, override: str | None = None) -> str | None:
    if override:
        try:
            if Path(override).exists():
                return override
        except OSError:
            pass
        return shutil.which(override)
    found = shutil.which(name)
    if found:
        return found
    if os.name != "nt":
        return None
    home = Path(os.environ.get("USERPROFILE", ""))
    candidates = {
        "opencode.cmd": [home / "AppData/Roaming/npm/opencode.cmd"],
        "ollama": [home / "AppData/Local/Programs/Ollama/ollama.exe"],
        "claude": [home / ".local/bin/claude.exe"],
    }
    for candidate in candidates.get(name, []):
        try:
            if candidate.exists():
                return str(candidate)
        except OSError:
            continue
    return None


def _probe(name: str, executable: str | None, arguments: Sequence[str]) -> Check:
    if not executable:
        return Check(name, False, "not found")
    try:
        completed = subprocess.run(
            [executable, *arguments],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return Check(name, False, f"{executable}: {error}")
    detail = (completed.stdout or completed.stderr or "").strip().splitlines()
    return Check(name, completed.returncode == 0, detail[0] if detail else executable)


def doctor(*, deep: bool = False) -> int:
    print("Doctor: checking local tools in parallel...", flush=True)
    probe_jobs = (
        ("Git", _executable("git"), ("--version",)),
        ("Python", sys.executable, ("--version",)),
        ("Claude Code", _executable("claude"), ("--version",)),
        ("Ollama", _executable("ollama", os.getenv("OLLAMA_BIN")), ("--version",)),
        ("OpenCode", _executable("opencode.cmd", os.getenv("OPENCODE_BIN")), ("--version",)),
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(probe_jobs)) as executor:
        checks = list(executor.map(lambda job: _probe(*job), probe_jobs))
    checks.append(Check("Git repository", (ROOT / ".git").exists(), str(ROOT)))

    try:
        registry, profiles = load_registry(ROOT)
        checks.append(Check("Worker registry", True, f"{len(registry)} free workers; {len(profiles)} profiles"))
    except Exception as error:
        registry, profiles = {}, {}
        checks.append(Check("Worker registry", False, str(error)))

    for task_file in (ROOT / "agent" / "tasks" / "ready").glob("TASK-*.md"):
        task_id = task_file.stem
        try:
            validate_task_path(task_id, task_file)
            checks.append(Check(f"Ready task {task_id}", True, "contract valid", required=False))
        except ValueError as error:
            checks.append(Check(f"Ready task {task_id}", False, str(error)))

    if deep and registry:
        print("Doctor: checking approved model catalogs in parallel (up to 60 seconds)...", flush=True)
        opencode = _executable("opencode.cmd", os.getenv("OPENCODE_BIN"))
        ollama = _executable("ollama", os.getenv("OLLAMA_BIN"))

        def check_opencode_models() -> Check | None:
            if not opencode:
                return None
            try:
                completed = subprocess.run(
                    [opencode, "models"],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    timeout=60,
                )
                available = set(completed.stdout.splitlines())
                expected = {spec.model for spec in registry.values() if spec.harness == "opencode"}
                missing = sorted(expected - available)
                return Check(
                    "OpenCode approved models",
                    completed.returncode == 0 and not missing,
                    "all present" if not missing else "missing: " + ", ".join(missing),
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                return Check("OpenCode approved models", False, str(error))

        def check_ollama_models() -> Check | None:
            if not ollama:
                return None
            try:
                completed = subprocess.run(
                    [ollama, "list"],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    timeout=30,
                )
                output = completed.stdout
                missing = [
                    model
                    for model in ("gpt-oss:20b", "gpt-oss:120b-cloud")
                    if model not in output
                ]
                return Check(
                    "Ollama approved models",
                    completed.returncode == 0 and not missing,
                    "all present" if not missing else "missing: " + ", ".join(missing),
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                return Check("Ollama approved models", False, str(error))

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            deep_checks = list(executor.map(lambda check: check(), (check_opencode_models, check_ollama_models)))
        checks.extend(check for check in deep_checks if check is not None)

    width = max(len(check.name) for check in checks)
    for check in checks:
        label = "PASS" if check.ok else ("FAIL" if check.required else "WARN")
        print(f"{label:4}  {check.name:<{width}}  {check.detail}")
    failed = [check for check in checks if check.required and not check.ok]
    print(f"\nDoctor result: {'READY' if not failed else 'NOT READY'}")
    return 0 if not failed else 1


def show_route(profile: str) -> int:
    registry, profiles = load_registry(ROOT)
    ledger = UsageLedger(ROOT / ".agent-worker" / "usage-ledger.json")
    route, skipped = schedule_workers(profile, registry, profiles, ledger)
    print(f"{profile.upper()} route")
    if route:
        for index, spec in enumerate(route, start=1):
            pressure = ledger.pressure(spec.usage_key, spec.budget)
            print(
                f"{index}. {spec.provider} - {spec.model} [{spec.harness}] "
                f"usage-pressure={pressure:g}"
            )
    else:
        print("No eligible workers.")
    for spec, reason in skipped:
        print(f"SKIP {spec.provider} - {spec.model}: {reason}")
    return 0 if route else 1


def show_status() -> int:
    print(f"Project: {ROOT}")
    live_count = 0
    for folder in ("active", "review", "blocked", "ready", "done", "backlog"):
        directory = ROOT / "agent" / "tasks" / folder
        tasks = []
        if directory.exists():
            for path in sorted(directory.glob("TASK-*.md")):
                locations = find_task_locations(path.stem, folders=(folder,))
                if locations:
                    tasks.append(path.stem)
        if tasks:
            live_count += len(tasks)
            print(f"{folder.upper():7} " + ", ".join(tasks))
    if not live_count:
        print("No live tasks.")
    print("")
    for profile in ("SMALL", "MEDIUM", "HIGH"):
        show_route(profile)
        print("")
    return 0


def run_tests() -> int:
    environment = os.environ.copy()
    agents_path = str(ROOT / "tools" / "agents")
    environment["PYTHONPATH"] = agents_path + (
        os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else ""
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tools/agents/tests",
            "-t",
            "tools/agents",
            "-v",
        ],
        cwd=ROOT,
        env=environment,
    )
    return completed.returncode


def _copy_if_missing(source: Path, destination: Path, copied: list[str], conflicts: list[str]) -> None:
    relative = str(destination)
    if destination.exists():
        try:
            same = source.read_bytes() == destination.read_bytes()
        except OSError:
            same = False
        if not same:
            conflicts.append(relative)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    copied.append(relative)


def init_project(target: Path, *, init_git: bool = False) -> int:
    target = target.resolve()
    source_root = ROOT.resolve()
    if target == source_root or source_root in target.parents:
        print("Refusing to install the agent system inside its source repository.", file=sys.stderr)
        return 2
    if not target.exists() or not target.is_dir():
        print(f"Target directory does not exist: {target}", file=sys.stderr)
        return 2
    if not (target / ".git").exists():
        if not init_git:
            print(
                "Target is not a Git repository. Re-run with --init-git after confirming a Git baseline is appropriate.",
                file=sys.stderr,
            )
            return 2
        completed = subprocess.run(["git", "init"], cwd=target)
        if completed.returncode:
            return completed.returncode

    copied: list[str] = []
    conflicts: list[str] = []

    runtime_root = source_root / "tools" / "agents"
    for source in sorted(runtime_root.rglob("*")):
        if not source.is_file() or "__pycache__" in source.parts:
            continue
        relative = source.relative_to(source_root)
        _copy_if_missing(source, target / relative, copied, conflicts)

    for directory in (source_root / ".claude", source_root / ".roo"):
        if not directory.exists():
            continue
        for source in sorted(directory.rglob("*")):
            if source.is_file() and "__pycache__" not in source.parts:
                relative = source.relative_to(source_root)
                _copy_if_missing(source, target / relative, copied, conflicts)

    for name in ("AGENTS.md", "CLAUDE.md", ".rooignore"):
        source = source_root / name
        if source.exists():
            _copy_if_missing(source, target / name, copied, conflicts)

    for folder in ("agent/templates", "agent/quality"):
        source_dir = source_root / folder
        if source_dir.exists():
            for source in sorted(source_dir.rglob("*")):
                if source.is_file():
                    relative = source.relative_to(source_root)
                    _copy_if_missing(source, target / relative, copied, conflicts)

    for relative, content in GENERIC_PROJECT_FILES.items():
        destination = target / relative
        if destination.exists():
            if destination.read_text(encoding="utf-8") != content:
                conflicts.append(str(destination))
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        copied.append(str(destination))
    for relative in EMPTY_PROJECT_DIRECTORIES:
        directory = target / relative
        directory.mkdir(parents=True, exist_ok=True)
        keep = directory / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
            copied.append(str(keep))

    gitignore = target / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    missing_entries = [entry for entry in GITIGNORE_ENTRIES if entry not in existing.splitlines()]
    if missing_entries:
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        gitignore.write_text(
            existing + prefix + "\n# Zoo agent runtime\n" + "\n".join(missing_entries) + "\n",
            encoding="utf-8",
        )
        copied.append(str(gitignore))

    report = target / "agent" / "INSTALL_REPORT.md"
    relative_copied = [str(Path(path).relative_to(target)) for path in copied]
    relative_conflicts = sorted(
        {str(Path(path).relative_to(target)) for path in conflicts if Path(path).is_absolute()}
    )
    lines = [
        "# Agent System Installation Report",
        "",
        f"- Files created or updated: {len(relative_copied)}",
        f"- Existing conflicting files left untouched: {len(relative_conflicts)}",
        "",
        "## Conflicts requiring review",
    ]
    lines.extend((f"- `{path}`" for path in relative_conflicts) or ["- None."])
    lines.extend(
        [
            "",
            "## Next steps",
            "1. Review and merge any conflicts above; the installer never overwrites them.",
            "2. Run `python tools/agents/agentctl.py doctor --deep`.",
            "3. Run `python tools/agents/agentctl.py test`.",
            "4. Ask Claude Code to audit the existing project before creating a READY task.",
        ]
    )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Installed agent system into {target}")
    print(f"Created/updated: {len(relative_copied)}; conflicts preserved: {len(relative_conflicts)}")
    print(f"Report: {report}")
    return 1 if relative_conflicts else 0


def import_legacy_context(source: Path, *, root: Path = ROOT) -> int:
    """Copy only top-level Markdown history into inert, selectively-readable project memory."""
    source = source.resolve()
    root = root.resolve()
    if not source.exists() or not source.is_dir():
        print(f"Context source directory does not exist: {source}", file=sys.stderr)
        return 2
    if source == root:
        print("Context source must be outside the project root.", file=sys.stderr)
        return 2
    if not (root / "agent").is_dir():
        print("The agent system is not installed in the target project.", file=sys.stderr)
        return 2

    destination = root / "agent" / "legacy-context"
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[tuple[str, str, str]] = []
    unchanged: list[str] = []
    conflicts: list[str] = []
    secret_skips: list[str] = []

    for source_file in sorted(source.glob("*.md")):
        try:
            text = source_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            conflicts.append(source_file.name + " (unreadable)")
            continue
        if POTENTIAL_SECRET.search(text):
            secret_skips.append(source_file.name)
            continue
        destination_name = "PARENT-CLAUDE.md" if source_file.name.lower() == "claude.md" else source_file.name
        destination_file = destination / destination_name
        heading = next(
            (line[2:].strip() for line in text.splitlines() if line.startswith("# ")),
            source_file.stem,
        )
        if destination_file.exists():
            try:
                if destination_file.read_bytes() == source_file.read_bytes():
                    unchanged.append(destination_name)
                else:
                    conflicts.append(destination_name)
            except OSError:
                conflicts.append(destination_name)
            continue
        shutil.copy2(source_file, destination_file)
        copied.append((destination_name, heading, source_file.name))

    indexed_files = []
    for file in sorted(destination.glob("*.md")):
        if file.name == "IMPORT_INDEX.md":
            continue
        try:
            text = file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        heading = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), file.stem)
        indexed_files.append((file.name, heading))

    index = destination / "IMPORT_INDEX.md"
    lines = [
        "# Imported Legacy Context",
        "",
        f"- Source: `{source}`",
        f"- Imported Markdown files: {len(indexed_files)}",
        "- Role: historical evidence only; current code and approved agent records take precedence.",
        "- Usage: Claude should read this index first, then open only documents relevant to the current audit/task.",
        "",
        "## Available documents",
    ]
    lines.extend(f"- `{name}` — {heading}" for name, heading in indexed_files)
    if not indexed_files:
        lines.append("- None.")
    lines.extend(["", "## Skipped for possible credential content"])
    if secret_skips:
        lines.extend(f"- `{name}`" for name in secret_skips)
    else:
        lines.append("- None.")
    lines.extend(["", "## Conflicts left untouched"])
    if conflicts:
        lines.extend(f"- `{name}`" for name in conflicts)
    else:
        lines.append("- None.")
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Legacy context imported into {destination}")
    print(
        f"Copied: {len(copied)}; already present: {len(unchanged)}; "
        f"possible-secret skips: {len(secret_skips)}; conflicts: {len(conflicts)}"
    )
    print(f"Index: {index}")
    return 1 if secret_skips or conflicts else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentctl")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser("doctor", help="Check local tools and configuration")
    doctor_parser.add_argument("--deep", action="store_true", help="Also verify approved model IDs")
    route_parser = subparsers.add_parser("route", help="Preview usage-aware worker ordering")
    route_parser.add_argument("profile", choices=("SMALL", "MEDIUM", "HIGH"))
    subparsers.add_parser("status", help="Show task state and worker routes")
    validate_parser = subparsers.add_parser("validate", help="Validate a task contract")
    validate_parser.add_argument("task_id")
    validate_parser.add_argument("--folder", choices=("ready", "blocked"), default="ready")
    dispatch_parser = subparsers.add_parser("dispatch", help="Dispatch an approved implementation task")
    dispatch_parser.add_argument("task_id")
    recheck_parser = subparsers.add_parser("recheck", help="Re-run wrapper verification without a worker")
    recheck_parser.add_argument("task_id")
    subparsers.add_parser("test", help="Run agent-tool regression tests")
    init_parser = subparsers.add_parser("init", help="Safely install into an existing project")
    init_parser.add_argument("target", type=Path)
    init_parser.add_argument(
        "--init-git",
        action="store_true",
        help="Initialize Git when the target has no repository (never commits automatically).",
    )
    import_parser = subparsers.add_parser(
        "import-context", help="Safely archive top-level Markdown history from outside the project"
    )
    import_parser.add_argument("source", type=Path)
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return doctor(deep=args.deep)
    if args.command == "route":
        return show_route(args.profile)
    if args.command == "status":
        return show_status()
    if args.command == "test":
        return run_tests()
    if args.command == "init":
        return init_project(args.target, init_git=args.init_git)
    if args.command == "import-context":
        return import_legacy_context(args.source)
    if args.command == "validate":
        task_id = normalize_id(args.task_id)
        path = ROOT / "agent" / "tasks" / args.folder / f"{task_id}.md"
        statuses = ("READY",) if args.folder == "ready" else ("READY", "BLOCKED")
        try:
            _, allowed, profile = validate_task_path(task_id, path, accepted_statuses=statuses)
        except ValueError as error:
            print(f"INVALID {task_id}: {error}", file=sys.stderr)
            return 2
        print(f"VALID {task_id}: profile={profile}; allowed-paths={len(allowed)}")
        return 0

    from run_code_task import main as run_code_task

    task_id = normalize_id(args.task_id)
    return run_code_task([task_id, "--recheck"] if args.command == "recheck" else [task_id])


if __name__ == "__main__":
    raise SystemExit(main())
