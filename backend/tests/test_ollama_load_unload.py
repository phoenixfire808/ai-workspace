import os
import unittest

from backend.ollama_control import (
    DEFAULT_OLLAMA_MODEL,
    preload_ollama_model,
    unload_ollama_model,
)


class ExactModelLoadUnloadTests(unittest.TestCase):
    """Lock the exact-model policy on the one-click preload / unload endpoints.

    The endpoints are reached from the UI's symmetric Load / Unload
    buttons. They deliberately bypass the chat-tool approval modal because
    the pair (load / unload) is the user's explicit on-demand request.
    The exact-model policy is still enforced so a non-exact tag is
    rejected with a structured failure rather than silently operating on
    the wrong model.
    """

    def setUp(self) -> None:
        self._env = {key: os.environ.get(key) for key in ("OLLAMA_BASE_URL",)}
        for key in self._env:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_preload_rejects_empty_model(self) -> None:
        result = preload_ollama_model("")
        self.assertEqual(result["status"], "invalid-model")
        self.assertEqual(result["failure_class"], "ollama_exact_model_required")
        self.assertEqual(result["mutation"], "none")

    def test_preload_rejects_non_exact_model(self) -> None:
        result = preload_ollama_model("llama3.2:3b")
        self.assertEqual(result["status"], "model-policy-mismatch")
        self.assertEqual(result["failure_class"], "ollama_exact_model_required")
        self.assertEqual(result["mutation"], "none")
        self.assertEqual(result["approved_model"], DEFAULT_OLLAMA_MODEL)

    def test_preload_accepts_exact_default_model_for_preflight_only(self) -> None:
        # Without a real Ollama backend the request must still pass the
        # exact-model policy gate and reach the network call. We can't
        # assert a successful preload here without a live Ollama; we only
        # assert that the exact default tag is not blocked at the gate.
        os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:11434"
        # The result will be timeout / unavailable / error depending on
        # whether Ollama is actually running, but it must NOT be a
        # policy-mismatch failure.
        result = preload_ollama_model(DEFAULT_OLLAMA_MODEL)
        self.assertNotEqual(result["status"], "model-policy-mismatch")
        self.assertNotEqual(result["status"], "invalid-model")
        self.assertTrue(result["exact_model"])

    def test_unload_rejects_empty_model(self) -> None:
        result = unload_ollama_model("")
        self.assertEqual(result["status"], "invalid-model")
        self.assertEqual(result["failure_class"], "ollama_exact_model_required")
        self.assertEqual(result["mutation"], "none")

    def test_unload_rejects_non_exact_model(self) -> None:
        result = unload_ollama_model("llama3.2:3b")
        self.assertEqual(result["status"], "model-policy-mismatch")
        self.assertEqual(result["failure_class"], "ollama_exact_model_required")
        self.assertEqual(result["mutation"], "none")
        self.assertEqual(result["approved_model"], DEFAULT_OLLAMA_MODEL)


if __name__ == "__main__":
    unittest.main()