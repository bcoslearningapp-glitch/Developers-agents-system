import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENTS_DIR))

from verification import independent_node_verification, select_node_scripts


class TestLongLivedCommandDenylist(unittest.TestCase):
    def test_refuses_each_reserved_script_name(self):
        scripts = {name: "harmless-placeholder" for name in ("dev", "start", "preview", "watch", "serve")}
        selected, refused, missing = select_node_scripts(
            scripts,
            "## Test / verification plan\n\n" + "\n".join(f"npm run {name}" for name in scripts),
        )
        self.assertEqual(selected, [])
        self.assertEqual(set(refused), set(scripts))
        self.assertEqual(missing, [])

    def test_refuses_long_lived_command_hidden_behind_alias(self):
        selected, refused, _ = select_node_scripts(
            {"smoke": "vite preview", "typecheck": "tsc --noEmit"},
            "## Test / verification plan\n\nnpm run smoke\nnpm run typecheck\n",
        )
        self.assertEqual(selected, ["typecheck"])
        self.assertEqual(refused, ["smoke"])

    def test_verification_uses_temp_project_and_mocked_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"preview": "vite preview", "typecheck": "tsc --noEmit"}}),
                encoding="utf-8",
            )

            calls = []

            def fake_run(command, **kwargs):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, "ok", "")

            result = independent_node_verification(
                "TASK-9999",
                "## Test / verification plan\n\nnpm run preview\nnpm run typecheck\n",
                root=root,
                run=fake_run,
            )
            self.assertTrue(result.ok)
            self.assertEqual(len(calls), 1)
            self.assertIn("typecheck", " ".join(calls[0]))
            summary = result.summary_path.read_text(encoding="utf-8")
            self.assertIn("Refused (long-lived command, never auto-run)", summary)
            self.assertIn("- npm run preview", summary)


if __name__ == "__main__":
    unittest.main()
