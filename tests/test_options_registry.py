from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import get_args

_OWNS_TEST_ROOT = "backend.main" not in sys.modules
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="mo-options-registry-")) if _OWNS_TEST_ROOT else None
if _TEST_ROOT is not None:
    os.environ["WORKSPACE_ROOT"] = str(_TEST_ROOT)
    os.environ["WORKSPACE_DATABASE_URL"] = f"sqlite:///{(_TEST_ROOT / 'options.db').as_posix()}"

from fastapi.testclient import TestClient

from backend.main import app
from backend.options_registry import CONTROL_SURFACES, OPTIONS, option_inventory, option_inventory_markdown, validate_registry
from backend.schema import NodeType


class OptionRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def test_registry_is_unique_complete_and_honest(self) -> None:
        inventory = option_inventory()
        self.assertEqual(inventory["mutation"], "none")
        self.assertEqual(inventory["phase"], 0)
        self.assertEqual(inventory["invalid"], [])
        self.assertEqual(inventory["summary"]["invalid"], 0)
        self.assertEqual(inventory["summary"]["node_types"], len(get_args(NodeType)))
        option_ids = [item.option_id for item in OPTIONS]
        self.assertEqual(len(option_ids), len(set(option_ids)))
        represented = {item.subgroup for item in OPTIONS if item.category == "nodes"}
        self.assertEqual(represented, set(get_args(NodeType)))
        self.assertTrue(all(surface.option_ids or surface.exemption_reason for surface in CONTROL_SURFACES))

    def test_invalid_default_is_rejected(self) -> None:
        item = OPTIONS[0].model_copy(update={"default": "not-a-choice"})
        failures = validate_registry((item,))
        self.assertIn("invalid_default", {entry["failure_class"] for entry in failures})

    def test_duplicate_id_is_rejected(self) -> None:
        failures = validate_registry((OPTIONS[0], OPTIONS[0]))
        self.assertIn("duplicate_option_id", {entry["failure_class"] for entry in failures})

    def test_unsafe_inheritance_is_rejected(self) -> None:
        source = next(item for item in OPTIONS if item.effect == "external_publication")
        unsafe = source.model_copy(update={"inheritance": "safe"})
        failures = validate_registry((unsafe,))
        self.assertIn("unsafe_inheritance", {entry["failure_class"] for entry in failures})

    def test_ready_without_evidence_is_rejected(self) -> None:
        source = next(item for item in OPTIONS if item.status == "ready")
        unsupported = source.model_copy(update={"evidence": []})
        failures = validate_registry((unsupported,))
        self.assertIn("ready_without_evidence", {entry["failure_class"] for entry in failures})

    def test_markdown_uses_same_registry(self) -> None:
        inventory = option_inventory()
        markdown = option_inventory_markdown(inventory)
        self.assertIn("Phase 0 is a read-only contract inventory", markdown)
        self.assertIn("Control-surface coverage", markdown)
        for item in OPTIONS:
            self.assertIn(f"`{item.option_id}`", markdown)
        self.assertIn("Invalid registry rows: **0**", markdown)

    def test_option_api_is_read_only_and_honest(self) -> None:
        response = self.client.get("/api/options")
        self.assertEqual(response.status_code, 200, response.text)
        inventory = response.json()
        self.assertEqual(inventory["mutation"], "none")
        self.assertEqual(inventory["invalid"], [])
        self.assertEqual(inventory["summary"]["node_types"], 20)
        self.assertEqual(len(inventory["definitions"]), len(OPTIONS))
        self.assertEqual(self.client.post("/api/options", json={"option_id": "run.max_parallel", "value": 8}).status_code, 405)
        markdown = self.client.get("/api/options/export.md")
        self.assertEqual(markdown.status_code, 200, markdown.text)
        self.assertIn("M⊕ option registry", markdown.text)
        matrix = self.client.get("/api/capabilities/matrix")
        self.assertEqual(matrix.status_code, 200, matrix.text)
        self.assertEqual(len(matrix.json()["options"]), len(OPTIONS))
        self.assertIn("options", matrix.json()["summary"])


def tearDownModule() -> None:
    if not _OWNS_TEST_ROOT or _TEST_ROOT is None:
        return
    from backend.database import engine

    engine.dispose()
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
