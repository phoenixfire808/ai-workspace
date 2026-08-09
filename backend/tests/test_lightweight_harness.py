import json
import unittest

from harness.lightweight_agent import HarnessConfig, LightweightHarness


class FakeMcp:
    def __init__(self):
        self.calls = []
        self.catalog = [
            {
                "name": "search_web",
                "description": "Search local web",
                "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
            {
                "name": "create_workspace_file",
                "description": "Create a workspace file",
                "inputSchema": {"type": "object", "properties": {"relative_path": {"type": "string"}}},
            },
        ]

    def list_tools(self):
        return self.catalog

    def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if name == "create_workspace_file" and "_preview_id" not in arguments:
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "status": "approval_required",
                    "requires_approval": True,
                    "preview_id": "preview-test",
                    "arguments": arguments,
                    "next_call": {"name": name, "arguments": {**arguments, "_preview_id": "preview-test", "_approved": True}},
                })}],
                "isError": False,
            }
        return {"content": [{"type": "text", "text": "tool-result"}], "isError": False}


class LightweightHarnessTests(unittest.TestCase):
    def make_harness(self):
        harness = LightweightHarness(HarnessConfig(model="test-model", request_timeout=2, max_turns=3))
        harness.mcp = FakeMcp()
        return harness

    def test_tool_call_arguments_accept_json_string(self):
        calls = LightweightHarness._tool_calls({
            "tool_calls": [{"id": "call-1", "function": {"name": "search_web", "arguments": '{"query":"ollama"}'}}]
        })
        self.assertEqual(calls[0]["name"], "search_web")
        self.assertEqual(calls[0]["arguments"], {"query": "ollama"})

    def test_read_only_tool_continues_to_final_answer(self):
        harness = self.make_harness()
        responses = iter([
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1", "function": {"name": "search_web", "arguments": '{"query":"ollama"}'}}]},
            {"role": "assistant", "content": "done", "tool_calls": []},
        ])
        harness._model_chat = lambda messages, tools: next(responses)
        result = harness.run("search for Ollama")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["content"], "done")
        self.assertEqual(harness.mcp.calls[0][0], "search_web")

    def test_mutation_pauses_then_resume_executes_preview(self):
        harness = self.make_harness()
        first = {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1", "function": {"name": "create_workspace_file", "arguments": '{"relative_path":"output/test.json"}'}}]}
        harness._model_chat = lambda messages, tools: first
        pending = harness.run("create a file")
        self.assertEqual(pending["status"], "approval_required")
        self.assertEqual(pending["approval"]["preview"]["preview_id"], "preview-test")
        harness._model_chat = lambda messages, tools: {"role": "assistant", "content": "created", "tool_calls": []}
        resumed = harness.resume(pending["run_id"], approve=True)
        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(resumed["content"], "created")
        self.assertEqual(harness.mcp.calls[-1][1]["_approved"], True)

    def test_explicit_mutation_approval_executes_without_pause(self):
        harness = self.make_harness()
        responses = iter([
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1", "function": {"name": "create_workspace_file", "arguments": '{"relative_path":"output/test.json"}'}}]},
            {"role": "assistant", "content": "created", "tool_calls": []},
        ])
        harness._model_chat = lambda messages, tools: next(responses)
        result = harness.run("create a file", approved_tools=["create_workspace_file"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(harness.mcp.calls[-1][1]["_approved"], True)


if __name__ == "__main__":
    unittest.main()
