from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_core.project_init import analyze_project, init_project_full


@pytest.fixture()
def python_project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'svc'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Svc\n\nA Python service.\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("# entry point\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def harness_root(tmp_path: Path) -> Path:
    root = tmp_path / "Harness"
    (root / "scripts").mkdir(parents=True)
    return root


class TestAnalyzeProject:
    def test_returns_required_keys(self, python_project: Path) -> None:
        analysis = analyze_project(python_project)
        for key in ("language", "framework", "project_name", "key_files", "routing_keywords", "initial_features", "initial_memories"):
            assert key in analysis, f"missing key: {key}"

    def test_language_detected(self, python_project: Path) -> None:
        analysis = analyze_project(python_project)
        assert analysis["language"] == "python"

    def test_project_name_from_dir(self, python_project: Path) -> None:
        analysis = analyze_project(python_project)
        assert analysis["project_name"] == python_project.name

    def test_routing_keywords_present(self, python_project: Path) -> None:
        analysis = analyze_project(python_project)
        kw = analysis["routing_keywords"]
        assert "research_heavy_keywords" in kw
        assert "coding_keywords" in kw
        assert len(kw["research_heavy_keywords"]) > 0


class TestInitProjectFull:
    def test_dry_run_creates_no_files(self, python_project: Path, harness_root: Path) -> None:
        analysis = analyze_project(python_project)
        init_project_full(python_project, harness_root, analysis, dry_run=True)
        assert not (python_project / ".harness" / "state.json").exists()
        assert not (python_project / "HARNESS.md").exists()

    def test_creates_harness_state(self, python_project: Path, harness_root: Path) -> None:
        analysis = analyze_project(python_project)
        init_project_full(python_project, harness_root, analysis, skip_index=True)
        state_path = python_project / ".harness" / "state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert "routing_policy" in state
        assert "research_heavy_keywords" in state["routing_policy"]

    def test_routing_keywords_project_specific(self, python_project: Path, harness_root: Path) -> None:
        analysis = analyze_project(python_project)
        init_project_full(python_project, harness_root, analysis, skip_index=True)
        state = json.loads((python_project / ".harness" / "state.json").read_text())
        assert "pytest" in state["routing_policy"]["coding_keywords"]

    def test_creates_project_json(self, python_project: Path, harness_root: Path) -> None:
        analysis = analyze_project(python_project)
        init_project_full(python_project, harness_root, analysis, skip_index=True)
        project_json = python_project / ".harness" / "project.json"
        assert project_json.exists()
        meta = json.loads(project_json.read_text())
        assert meta["language"] == "python"

    def test_creates_harness_md(self, python_project: Path, harness_root: Path) -> None:
        analysis = analyze_project(python_project)
        init_project_full(python_project, harness_root, analysis, skip_index=True)
        harness_md = python_project / "HARNESS.md"
        assert harness_md.exists()
        content = harness_md.read_text()
        assert "harness-route" in content
        assert python_project.name in content

    def test_creates_mcp_config(self, python_project: Path, harness_root: Path) -> None:
        analysis = analyze_project(python_project)
        init_project_full(python_project, harness_root, analysis, skip_index=True)
        mcp_config_path = python_project / "configs" / "claude-mcp.json"
        assert mcp_config_path.exists()
        config = json.loads(mcp_config_path.read_text())
        assert "mcpServers" in config
        env = config["mcpServers"]["harness"]["env"]
        assert str(python_project / ".harness" / "state.json") == env["HARNESS_STATE_PATH"]

    def test_creates_feature_list(self, python_project: Path, harness_root: Path) -> None:
        analysis = analyze_project(python_project)
        init_project_full(python_project, harness_root, analysis, skip_index=True)
        feature_list = python_project / "production_artifacts" / "feature_list.json"
        assert feature_list.exists()
        data = json.loads(feature_list.read_text())
        assert data["version"] == 1
        assert len(data["features"]) > 0

    def test_seeds_memory(self, python_project: Path, harness_root: Path) -> None:
        analysis = analyze_project(python_project)
        init_project_full(python_project, harness_root, analysis, skip_index=True)
        memory_path = python_project / "production_artifacts" / "memory.jsonl"
        assert memory_path.exists()
        lines = [json.loads(l) for l in memory_path.read_text().splitlines() if l.strip()]
        assert len(lines) >= 1

    def test_creates_artifact_dirs(self, python_project: Path, harness_root: Path) -> None:
        analysis = analyze_project(python_project)
        init_project_full(python_project, harness_root, analysis, skip_index=True)
        for subdir in ("handoffs", "context_packs", "evaluations"):
            assert (python_project / "production_artifacts" / subdir).is_dir()

    def test_manifest_returned(self, python_project: Path, harness_root: Path) -> None:
        analysis = analyze_project(python_project)
        result = init_project_full(python_project, harness_root, analysis, skip_index=True)
        assert "created" in result
        assert isinstance(result["created"], list)
        assert len(result["created"]) > 0

    def test_idempotent_second_run(self, python_project: Path, harness_root: Path) -> None:
        analysis = analyze_project(python_project)
        init_project_full(python_project, harness_root, analysis, skip_index=True)
        result2 = init_project_full(python_project, harness_root, analysis, skip_index=True)
        assert len(result2["created"]) > 0
