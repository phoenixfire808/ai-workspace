from __future__ import annotations

import unittest

from backend.graph import NodeExecutionError, _enforce_model_policy, _model_output
from backend.model_profiles import EndpointProfilePayload, save_endpoint_profile
from backend.ollama_control import DEFAULT_OLLAMA_MODEL, preflight_ollama_model


class ExactModelPolicyTests(unittest.TestCase):
    def test_approved_model_is_accepted(self) -> None:
        self.assertEqual(_enforce_model_policy(DEFAULT_OLLAMA_MODEL), DEFAULT_OLLAMA_MODEL)

    def test_alternate_model_fails_before_inventory_lookup(self) -> None:
        result = preflight_ollama_model("llama3.2:3b")
        self.assertEqual(result["status"], "model-policy-mismatch")
        self.assertEqual(result["failure_class"], "ollama_exact_model_required")
        self.assertFalse(result["exact_model"])

    def test_graph_rejects_alternate_provider(self) -> None:
        with self.assertRaises(NodeExecutionError) as raised:
            _model_output("hello", {"provider": "openrouter", "model": "provider/other-model"})
        self.assertEqual(raised.exception.failure_class, "model_policy_rejected")

    def test_graph_rejects_alternate_model(self) -> None:
        with self.assertRaises(NodeExecutionError) as raised:
            _enforce_model_policy("hermes3:latest")
        self.assertEqual(raised.exception.failure_class, "model_policy_rejected")

    def test_endpoint_save_rejects_non_ollama_provider(self) -> None:
        payload = EndpointProfilePayload(
            id="blocked-cloud",
            name="Blocked cloud",
            provider_kind="openrouter",
            base_url="https://openrouter.ai/api/v1",
            settings={"model": "provider/other-model"},
            enabled=False,
        )
        with self.assertRaisesRegex(ValueError, "exact local Ollama"):
            save_endpoint_profile(payload)


if __name__ == "__main__":
    unittest.main()
