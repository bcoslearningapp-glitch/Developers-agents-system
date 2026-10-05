from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from common import ROOT
from usage_ledger import UsageBudget, UsageLedger


FALLBACK_ELIGIBLE = {"provider_failure", "credential_missing", "harness_unavailable"}


@dataclass(frozen=True)
class WorkerSpec:
    worker_id: str
    harness: str
    provider: str
    model: str
    credential_env: tuple[str, ...] = ()
    variant: str | None = None
    free: bool = True
    local: bool = False
    weight: float = 1.0
    budget: UsageBudget = UsageBudget()
    default_cooldown_seconds: int = 900
    usage_group: str | None = None

    @property
    def usage_key(self) -> str:
        return self.usage_group or self.worker_id


def _credentials(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise ValueError("credential_env must be a string, a string list, or null")


def _budget(value: Any) -> UsageBudget:
    if value is None:
        return UsageBudget()
    if not isinstance(value, dict):
        raise ValueError("budget must be an object")
    return UsageBudget(
        window_hours=max(1, int(value.get("window_hours", 24))),
        request_limit=(int(value["request_limit"]) if value.get("request_limit") else None),
        token_limit=(int(value["token_limit"]) if value.get("token_limit") else None),
        reserve_percent=max(0.0, min(100.0, float(value.get("reserve_percent", 10.0)))),
    )


def load_registry(root: Path = ROOT) -> tuple[dict[str, WorkerSpec], dict[str, list[str]]]:
    models_path = root / "tools" / "agents" / "worker_models.json"
    profiles_path = root / "tools" / "agents" / "worker_profiles.json"
    models_raw = json.loads(models_path.read_text(encoding="utf-8"))
    profiles_raw = json.loads(profiles_path.read_text(encoding="utf-8"))
    if not isinstance(models_raw, dict) or not isinstance(profiles_raw, dict):
        raise ValueError("Worker registry and profiles must be JSON objects")

    registry: dict[str, WorkerSpec] = {}
    for worker_id, raw in models_raw.items():
        if not isinstance(raw, dict):
            raise ValueError(f"Worker {worker_id} must be an object")
        harness = str(raw.get("harness", "")).lower()
        if harness not in {"ollama", "opencode"}:
            raise ValueError(f"Worker {worker_id} has unsupported harness {harness!r}")
        model = str(raw.get("model", "")).strip()
        if not model:
            raise ValueError(f"Worker {worker_id} has no model")
        if harness == "opencode" and "/" not in model:
            raise ValueError(f"OpenCode model {worker_id} must use an exact provider/model id")
        free = raw.get("free", True) is True
        if not free:
            raise ValueError(f"Paid worker {worker_id} is forbidden by policy")
        registry[worker_id] = WorkerSpec(
            worker_id=worker_id,
            harness=harness,
            provider=str(raw.get("provider", worker_id)),
            model=model,
            credential_env=_credentials(raw.get("credential_env")),
            variant=(str(raw["variant"]) if raw.get("variant") else raw.get("reasoning")),
            free=free,
            local=bool(raw.get("local", False)),
            weight=max(0.01, float(raw.get("weight", 1.0))),
            budget=_budget(raw.get("budget")),
            default_cooldown_seconds=max(30, int(raw.get("default_cooldown_seconds", 900))),
            usage_group=(str(raw["usage_group"]) if raw.get("usage_group") else None),
        )

    profiles: dict[str, list[str]] = {}
    for profile, worker_ids in profiles_raw.items():
        normalized = str(profile).upper()
        if normalized not in {"SMALL", "MEDIUM", "HIGH"}:
            raise ValueError(f"Unknown worker profile {profile!r}")
        if not isinstance(worker_ids, list) or not worker_ids:
            raise ValueError(f"Profile {normalized} must contain at least one worker")
        missing = [worker_id for worker_id in worker_ids if worker_id not in registry]
        if missing:
            raise ValueError(f"Profile {normalized} references unknown workers: {', '.join(missing)}")
        profiles[normalized] = list(worker_ids)
    return registry, profiles


def missing_credentials(spec: WorkerSpec, environment: Mapping[str, str] = os.environ) -> list[str]:
    return [name for name in spec.credential_env if not environment.get(name)]


def schedule_workers(
    profile: str,
    registry: Mapping[str, WorkerSpec],
    profiles: Mapping[str, Sequence[str]],
    ledger: UsageLedger,
    *,
    environment: Mapping[str, str] = os.environ,
) -> tuple[list[WorkerSpec], list[tuple[WorkerSpec, str]]]:
    profile = profile.upper()
    if profile not in profiles:
        raise ValueError(f"Unknown worker profile {profile}")

    candidates: list[tuple[int, WorkerSpec]] = []
    skipped: list[tuple[WorkerSpec, str]] = []
    for position, worker_id in enumerate(profiles[profile]):
        spec = registry[worker_id]
        missing = missing_credentials(spec, environment)
        if missing:
            skipped.append((spec, "missing credentials: " + ", ".join(missing)))
            continue
        if ledger.is_cooling_down(spec.usage_key, spec.budget):
            skipped.append((spec, "provider cooldown is active"))
            continue
        pressure = ledger.pressure(spec.usage_key, spec.budget)
        reserve_threshold = 1.0 - spec.budget.reserve_percent / 100.0
        has_known_limit = bool(spec.budget.request_limit or spec.budget.token_limit)
        if has_known_limit and pressure >= reserve_threshold:
            skipped.append((spec, f"configured {spec.budget.reserve_percent:g}% reserve reached"))
            continue
        candidates.append((position, spec))

    def sort_key(item: tuple[int, WorkerSpec]):
        position, spec = item
        # SMALL is deliberately local-first. Cloud candidates are fair-shared.
        local_rank = 0 if profile == "SMALL" and spec.local else 1
        pressure = ledger.pressure(spec.usage_key, spec.budget) / spec.weight
        return local_rank, pressure, ledger.last_used(spec.usage_key, spec.budget), position

    candidates.sort(key=sort_key)
    return [spec for _, spec in candidates], skipped


def build_ollama_command(
    spec: WorkerSpec,
    prompt: str,
    root: Path = ROOT,
    settings_path: Path | None = None,
) -> list[str]:
    ollama_bin = os.getenv("OLLAMA_BIN", "ollama")
    settings_path = settings_path or root / ".claude" / "worker-settings.json"
    return [
        ollama_bin,
        "launch",
        "claude",
        "--model",
        spec.model,
        "--yes",
        "--",
        "--restricted",
        "--settings",
        str(settings_path),
        "--tools",
        "Bash,Edit,Read,Write,Glob,Grep",
        "--permission-mode",
        "acceptEdits",
        "--permission-prompts",
        "none",
        "-p",
        prompt,
    ]


def _permission_patterns(shell_commands: Sequence[str]) -> list[str]:
    patterns: list[str] = []
    for command in shell_commands:
        if command not in patterns:
            patterns.append(command)
    return patterns


def write_claude_worker_settings(
    root: Path, dispatch_id: str, shell_commands: Sequence[str]
) -> Path:
    config_dir = root / ".agent-worker" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / f"claude-{dispatch_id}.json"
    allow = [f"Bash({pattern})" for pattern in _permission_patterns(shell_commands)]
    config = {"permissions": {"allow": allow}}
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def build_opencode_command(spec: WorkerSpec, prompt: str, root: Path = ROOT) -> list[str]:
    opencode_bin = os.getenv("OPENCODE_BIN", "opencode.cmd")
    command = [
        opencode_bin,
        "run",
        "--model",
        spec.model,
        "--format",
        "json",
        "--pure",
        "--agent",
        "build",
        "--dir",
        str(root),
    ]
    if spec.variant:
        command.extend(["--variant", spec.variant])
    command.append(prompt)
    return command


def write_opencode_config(
    root: Path,
    dispatch_id: str,
    allowed_paths: Sequence[str],
    report_relative_path: str,
    provider_id: str | None = None,
    shell_commands: Sequence[str] = (),
) -> Path:
    config_dir = root / ".agent-worker" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / f"opencode-{dispatch_id}.json"

    edit_permissions: dict[str, str] = {"*": "deny"}
    for pattern in allowed_paths:
        edit_permissions[pattern.replace("\\", "/").lstrip("./")] = "allow"
    for protected in (
        "agent/**",
        ".claude/**",
        ".roo/**",
        ".git/**",
        ".agent-worker/**",
        "AGENTS.md",
        "CLAUDE.md",
        "SETUP.md",
        "README.md",
    ):
        edit_permissions[protected] = "deny"
    edit_permissions[report_relative_path] = "allow"

    bash_permissions = {
        "*": "deny",
        "git status": "allow",
        "git status --short": "allow",
        "git diff": "allow",
        "git diff --check": "allow",
        "git diff --stat": "allow",
        "git diff --name-only": "allow",
        "npm install": "allow",
        "npm ci": "allow",
        "npm run build": "allow",
        "npm run test": "allow",
        "npm run lint": "allow",
        "npm run typecheck": "allow",
        "npm run check": "allow",
        "npm run format:check": "allow",
    }
    for pattern in _permission_patterns(shell_commands):
        bash_permissions[pattern] = "allow"
    for pattern in (
        "git push*",
        "git commit*",
        "git reset*",
        "git clean*",
        "git checkout*",
        "git restore*",
        "npm publish*",
        "pnpm publish*",
        "yarn npm publish*",
    ):
        bash_permissions[pattern] = "deny"

    config = {
        "$schema": "https://opencode.ai/config.json",
        "autoupdate": False,
        "share": "disabled",
        "snapshot": False,
        "permission": {
            "*": "deny",
            "read": {
                "*": "allow",
                ".env": "deny",
                ".env.*": "deny",
                "**/.env": "deny",
                "**/.env.*": "deny",
                "**/secrets/**": "deny",
                "**/credentials/**": "deny",
            },
            "edit": edit_permissions,
            "glob": "allow",
            "grep": "allow",
            "list": "allow",
            "bash": bash_permissions,
            "external_directory": "deny",
            "task": "deny",
            "webfetch": "deny",
            "websearch": "deny",
            "question": "deny",
            "doom_loop": "deny",
        },
    }
    if provider_id:
        config["enabled_providers"] = [provider_id]
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def classify_worker_failure(stdout: str, stderr: str) -> str:
    blob = ((stdout or "") + "\n" + (stderr or "")).lower()
    if any(
        signal in blob
        for signal in ("401", "403", "unauthorized", "forbidden", "invalid api key", "invalid token")
    ):
        return "credential_missing"
    if any(
        signal in blob
        for signal in ("429", "usage limit", "quota", "rate limit", "too many requests", "402")
    ):
        return "provider_failure"
    if re.search(r"\b5\d{2}\b", blob) and any(
        context in blob
        for context in ("internal server error", "bad gateway", "service unavailable", "temporarily unavailable")
    ):
        return "provider_failure"
    if any(
        signal in blob
        for signal in ("connection refused", "failed to connect", "connection reset", "request timeout")
    ):
        return "provider_failure"
    return "implementation_failure"


def redact_secrets(text: str, environment: Mapping[str, str] = os.environ) -> str:
    redacted = text
    secret_names = {
        name
        for name in environment
        if name.endswith(("_API_KEY", "_TOKEN", "_SECRET"))
        or name
        in {
            "OPENROUTER_API_KEY",
            "GROQ_API_KEY",
            "CLOUDFLARE_API_TOKEN",
            "CLOUDFLARE_ACCOUNT_ID",
            "GEMINI_API_KEY",
            "GOOGLE_GENERATIVE_AI_API_KEY",
        }
    }
    for name in secret_names:
        value = environment.get(name)
        if value and len(value) >= 6:
            redacted = redacted.replace(value, f"<redacted:{name}>")
    return redacted
