from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Any

TOOL_REF_RE = re.compile(r"\bharness_[A-Za-z0-9_]+\b")
SCRIPT_REF_RE = re.compile(r"(?:\./|/[^`\s]*/)?scripts/(harness-[A-Za-z0-9_-]+)")


def run_harness_doctor(root: Path) -> dict[str, Any]:
    root = root.resolve()
    tool_names = _server_tool_names(root / "harness_mcp" / "server.py")
    doc_texts = _doc_texts(root)
    documented_tools = _documented_tools(doc_texts)
    script_refs = _documented_scripts(doc_texts)
    issues: list[dict[str, str]] = []

    for script_name in sorted(script_refs):
        script_path = root / "scripts" / script_name
        if not script_path.exists():
            issues.append(
                {
                    "severity": "error",
                    "category": "cli_script",
                    "code": "missing_script",
                    "message": f"Documented script does not exist: scripts/{script_name}",
                    "source": "docs",
                }
            )
        elif not os.access(script_path, os.X_OK):
            issues.append(
                {
                    "severity": "error",
                    "category": "cli_script",
                    "code": "non_executable_script",
                    "message": f"Documented script is not executable: scripts/{script_name}",
                    "source": "docs",
                }
            )

    for tool_name in sorted(tool_names - documented_tools):
        issues.append(
            {
                "severity": "warning",
                "category": "mcp_tool",
                "code": "undocumented_tool",
                "message": f"MCP tool is registered but not documented: {tool_name}",
                "source": "harness_mcp/server.py",
            }
        )

    for tool_name in sorted(documented_tools - tool_names):
        issues.append(
            {
                "severity": "warning",
                "category": "mcp_tool",
                "code": "unknown_documented_tool",
                "message": f"Document references a tool that is not registered: {tool_name}",
                "source": "docs",
            }
        )

    return {
        "root": str(root),
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "tool_count": len(tool_names),
        "documented_tool_count": len(documented_tools),
        "documented_script_count": len(script_refs),
        "issues": issues,
    }


def _server_tool_names(server_path: Path) -> set[str]:
    if not server_path.exists():
        return set()
    tree = ast.parse(server_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TOOLS":
                    return _tool_names_from_literal(node.value)
    return set()


def _tool_names_from_literal(node: ast.AST) -> set[str]:
    names: set[str] = set()
    if not isinstance(node, ast.List):
        return names
    for item in node.elts:
        if not isinstance(item, ast.Dict):
            continue
        for key, value in zip(item.keys, item.values):
            if isinstance(key, ast.Constant) and key.value == "name" and isinstance(value, ast.Constant):
                if isinstance(value.value, str):
                    names.add(value.value)
    return names


def _doc_texts(root: Path) -> dict[str, str]:
    candidates = [root / "README.md", root / "CLAUDE.md", root / "AGENTS.md"]
    candidates.extend(sorted((root / "rules").glob("*.md")) if (root / "rules").exists() else [])
    skill_dir = root / "antigravity-plugin" / "skills"
    if skill_dir.exists():
        candidates.extend(sorted(skill_dir.glob("*/SKILL.md")))
    texts: dict[str, str] = {}
    for path in candidates:
        if path.exists():
            texts[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8", errors="ignore")
    return texts


def _documented_tools(doc_texts: dict[str, str]) -> set[str]:
    tools: set[str] = set()
    for text in doc_texts.values():
        tools.update(TOOL_REF_RE.findall(text))
    return {tool for tool in tools if tool not in {"harness_mcp", "harness_core"}}


def _documented_scripts(doc_texts: dict[str, str]) -> set[str]:
    scripts: set[str] = set()
    for text in doc_texts.values():
        scripts.update(SCRIPT_REF_RE.findall(text))
    return scripts
