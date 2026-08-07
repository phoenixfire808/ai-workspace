from __future__ import annotations

import os
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="mo-durable-runtime-"))
os.environ["WORKSPACE_ROOT"] = str(_TEST_ROOT)
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_ROOT / 'acceptance.db').as_posix()}"

from fastapi.testclient import TestClient

from backend.main import app


class DurableRuntimeAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        shutil.rmtree(_TEST_ROOT, ignore_errors=True)

    def wait_run(self, run_id: str, terminal: set[str] | None = None, timeout: float = 8.0) -> dict:
        terminal = terminal or {"completed", "error", "waiting_approval", "waiting_input", "denied", "cancelled"}
        deadline = time.monotonic() + timeout
        payload: dict = {}
        while time.monotonic() < deadline:
            response = self.client.get(f"/api/runs/{run_id}")
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            if payload["status"] in terminal:
                return payload
            time.sleep(0.05)
        self.fail(f"run {run_id} did not reach {terminal}; last={payload.get('status')}")

    @staticmethod
    def graph(nodes: list[dict], edges: list[dict]) -> dict:
        return {"nodes": nodes, "edges": edges, "settings": {}}

    @staticmethod
    def node(node_id: str, kind: str, data: dict | None = None) -> dict:
        return {"id": node_id, "type": kind, "position": {"x": 0, "y": 0}, "data": data or {}}

    @staticmethod
    def edge(edge_id: str, source: str, target: str, **extra: object) -> dict:
        return {"id": edge_id, "source": source, "target": target, **extra}

    def start(self, graph: dict, input_text: str = "acceptance input", policy: str = "per_action") -> dict:
        response = self.client.post("/api/runs", json={"graph": graph, "input_text": input_text, "approval_policy": policy, "retain_context": True, "max_parallel": 4})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def approve_pending(self, run: dict, **extra: object) -> dict:
        pending = next(item for item in run["approvals"] if item["status"] == "pending")
        body = {"decision": "approve", "arguments": pending["arguments"], "note": "acceptance approval", **extra}
        response = self.client.post(f"/api/runs/{run['id']}/approvals/{pending['id']}", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_01_registry_and_profile_contracts(self) -> None:
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200, health.text)
        audit = self.client.get("/api/library/capability-audit")
        self.assertEqual(audit.status_code, 200, audit.text)
        payload = audit.json()
        self.assertGreaterEqual(payload["total"], 1)
        self.assertEqual(payload["invalid_ready"], [])
        hermes_audit = self.client.get("/api/hermes/capability-audit")
        self.assertEqual(hermes_audit.status_code, 200, hermes_audit.text)
        self.assertFalse(hermes_audit.json()["profile_mutation_supported"])
        plugins = self.client.get("/api/plugins")
        self.assertEqual(plugins.status_code, 200, plugins.text)
        self.assertEqual({item["plugin_id"] for item in plugins.json()["plugins"]}, {"run_annotation", "context_selector"})
        endpoints = self.client.get("/api/model-endpoints")
        hardware = self.client.get("/api/hardware/profiles")
        self.assertEqual(endpoints.status_code, 200, endpoints.text)
        self.assertEqual(hardware.status_code, 200, hardware.text)
        self.assertTrue(any(item["id"] == "local-ollama" for item in endpoints.json()["profiles"]))
        self.assertTrue(any(item["id"] == "auto" for item in hardware.json()["profiles"]))

    def test_02_start_split_merge_and_plugin(self) -> None:
        graph = self.graph(
            [
                self.node("start-a", "start"),
                self.node("split-a", "split", {"chunk_strategy": "paragraphs", "max_chunks": 8}),
                self.node("merge-a", "merge", {"merge_strategy": "json_array"}),
                self.node("plugin-a", "plugin", {"plugin_id": "run_annotation", "note": "merged"}),
            ],
            [
                self.edge("edge-a1", "start-a", "split-a"),
                self.edge("edge-a2", "split-a", "merge-a"),
                self.edge("edge-a3", "merge-a", "plugin-a"),
            ],
        )
        created = self.start(graph, "alpha\n\nbeta")
        run = self.wait_run(created["id"], {"completed", "error"})
        self.assertEqual(run["status"], "completed", run.get("error_detail"))
        self.assertIn("alpha", run["final_output"])
        self.assertIn("beta", run["final_output"])
        self.assertTrue(any(step["node_type"] == "split" for step in run["steps"]))
        self.assertTrue(any(step["node_type"] == "merge" for step in run["steps"]))

    def test_03_human_review_resume(self) -> None:
        graph = self.graph(
            [self.node("start-b", "start"), self.node("review-b", "review", {"prompt": "Continue?"}), self.node("context-b", "context", {"selector": ""})],
            [self.edge("edge-b1", "start-b", "review-b"), self.edge("edge-b2", "review-b", "context-b")],
        )
        created = self.start(graph)
        waiting = self.wait_run(created["id"], {"waiting_approval", "error"})
        self.assertEqual(waiting["status"], "waiting_approval", waiting.get("error_detail"))
        self.assertEqual(waiting["approvals"][-1]["action_type"], "human_review")
        self.approve_pending(waiting)
        completed = self.wait_run(created["id"], {"completed", "error"})
        self.assertEqual(completed["status"], "completed", completed.get("error_detail"))

    def test_04_file_preview_resume_and_delete_context(self) -> None:
        graph = self.graph(
            [self.node("start-c", "start"), self.node("file-c", "file", {"mode": "write", "path": "acceptance/result.txt"})],
            [self.edge("edge-c1", "start-c", "file-c")],
        )
        created = self.start(graph, "exact file body")
        waiting = self.wait_run(created["id"], {"waiting_approval", "error"})
        self.assertEqual(waiting["status"], "waiting_approval", waiting.get("error_detail"))
        pending = next(item for item in waiting["approvals"] if item["status"] == "pending")
        self.assertIn("result.txt", pending["impact_preview"])
        self.approve_pending(waiting)
        completed = self.wait_run(created["id"], {"completed", "error"})
        self.assertEqual(completed["status"], "completed", completed.get("error_detail"))
        self.assertEqual((_TEST_ROOT / "acceptance" / "result.txt").read_text(encoding="utf-8"), "exact file body")
        deleted = self.client.delete(f"/api/runs/{created['id']}")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(self.client.get(f"/api/runs/{created['id']}").status_code, 404)

    def test_05_chat_and_step_through(self) -> None:
        graph = self.graph(
            [self.node("start-d", "start"), self.node("chat-d", "chat", {"prompt": "Add context"})],
            [self.edge("edge-d1", "start-d", "chat-d")],
        )
        created = self.start(graph, policy="per_action")
        waiting = self.wait_run(created["id"], {"waiting_input", "error"})
        self.assertEqual(waiting["status"], "waiting_input", waiting.get("error_detail"))
        continued = self.client.post(f"/api/runs/{created['id']}/input", json={"content": "human continuation"})
        self.assertEqual(continued.status_code, 200, continued.text)
        completed = self.wait_run(created["id"], {"completed", "error"})
        self.assertEqual(completed["status"], "completed", completed.get("error_detail"))
        self.assertEqual(completed["final_output"], "human continuation")

        step_graph = self.graph([self.node("start-e", "start")], [])
        step_created = self.start(step_graph, policy="step_through")
        step_waiting = self.wait_run(step_created["id"], {"waiting_approval", "error"})
        self.assertEqual(step_waiting["status"], "waiting_approval")
        self.approve_pending(step_waiting)
        step_completed = self.wait_run(step_created["id"], {"completed", "error"})
        self.assertEqual(step_completed["status"], "completed", step_completed.get("error_detail"))

    def test_06_delegate_plan_only(self) -> None:
        graph = self.graph(
            [self.node("start-f", "start"), self.node("delegate-f", "delegate", {"decompose_strategy": "lines", "dispatch_mode": "plan_only", "max_subtasks": 4})],
            [self.edge("edge-f1", "start-f", "delegate-f")],
        )
        created = self.start(graph, "Inspect backend\nInspect frontend")
        completed = self.wait_run(created["id"], {"completed", "error"})
        self.assertEqual(completed["status"], "completed", completed.get("error_detail"))
        self.assertIn('"status": "planned"', completed["final_output"])
        self.assertIn('"subtask_count": 2', completed["final_output"])

    def test_07_delegate_child_receipt_and_completion(self) -> None:
        worker_script = "import sys; sys.stdin.read(); print('worker complete')"
        previous = os.environ.get("WORKSPACE_AGENT_COMMANDS")
        os.environ["WORKSPACE_AGENT_COMMANDS"] = json.dumps({"acceptance-worker": [sys.executable, "-c", worker_script]})
        try:
            graph = self.graph(
                [self.node("start-g", "start"), self.node("delegate-g", "delegate", {"decompose_strategy": "lines", "dispatch_mode": "sequential", "worker_target": "acceptance-worker", "max_subtasks": 2})],
                [self.edge("edge-g1", "start-g", "delegate-g")],
            )
            created = self.start(graph, "Child acceptance assignment")
            waiting = self.wait_run(created["id"], {"waiting_approval", "error"})
            self.assertEqual(waiting["status"], "waiting_approval", waiting.get("error_detail"))
            self.assertEqual(waiting["approvals"][-1]["action_type"], "delegate:delegate-g")
            self.approve_pending(waiting)
            completed = self.wait_run(created["id"], {"completed", "error"})
            self.assertEqual(completed["status"], "completed", completed.get("error_detail"))

            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                completed = self.client.get(f"/api/runs/{created['id']}").json()
                if completed.get("children") and completed["children"][0]["status"] in {"completed", "error"}:
                    break
                time.sleep(0.05)
            self.assertEqual(len(completed["children"]), 1)
            child = completed["children"][0]
            self.assertEqual(child["child_run_id"], child["id"])
            self.assertEqual(child["parent_run_id"], created["id"])
            self.assertEqual(child["parent_step_id"], completed["steps"][-1]["id"])
            self.assertEqual(child["status"], "completed")
            self.assertEqual(child["output"].strip(), "worker complete")
            self.assertEqual(len(child["receipt"]["context"]["context_sha256"]), 64)
            self.assertEqual(child["receipt"]["completion"]["status"], "completed")
        finally:
            if previous is None:
                os.environ.pop("WORKSPACE_AGENT_COMMANDS", None)
            else:
                os.environ["WORKSPACE_AGENT_COMMANDS"] = previous

    def test_08_all_file_actuators_stale_and_replay(self) -> None:
        def preview(resource_id: str, arguments: dict) -> dict:
            response = self.client.post("/api/actions/preview", json={"resource_id": resource_id, "arguments": arguments})
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()

        def apply(receipt: dict, approved: bool = True):
            return self.client.post("/api/actions/run", json={"resource_id": receipt["resource"]["resource_id"], "arguments": receipt["arguments"], "preview_id": receipt["preview_id"], "approved": approved})

        created = preview("tool:create_workspace_file", {"relative_path": "actuators/a.txt", "content": "alpha"})
        denied = apply(created, approved=False)
        self.assertEqual(denied.status_code, 403, denied.text)
        created = preview("tool:create_workspace_file", {"relative_path": "actuators/a.txt", "content": "alpha"})
        applied = apply(created)
        self.assertEqual(applied.status_code, 200, applied.text)
        replay = apply(created)
        self.assertNotEqual(replay.status_code, 200, replay.text)

        patched = preview("tool:patch_workspace_file", {"relative_path": "actuators/a.txt", "old_text": "alpha", "new_text": "beta"})
        (_TEST_ROOT / "actuators" / "a.txt").write_text("external change", encoding="utf-8")
        stale = apply(patched)
        self.assertNotEqual(stale.status_code, 200, stale.text)
        self.assertEqual((_TEST_ROOT / "actuators" / "a.txt").read_text(encoding="utf-8"), "external change")

        patched = preview("tool:patch_workspace_file", {"relative_path": "actuators/a.txt", "old_text": "external change", "new_text": "beta"})
        self.assertEqual(apply(patched).status_code, 200)
        renamed = preview("tool:rename_workspace_file", {"source_path": "actuators/a.txt", "destination_path": "actuators/b.txt"})
        self.assertEqual(apply(renamed).status_code, 200)
        self.assertFalse((_TEST_ROOT / "actuators" / "a.txt").exists())
        self.assertTrue((_TEST_ROOT / "actuators" / "b.txt").exists())
        deleted = preview("tool:delete_workspace_file", {"relative_path": "actuators/b.txt"})
        self.assertIn("b.txt", deleted["impact_preview"])
        self.assertEqual(apply(deleted).status_code, 200)
        self.assertFalse((_TEST_ROOT / "actuators" / "b.txt").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
