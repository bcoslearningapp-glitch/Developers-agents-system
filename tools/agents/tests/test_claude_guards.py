import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
GUARD = ROOT / ".claude" / "hooks" / "guard_claude_bash.py"
SETTINGS = ROOT / ".claude" / "settings.json"


def run_guard(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps({"tool_input": {"command": command}}),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


class TestClaudeBashGuard(unittest.TestCase):
    def test_allows_cross_platform_agentctl_spellings(self):
        commands = (
            "./tools/agents/agentctl validate TASK-0001",
            "./tools/agents/agentctl.cmd dispatch TASK-0001",
            "tools/agents/agentctl.cmd status",
            r".\tools\agents\agentctl.cmd validate TASK-0001",
            r"tools\agents\agentctl.cmd recheck TASK-0001",
            r'".\tools\agents\agentctl.cmd" test',
        )
        for command in commands:
            with self.subTest(command=command):
                result = run_guard(command)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")

    def test_rejects_unapproved_agentctl_subcommand(self):
        result = run_guard(r".\tools\agents\agentctl.cmd init C:\other-project")
        self.assertEqual(result.returncode, 0)
        decision = json.loads(result.stdout)
        self.assertEqual(
            decision["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )

    def test_settings_allow_the_same_cross_platform_spellings(self):
        allow = json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]["allow"]
        expected = {
            "Bash(./tools/agents/agentctl *)",
            "Bash(./tools/agents/agentctl.cmd *)",
            "Bash(tools/agents/agentctl *)",
            "Bash(tools/agents/agentctl.cmd *)",
            r"Bash(.\tools\agents\agentctl.cmd *)",
            r"Bash(tools\agents\agentctl.cmd *)",
        }
        self.assertTrue(expected.issubset(set(allow)))


if __name__ == "__main__":
    unittest.main()
