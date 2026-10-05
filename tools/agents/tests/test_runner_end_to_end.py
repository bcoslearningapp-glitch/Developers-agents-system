import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

AGENTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENTS_DIR))

import run_code_task
from common import git_dirty_state
from routing import WorkerSpec
from verification import VerificationResult


TASK_ID = "TASK-9000"


def task_text(allowed="src/**"):
    return f"""# {TASK_ID}

## Status
READY

## Goal
Test the runner.

## Requirement sources
- Test fixture.

## Allowed paths
- `{allowed}`

## Worker profile
SMALL

## Acceptance criteria
- The fixture changes.

## Quality requirements
- Remain deterministic.

## Test / verification plan
- Wrapper test.

## Security / privacy
- No secrets.

## Out of scope
- Everything else.

## Decision gate
- Approved.
"""


def implementation_report():
    return f"""# Implementation Report — {TASK_ID}

## Status
COMPLETED

## Summary
Fixture completed.

## Files changed
- `src/result.txt`

## Acceptance criteria
- Passed.

## Commands / verification executed
- Wrapper-owned test.

## Security/privacy notes
- No secrets.

## Deviations from task/architecture
- None.

## Known limitations / residual risk
- None.
"""


class RunnerFixture:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for directory in (
            "agent/tasks/ready",
            "agent/tasks/active",
            "agent/tasks/review",
            "agent/tasks/blocked",
            "agent/tasks/done",
            "agent/tasks/backlog",
            "agent/reports/implementation",
            "agent/reports/qa",
            "src",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "agent/tasks/ready" / f"{TASK_ID}.md").write_text(task_text(), encoding="utf-8")
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=self.root, check=True)
        (self.root / ".gitignore").write_text(".agent-worker/\n", encoding="utf-8")
        (self.root / "baseline.txt").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore", "baseline.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=self.root, check=True, capture_output=True)
        return self

    def __exit__(self, *args):
        self.temp.cleanup()


class TestRunnerEndToEnd(unittest.TestCase):
    def _worker(self, *, forbidden=False):
        def fake_worker(spec, task_id, dispatch_id, prompt, allowed, report_relative, ledger, report, report_before, *, root):
            target = root / ("outside.txt" if forbidden else "src/result.txt")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("implemented\n", encoding="utf-8")
            report.write_text(implementation_report(), encoding="utf-8")
            return {
                "worker_id": spec.worker_id,
                "harness": spec.harness,
                "provider": spec.provider,
                "model": spec.model,
                "classification": "success",
                "returncode": 0,
            }

        return fake_worker

    def _patches(self, worker):
        spec = WorkerSpec("fixture", "ollama", "Fixture", "fixture-model", local=True)
        return (
            mock.patch.object(run_code_task, "_legacy_workers", return_value=[spec]),
            mock.patch.object(run_code_task, "_attempt_worker", side_effect=worker),
            mock.patch.object(
                run_code_task,
                "_run_verification",
                return_value=VerificationResult(True, None, []),
            ),
        )

    def test_success_moves_task_to_review(self):
        with RunnerFixture() as fixture:
            patches = self._patches(self._worker())
            with patches[0], patches[1], patches[2]:
                result = run_code_task.execute_dispatch(TASK_ID, root=fixture.root)
            self.assertEqual(result, 0)
            self.assertTrue((fixture.root / "agent/tasks/review" / f"{TASK_ID}.md").exists())
            self.assertTrue((fixture.root / "agent/reports/qa" / f"{TASK_ID}-EVIDENCE.md").exists())
            self.assertFalse((fixture.root / ".agent-worker/state" / f"{TASK_ID}-current.json").exists())

    def test_forbidden_change_blocks_task(self):
        with RunnerFixture() as fixture:
            patches = self._patches(self._worker(forbidden=True))
            with patches[0], patches[1], patches[2]:
                result = run_code_task.execute_dispatch(TASK_ID, root=fixture.root)
            self.assertEqual(result, 2)
            self.assertTrue((fixture.root / "agent/tasks/blocked" / f"{TASK_ID}.md").exists())
            failure = (fixture.root / "agent/reports/qa" / f"{TASK_ID}-WORKER_FAILURE.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("outside task Allowed paths", failure)

    def test_verification_side_effect_outside_contract_blocks_task(self):
        with RunnerFixture() as fixture:
            patches = self._patches(self._worker())

            def verification_with_side_effect(*args, **kwargs):
                (fixture.root / "verification-cache.out").write_text("unexpected\n", encoding="utf-8")
                return VerificationResult(True, None, [])

            with (
                patches[0],
                patches[1],
                mock.patch.object(
                    run_code_task, "_run_verification", side_effect=verification_with_side_effect
                ),
            ):
                result = run_code_task.execute_dispatch(TASK_ID, root=fixture.root)
            self.assertEqual(result, 2)
            failure = (fixture.root / "agent/reports/qa" / f"{TASK_ID}-WORKER_FAILURE.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("verification-cache.out", failure)

    def test_provider_failure_advances_to_next_worker(self):
        with RunnerFixture() as fixture:
            workers = [
                WorkerSpec("one", "opencode", "One", "one/model"),
                WorkerSpec("two", "opencode", "Two", "two/model"),
            ]
            attempts = []

            def failed_worker(spec, *args, **kwargs):
                attempts.append(spec.worker_id)
                return {
                    "worker_id": spec.worker_id,
                    "harness": spec.harness,
                    "provider": spec.provider,
                    "model": spec.model,
                    "classification": "provider_failure",
                    "returncode": 429,
                }

            with (
                mock.patch.object(run_code_task, "_legacy_workers", return_value=workers),
                mock.patch.object(run_code_task, "_attempt_worker", side_effect=failed_worker),
            ):
                result = run_code_task.execute_dispatch(TASK_ID, root=fixture.root)
            self.assertEqual(result, 2)
            self.assertEqual(attempts, ["one", "two"])

    def test_implementation_failure_does_not_model_hop(self):
        with RunnerFixture() as fixture:
            workers = [
                WorkerSpec("one", "opencode", "One", "one/model"),
                WorkerSpec("two", "opencode", "Two", "two/model"),
            ]
            attempts = []

            def failed_worker(spec, *args, **kwargs):
                attempts.append(spec.worker_id)
                return {
                    "worker_id": spec.worker_id,
                    "harness": spec.harness,
                    "provider": spec.provider,
                    "model": spec.model,
                    "classification": "implementation_failure",
                    "returncode": 1,
                }

            with (
                mock.patch.object(run_code_task, "_legacy_workers", return_value=workers),
                mock.patch.object(run_code_task, "_attempt_worker", side_effect=failed_worker),
            ):
                result = run_code_task.execute_dispatch(TASK_ID, root=fixture.root)
            self.assertEqual(result, 2)
            self.assertEqual(attempts, ["one"])

    def test_recheck_uses_persisted_baseline_and_moves_to_review(self):
        with RunnerFixture() as fixture:
            ready = fixture.root / "agent/tasks/ready" / f"{TASK_ID}.md"
            blocked = fixture.root / "agent/tasks/blocked" / f"{TASK_ID}.md"
            ready.replace(blocked)
            report = fixture.root / "agent/reports/implementation" / f"{TASK_ID}.md"
            report.write_text(implementation_report(), encoding="utf-8")
            before = git_dirty_state(fixture.root)
            _, _ = run_code_task.save_baseline(TASK_ID, before, ["src/**"], root=fixture.root)
            (fixture.root / "src/result.txt").write_text("implemented\n", encoding="utf-8")
            with mock.patch.object(
                run_code_task,
                "_run_verification",
                return_value=VerificationResult(True, None, []),
            ):
                result = run_code_task.execute_recheck(TASK_ID, root=fixture.root)
            self.assertEqual(result, 0)
            self.assertTrue((fixture.root / "agent/tasks/review" / f"{TASK_ID}.md").exists())


if __name__ == "__main__":
    unittest.main()
