from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

if "backend.main" not in sys.modules:
    _TEST_ROOT = Path(tempfile.mkdtemp(prefix="mo-phase26-controls-"))
    os.environ["WORKSPACE_ROOT"] = str(_TEST_ROOT)
    os.environ["WORKSPACE_DATABASE_URL"] = f"sqlite:///{(_TEST_ROOT / 'phase26.db').as_posix()}"

from fastapi.testclient import TestClient

from backend.main import app


class Phase26ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_01_capability_matrix_requires_evidence_for_pass(self) -> None:
        response = self.client.get("/api/capabilities/matrix")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertGreaterEqual(len(payload["nodes"]), 20)
        self.assertGreaterEqual(len(payload["resources"]), 200)
        self.assertGreaterEqual(len(payload["routes"]), 40)
        self.assertEqual(payload["registry_honesty"]["invalid_ready"], [])
        for section in ("nodes", "resources", "routes", "approvals"):
            for row in payload[section]:
                self.assertIn(row["status"], {"PASS", "BLOCKED", "DISABLED", "FAIL"})
                if row["status"] == "PASS":
                    self.assertTrue(row["evidence"], row)
        markdown = self.client.get("/api/capabilities/export.md")
        self.assertEqual(markdown.status_code, 200, markdown.text)
        self.assertIn("Registration alone is BLOCKED", markdown.text)

    def test_02_openrouter_requires_alias_exact_model_and_explicit_fallback(self) -> None:
        profiles = self.client.get("/api/model-endpoints").json()["profiles"]
        profile = next(item for item in profiles if item["id"] == "openrouter")
        disabled = self.client.get("/api/model-endpoints/openrouter/preflight")
        self.assertEqual(disabled.status_code, 200, disabled.text)
        self.assertFalse(disabled.json()["ready"])
        self.assertEqual(disabled.json()["reason"], "profile_disabled")
        base = {**profile, "settings": {**profile["settings"], "fallback_policy": "explicit_only"}}
        missing_model = self.client.post("/api/model-endpoints", json={**base, "enabled": True, "settings": {**base["settings"], "model": ""}})
        self.assertEqual(missing_model.status_code, 400, missing_model.text)
        raw_secret = self.client.post("/api/model-endpoints", json={**base, "credential_alias": "not-an-alias", "enabled": False})
        self.assertEqual(raw_secret.status_code, 400, raw_secret.text)
        wrong_fallback = self.client.post("/api/model-endpoints", json={**base, "enabled": False, "settings": {**base["settings"], "model": "vendor/model", "fallback_policy": "automatic"}})
        self.assertEqual(wrong_fallback.status_code, 400, wrong_fallback.text)
        saved = self.client.post("/api/model-endpoints", json={**base, "credential_alias": "env:OPENROUTER_API_KEY", "enabled": False, "settings": {**base["settings"], "model": "vendor/model", "fallback_policy": "explicit_only"}})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["settings"]["model"], "vendor/model")
        self.assertNotIn("credential", str(saved.json().get("credential_value", "")))
        restore = self.client.post("/api/model-endpoints", json={**base, "credential_alias": "env:OPENROUTER_API_KEY", "enabled": False, "settings": {**base["settings"], "model": "", "fallback_policy": "explicit_only"}})
        self.assertEqual(restore.status_code, 200, restore.text)

    def test_03_feedback_is_local_and_publisher_disabled_by_default(self) -> None:
        previous = os.environ.pop("WORKSPACE_FEEDBACK_PUBLISHER", None)
        try:
            created = self.client.post("/api/feedback", json={"kind": "feature", "title": "Local acceptance draft", "description": "Persist this only in the local test database.", "steps": "No external send."})
            self.assertEqual(created.status_code, 200, created.text)
            feedback_id = created.json()["id"]
            self.assertEqual(created.json()["status"], "draft")
            preview = self.client.get(f"/api/feedback/{feedback_id}/publish-preview")
            self.assertEqual(preview.status_code, 200, preview.text)
            self.assertEqual(preview.json()["status"], "blocked")
            self.assertEqual(preview.json()["failure_class"], "feedback_publisher_disabled")
            self.assertEqual(preview.json()["mutation"], "none")
            publish = self.client.post(f"/api/feedback/{feedback_id}/publish", json={"confirmation": "PUBLISH_TO_GITHUB"})
            self.assertEqual(publish.status_code, 503, publish.text)
            self.assertEqual(self.client.get("/api/feedback").status_code, 200)
        finally:
            if previous is not None:
                os.environ["WORKSPACE_FEEDBACK_PUBLISHER"] = previous

    def test_04_gpu_inventory_is_bounded_and_read_only(self) -> None:
        response = self.client.get("/api/hardware/gpus")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mutation"], "none")
        self.assertEqual(payload["process_fields"], ["pid", "gpu_uuid", "process_name", "used_memory_mb"])
        self.assertLessEqual(len(payload["devices"]), 16)
        self.assertLessEqual(len(payload["processes"]), 128)
        self.assertTrue(all(set(item) == set(payload["process_fields"]) for item in payload["processes"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
