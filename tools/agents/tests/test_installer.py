import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

AGENTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENTS_DIR))

from agentctl import _executable, import_legacy_context, init_project


class TestInstaller(unittest.TestCase):
    def test_inaccessible_executable_probe_does_not_crash(self):
        with (
            mock.patch("agentctl.Path.exists", side_effect=PermissionError("denied")),
            mock.patch("agentctl.shutil.which", return_value=None),
        ):
            self.assertIsNone(_executable("ollama", "C:/denied/ollama.exe"))

    def test_installs_generic_system_without_kaizen_context(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
            result = init_project(target)
            self.assertEqual(result, 0)
            self.assertTrue((target / "tools/agents/agentctl.py").exists())
            self.assertTrue((target / ".claude/settings.json").exists())
            state = (target / "agent/STATE.md").read_text(encoding="utf-8")
            self.assertNotIn("Kaizen", state)
            self.assertIn("existing project", state)

    def test_existing_instruction_file_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
            existing = target / "AGENTS.md"
            existing.write_text("user instructions\n", encoding="utf-8")
            result = init_project(target)
            self.assertEqual(result, 1)
            self.assertEqual(existing.read_text(encoding="utf-8"), "user instructions\n")
            report = (target / "agent/INSTALL_REPORT.md").read_text(encoding="utf-8")
            self.assertIn("AGENTS.md", report)

    def test_imports_only_safe_markdown_as_indexed_legacy_context(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "history"
            target = base / "project"
            source.mkdir()
            (target / "agent").mkdir(parents=True)
            (source / "CLAUDE.md").write_text("# Previous project memory\n", encoding="utf-8")
            (source / "TASK-1.md").write_text("# Previous task\n", encoding="utf-8")
            (source / "DEPLOY.md").write_text(
                "# Deploy\npassword = abcdefghijklmnop\n", encoding="utf-8"
            )
            (source / ".env").write_text("SECRET=value\n", encoding="utf-8")

            result = import_legacy_context(source, root=target)

            legacy = target / "agent/legacy-context"
            self.assertEqual(result, 1)
            self.assertTrue((legacy / "PARENT-CLAUDE.md").exists())
            self.assertTrue((legacy / "TASK-1.md").exists())
            self.assertFalse((legacy / "DEPLOY.md").exists())
            self.assertFalse((legacy / ".env").exists())
            index = (legacy / "IMPORT_INDEX.md").read_text(encoding="utf-8")
            self.assertIn("TASK-1.md", index)
            self.assertIn("DEPLOY.md", index)


if __name__ == "__main__":
    unittest.main()
