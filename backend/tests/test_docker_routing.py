import os
import unittest

from backend.ollama_control import safe_ollama_base_url
from backend.web_research import _searxng_url


class DockerRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = {key: os.environ.get(key) for key in ("WORKSPACE_DOCKER_MODE", "SEARXNG_URL", "OLLAMA_BASE_URL")}
        for key in self._env:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_loopback_remains_default_for_ollama(self) -> None:
        self.assertEqual(safe_ollama_base_url("http://127.0.0.1:11434"), "http://127.0.0.1:11434")
        with self.assertRaises(ValueError):
            safe_ollama_base_url("http://ollama:11434")

    def test_docker_allows_only_internal_ollama_service(self) -> None:
        os.environ["WORKSPACE_DOCKER_MODE"] = "1"
        self.assertEqual(safe_ollama_base_url("http://ollama:11434"), "http://ollama:11434")
        with self.assertRaises(ValueError):
            safe_ollama_base_url("http://example.invalid:11434")

    def test_host_docker_internal_accepted_for_standalone_ollama(self) -> None:
        # host.docker.internal is allowed even when WORKSPACE_DOCKER_MODE=0
        # because Ollama (rws-ollama on :11435) runs as its own container on
        # the host loopback and the backend container reaches it via this
        # hostname. No explicit docker_mode required.
        os.environ["WORKSPACE_DOCKER_MODE"] = "0"
        self.assertEqual(
            safe_ollama_base_url("http://host.docker.internal:11435"),
            "http://host.docker.internal:11435",
        )

        # And the bare loopback remains the default.
        self.assertEqual(safe_ollama_base_url("http://127.0.0.1:11434"), "http://127.0.0.1:11434")

        # And other public hostnames still fail closed.
        with self.assertRaises(ValueError):
            safe_ollama_base_url("http://example.invalid:11434")

    def test_docker_allows_only_internal_searxng_service(self) -> None:
        os.environ["WORKSPACE_DOCKER_MODE"] = "true"
        os.environ["SEARXNG_URL"] = "http://searxng:8080"
        self.assertEqual(_searxng_url(), "http://searxng:8080")
        os.environ["SEARXNG_URL"] = "http://example.invalid:8080"
        with self.assertRaisesRegex(Exception, "SEARXNG_URL"):
            _searxng_url()

    def test_host_docker_internal_accepted_for_standalone_searxng(self) -> None:
        # host.docker.internal is allowed even when WORKSPACE_DOCKER_MODE=0
        # because SearXNG normally runs as its own container on the host
        # (searxng-hermes) and the backend container reaches it via this
        # hostname. No explicit docker_mode required.
        os.environ["WORKSPACE_DOCKER_MODE"] = "0"
        os.environ["SEARXNG_URL"] = "http://host.docker.internal:8888"
        self.assertEqual(_searxng_url(), "http://host.docker.internal:8888")

        # And the bare loopback is still the default.
        os.environ.pop("SEARXNG_URL", None)
        self.assertEqual(_searxng_url(), "http://127.0.0.1:8888")


if __name__ == "__main__":
    unittest.main()
