#!/usr/bin/env python3
"""Local CLI client for Refactor Workflow Studio's approval-gated MCP bridge.

Examples:
  python scripts/rws_workflow_cli.py ideas
  python scripts/rws_workflow_cli.py files
  python scripts/rws_workflow_cli.py search --query "Ollama API"
  python scripts/rws_workflow_cli.py create --path output/demo.json --content '{}' --approve
  python scripts/rws_workflow_cli.py patch --path output/demo.json --old-text '{}' --new-text '{"ok":true}' --approve
  python scripts/rws_workflow_cli.py run-code --script "print(2 + 3)" --approve

Without --approve, write/sandbox commands print the normalized preview and exit 2.
This makes the CLI safe to call from Codex, Claude Code, OpenCode, or another
local coding harness without bypassing the workspace's existing approval gates.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_URL = "http://127.0.0.1:8100/mcp"


class McpClientError(RuntimeError):
    pass


def rpc(url: str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
    request = urllib.request.Request(url, method="POST", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1000]
        raise McpClientError(f"MCP HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise McpClientError(f"MCP connection failed: {type(exc).__name__}: {exc}") from exc
    if "error" in payload:
        raise McpClientError(json.dumps(payload["error"], ensure_ascii=False))
    return payload.get("result", payload)


def text_result(result: dict[str, Any]) -> str:
    content = result.get("content") or []
    if not content:
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(content[0].get("text", ""))


def json_text_result(result: dict[str, Any]) -> Any:
    text = text_result(result)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def resource_value(result: dict[str, Any]) -> Any:
    contents = result.get("contents") or []
    if contents:
        text = str(contents[0].get("text", ""))
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return result


def print_value(value: Any, as_json: bool) -> None:
    if as_json or not isinstance(value, str):
        print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    else:
        print(value)


def approval_call(url: str, tool: str, arguments: dict[str, Any], approve: bool, as_json: bool) -> int:
    preview_result = rpc(url, "tools/call", {"name": tool, "arguments": arguments})
    preview = json_text_result(preview_result)
    if preview_result.get("isError") or not isinstance(preview, dict) or "next_call" not in preview:
        print_value(preview, as_json)
        return 1 if preview_result.get("isError") else 0
    if not approve:
        print_value({"status": "approval_required", "preview": preview}, True)
        print("Re-run with --approve to execute this exact preview.", file=sys.stderr)
        return 2
    next_call = preview["next_call"]
    result = rpc(url, "tools/call", next_call)
    print_value(json_text_result(result), as_json)
    return 1 if result.get("isError") else 0


def read_script(args: argparse.Namespace) -> str:
    if args.script is not None:
        return args.script
    path = Path(args.script_file).expanduser().resolve()
    cwd = Path.cwd().resolve()
    if cwd not in path.parents and path != cwd:
        raise McpClientError("--script-file must be inside the current workspace")
    return path.read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refactor Workflow Studio local MCP/ACLI client")
    parser.add_argument("--url", default=os.getenv("RWS_MCP_URL", DEFAULT_URL), help="MCP endpoint")
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="read workspace and model health")
    sub.add_parser("files", help="list workspace files")
    sub.add_parser("ideas", help="list runnable workflow/template ideas")
    read = sub.add_parser("read", help="read a workspace file")
    read.add_argument("--path", required=True)
    search = sub.add_parser("search", help="search local SearXNG")
    search.add_argument("--query", required=True)
    search.add_argument("--max-results", type=int, default=5)

    create = sub.add_parser("create", help="create a workflow/workspace file")
    create.add_argument("--path", required=True)
    create.add_argument("--content", required=True)
    create.add_argument("--approve", action="store_true")

    patch = sub.add_parser("patch", help="patch a workflow/workspace file with preimage protection")
    patch.add_argument("--path", required=True)
    patch.add_argument("--old-text", required=True)
    patch.add_argument("--new-text", required=True)
    patch.add_argument("--approve", action="store_true")

    delete = sub.add_parser("delete", help="delete a workspace file")
    delete.add_argument("--path", required=True)
    delete.add_argument("--approve", action="store_true")

    code = sub.add_parser("run-code", help="run bounded Python in the approved sandbox")
    source = code.add_mutually_exclusive_group(required=True)
    source.add_argument("--script")
    source.add_argument("--script-file")
    code.add_argument("--approve", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "health":
            result = rpc(args.url, "resources/read", {"uri": "workspace://health"})
            print_value(resource_value(result), args.as_json)
            return 0
        if args.command == "ideas":
            templates_payload = resource_value(rpc(args.url, "resources/read", {"uri": "workspace://templates"}))
            templates = templates_payload.get("templates", templates_payload) if isinstance(templates_payload, dict) else templates_payload
            ideas = [{"template_id": item.get("template_id"), "label": item.get("label"), "description": item.get("description")} for item in templates if isinstance(item, dict)]
            print_value(ideas, True)
            return 0
        if args.command == "files":
            result = rpc(args.url, "tools/call", {"name": "list_workspace_files", "arguments": {}})
            print_value(json_text_result(result), args.as_json)
            return 1 if result.get("isError") else 0
        if args.command == "read":
            result = rpc(args.url, "tools/call", {"name": "read_workspace_file", "arguments": {"relative_path": args.path}})
            print_value(text_result(result), args.as_json)
            return 1 if result.get("isError") else 0
        if args.command == "search":
            result = rpc(args.url, "tools/call", {"name": "search_web", "arguments": {"query": args.query, "max_results": args.max_results}})
            print_value(json_text_result(result), args.as_json)
            return 1 if result.get("isError") else 0
        if args.command == "create":
            return approval_call(args.url, "create_workspace_file", {"relative_path": args.path, "content": args.content, "expected_absent": True}, args.approve, args.as_json)
        if args.command == "patch":
            return approval_call(args.url, "patch_workspace_file", {"relative_path": args.path, "old_text": args.old_text, "new_text": args.new_text}, args.approve, args.as_json)
        if args.command == "delete":
            return approval_call(args.url, "delete_workspace_file", {"relative_path": args.path}, args.approve, args.as_json)
        if args.command == "run-code":
            return approval_call(args.url, "execute_python_sandbox", {"script_content": read_script(args)}, args.approve, args.as_json)
        raise McpClientError(f"unknown command: {args.command}")
    except McpClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
