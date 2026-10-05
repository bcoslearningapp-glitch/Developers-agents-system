from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Sequence

from common import INFRA_PATH_PREFIXES, ROOT, task_section


LONG_LIVED_SCRIPT_NAMES = {"dev", "start", "preview", "watch", "serve"}
FORBIDDEN_SCRIPT_NAMES = LONG_LIVED_SCRIPT_NAMES | {"deploy", "publish", "release"}
LONG_LIVED_SCRIPT_CONTENTS = ("vite preview", "vite dev", "--watch", "nodemon")
SHELL_CONTROL_TOKENS = ("&&", "||", ";", "|", ">", "<", "`", "$(", "\n", "\r")
PYTHON_MODULES = {"compileall", "py_compile", "pytest", "unittest", "ruff", "mypy"}


@dataclass
class VerificationResult:
    ok: bool
    summary_path: Path | None
    failures: list[str] = field(default_factory=list)


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def _is_infra_path(value: str) -> bool:
    normalized = _normalize_path(value)
    return any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in INFRA_PATH_PREFIXES
    )


def _pattern_is_strictly_infra(value: str) -> bool:
    normalized = _normalize_path(value)
    wildcard_at = min(
        (position for marker in "*[?" if (position := normalized.find(marker)) >= 0),
        default=len(normalized),
    )
    literal_prefix = normalized[:wildcard_at].rstrip("/")
    return any(
        literal_prefix == prefix.rstrip("/") or literal_prefix.startswith(prefix)
        for prefix in INFRA_PATH_PREFIXES
    )


def determine_verification_scope(allowed_patterns: Sequence[str], changed_paths: Sequence[str] | None) -> str:
    """Return INFRA_ONLY, APP_ONLY, or MIXED using fail-closed structural checks."""
    if not allowed_patterns or not changed_paths:
        return "MIXED"

    declared_all_infra = all(_pattern_is_strictly_infra(pattern) for pattern in allowed_patterns)
    declared_no_infra = all(not _is_infra_path(pattern) for pattern in allowed_patterns)
    changed_all_infra = all(_is_infra_path(path) for path in changed_paths)
    changed_no_infra = all(not _is_infra_path(path) for path in changed_paths)

    if declared_all_infra and changed_all_infra:
        return "INFRA_ONLY"
    if declared_no_infra and changed_no_infra:
        return "APP_ONLY"
    return "MIXED"


def select_node_scripts(
    package_scripts: Mapping[str, str], task_text: str
) -> tuple[list[str], list[str], list[str]]:
    plan = task_section(task_text, "Test / verification plan").lower()
    explicit: list[str] = []
    for name in re.findall(r"\bnpm\s+run\s+([a-zA-Z0-9:_-]+)", plan):
        if name not in explicit:
            explicit.append(name)

    selected: list[str] = []
    refused: list[str] = []
    # The Claude-authored task contract is authoritative.  Do not silently add
    # every conventional script from package.json: doing so can duplicate a
    # shorthand command such as `npm test`, trigger expensive builds, or run a
    # gate that the task deliberately did not declare.
    for name in explicit:
        if name in selected or name in refused or name not in package_scripts:
            continue
        command = str(package_scripts.get(name, "")).lower()
        if name.lower() in FORBIDDEN_SCRIPT_NAMES or any(
            marker in command for marker in LONG_LIVED_SCRIPT_CONTENTS
        ):
            refused.append(name)
        else:
            selected.append(name)

    missing = [
        f"Task declares `npm run {name}`, but package.json has no `{name}` script"
        for name in explicit
        if name not in package_scripts
    ]
    return selected, refused, missing


def _program_name(value: str) -> str:
    return Path(value.replace("\\", "/")).name.lower().removesuffix(".cmd").removesuffix(".exe")


def _safe_command_parts(command: str) -> list[str] | None:
    """Accept bounded build/check commands without accepting a general shell program."""
    if not command or any(token in command for token in SHELL_CONTROL_TOKENS):
        return None
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        return None
    if not parts:
        return None

    lowered = [part.lower() for part in parts]
    program = _program_name(parts[0])
    tail = lowered[1:]
    joined = " ".join(lowered)
    if any(marker in joined for marker in LONG_LIVED_SCRIPT_CONTENTS):
        return None

    if program in {"npm", "pnpm", "yarn", "bun"}:
        if not tail:
            return None
        action = tail[0]
        if action == "run" and len(tail) >= 2:
            return None if tail[1] in FORBIDDEN_SCRIPT_NAMES else parts
        return parts if action in {"test", "install", "ci", "check", "lint"} else None

    if program in {"python", "python3", "py"}:
        return parts if len(tail) >= 2 and tail[0] == "-m" and tail[1] in PYTHON_MODULES else None
    if program in {"pytest", "ruff", "mypy"}:
        return parts
    if program in {"uv", "poetry"} and tail and tail[0] == "run":
        return parts if _safe_command_parts(" ".join(parts[2:])) else None
    if program == "cargo":
        return parts if tail and tail[0] in {"test", "check", "build", "clippy", "fmt"} else None
    if program == "go":
        return parts if tail and tail[0] in {"test", "build", "vet"} else None
    if program == "dotnet":
        return parts if tail and tail[0] in {"test", "build", "restore", "format"} else None
    if program in {"mvn", "mvnw"}:
        goals = [part for part in tail if not part.startswith("-")]
        return parts if goals and all(goal in {"test", "verify", "package"} for goal in goals) else None
    if program in {"gradle", "gradlew", "make"}:
        goals = [part for part in tail if not part.startswith("-")]
        return parts if goals and all(goal in {"test", "check", "build", "lint"} for goal in goals) else None
    if program == "git":
        if not tail or tail[0] not in {"status", "diff"}:
            return None
        forbidden_git_flags = ("--output", "--ext-diff", "--no-index")
        return None if any(part.startswith(forbidden_git_flags) for part in tail[1:]) else parts
    return None


def extract_safe_verification_commands(task_text: str) -> tuple[list[str], list[str]]:
    """Extract exact, Claude-authored checks from the task contract and reject unsafe ones."""
    plan = task_section(task_text, "Test / verification plan")
    candidates = re.findall(r"`([^`\r\n]+)`", plan)
    commands: list[str] = []
    refused: list[str] = []
    for candidate in candidates:
        command = candidate.strip()
        parts = _safe_command_parts(command)
        if parts is None:
            # Record command-looking spans, but ignore ordinary backticked filenames/identifiers.
            first = command.split(maxsplit=1)[0] if command else ""
            known = {
                "npm", "pnpm", "yarn", "bun", "python", "python3", "py", "pytest",
                "ruff", "mypy", "uv", "poetry", "cargo", "go", "dotnet", "mvn",
                "mvnw", "gradle", "gradlew", "make", "git",
            }
            if _program_name(first) in known and command not in refused:
                refused.append(command)
            continue
        normalized = " ".join(parts)
        if normalized not in commands:
            commands.append(normalized)
    return commands, refused


def planned_verification_commands(
    task_text: str, *, root: Path = ROOT
) -> tuple[list[str], list[str], list[str]]:
    commands, refused = extract_safe_verification_commands(task_text)
    failures: list[str] = []
    package_path = root / "package.json"
    if package_path.exists():
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
            scripts = package.get("scripts") or {}
            selected, refused_scripts, missing = select_node_scripts(scripts, task_text)
            failures.extend(missing)
            refused.extend(f"npm run {name}" for name in refused_scripts)
            for script in selected:
                command = f"npm run {script}"
                if command not in commands:
                    commands.append(command)
        except (OSError, json.JSONDecodeError) as error:
            failures.append(f"package.json could not be parsed: {error}")
    return commands, refused, failures


def _execution_command(command: str) -> list[str]:
    parts = _safe_command_parts(command)
    if parts is None:
        raise ValueError(f"Unsafe verification command: {command}")
    if _program_name(parts[0]) in {"python", "python3", "py"}:
        parts[0] = sys.executable
    if os.name == "nt" and _program_name(parts[0]) in {"npm", "pnpm", "yarn", "bun"}:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command]
    return parts


def independent_project_verification(
    tid: str,
    task_text: str,
    *,
    root: Path = ROOT,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> VerificationResult:
    summary = root / "agent" / "reports" / "qa" / f"{tid}-INDEPENDENT-VERIFICATION.md"
    log_dir = root / ".agent-worker" / "logs"
    summary.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    selected, refused, failures = planned_verification_commands(task_text, root=root)
    if not selected:
        failures.append(
            "No safe runnable verification command was declared or discovered; app verification fails closed"
        )
    results: list[tuple[str, int, str]] = []
    environment = os.environ.copy()
    environment["CI"] = "true"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPYCACHEPREFIX"] = str(log_dir.parent / "pycache" / tid)
    pytest_options = environment.get("PYTEST_ADDOPTS", "").strip()
    environment["PYTEST_ADDOPTS"] = (pytest_options + " -p no:cacheprovider").strip()

    for command in selected:
        log = log_dir / f"{tid}-verify-{re.sub(r'[^A-Za-z0-9_.-]+', '_', command)}.log"
        try:
            completed = run(
                _execution_command(command),
                cwd=root,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=int(os.getenv("ZOO_VERIFY_TIMEOUT_SECONDS", "600")),
                env=environment,
            )
            log.write_text(
                (completed.stdout or "") + "\n--- STDERR ---\n" + (completed.stderr or ""),
                encoding="utf-8",
            )
            results.append((command, completed.returncode, str(log.relative_to(root))))
            if completed.returncode != 0:
                failures.append(f"`{command}` failed with exit code {completed.returncode}")
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else error.stdout
            stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else error.stderr
            log.write_text(
                (stdout or "")
                + "\n--- STDERR ---\n"
                + (stderr or "")
                + "\n--- TIMEOUT ---\nVerification timed out.\n",
                encoding="utf-8",
            )
            results.append((command, 124, str(log.relative_to(root))))
            failures.append(f"`{command}` timed out")
        except OSError as error:
            log.write_text(f"Verifier error: {error}\n", encoding="utf-8")
            results.append((command, 125, str(log.relative_to(root))))
            failures.append(f"`{command}` could not be executed: {error}")

    lines = [
        f"# Independent Verification — {tid}",
        "",
        "- Authority: wrapper-owned verification; model reports are not trusted as proof.",
        "",
        "## Selected checks",
    ]
    lines.extend((f"- `{command}`" for command in selected))
    if not selected:
        lines.append("- No safe runnable project verification commands selected.")
    lines.extend(["", "## Results"])
    lines.extend(
        f"- **{'PASS' if code == 0 else 'FAIL'}** — `{command}` — exit `{code}` — log `{log}`"
        for command, code, log in results
    )
    if refused:
        lines.extend(["", "## Refused (long-lived command, never auto-run)"])
        lines.extend(f"- {name}" for name in refused)
    lines.extend(["", "## Verdict", "**PASS**" if not failures else "**FAIL**"])
    if failures:
        lines.extend(["", "## Failures"])
        lines.extend(f"- {failure}" for failure in failures)
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return VerificationResult(not failures, summary, failures)


# Compatibility for repositories that imported the original Node-specific name.
independent_node_verification = independent_project_verification


def infra_verification(
    tid: str,
    *,
    root: Path = ROOT,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> VerificationResult:
    summary = root / "agent" / "reports" / "qa" / f"{tid}-INFRA-VERIFICATION.md"
    log = root / ".agent-worker" / "logs" / f"{tid}-verify-agent-tools.log"
    summary.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    output_parts: list[str] = []

    with tempfile.TemporaryDirectory(prefix="zoo-agent-pyc-") as pycache:
        environment = os.environ.copy()
        environment["PYTHONPYCACHEPREFIX"] = pycache
        python_files = sorted((root / "tools" / "agents").rglob("*.py"))
        if python_files:
            completed = run(
                [sys.executable, "-m", "py_compile", *(str(path) for path in python_files)],
                cwd=root,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                env=environment,
            )
            output_parts.append("PY_COMPILE\n" + (completed.stdout or "") + (completed.stderr or ""))
            if completed.returncode:
                failures.append("Python compilation failed")

        agents_path = str(root / "tools" / "agents")
        existing_pythonpath = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            agents_path + os.pathsep + existing_pythonpath if existing_pythonpath else agents_path
        )
        completed = run(
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
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            env=environment,
        )
        output_parts.append("UNIT_TESTS\n" + (completed.stdout or "") + (completed.stderr or ""))
        if completed.returncode:
            failures.append("Agent-tool unit tests failed")

    log.write_text("\n\n".join(output_parts), encoding="utf-8")
    lines = [
        f"# Infrastructure Verification — {tid}",
        "",
        f"- Verdict: **{'PASS' if not failures else 'FAIL'}**",
        f"- Log: `{log.relative_to(root)}`",
    ]
    if failures:
        lines.extend(["", "## Failures"])
        lines.extend(f"- {failure}" for failure in failures)
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return VerificationResult(not failures, summary, failures)
