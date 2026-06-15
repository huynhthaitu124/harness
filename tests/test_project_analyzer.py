from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from harness_core.project_analyzer import (
    build_analysis_context,
    detect_project_type,
    extract_key_files,
    generate_initial_features,
    generate_initial_memories,
    generate_mcp_config,
    generate_routing_keywords,
    render_harness_md,
)


@pytest.fixture()
def python_project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'my-service'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# My Service\n\nA fastapi service.\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def node_project(tmp_path: Path) -> Path:
    pkg = {"name": "my-app", "dependencies": {"next": "14.0.0", "react": "18.0.0"}, "main": "index.js"}
    (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    (tmp_path / "README.md").write_text("# My App\n", encoding="utf-8")
    (tmp_path / "index.js").write_text("const express = require('express')\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def go_project(tmp_path: Path) -> Path:
    (tmp_path / "go.mod").write_text("module example.com/app\ngo 1.22\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
    return tmp_path


class TestDetectProjectType:
    def test_detects_python(self, python_project: Path) -> None:
        result = detect_project_type(python_project)
        assert result["language"] == "python"
        assert result["config_file"] == "pyproject.toml"

    def test_detects_javascript_with_framework(self, node_project: Path) -> None:
        result = detect_project_type(node_project)
        assert result["language"] == "javascript"
        assert result["framework"] == "next.js"

    def test_detects_go(self, go_project: Path) -> None:
        result = detect_project_type(go_project)
        assert result["language"] == "go"
        assert result["config_file"] == "go.mod"

    def test_unknown_project(self, tmp_path: Path) -> None:
        result = detect_project_type(tmp_path)
        assert result["language"] == "unknown"


class TestExtractKeyFiles:
    def test_finds_readme_and_config(self, python_project: Path) -> None:
        files = extract_key_files(python_project)
        names = [p.name for p in files]
        assert "README.md" in names
        assert "pyproject.toml" in names

    def test_finds_entry_point(self, python_project: Path) -> None:
        files = extract_key_files(python_project)
        names = [p.name for p in files]
        assert "main.py" in names

    def test_no_duplicates(self, python_project: Path) -> None:
        files = extract_key_files(python_project)
        assert len(files) == len(set(files))


class TestGenerateRoutingKeywords:
    def test_python_includes_pytest(self) -> None:
        kw = generate_routing_keywords("python", "")
        assert "pytest" in kw["coding_keywords"]

    def test_framework_added_to_research(self) -> None:
        kw = generate_routing_keywords("python", "fastapi")
        assert "fastapi" in kw["research_heavy_keywords"]

    def test_extra_terms_included(self) -> None:
        kw = generate_routing_keywords("go", "", ["grpc", "protobuf"])
        assert "grpc" in kw["research_heavy_keywords"]
        assert "protobuf" in kw["research_heavy_keywords"]

    def test_no_duplicates_in_research(self) -> None:
        kw = generate_routing_keywords("javascript", "next.js")
        assert len(kw["research_heavy_keywords"]) == len(set(kw["research_heavy_keywords"]))


class TestGenerateInitialFeatures:
    def test_python_features_include_pytest(self) -> None:
        features = generate_initial_features("python")
        assert any("pytest" in f.lower() or "test" in f.lower() for f in features)

    def test_default_features_fallback(self) -> None:
        features = generate_initial_features("cobol")
        assert len(features) > 0

    def test_always_includes_init_feature(self) -> None:
        for lang in ("python", "javascript", "go", "rust", "unknown"):
            features = generate_initial_features(lang)
            assert any("init" in f.lower() for f in features)


class TestGenerateInitialMemories:
    def test_generates_tech_stack_memory(self, python_project: Path) -> None:
        analysis = {"language": "python", "framework": "fastapi", "config_file": "pyproject.toml", "entry_points": ["main.py"]}
        memories = generate_initial_memories(analysis, python_project)
        contents = [m["content"] for m in memories]
        assert any("python" in c.lower() for c in contents)

    def test_generates_entry_point_memory(self, python_project: Path) -> None:
        analysis = {"language": "python", "framework": "", "config_file": "pyproject.toml", "entry_points": ["main.py"]}
        memories = generate_initial_memories(analysis, python_project)
        contents = [m["content"] for m in memories]
        assert any("main.py" in c for c in contents)

    def test_all_memories_have_required_fields(self, tmp_path: Path) -> None:
        analysis = {"language": "go", "framework": "gin", "config_file": "go.mod", "entry_points": []}
        memories = generate_initial_memories(analysis, tmp_path)
        for m in memories:
            assert "content" in m
            assert "kind" in m
            assert "tags" in m
            assert "source" in m


class TestRenderHarnessMd:
    def test_includes_project_name(self, tmp_path: Path) -> None:
        analysis = {"language": "python", "framework": "fastapi"}
        md = render_harness_md(analysis, tmp_path / "scripts", "my-service")
        assert "my-service" in md

    def test_includes_language_and_framework(self, tmp_path: Path) -> None:
        analysis = {"language": "python", "framework": "fastapi"}
        md = render_harness_md(analysis, tmp_path / "scripts", "proj")
        assert "python" in md
        assert "fastapi" in md

    def test_includes_quick_start_commands(self, tmp_path: Path) -> None:
        analysis = {"language": "go", "framework": ""}
        md = render_harness_md(analysis, tmp_path / "scripts", "proj")
        assert "harness-route" in md
        assert "harness-hybrid-context" in md

    def test_includes_customize_section(self, tmp_path: Path) -> None:
        analysis = {"language": "rust", "framework": "axum"}
        md = render_harness_md(analysis, tmp_path / "scripts", "proj")
        assert "CUSTOMIZE" in md

    def test_written_in_english(self, tmp_path: Path) -> None:
        analysis = {"language": "python", "framework": "fastapi"}
        md = render_harness_md(analysis, tmp_path / "scripts", "proj")
        vietnamese_markers = ["chọn", "tìm kiếm", "luôn dùng", "viết"]
        for marker in vietnamese_markers:
            assert marker not in md, f"Vietnamese text found: {marker}"


class TestGenerateMcpConfig:
    def test_config_structure(self, tmp_path: Path) -> None:
        harness = tmp_path / "Harness"
        target = tmp_path / "MyProject"
        config = generate_mcp_config(harness, target)
        assert "mcpServers" in config
        server = config["mcpServers"]["harness"]
        assert "harness-mcp-server" in server["command"]
        assert str(target / ".harness" / "state.json") == server["env"]["HARNESS_STATE_PATH"]
        assert str(target / "production_artifacts") == server["env"]["HARNESS_ARTIFACTS_DIR"]


class TestBuildAnalysisContext:
    def test_returns_string(self, python_project: Path) -> None:
        key_files = extract_key_files(python_project)
        ctx = build_analysis_context(python_project, key_files)
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_respects_max_chars(self, python_project: Path) -> None:
        key_files = extract_key_files(python_project)
        ctx = build_analysis_context(python_project, key_files, max_chars=500)
        assert len(ctx) <= 700  # some header overhead allowed
