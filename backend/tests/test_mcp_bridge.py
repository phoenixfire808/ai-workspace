import json
import unittest
from unittest.mock import patch

from backend.mcp_bridge import call_tool, handle_request, read_resource


class McpBridgeTests(unittest.TestCase):
    def test_initialize_and_ping(self) -> None:
        initialized = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(initialized["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "refactor-workflow-studio")
        self.assertEqual(handle_request({"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"], {"ok": True})

    def test_tools_list_exposes_search_and_approved_code_execution(self) -> None:
        response = handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
        names = {item["name"] for item in response["result"]["tools"]}
        self.assertIn("search_web", names)
        self.assertIn("execute_python_sandbox", names)
        self.assertIn("create_workspace_file", names)

    def test_templates_resource_serializes_python_booleans(self) -> None:
        response = read_resource("workspace://templates")
        templates = json.loads(response["contents"][0]["text"])
        self.assertGreaterEqual(len(templates), 20)
        self.assertIn("mcp-create-workflow", {item["template_id"] for item in templates})

    def test_read_only_tool_uses_invoke_and_returns_text(self) -> None:
        response = call_tool("list_workspace_files", {"relative_path": ""})
        self.assertFalse(response["isError"])
        payload = json.loads(response["content"][0]["text"])
        self.assertEqual(payload["root"], ".")
        self.assertIn("backend", {entry["path"] for entry in payload["entries"]})

    def test_approval_required_tool_returns_preview_without_running(self) -> None:
        preview = {
            "requires_approval": True,
            "preview_id": "preview-123",
            "arguments": {"script_content": "print(2 + 3)"},
            "impact_preview": "",
        }
        with patch("backend.library.preview_action", return_value=preview) as preview_action:
            response = call_tool("execute_python_sandbox", {"script_content": "print(2 + 3)"})
        self.assertFalse(response["isError"])
        body = json.loads(response["content"][0]["text"])
        self.assertEqual(body["status"], "approval_required")
        self.assertEqual(body["preview_id"], "preview-123")
        preview_action.assert_called_once()

    def test_approved_tool_call_uses_existing_run_action(self) -> None:
        with patch("backend.library.run_action", return_value={"status": "completed", "output": "5"}) as run_action:
            response = call_tool(
                "execute_python_sandbox",
                {"script_content": "print(2 + 3)", "_preview_id": "preview-123", "_approved": True},
            )
        self.assertFalse(response["isError"])
        self.assertIn('"status": "completed"', response["content"][0]["text"])
        run_action.assert_called_once()

    def test_unknown_method_and_tool_fail_closed(self) -> None:
        method = handle_request({"jsonrpc": "2.0", "id": 4, "method": "not/a-method"})
        self.assertEqual(method["error"]["code"], -32601)
        tool = call_tool("not_a_tool", {})
        self.assertTrue(tool["isError"])


if __name__ == "__main__":
    unittest.main()
