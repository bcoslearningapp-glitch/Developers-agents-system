import os
import unittest
import sys
from pathlib import Path

AGENTS_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENTS_PATH))

from routing import classify_worker_failure, redact_secrets
from verification import (
    determine_verification_scope,
    extract_safe_verification_commands,
    independent_node_verification,
    planned_verification_commands,
)

class TestWorkerLogic(unittest.TestCase):
    def test_classify_quota_failure(self):
        out = classify_worker_failure('Error 429: Too many requests', '')
        self.assertEqual(out, 'provider_failure')

    def test_classify_auth_failure(self):
        out = classify_worker_failure('', '401 Unauthorized')
        self.assertEqual(out, 'credential_missing')

    def test_redact_secrets(self):
        os.environ['TEST_API_KEY'] = 'supersecretvalue'
        text = 'The key is supersecretvalue and should be hidden.'
        redacted = redact_secrets(text)
        self.assertNotIn('supersecretvalue', redacted)
        self.assertIn('<redacted:TEST_API_KEY>', redacted)
        # Cleanup
        del os.environ['TEST_API_KEY']

    def test_determine_verification_scope_infra_only(self):
        allowed = ['tools/agents/**']
        changed = ['tools/agents/run_code_task.py']
        scope = determine_verification_scope(allowed, changed)
        self.assertEqual(scope, 'INFRA_ONLY')

    def test_determine_verification_scope_app_only(self):
        allowed = ['src/**']
        changed = ['src/main.py']
        scope = determine_verification_scope(allowed, changed)
        self.assertEqual(scope, 'APP_ONLY')

    def test_determine_verification_scope_mixed(self):
        allowed = ['tools/agents/**', 'src/**']
        changed = ['tools/agents/run_code_task.py', 'src/main.py']
        scope = determine_verification_scope(allowed, changed)
        self.assertEqual(scope, 'MIXED')

    def test_zero_changes_fail_closed_to_mixed(self):
        self.assertEqual(determine_verification_scope(['tools/agents/**'], []), 'MIXED')

    def test_extracts_common_stack_command(self):
        commands, refused = extract_safe_verification_commands(
            "## Test / verification plan\n\n- `python -m pytest -q`\n"
        )
        self.assertEqual(commands, ["python -m pytest -q"])
        self.assertEqual(refused, [])

    def test_refuses_compound_or_deploy_command(self):
        commands, refused = extract_safe_verification_commands(
            "## Test / verification plan\n\n"
            "- `python -m pytest && git push`\n"
            "- `npm run deploy`\n"
        )
        self.assertEqual(commands, [])
        self.assertEqual(refused, ["python -m pytest && git push", "npm run deploy"])

    def test_non_node_project_executes_declared_check(self):
        import subprocess
        import tempfile

        calls = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def fake_run(command, **kwargs):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, "ok", "")

            result = independent_node_verification(
                "TASK-8888",
                "## Test / verification plan\n\n- `python -m unittest discover -s tests`\n",
                root=root,
                run=fake_run,
            )
        self.assertTrue(result.ok)
        self.assertEqual(len(calls), 1)
        self.assertIn("unittest", calls[0])

    def test_project_without_runnable_check_fails_closed(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            result = independent_node_verification(
                "TASK-8888",
                "## Test / verification plan\n\n- Inspect manually.\n",
                root=Path(directory),
            )
        self.assertFalse(result.ok)
        self.assertIn("fails closed", result.failures[0])

    def test_node_verification_runs_only_declared_commands_once(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "lint": "eslint .",
                            "typecheck": "tsc --noEmit",
                            "test": "vitest run",
                            "build": "next build",
                        }
                    }
                ),
                encoding="utf-8",
            )
            commands, refused, failures = planned_verification_commands(
                "## Test / verification plan\n\n"
                "- `pnpm install --frozen-lockfile`\n"
                "- `npm run lint`\n"
                "- `npm run typecheck`\n"
                "- `npm test`\n",
                root=root,
            )

        self.assertEqual(
            commands,
            [
                "pnpm install --frozen-lockfile",
                "npm run lint",
                "npm run typecheck",
                "npm test",
            ],
        )
        self.assertEqual(refused, [])
        self.assertEqual(failures, [])

if __name__ == '__main__':
    unittest.main()
