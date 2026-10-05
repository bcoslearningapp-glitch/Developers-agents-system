from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


UTC = dt.timezone.utc


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def _parse_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iso(value: dt.datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z") if value else None


@dataclass(frozen=True)
class UsageBudget:
    window_hours: int = 24
    request_limit: int | None = None
    token_limit: int | None = None
    reserve_percent: float = 10.0


class UsageLedger:
    VERSION = 1

    def __init__(self, path: Path, *, now=utc_now):
        self.path = path
        self._now = now
        self.data: dict[str, Any] = {"version": self.VERSION, "workers": {}}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if loaded.get("version") == self.VERSION and isinstance(loaded.get("workers"), dict):
            self.data = loaded

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def _entry(self, worker_id: str, budget: UsageBudget) -> dict[str, Any]:
        workers = self.data.setdefault("workers", {})
        entry = workers.setdefault(
            worker_id,
            {
                "window_started_at": _iso(self._now()),
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "successes": 0,
                "provider_failures": 0,
                "implementation_failures": 0,
                "consecutive_provider_failures": 0,
                "last_used_at": None,
                "last_success_at": None,
                "cooldown_until": None,
            },
        )
        started = _parse_time(entry.get("window_started_at"))
        if started is None or self._now() - started >= dt.timedelta(hours=budget.window_hours):
            preserved_cooldown = entry.get("cooldown_until")
            workers[worker_id] = {
                "window_started_at": _iso(self._now()),
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "successes": 0,
                "provider_failures": 0,
                "implementation_failures": 0,
                "consecutive_provider_failures": 0,
                "last_used_at": entry.get("last_used_at"),
                "last_success_at": entry.get("last_success_at"),
                "cooldown_until": preserved_cooldown,
            }
            entry = workers[worker_id]
        return entry

    def is_cooling_down(self, worker_id: str, budget: UsageBudget) -> bool:
        until = _parse_time(self._entry(worker_id, budget).get("cooldown_until"))
        return bool(until and until > self._now())

    def pressure(self, worker_id: str, budget: UsageBudget) -> float:
        entry = self._entry(worker_id, budget)
        ratios = []
        if budget.request_limit:
            ratios.append(entry["requests"] / budget.request_limit)
        if budget.token_limit:
            ratios.append(
                (entry["input_tokens"] + entry["output_tokens"]) / budget.token_limit
            )
        if ratios:
            return max(ratios)
        # Unknown provider quota: fair-share by successful/attempted requests.
        return float(entry["requests"])

    def last_used(self, worker_id: str, budget: UsageBudget) -> dt.datetime:
        return _parse_time(self._entry(worker_id, budget).get("last_used_at")) or dt.datetime.min.replace(
            tzinfo=UTC
        )

    def record_attempt(
        self,
        worker_id: str,
        budget: UsageBudget,
        *,
        classification: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        retry_after_seconds: int | None = None,
        default_cooldown_seconds: int = 900,
    ) -> None:
        entry = self._entry(worker_id, budget)
        now = self._now()
        entry["requests"] += 1
        entry["input_tokens"] += max(0, int(input_tokens))
        entry["output_tokens"] += max(0, int(output_tokens))
        entry["last_used_at"] = _iso(now)
        if classification == "success":
            entry["successes"] += 1
            entry["consecutive_provider_failures"] = 0
            entry["last_success_at"] = _iso(now)
            entry["cooldown_until"] = None
        elif classification in {"provider_failure", "credential_missing", "harness_unavailable"}:
            entry["provider_failures"] += 1
            entry["consecutive_provider_failures"] += 1
            multiplier = min(8, 2 ** max(0, entry["consecutive_provider_failures"] - 1))
            seconds = retry_after_seconds or default_cooldown_seconds * multiplier
            entry["cooldown_until"] = _iso(now + dt.timedelta(seconds=seconds))
        else:
            entry["implementation_failures"] += 1
        self.save()


def parse_retry_after_seconds(text: str) -> int | None:
    patterns = (
        r"retry[- ]after\s*[:=]?\s*(\d+)\s*(?:seconds?|secs?|s)\b",
        r"try again in\s+(\d+)\s*(?:seconds?|secs?|s)\b",
    )
    lowered = text.lower()
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return max(1, int(match.group(1)))
    return None


def extract_token_usage(json_lines: str) -> tuple[int, int]:
    """Best-effort OpenCode JSON event parser; unknown event shapes safely count as zero."""
    input_tokens = 0
    output_tokens = 0

    def visit(value: Any) -> None:
        nonlocal input_tokens, output_tokens
        if isinstance(value, Mapping):
            for key, nested in value.items():
                normalized = str(key).lower().replace("-", "_")
                if isinstance(nested, (int, float)):
                    if normalized in {"input_tokens", "prompt_tokens", "input"}:
                        input_tokens = max(input_tokens, int(nested))
                    elif normalized in {"output_tokens", "completion_tokens", "output"}:
                        output_tokens = max(output_tokens, int(nested))
                else:
                    visit(nested)
        elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            for nested in value:
                visit(nested)

    for line in json_lines.splitlines():
        try:
            visit(json.loads(line))
        except json.JSONDecodeError:
            continue
    return input_tokens, output_tokens
