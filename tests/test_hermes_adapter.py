from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from backend.hermes_adapter import dispatch_hermes_skill, hermes_capability_audit, list_hermes_skills, read_hermes_skill, take_dispatch_process


class HermesAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "demo").mkdir()
        (self.root / "demo" / "SKILL.md").write_text("---\ndescription: Demo skill\n---\nUse bounded local context.\n", encoding="utf-8")
        self.previous_root = os.environ.get("HERMES_SKILLS_ROOT")
        self.previous_commands = os.environ.get("HERMES_SKILL_COMMANDS")
        self.previous_workspace = os.environ.get("WORKSPACE_ROOT")
        os.environ["HERMES_SKILLS_ROOT"] = str(self.root)
        os.environ["WORKSPACE_ROOT"] = str(self.root)

    def tearDown(self) -> None:
        if self.previous_root is None:
            os.environ.pop("HERMES_SKILLS_ROOT", None)
        else:
            os.environ["HERMES_SKILLS_ROOT"] = self.previous_root
        if self.previous_commands is None:
            os.environ.pop("HERMES_SKILL_COMMANDS", None)
        else:
            os.environ["HERMES_SKILL_COMMANDS"] = self.previous_commands
        if self.previous_workspace is None:
            os.environ.pop("WORKSPACE_ROOT", None)
        else:
            os.environ["WORKSPACE_ROOT"] = self.previous_workspace
        self.temp.cleanup()

    def test_inventory_and_read_receipts(self) -> None:
        inventory = json.loads(list_hermes_skills.invoke({"skill_name": ""}))
        self.assertEqual(inventory["status"], "completed")
        self.assertEqual(inventory["skill_count"], 1)
        self.assertTrue(inventory["inventory_id"])

        read = json.loads(read_hermes_skill.invoke({"skill_name": "demo"}))
        self.assertEqual(read["status"], "completed")
        self.assertEqual(read["skill_name"], "demo")
        self.assertEqual(len(read["skill_sha256"]), 64)
        self.assertFalse(read["truncated"])
        self.assertIn("bounded local context", read["content"])

    def test_read_rejects_traversal_with_failure_class(self) -> None:
        rejected = json.loads(read_hermes_skill.invoke({"skill_name": "../secrets"}))
        self.assertEqual(rejected["status"], "error")
        self.assertEqual(rejected["failure_class"], "hermes_skill_read_rejected")

    def test_capability_audit_is_truthful_and_mutation_disabled(self) -> None:
        os.environ.pop("HERMES_SKILL_COMMANDS", None)
        disabled = hermes_capability_audit()
        states = {item["capability"]: item for item in disabled["capabilities"]}
        self.assertTrue(states["inventory"]["ready"])
        self.assertFalse(states["dispatch_skill"]["ready"])
        self.assertEqual(states["dispatch_skill"]["disabled_reason"], "hermes_dispatch_targets_not_configured")
        self.assertFalse(states["profile_mutation"]["ready"])
        self.assertFalse(disabled["profile_mutation_supported"])

        os.environ["HERMES_SKILL_COMMANDS"] = json.dumps({"demo": [sys.executable, "-c", "pass"]})
        configured = hermes_capability_audit()
        self.assertEqual(configured["configured_dispatch_targets"], ["demo"])
        self.assertTrue(next(item for item in configured["capabilities"] if item["capability"] == "dispatch_skill")["ready"])

    def test_dispatch_receipt_uses_configured_stdin_adapter(self) -> None:
        command = [sys.executable, "-c", "import sys; sys.stdin.read()"]
        os.environ["HERMES_SKILL_COMMANDS"] = json.dumps({"demo": command})
        receipt = json.loads(dispatch_hermes_skill.invoke({"skill_name": "demo", "prompt": "local prompt"}))
        self.assertEqual(receipt["status"], "queued")
        self.assertEqual(receipt["prompt_chars"], len("local prompt"))
        process = take_dispatch_process(receipt["process_id"])
        self.assertIsNotNone(process)
        assert process is not None
        process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
