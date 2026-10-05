#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any, Iterator, Sequence

from common import (
    REQUIRED_REPORT_HEADINGS,
    ROOT,
    git_dirty_state,
    is_superseded_task,
    normalize_id,
    path_allowed,
    sha_file,
    task_section,
    worker_changed_paths,
)
from collect_evidence import collect_evidence
from routing import (
    FALLBACK_ELIGIBLE,
    WorkerSpec,
    build_ollama_command,
    build_opencode_command,
    classify_worker_failure,
    load_registry,
    redact_secrets,
    schedule_workers,
    write_claude_worker_settings,
    write_opencode_config,
)
from usage_ledger import UsageLedger, extract_token_usage, parse_retry_after_seconds
from validate_task import validate_task_path
from verification import (
    VerificationResult,
    determine_verification_scope,
    independent_project_verification,
    infra_verification,
    planned_verification_commands,
)


TASK_FOLDERS = ("ready", "active", "review", "blocked", "done", "backlog")
PROTECTED_PREFIXES = ("agent/", ".claude/", ".roo/")
PROTECTED_ROOT_FILES = {"AGENTS.md", "CLAUDE.md", "SETUP.md", "README.md"}


def fail_report(task_id: str, message: str, attempts: Sequence[dict[str, Any]], *, root: Path = ROOT) -> Path:
    output = root / "agent" / "reports" / "qa" / f"{task_id}-WORKER_FAILURE.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Worker Failure — {task_id}",
        "",
        f"- Time: {dt.datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Reason",
        message,
        "",
        "## Attempts",
    ]
    if not attempts:
        lines.append("- No worker process was launched.")
    for attempt in attempts:
        lines.extend(
            [
                f"### {attempt.get('worker_id') or attempt.get('model') or 'worker'}",
                f"- Harness: {attempt.get('harness', 'unknown')}",
                f"- Provider: {attempt.get('provider', 'unknown')}",
                f"- Model: {attempt.get('model', 'unknown')}",
                f"- Classification: {attempt.get('classification', 'unknown')}",
                f"- Exit: {attempt.get('returncode', 'not launched')}",
            ]
        )
        if attempt.get("log"):
            lines.append(f"- Log: `{attempt['log']}`")
        if attempt.get("reason"):
            lines.append(f"- Reason: {attempt['reason']}")
        lines.append("")
    lines.extend(
        [
            "## Recovery",
            "Preserve the worktree and baseline. Inspect the evidence before redispatching.",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def crash_report(task_id: str, error: BaseException, *, root: Path = ROOT) -> Path:
    output = root / "agent" / "reports" / "qa" / f"{task_id}-WRAPPER-CRASH.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f"# Unexpected Wrapper Crash — {task_id}\n\n"
        f"- Time: {dt.datetime.now().isoformat(timespec='seconds')}\n"
        "- Classification: **WRAPPER_CRASH**\n\n"
        "## Error\n"
        f"{type(error).__name__}: {error}\n\n"
        "## Traceback\n```text\n"
        + "".join(traceback.format_exception(type(error), error, error.__traceback__))
        + "```\n",
        encoding="utf-8",
    )
    return output


def lifecycle_paths(task_id: str) -> set[str]:
    return {f"agent/tasks/{folder}/{task_id}.md" for folder in TASK_FOLDERS}


def enforce_changed_paths(
    task_id: str,
    changed: Sequence[str] | None,
    allowed: Sequence[str],
    report_relative_path: str,
    *,
    extra_exempt: Sequence[str] = (),
) -> list[str]:
    if changed is None:
        return ["Git state unavailable; change-contract enforcement failed closed"]
    exempt_lifecycle = lifecycle_paths(task_id)
    exempt_paths = {
        path.replace("\\", "/").lstrip("./") for path in extra_exempt
    }
    violations: list[str] = []
    for path in changed:
        normalized = path.replace("\\", "/").lstrip("./")
        if (
            normalized == report_relative_path
            or normalized in exempt_paths
            or normalized.startswith(".agent-worker/")
        ):
            continue
        if normalized in exempt_lifecycle:
            continue
        if normalized.startswith(PROTECTED_PREFIXES) or normalized in PROTECTED_ROOT_FILES:
            violations.append(f"{normalized} (governance/context file is worker-forbidden)")
        elif not path_allowed(normalized, allowed):
            violations.append(f"{normalized} (outside task Allowed paths)")
    return violations


def verification_output_paths(task_id: str) -> set[str]:
    return {
        f"agent/reports/qa/{task_id}-INDEPENDENT-VERIFICATION.md",
        f"agent/reports/qa/{task_id}-INFRA-VERIFICATION.md",
    }


def production_changed_paths(task_id: str, changed: Sequence[str], report_relative_path: str) -> list[str]:
    lifecycle = lifecycle_paths(task_id)
    return [
        normalized
        for path in changed
        if (normalized := path.replace("\\", "/").lstrip("./")) != report_relative_path
        and normalized not in lifecycle
        and not normalized.startswith(".agent-worker/")
    ]


def _baseline_state_dir(root: Path) -> Path:
    return root / ".agent-worker" / "state"


def save_baseline(
    task_id: str,
    state: dict[str, str],
    allowed: Sequence[str],
    *,
    root: Path = ROOT,
) -> tuple[str, Path]:
    dispatch_id = dt.datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    state_dir = _baseline_state_dir(root)
    state_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = state_dir / f"{task_id}-{dispatch_id}.json"
    pointer_path = state_dir / f"{task_id}-current.json"
    payload = {
        "version": 1,
        "task_id": task_id,
        "dispatch_id": dispatch_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "allowed_paths": list(allowed),
        "git_state": state,
    }
    baseline_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pointer_path.write_text(
        json.dumps({"version": 1, "baseline": baseline_path.name}, indent=2) + "\n",
        encoding="utf-8",
    )
    return dispatch_id, baseline_path


def load_baseline(task_id: str, *, root: Path = ROOT) -> tuple[dict[str, str], list[str], str, Path]:
    state_dir = _baseline_state_dir(root)
    pointer_path = state_dir / f"{task_id}-current.json"
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        baseline_name = pointer["baseline"]
        if not isinstance(baseline_name, str) or Path(baseline_name).name != baseline_name:
            raise ValueError("invalid baseline filename")
        baseline_path = state_dir / baseline_name
        payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"Missing or malformed persisted baseline for {task_id}: {error}") from error

    if payload.get("version") != 1 or payload.get("task_id") != task_id:
        raise ValueError(f"Persisted baseline does not belong to {task_id}")
    git_state = payload.get("git_state")
    allowed = payload.get("allowed_paths")
    dispatch_id = payload.get("dispatch_id")
    if not isinstance(git_state, dict) or not all(
        isinstance(path, str) and isinstance(digest, str) for path, digest in git_state.items()
    ):
        raise ValueError("Persisted baseline git_state is invalid")
    if not isinstance(allowed, list) or not all(isinstance(pattern, str) for pattern in allowed):
        raise ValueError("Persisted baseline allowed_paths is invalid")
    if not isinstance(dispatch_id, str) or not dispatch_id:
        raise ValueError("Persisted baseline dispatch_id is invalid")
    return git_state, allowed, dispatch_id, baseline_path


def archive_baseline(task_id: str, baseline_path: Path, *, root: Path = ROOT) -> None:
    state_dir = _baseline_state_dir(root)
    archive_dir = state_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    if baseline_path.exists():
        shutil.move(str(baseline_path), str(archive_dir / baseline_path.name))
    pointer = state_dir / f"{task_id}-current.json"
    if pointer.exists():
        pointer.unlink()


def _archive_superseded_destination(path: Path, *, root: Path) -> None:
    if not path.exists():
        return
    if not is_superseded_task(path):
        raise RuntimeError(f"Refusing to overwrite live task record: {path.relative_to(root)}")
    relative = path.relative_to(root / "agent" / "tasks")
    archive = root / "agent" / "tasks" / "archive" / relative.parent
    archive.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    shutil.move(str(path), str(archive / f"{path.stem}-{stamp}{path.suffix}"))


def move_task(task_id: str, source_folder: str, destination_folder: str, *, root: Path = ROOT) -> Path:
    source = root / "agent" / "tasks" / source_folder / f"{task_id}.md"
    destination = root / "agent" / "tasks" / destination_folder / f"{task_id}.md"
    if not source.exists():
        raise RuntimeError(f"Task source does not exist: {source.relative_to(root)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    _archive_superseded_destination(destination, root=root)
    shutil.move(str(source), str(destination))
    return destination


@contextlib.contextmanager
def dispatch_lock(*, root: Path = ROOT) -> Iterator[None]:
    lock_path = root / ".agent-worker" / "dispatch.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError(
            f"Another dispatch appears active ({lock_path.relative_to(root)} exists)."
        ) from error
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    }
                )
                + "\n"
            )
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock_path.unlink()


def _legacy_workers() -> list[WorkerSpec] | None:
    raw = os.getenv("ZOO_WORKER_MODELS")
    if not raw:
        return None
    return [
        WorkerSpec(
            worker_id=f"ollama-manual-{index}",
            harness="ollama",
            provider="Ollama",
            model=model.strip(),
            local=model.strip() == "gpt-oss:20b",
        )
        for index, model in enumerate(raw.split(","), start=1)
        if model.strip()
    ]


def _prompt(task_id: str, report_relative_path: str) -> str:
    return (
        f"Implement exactly one approved software task: {task_id}. "
        f"Read AGENTS.md, .roo/rules-code/10-implementation-worker.md, and "
        f"agent/tasks/active/{task_id}.md. You are an implementation worker only: do not "
        "plan product scope, change architecture or decisions, launch subagents, browse the web, "
        "commit, push, deploy, or edit outside Allowed paths. Preserve existing work. Run only the "
        "task's permitted checks and write a truthful implementation report at "
        f"{report_relative_path}."
    )


def _attempt_worker(
    spec: WorkerSpec,
    task_id: str,
    dispatch_id: str,
    prompt: str,
    allowed: Sequence[str],
    report_relative_path: str,
    ledger: UsageLedger,
    report: Path,
    report_before: str,
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    work = root / ".agent-worker"
    log_dir = work / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{spec.provider}-{spec.model}")
    log = log_dir / f"{task_id}-{dispatch_id}-{safe_name}.log"
    environment = os.environ.copy()
    active_task = root / "agent" / "tasks" / "active" / f"{task_id}.md"
    task_text = active_task.read_text(encoding="utf-8")
    shell_commands, _, _ = planned_verification_commands(task_text, root=root)
    if spec.harness == "ollama":
        settings = write_claude_worker_settings(root, dispatch_id, shell_commands)
        command = build_ollama_command(spec, prompt, root, settings)
    elif spec.harness == "opencode":
        config = write_opencode_config(
            root,
            dispatch_id,
            allowed,
            report_relative_path,
            provider_id=spec.model.split("/", 1)[0],
            shell_commands=shell_commands,
        )
        environment["OPENCODE_CONFIG_CONTENT"] = config.read_text(encoding="utf-8")
        command = build_opencode_command(spec, prompt, root)
    else:
        raise ValueError(f"Unsupported harness: {spec.harness}")

    attempt: dict[str, Any] = {
        "worker_id": spec.worker_id,
        "harness": spec.harness,
        "provider": spec.provider,
        "model": spec.model,
        "log": str(log.relative_to(root)),
    }
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=int(os.getenv("ZOO_WORKER_TIMEOUT_SECONDS", "3600")),
            env=environment,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if completed.returncode == 0 and report.exists() and sha_file(report) != report_before:
            classification = "success"
        elif completed.returncode == 0:
            classification = "implementation_failure"
            attempt["reason"] = "Worker exited successfully but did not create or update its report"
        else:
            classification = classify_worker_failure(stdout, stderr)
        input_tokens, output_tokens = extract_token_usage(stdout) if spec.harness == "opencode" else (0, 0)
        retry_after = parse_retry_after_seconds(stdout + "\n" + stderr)
        ledger.record_attempt(
            spec.usage_key,
            spec.budget,
            classification=classification,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            retry_after_seconds=retry_after,
            default_cooldown_seconds=spec.default_cooldown_seconds,
        )
        log.write_text(
            redact_secrets(stdout, environment)
            + "\n--- STDERR ---\n"
            + redact_secrets(stderr, environment),
            encoding="utf-8",
        )
        attempt.update(returncode=completed.returncode, classification=classification)
    except FileNotFoundError as error:
        classification = "harness_unavailable"
        ledger.record_attempt(
            spec.usage_key,
            spec.budget,
            classification=classification,
            default_cooldown_seconds=spec.default_cooldown_seconds,
        )
        log.write_text(f"Worker executable not found: {error.filename or command[0]}\n", encoding="utf-8")
        attempt.update(returncode=127, classification=classification)
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else error.stdout
        stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else error.stderr
        classification = "implementation_failure"
        ledger.record_attempt(spec.usage_key, spec.budget, classification=classification)
        log.write_text(
            redact_secrets(stdout or "", environment)
            + "\n--- STDERR ---\n"
            + redact_secrets(stderr or "", environment)
            + "\n--- TIMEOUT ---\nWorker execution timed out.\n",
            encoding="utf-8",
        )
        attempt.update(returncode=124, classification=classification)
    return attempt


def _report_problem(report: Path) -> str | None:
    if not report.exists():
        return "Implementation report was not produced or updated"
    text = report.read_text(encoding="utf-8")
    missing = [heading for heading in REQUIRED_REPORT_HEADINGS if heading not in text]
    if missing:
        return "Implementation report missing: " + ", ".join(missing)
    status = task_section(text, "Status").upper()
    if "BLOCKED" in status or "FAILED" in status:
        return f"Implementation report status is not completed: {status or 'missing'}"
    return None


def _run_verification(
    task_id: str,
    task_text: str,
    allowed: Sequence[str],
    changed: Sequence[str],
    report_relative_path: str,
    *,
    root: Path,
) -> VerificationResult:
    production_changes = production_changed_paths(task_id, changed, report_relative_path)
    scope = determine_verification_scope(allowed, production_changes)
    if scope == "INFRA_ONLY":
        return infra_verification(task_id, root=root)
    if scope == "APP_ONLY":
        return independent_project_verification(task_id, task_text, root=root)
    infra = infra_verification(task_id, root=root)
    project = independent_project_verification(task_id, task_text, root=root)
    failures = [*infra.failures, *project.failures]
    return VerificationResult(
        infra.ok and project.ok,
        project.summary_path or infra.summary_path,
        failures,
    )


def execute_dispatch(task_id: str, *, root: Path = ROOT) -> int:
    ready = root / "agent" / "tasks" / "ready" / f"{task_id}.md"
    task_text, allowed, profile = validate_task_path(task_id, ready)
    if not (root / ".git").exists() and os.getenv("ZOO_ALLOW_NO_GIT") != "1":
        raise RuntimeError("Autonomous implementation requires Git for change-contract enforcement")

    for folder in ("active", "review", "blocked"):
        candidate = root / "agent" / "tasks" / folder / f"{task_id}.md"
        if candidate.exists() and not is_superseded_task(candidate):
            raise RuntimeError(f"{task_id} already has a live record in agent/tasks/{folder}/")

    active = move_task(task_id, "ready", "active", root=root)
    baseline_state = git_dirty_state(root)
    if baseline_state is None:
        move_task(task_id, "active", "blocked", root=root)
        raise RuntimeError("Git state could not be captured; dispatch refused")
    dispatch_id, baseline_path = save_baseline(task_id, baseline_state, allowed, root=root)

    report_relative = f"agent/reports/implementation/{task_id}.md"
    report = root / report_relative
    report_before = sha_file(report)
    prompt = _prompt(task_id, report_relative)
    prompt_path = root / ".agent-worker" / "prompts" / f"{task_id}-{dispatch_id}.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt + "\n", encoding="utf-8")

    ledger = UsageLedger(root / ".agent-worker" / "usage-ledger.json")
    workers = _legacy_workers()
    skipped: list[tuple[WorkerSpec, str]] = []
    if workers is None:
        registry, profiles = load_registry(root)
        workers, skipped = schedule_workers(profile, registry, profiles, ledger)

    attempts: list[dict[str, Any]] = [
        {
            "worker_id": spec.worker_id,
            "harness": spec.harness,
            "provider": spec.provider,
            "model": spec.model,
            "classification": "skipped",
            "reason": reason,
        }
        for spec, reason in skipped
    ]
    success = False
    for spec in workers:
        attempt = _attempt_worker(
            spec,
            task_id,
            dispatch_id,
            prompt,
            allowed,
            report_relative,
            ledger,
            report,
            report_before,
            root=root,
        )
        attempts.append(attempt)
        if attempt["classification"] == "success":
            success = True
            break
        if attempt["classification"] not in FALLBACK_ELIGIBLE:
            break

    current_state = git_dirty_state(root)
    changed = worker_changed_paths(baseline_state, current_state)
    violations = enforce_changed_paths(task_id, changed, allowed, report_relative)
    report_problem = _report_problem(report) if success else None
    verification = VerificationResult(False, None, ["Worker did not complete"])
    if success and not violations and not report_problem and changed is not None:
        verification_baseline = current_state
        verification = _run_verification(
            task_id, task_text, allowed, changed, report_relative, root=root
        )
        post_verification_state = git_dirty_state(root)
        verification_changes = worker_changed_paths(verification_baseline, post_verification_state)
        side_effect_violations = enforce_changed_paths(
            task_id,
            verification_changes,
            allowed,
            report_relative,
            extra_exempt=verification_output_paths(task_id),
        )
        violations.extend(
            violation for violation in side_effect_violations if violation not in violations
        )

    reasons: list[str] = []
    if not success:
        reasons.append("All eligible workers failed, were unavailable, or produced no updated report.")
    if violations:
        reasons.append("Out-of-contract changes detected:\n- " + "\n- ".join(violations))
    if report_problem:
        reasons.append(report_problem)
    if success and not violations and not report_problem and not verification.ok:
        reasons.append("Independent wrapper verification failed:\n- " + "\n- ".join(verification.failures))
        if verification.summary_path:
            reasons.append(f"Evidence: `{verification.summary_path.relative_to(root)}`")

    if reasons:
        failure = fail_report(task_id, "\n\n".join(reasons), attempts, root=root)
        if active.exists():
            move_task(task_id, "active", "blocked", root=root)
        print(f"BLOCKED {task_id}. See {failure.relative_to(root)}", file=sys.stderr)
        return 2

    move_task(task_id, "active", "review", root=root)
    archive_baseline(task_id, baseline_path, root=root)
    collect_evidence(task_id, root=root)
    winner = next(
        (attempt for attempt in reversed(attempts) if attempt.get("classification") == "success"), {}
    )
    print(
        f"READY_FOR_REVIEW {task_id} using {winner.get('provider', 'unknown')}/"
        f"{winner.get('model', 'unknown')}."
    )
    return 0


def execute_recheck(task_id: str, *, root: Path = ROOT) -> int:
    blocked = root / "agent" / "tasks" / "blocked" / f"{task_id}.md"
    task_text, allowed, _ = validate_task_path(
        task_id, blocked, accepted_statuses=("READY", "BLOCKED")
    )
    baseline_state, baseline_allowed, _, baseline_path = load_baseline(task_id, root=root)
    if allowed != baseline_allowed:
        raise ValueError("Blocked task Allowed paths do not match the persisted dispatch baseline")

    report_relative = f"agent/reports/implementation/{task_id}.md"
    report = root / report_relative
    report_problem = _report_problem(report)
    current_state = git_dirty_state(root)
    changed = worker_changed_paths(baseline_state, current_state)
    violations = enforce_changed_paths(task_id, changed, allowed, report_relative)
    if report_problem or violations or changed is None:
        reasons = []
        if report_problem:
            reasons.append(report_problem)
        if violations:
            reasons.append("Out-of-contract changes detected:\n- " + "\n- ".join(violations))
        failure = fail_report(task_id, "\n\n".join(reasons), [], root=root)
        print(f"BLOCKED {task_id}. See {failure.relative_to(root)}", file=sys.stderr)
        return 2

    verification_baseline = current_state
    verification = _run_verification(
        task_id, task_text, allowed, changed, report_relative, root=root
    )
    post_verification_state = git_dirty_state(root)
    verification_changes = worker_changed_paths(verification_baseline, post_verification_state)
    side_effect_violations = enforce_changed_paths(
        task_id,
        verification_changes,
        allowed,
        report_relative,
        extra_exempt=verification_output_paths(task_id),
    )
    if side_effect_violations:
        reason = "Verification created out-of-contract changes:\n- " + "\n- ".join(
            side_effect_violations
        )
        failure = fail_report(task_id, reason, [], root=root)
        print(f"BLOCKED {task_id}. See {failure.relative_to(root)}", file=sys.stderr)
        return 2
    if not verification.ok:
        reason = "Independent wrapper verification failed:\n- " + "\n- ".join(
            verification.failures
        )
        failure = fail_report(task_id, reason, [], root=root)
        print(f"BLOCKED {task_id}. See {failure.relative_to(root)}", file=sys.stderr)
        return 2

    move_task(task_id, "blocked", "review", root=root)
    archive_baseline(task_id, baseline_path, root=root)
    collect_evidence(task_id, root=root)
    print(f"READY_FOR_REVIEW {task_id} after wrapper-owned recheck.")
    return 0


def _recover_after_crash(task_id: str, *, root: Path) -> None:
    active = root / "agent" / "tasks" / "active" / f"{task_id}.md"
    if active.exists() and not is_superseded_task(active):
        try:
            move_task(task_id, "active", "blocked", root=root)
        except Exception:
            pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run-code-task")
    parser.add_argument("task_id")
    parser.add_argument("--recheck", action="store_true")
    args = parser.parse_args(argv)
    task_id = normalize_id(args.task_id)
    try:
        with dispatch_lock(root=ROOT):
            return execute_recheck(task_id, root=ROOT) if args.recheck else execute_dispatch(task_id, root=ROOT)
    except (ValueError, RuntimeError) as error:
        print(f"REFUSED {task_id}: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        report = crash_report(task_id, error, root=ROOT)
        _recover_after_crash(task_id, root=ROOT)
        print(f"WRAPPER_CRASH {task_id}. See {report.relative_to(ROOT)}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
