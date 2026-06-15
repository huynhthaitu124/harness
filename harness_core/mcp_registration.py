"""Register the harness MCP server into agent config files.

Each agent reads its own config at session start — not .harness/mcp.json.
This module writes the harness server entry into the actual files agents load.

Supported targets:
  Claude Code    → <project>/.mcp.json  (project-scoped, native support)
  Antigravity IDE → ~/.gemini/antigravity-ide/mcp_config.json  (global)
  Antigravity CLI → ~/.gemini/antigravity/mcp_config.json      (global)
  Antigravity standalone → ~/.gemini/antigravity-backup/mcp_config.json
  Gemini CLI     → ~/.gemini/config/mcp_config.json            (global)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_HARNESS_SERVER_KEY = "harness"


def _mcp_entry(harness_root: Path, target_root: Path) -> dict[str, Any]:
    """Build the mcpServers entry for this project."""
    return {
        "command": str(harness_root / "scripts" / "harness-mcp-server"),
        "args": [],
        "env": {
            "HARNESS_STATE_PATH":   str(target_root / ".harness" / "state.json"),
            "HARNESS_ARTIFACTS_DIR": str(target_root / ".harness"),
        },
    }


def _global_entry(harness_root: Path) -> dict[str, Any]:
    """Build the mcpServers entry without project env vars (cwd-detection fallback)."""
    return {
        "command": str(harness_root / "scripts" / "harness-mcp-server"),
        "args": [],
    }


def _merge_into_config(config_path: Path, entry: dict[str, Any]) -> bool:
    """Add or update the harness entry in an existing mcp_config.json file.

    Returns True if the file was written, False on error.
    """
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
        servers = data.setdefault("mcpServers", {})
        servers[_HARNESS_SERVER_KEY] = entry
        config_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def register_mcp_project(target_root: Path, harness_root: Path) -> list[str]:
    """Write .mcp.json at project root for Claude Code (project-scoped)."""
    path = target_root / ".mcp.json"
    ok = _merge_into_config(path, _mcp_entry(harness_root, target_root))
    return [str(path)] if ok else []


def register_mcp_global(harness_root: Path) -> list[str]:
    """Register harness in all Antigravity / Gemini global MCP config files.

    Uses cwd-detection entry (no project env vars) — the server resolves
    the project from cwd automatically when launched by the agent.
    """
    entry = _global_entry(harness_root)
    home  = Path.home()
    targets = [
        home / ".gemini" / "antigravity-ide" / "mcp_config.json",
        home / ".gemini" / "antigravity"     / "mcp_config.json",
        home / ".gemini" / "config"          / "mcp_config.json",
    ]
    written = []
    for path in targets:
        # Only update if file exists (agent is installed) OR it's the IDE config
        # (IDE is the primary target from the screenshot)
        if path.exists() or "antigravity-ide" in str(path):
            if _merge_into_config(path, entry):
                written.append(str(path))
    return written


def mcp_registration_status(target_root: Path, harness_root: Path) -> dict[str, Any]:
    """Check registration state across all agent config files."""
    home = Path.home()
    results: dict[str, str] = {}

    # Claude Code project-level
    project_mcp = target_root / ".mcp.json"
    if project_mcp.exists():
        data = json.loads(project_mcp.read_text(encoding="utf-8"))
        registered = _HARNESS_SERVER_KEY in data.get("mcpServers", {})
        results["claude_project"] = "registered" if registered else "missing"
    else:
        results["claude_project"] = "file absent"

    # Antigravity configs
    ag_targets = {
        "antigravity_ide":    home / ".gemini" / "antigravity-ide" / "mcp_config.json",
        "antigravity_global": home / ".gemini" / "antigravity"     / "mcp_config.json",
        "gemini_config":      home / ".gemini" / "config"          / "mcp_config.json",
    }
    for key, path in ag_targets.items():
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            registered = _HARNESS_SERVER_KEY in data.get("mcpServers", {})
            results[key] = "registered" if registered else "missing"
        else:
            results[key] = "file absent"

    return results


def unregister_mcp(target_root: Path) -> list[str]:
    """Remove harness from all config files (eject support)."""
    home = Path.home()
    paths = [
        target_root / ".mcp.json",
        home / ".gemini" / "antigravity-ide" / "mcp_config.json",
        home / ".gemini" / "antigravity"     / "mcp_config.json",
        home / ".gemini" / "config"          / "mcp_config.json",
    ]
    removed = []
    for path in paths:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            servers = data.get("mcpServers", {})
            if _HARNESS_SERVER_KEY in servers:
                del servers[_HARNESS_SERVER_KEY]
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
                removed.append(str(path))
        except Exception:
            pass
    return removed
