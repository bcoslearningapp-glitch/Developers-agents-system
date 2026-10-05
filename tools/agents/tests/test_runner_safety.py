import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

AGENTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENTS_DIR))

import run_code_task
from common import sha_file, worker_changed_paths
from routing import WorkerSpec
from run_code_task import enforce_changed_paths, load_baseline, save_baseline
from usage_ledger import UsageLedger


class TestRunnerSafety(unittest.TestCase):
    def test_preexisting_unchanged_dirty_file_is_not_attributed(self):
        before = {"unrelated.txt": "same"}
        after = {"unrelated.txt": "same", "src/new.ts": "new"}
        self.assertEqual(worker_changed_paths(before, after), ["src/new.ts"])

    def test_allowed_change_is_not_violation(self):
        violations = enforce_changed_paths(
            "TASK-1000", ["src/new.ts"], ["src/**"], "agent/reports/implementation/TASK-1000.md"
        )
        self.assertEqual(violations, [])

    def test_outside_change_is_violation(self):
        violations = enforce_changed_paths(
            "TASK-1000", ["other/new.ts"], ["src/**"], "agent/reports/implementation/TASK-1000.md"
        )
        self.assertIn("outside task Allowed paths", violations[0])

    def test_governance_change_is_always_violation(self):
        violations = enforce_changed_paths(
            "TASK-1000", ["agent/STATE.md"], ["**"], "agent/reports/implementation/TASK-1000.md"
        )
        self.assertIn("worker-forbidden", violations[0])

    def test_missing_git_state_fails_closed(self):
        violations = enforce_changed_paths(
            "TASK-1000", None, ["src/**"], "agent/reports/implementation/TASK-1000.md"
        )
        self.assertTrue(violations)

    def test_baseline_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, path = save_baseline(
                "TASK-1000", {"dirty.txt": "hash"}, ["src/**"], root=root
            )
            state, allowed, dispatch_id, loaded_path = load_baseline("TASK-1000", root=root)
            self.assertEqual(state, {"dirty.txt": "hash"})
            self.assertEqual(allowed, ["src/**"])
            self.assertTrue(dispatch_id)
            self.assertEqual(path, loaded_path)

    def test_missing_baseline_refuses_recheck(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Missing or malformed"):
                load_baseline("TASK-1000", root=Path(directory))

    def test_opencode_attempt_uses_inline_restrictive_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "agent/tasks/active/TASK-1000.md"
            report = root / "agent/reports/implementation/TASK-1000.md"
            active.parent.mkdir(parents=True)
            report.parent.mkdir(parents=True)
            active.write_text(
                "# Task\n\n## Test / verification plan\n- `python -m unittest discover -s tests`\n",
                encoding="utf-8",
            )
            captured = {}

            def fake_run(command, **kwargs):
                captured["command"] = command
                captured["env"] = kwargs["env"]
                report.write_text("updated\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "{}\n", "")

            spec = WorkerSpec(
                "groq", "opencode", "Groq", "groq/openai/gpt-oss-120b"
            )
            ledger = UsageLedger(root / ".agent-worker/usage-ledger.json")
            with mock.patch.object(run_code_task.subprocess, "run", side_effect=fake_run):
                attempt = run_code_task._attempt_worker(
                    spec,
                    "TASK-1000",
                    "dispatch",
                    "implement",
                    ["src/**"],
                    "agent/reports/implementation/TASK-1000.md",
                    ledger,
                    report,
                    sha_file(report),
                    root=root,
                )
            self.assertEqual(attempt["classification"], "success")
            self.assertNotIn("OPENCODE_CONFIG", captured["env"])
            config = json.loads(captured["env"]["OPENCODE_CONFIG_CONTENT"])
            self.assertEqual(config["enabled_providers"], ["groq"])
            self.assertEqual(
                config["permission"]["bash"]["python -m unittest discover -s tests"],
                "allow",
            )
            self.assertIn("--pure", captured["command"])


if __name__ == "__main__":
    unittest.main()
