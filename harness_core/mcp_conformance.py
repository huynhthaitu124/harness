from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


def run_mcp_conformance(command: Path, *, cwd: Path, timeout: int = 15) -> dict[str, Any]:
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "harness-conformance", "version": "1"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}},
        {"jsonrpc": "2.0", "id": 4, "method": "prompts/list", "params": {}},
    ]
    input_text = "\n".join(json.dumps(request) for request in requests) + "\n"
    try:
        completed = subprocess.run(
            [str(command)],
            cwd=str(cwd),
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"verdict": "NEEDS_WORK", "missing": ["server_timeout"], "errors": []}
    responses: dict[int, dict[str, Any]] = {}
    parse_errors = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            parse_errors.append(line[:200])
            continue
        if isinstance(payload, dict) and isinstance(payload.get("id"), int):
            responses[payload["id"]] = payload

    missing = []
    for request_id in range(1, 5):
        if request_id not in responses:
            missing.append(f"missing_response:{request_id}")
        elif "error" in responses[request_id]:
            missing.append(f"error_response:{request_id}")
    initialize = responses.get(1, {}).get("result", {})
    tools = responses.get(2, {}).get("result", {}).get("tools", [])
    resources = responses.get(3, {}).get("result", {}).get("resources", [])
    prompts = responses.get(4, {}).get("result", {}).get("prompts", [])
    tool_names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
    duplicate_tools = sorted(name for name, count in Counter(tool_names).items() if name and count > 1)
    if initialize.get("protocolVersion") != "2025-11-25":
        missing.append("protocol_negotiation_failed")
    if duplicate_tools:
        missing.append("duplicate_tools")
    if parse_errors:
        missing.append("non_json_stdout")
    return {
        "verdict": "PASS" if not missing else "NEEDS_WORK",
        "returncode": completed.returncode,
        "protocol_version": initialize.get("protocolVersion"),
        "tool_count": len(tool_names),
        "resource_count": len(resources),
        "prompt_count": len(prompts),
        "duplicate_tools": duplicate_tools,
        "missing": missing,
        "parse_errors": parse_errors,
        "stderr_tail": completed.stderr[-1000:],
    }
