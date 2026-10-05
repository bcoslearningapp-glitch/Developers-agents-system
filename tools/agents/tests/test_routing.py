import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENTS_DIR))

from routing import (
    WorkerSpec,
    build_opencode_command,
    load_registry,
    missing_credentials,
    schedule_workers,
    write_claude_worker_settings,
    write_opencode_config,
)
from usage_ledger import UsageBudget, UsageLedger


class Clock:
    def __init__(self):
        self.value = dt.datetime(2026, 9, 7, 12, tzinfo=dt.timezone.utc)

    def __call__(self):
        return self.value


class TestRouting(unittest.TestCase):
    def test_opencode_command_uses_exact_model_id_once(self):
        spec = WorkerSpec(
            worker_id="groq",
            harness="opencode",
            provider="Groq",
            model="groq/openai/gpt-oss-120b",
        )
        command = build_opencode_command(spec, "do the task", Path("C:/project"))
        self.assertEqual(command[1], "run")
        self.assertEqual(command[command.index("--model") + 1], "groq/openai/gpt-oss-120b")
        self.assertNotIn("Groq/groq/openai/gpt-oss-120b", command)
        self.assertIn("--format", command)
        self.assertIn("--pure", command)

    def test_high_reasoning_uses_variant(self):
        spec = WorkerSpec(
            worker_id="google-high",
            harness="opencode",
            provider="Google",
            model="google/gemini-3.8-flash",
            variant="high",
        )
        command = build_opencode_command(spec, "task")
        self.assertEqual(command[command.index("--variant") + 1], "high")

    def test_all_required_credentials_must_be_present(self):
        spec = WorkerSpec(
            worker_id="cf",
            harness="opencode",
            provider="Cloudflare",
            model="cloudflare-workers-ai/@cf/openai/gpt-oss-120b",
            credential_env=("TOKEN", "ACCOUNT"),
        )
        self.assertEqual(missing_credentials(spec, {"TOKEN": "set"}), ["ACCOUNT"])

    def test_small_profile_is_local_first(self):
        root = Path(__file__).resolve().parents[3]
        registry, profiles = load_registry(root)
        with tempfile.TemporaryDirectory() as directory:
            ledger = UsageLedger(Path(directory) / "usage.json")
            route, _ = schedule_workers("SMALL", registry, profiles, ledger, environment={})
        self.assertEqual(route[0].model, "gpt-oss:20b")

    def test_balanced_route_rotates_after_usage(self):
        clock = Clock()
        with tempfile.TemporaryDirectory() as directory:
            ledger = UsageLedger(Path(directory) / "usage.json", now=clock)
            budget = UsageBudget()
            registry = {
                name: WorkerSpec(name, "opencode", name, f"{name}/model", budget=budget)
                for name in ("one", "two", "three")
            }
            profiles = {"MEDIUM": ["one", "two", "three"]}
            first, _ = schedule_workers("MEDIUM", registry, profiles, ledger, environment={})
            self.assertEqual(first[0].worker_id, "one")
            ledger.record_attempt("one", budget, classification="success")
            second, _ = schedule_workers("MEDIUM", registry, profiles, ledger, environment={})
            self.assertEqual(second[0].worker_id, "two")

    def test_provider_failure_activates_cooldown(self):
        clock = Clock()
        with tempfile.TemporaryDirectory() as directory:
            ledger = UsageLedger(Path(directory) / "usage.json", now=clock)
            budget = UsageBudget()
            spec = WorkerSpec("one", "opencode", "one", "one/model", budget=budget)
            ledger.record_attempt("one", budget, classification="provider_failure")
            route, skipped = schedule_workers(
                "MEDIUM", {"one": spec}, {"MEDIUM": ["one"]}, ledger, environment={}
            )
        self.assertEqual(route, [])
        self.assertIn("cooldown", skipped[0][1])

    def test_generated_config_denies_governance_and_allows_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = write_opencode_config(
                root,
                "dispatch",
                ["src/**"],
                "agent/reports/implementation/TASK-1234.md",
                provider_id="groq",
                shell_commands=["python -m pytest -q"],
            )
            config = json.loads(config_path.read_text(encoding="utf-8"))
            edit = config["permission"]["edit"]
            self.assertEqual(edit["src/**"], "allow")
            self.assertEqual(edit["agent/**"], "deny")
            self.assertEqual(edit["agent/reports/implementation/TASK-1234.md"], "allow")
            self.assertEqual(edit[".agent-worker/**"], "deny")
            self.assertEqual(config["permission"]["task"], "deny")
            self.assertEqual(config["permission"]["webfetch"], "deny")
            self.assertEqual(config["enabled_providers"], ["groq"])
            self.assertEqual(config["permission"]["bash"]["python -m pytest -q"], "allow")
            self.assertNotIn("python -m pytest -q *", config["permission"]["bash"])

    def test_generated_claude_settings_allow_only_exact_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = write_claude_worker_settings(root, "dispatch", ["cargo test --locked"])
            config = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(config["permissions"]["allow"], ["Bash(cargo test --locked)"])


if __name__ == "__main__":
    unittest.main()
