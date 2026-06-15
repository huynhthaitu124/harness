import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import harness_mcp.server as server
from harness_mcp.server import dispatch


class McpServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_state_path = server.STATE_PATH
        self.old_artifacts_dir = server.ARTIFACTS_DIR
        server.STATE_PATH = Path(self.tmp.name) / "state.json"
        server.ARTIFACTS_DIR = Path(self.tmp.name) / "artifacts"

    def tearDown(self):
        server.STATE_PATH = self.old_state_path
        server.ARTIFACTS_DIR = self.old_artifacts_dir
        self.tmp.cleanup()

    def test_lists_harness_tools(self):
        response = dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})

        names = [tool["name"] for tool in response["result"]["tools"]]
        self.assertIn("harness_route_task", names)
        self.assertIn("harness_set_center", names)

    def test_initialize_negotiates_latest_stable_protocol(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 37,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
            }
        )

        self.assertEqual("2025-11-25", response["result"]["protocolVersion"])

    def test_initialize_preserves_supported_legacy_protocol(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 38,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
            }
        )

        self.assertEqual("2024-11-05", response["result"]["protocolVersion"])

    def test_initialize_falls_back_to_latest_for_unknown_protocol(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 39,
                "method": "initialize",
                "params": {"protocolVersion": "2099-01-01", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
            }
        )

        self.assertEqual("2025-11-25", response["result"]["protocolVersion"])

    def test_sets_and_reads_center(self):
        set_response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "harness_set_center", "arguments": {"center": "claude"}},
            }
        )
        get_response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "harness_get_status", "arguments": {}},
            }
        )

        self.assertIn("claude", set_response["result"]["content"][0]["text"])
        self.assertIn("claude", get_response["result"]["content"][0]["text"])

    def test_routes_research_task_to_rag_workflow(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "harness_route_task",
                    "arguments": {"task": "research this codebase before editing auth"},
                },
            }
        )

        self.assertIn("rag_summarize", response["result"]["content"][0]["text"])

    def test_route_task_uses_usage_ledger_for_auto_center(self):
        ledger = server.ARTIFACTS_DIR / "usage.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(
            '{"center":"codex","input_tokens":90000,"output_tokens":10000,"cost_usd":0}\n'
            '{"center":"claude","input_tokens":50000,"output_tokens":5000,"cost_usd":1}\n'
            '{"center":"antigravity","input_tokens":1000,"output_tokens":100,"cost_usd":0}\n',
            encoding="utf-8",
        )

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 26,
                "method": "tools/call",
                "params": {"name": "harness_route_task", "arguments": {"task": "general architecture question"}},
            }
        )

        text = response["result"]["content"][0]["text"]
        self.assertIn('"center": "antigravity"', text)
        self.assertIn("routing_metrics", text)

    def test_benchmarks_context_savings(self):
        root = Path(self.tmp.name) / "repo"
        root.mkdir()
        (root / "auth.py").write_text("auth token login\n" * 100, encoding="utf-8")

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "harness_benchmark_context",
                    "arguments": {"root": str(root), "query": "auth login"},
                },
            }
        )

        self.assertIn("savings_percent", response["result"]["content"][0]["text"])

    def test_feature_tools_default_fail_then_complete_with_evidence(self):
        feature_path = Path(self.tmp.name) / "features.json"
        init_response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "harness_init_features",
                    "arguments": {"path": str(feature_path), "features": ["Add evaluator"]},
                },
            }
        )
        next_response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "harness_next_feature", "arguments": {"path": str(feature_path)}},
            }
        )

        self.assertIn("\"passes\": false", init_response["result"]["content"][0]["text"])
        self.assertIn("Add evaluator", next_response["result"]["content"][0]["text"])

    def test_usage_tools_record_and_report(self):
        ledger = Path(self.tmp.name) / "usage.jsonl"
        dispatch(
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "harness_record_usage",
                    "arguments": {
                        "path": str(ledger),
                        "center": "claude",
                        "input_tokens": 10,
                        "output_tokens": 2,
                        "cost_usd": 0.01,
                    },
                },
            }
        )
        report = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {"name": "harness_usage_report", "arguments": {"path": str(ledger)}},
            }
        )

        self.assertIn("\"claude\"", report["result"]["content"][0]["text"])

    def test_search_tools_build_and_query_index(self):
        root = Path(self.tmp.name) / "repo"
        root.mkdir()
        (root / "auth.py").write_text("token login", encoding="utf-8")
        index = Path(self.tmp.name) / "index.json"
        dispatch(
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "harness_index_repo",
                    "arguments": {"root": str(root), "index_path": str(index)},
                },
            }
        )
        result = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "harness_search_index",
                    "arguments": {"index_path": str(index), "query": "login"},
                },
            }
        )

        self.assertIn("auth.py", result["result"]["content"][0]["text"])

    def test_indexed_context_pack_tool_uses_search_results(self):
        root = Path(self.tmp.name) / "repo"
        root.mkdir()
        (root / "auth.py").write_text("login token\n" * 30, encoding="utf-8")
        index = Path(self.tmp.name) / "index.json"
        dispatch(
            {
                "jsonrpc": "2.0",
                "id": 16,
                "method": "tools/call",
                "params": {"name": "harness_index_repo", "arguments": {"root": str(root), "index_path": str(index)}},
            }
        )
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 17,
                "method": "tools/call",
                "params": {
                    "name": "harness_indexed_context_pack",
                    "arguments": {"root": str(root), "index_path": str(index), "query": "login token"},
                },
            }
        )

        self.assertIn("Indexed context pack", response["result"]["content"][0]["text"])

    def test_init_project_tool_creates_harness_files(self):
        root = Path(self.tmp.name) / "target"
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "tools/call",
                "params": {
                    "name": "harness_init_project",
                    "arguments": {"root": str(root), "features": ["Add login"]},
                },
            }
        )

        self.assertIn("feature_list", response["result"]["content"][0]["text"])
        self.assertTrue((root / "init.sh").exists())

    def test_local_model_gate_tool_blocks_high_swap(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 13,
                "method": "tools/call",
                "params": {
                    "name": "harness_local_model_gate",
                    "arguments": {
                        "machine": {"swap_used_mb": 7600, "swap_total_mb": 8192, "memory_free_percent": 45},
                        "task_complexity": "complex",
                    },
                },
            }
        )

        self.assertIn("\"allow\": false", response["result"]["content"][0]["text"])

    def test_local_worker_plan_tool_uses_gate(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 18,
                "method": "tools/call",
                "params": {
                    "name": "harness_plan_local_worker",
                    "arguments": {
                        "task": "summarize large context",
                        "machine": {"swap_used_mb": 7600, "swap_total_mb": 8192, "memory_free_percent": 45},
                        "task_complexity": "complex",
                    },
                },
            }
        )

        self.assertIn("extractive", response["result"]["content"][0]["text"])

    def test_contextual_context_pack_tool_returns_context_headers(self):
        root = Path(self.tmp.name) / "contextual-repo"
        root.mkdir()
        (root / "auth.py").write_text("def login_user(token):\n    return bool(token)\n", encoding="utf-8")

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 23,
                "method": "tools/call",
                "params": {
                    "name": "harness_contextual_context_pack",
                    "arguments": {"root": str(root), "query": "login token", "top_k": 1},
                },
            }
        )

        text = response["result"]["content"][0]["text"]
        self.assertIn("Contextual context pack", text)
        self.assertIn("symbol: def login_user(token):", text)

    def test_structured_local_worker_tool_exposes_schema_plan(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 24,
                "method": "tools/call",
                "params": {
                    "name": "harness_plan_structured_local_worker",
                    "arguments": {
                        "task": "summarize",
                        "machine": {"swap_used_mb": 512, "swap_total_mb": 8192, "memory_free_percent": 55},
                        "task_complexity": "light",
                        "schema": {"type": "object", "properties": {"summary": {"type": "string"}}},
                    },
                },
            }
        )

        text = response["result"]["content"][0]["text"]
        self.assertIn("structured_ollama", text)
        self.assertIn("json_schema", text)

    def test_scaffold_capability_tool_creates_skill(self):
        root = Path(self.tmp.name) / "cap"
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 14,
                "method": "tools/call",
                "params": {
                    "name": "harness_scaffold_capability",
                    "arguments": {"root": str(root), "name": "memory-auditor", "description": "Audit memory quality"},
                },
            }
        )

        self.assertIn("SKILL.md", response["result"]["content"][0]["text"])

    def test_list_capabilities_tool_returns_scaffolded_items(self):
        root = Path(self.tmp.name) / "cap-list"
        dispatch(
            {
                "jsonrpc": "2.0",
                "id": 20,
                "method": "tools/call",
                "params": {
                    "name": "harness_scaffold_capability",
                    "arguments": {"root": str(root), "name": "rag-upgrader", "description": "Upgrade RAG"},
                },
            }
        )
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 21,
                "method": "tools/call",
                "params": {"name": "harness_list_capabilities", "arguments": {"root": str(root)}},
            }
        )

        self.assertIn("rag-upgrader", response["result"]["content"][0]["text"])

    def test_self_growth_cycle_tool_records_cycle(self):
        root = Path(self.tmp.name) / "growth"
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 15,
                "method": "tools/call",
                "params": {
                    "name": "harness_run_growth_cycle",
                    "arguments": {
                        "root": str(root),
                        "topic": "mcp memory",
                        "sources": [{"title": "MCP", "url": "https://example.test"}],
                        "actions": ["Add tool"],
                    },
                },
            }
        )

        self.assertIn("cycle_path", response["result"]["content"][0]["text"])

    def test_evaluated_growth_cycle_tool_records_pass(self):
        root = Path(self.tmp.name) / "growth-eval"
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 19,
                "method": "tools/call",
                "params": {
                    "name": "harness_run_evaluated_growth_cycle",
                    "arguments": {
                        "root": str(root),
                        "topic": "rag upgrade",
                        "sources": [{"title": "RAG", "url": "https://example.test"}],
                        "actions": ["Add index"],
                        "usage": {"center": "codex", "input_tokens": 10, "output_tokens": 1, "cost_usd": 0},
                        "required_evidence": ["cycle recorded", "usage recorded"],
                    },
                },
            }
        )

        self.assertIn("PASS", response["result"]["content"][0]["text"])

    def test_memory_audit_tool_reports_handoff_issues(self):
        root = Path(self.tmp.name) / "audit"
        handoffs = root / "production_artifacts" / "handoffs"
        handoffs.mkdir(parents=True)
        (handoffs / "weak.md").write_text("# Weak\n\nDone.\n", encoding="utf-8")

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 22,
                "method": "tools/call",
                "params": {"name": "harness_audit_handoffs", "arguments": {"root": str(root)}},
            }
        )

        self.assertIn("missing_evidence", response["result"]["content"][0]["text"])

    def test_doctor_tool_reports_harness_drift(self):
        root = Path(self.tmp.name) / "doctor"
        root.mkdir()
        (root / "README.md").write_text("Run `./scripts/harness-missing`.\n", encoding="utf-8")
        (root / "rules").mkdir()
        (root / "scripts").mkdir()
        (root / "harness_mcp").mkdir()
        (root / "harness_mcp" / "server.py").write_text("TOOLS = []\n", encoding="utf-8")

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 25,
                "method": "tools/call",
                "params": {"name": "harness_doctor", "arguments": {"root": str(root)}},
            }
        )

        self.assertIn("missing_script", response["result"]["content"][0]["text"])

    @patch("harness_mcp.server.subprocess.run")
    def test_delegate_claude_updates_quota_state_on_session_limit(self, run):
        run.return_value.returncode = 1
        run.return_value.stdout = "You've hit your session limit - resets 1:50am (Asia/Saigon)"
        run.return_value.stderr = ""

        dispatch(
            {
                "jsonrpc": "2.0",
                "id": 27,
                "method": "tools/call",
                "params": {"name": "harness_delegate_claude", "arguments": {"prompt": "review compact pack"}},
            }
        )

        state = server.load_state(server.STATE_PATH)
        self.assertFalse(state["quotas"]["claude"]["available"])
        self.assertEqual(0, state["quotas"]["claude"]["remaining_percent"])

    @patch("harness_mcp.server.subprocess.run")
    def test_delegate_timeout_updates_transient_failure_count(self, run):
        run.side_effect = server.subprocess.TimeoutExpired(cmd=["agy"], timeout=120)

        dispatch(
            {
                "jsonrpc": "2.0",
                "id": 31,
                "method": "tools/call",
                "params": {"name": "harness_delegate_antigravity", "arguments": {"prompt": "review"}},
            }
        )

        state = server.load_state(server.STATE_PATH)
        self.assertEqual(1, state["quotas"]["antigravity"]["consecutive_failures"])

    def test_experiment_tools_record_and_report_pair(self):
        path = Path(self.tmp.name) / "experiments.jsonl"
        for variant, input_tokens in (("baseline", 1000), ("harness", 400)):
            dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 28,
                    "method": "tools/call",
                    "params": {
                        "name": "harness_record_experiment_run",
                        "arguments": {
                            "path": str(path),
                            "experiment_id": "pair-1",
                            "task_fingerprint": "task-v1",
                            "center": "codex",
                            "variant": variant,
                            "input_tokens": input_tokens,
                            "output_tokens": 100,
                        },
                    },
                }
            )

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 29,
                "method": "tools/call",
                "params": {"name": "harness_experiment_report", "arguments": {"path": str(path)}},
            }
        )

        self.assertIn('"valid_pair_count": 1', response["result"]["content"][0]["text"])
        self.assertIn("token_savings_percent", response["result"]["content"][0]["text"])

    def test_hybrid_context_pack_tool_returns_ranked_line_chunks(self):
        root = Path(self.tmp.name) / "hybrid"
        root.mkdir()
        (root / "auth.py").write_text("def login(token):\n    return bool(token)\n", encoding="utf-8")

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 30,
                "method": "tools/call",
                "params": {
                    "name": "harness_hybrid_context_pack",
                    "arguments": {"root": str(root), "query": "login token", "top_k": 1},
                },
            }
        )

        text = response["result"]["content"][0]["text"]
        self.assertIn("Hybrid context pack", text)
        self.assertIn("lines: 1-2", text)

    def test_research_registry_tools_return_due_sources(self):
        path = Path(self.tmp.name) / "research.json"
        dispatch(
            {
                "jsonrpc": "2.0",
                "id": 32,
                "method": "tools/call",
                "params": {
                    "name": "harness_init_research_registry",
                    "arguments": {
                        "path": str(path),
                        "sources": [{"title": "MCP", "url": "https://example.test/mcp", "refresh_days": 7}],
                    },
                },
            }
        )
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 33,
                "method": "tools/call",
                "params": {"name": "harness_due_research_sources", "arguments": {"path": str(path)}},
            }
        )

        self.assertIn("never_checked", response["result"]["content"][0]["text"])

    def test_refresh_research_tool_handles_registry_with_no_due_sources(self):
        path = Path(self.tmp.name) / "research-fresh.json"
        server.init_research_registry(path, [])

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 34,
                "method": "tools/call",
                "params": {"name": "harness_refresh_research_sources", "arguments": {"path": str(path)}},
            }
        )

        self.assertIn('"checked_count": 0', response["result"]["content"][0]["text"])

    def test_semantic_index_plan_tool_blocks_high_swap(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 35,
                "method": "tools/call",
                "params": {
                    "name": "harness_plan_semantic_index",
                    "arguments": {
                        "machine": {"swap_used_mb": 12610, "swap_total_mb": 13312, "memory_free_percent": 36},
                        "installed_models": [],
                    },
                },
            }
        )

        text = response["result"]["content"][0]["text"]
        self.assertIn("hybrid_lexical", text)
        self.assertIn('"use_ollama": false', text)

    def test_retrieval_eval_tool_returns_pass_for_matching_dataset(self):
        root = Path(self.tmp.name) / "eval-repo"
        root.mkdir()
        (root / "auth.py").write_text("def login(token):\n    return bool(token)\n", encoding="utf-8")
        dataset = Path(self.tmp.name) / "eval.json"
        dataset.write_text(
            '{"cases":[{"id":"auth","query":"login token","expected_paths":["auth.py"]}]}',
            encoding="utf-8",
        )

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 36,
                "method": "tools/call",
                "params": {
                    "name": "harness_evaluate_hybrid_retrieval",
                    "arguments": {"root": str(root), "dataset_path": str(dataset), "top_k": 1},
                },
            }
        )

        self.assertIn('"verdict": "PASS"', response["result"]["content"][0]["text"])

    def test_readiness_tool_reports_degraded_center(self):
        state = server.default_state()
        state["quotas"]["antigravity"]["consecutive_failures"] = 1
        server.save_state(server.STATE_PATH, state)
        probes = {center: {"installed": True, "harness_connected": True} for center in ("codex", "claude", "antigravity")}

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 40,
                "method": "tools/call",
                "params": {"name": "harness_readiness_report", "arguments": {"probes": probes}},
            }
        )

        self.assertIn('"status": "degraded"', response["result"]["content"][0]["text"])

    def test_codex_experiment_ingest_tool_reads_jsonl_usage(self):
        path = Path(self.tmp.name) / "codex-exp.jsonl"
        raw = '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":20}}\n'

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 41,
                "method": "tools/call",
                "params": {
                    "name": "harness_ingest_codex_experiment",
                    "arguments": {
                        "path": str(path),
                        "raw_jsonl": raw,
                        "experiment_id": "codex-1",
                        "task_fingerprint": "task-v1",
                        "variant": "baseline",
                    },
                },
            }
        )

        self.assertIn('"input_tokens": 100', response["result"]["content"][0]["text"])

    def test_output_compactor_tool_deduplicates_warnings(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 42,
                "method": "tools/call",
                "params": {
                    "name": "harness_compact_tool_output",
                    "arguments": {"text": "WARN repeated\n" * 20 + "ERROR final\n", "max_chars": 500},
                },
            }
        )

        text = response["result"]["content"][0]["text"]
        self.assertIn("repeated 20 times", text)
        self.assertIn("ERROR final", text)

    def test_structured_handoff_tools_validate_evidence(self):
        root = Path(self.tmp.name) / "handoff-root"
        root.mkdir()
        (root / "evidence.txt").write_text("pass", encoding="utf-8")
        created = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 43,
                "method": "tools/call",
                "params": {
                    "name": "harness_record_structured_handoff",
                    "arguments": {
                        "root": str(root),
                        "title": "Review",
                        "summary": "Ready",
                        "from_center": "codex",
                        "to_center": "claude",
                        "task_fingerprint": "task-v1",
                        "evidence": ["evidence.txt"],
                    },
                },
            }
        )
        manifest = __import__("json").loads(created["result"]["content"][0]["text"])["manifest_path"]
        validated = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 44,
                "method": "tools/call",
                "params": {"name": "harness_validate_structured_handoff", "arguments": {"manifest_path": manifest, "root": str(root)}},
            }
        )

        self.assertIn('"verdict": "PASS"', validated["result"]["content"][0]["text"])

    def test_autopilot_plan_tool_uses_signals(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 45,
                "method": "tools/call",
                "params": {
                    "name": "harness_plan_next_growth_action",
                    "arguments": {
                        "doctor": {"ok": True, "issues": []},
                        "readiness": {"ready_centers": []},
                        "research": {"due_count": 0, "changed_count": 0},
                        "retrieval_eval": {"verdict": "PASS"},
                        "pending_feature": {"id": 1, "description": "Improve reporting"},
                    },
                },
            }
        )

        self.assertIn("local_maintenance", response["result"]["content"][0]["text"])

    def test_growth_campaign_tool_reports_in_progress(self):
        path = Path(self.tmp.name) / "campaign.json"
        dispatch(
            {
                "jsonrpc": "2.0",
                "id": 46,
                "method": "tools/call",
                "params": {"name": "harness_init_growth_campaign", "arguments": {"path": str(path), "target_hours": 10}},
            }
        )
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 47,
                "method": "tools/call",
                "params": {
                    "name": "harness_growth_campaign_status",
                    "arguments": {"path": str(path), "cycle_dir": str(Path(self.tmp.name) / "cycles")},
                },
            }
        )

        self.assertIn('"verdict": "IN_PROGRESS"', response["result"]["content"][0]["text"])

    def test_local_rag_pipeline_plan_blocks_high_swap(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 48,
                "method": "tools/call",
                "params": {
                    "name": "harness_plan_local_rag_pipeline",
                    "arguments": {
                        "task": "analyze architecture",
                        "chunk_count": 12,
                        "machine": {"swap_used_mb": 12600, "swap_total_mb": 13312, "memory_free_percent": 36},
                        "installed_models": ["qwen35-codex-local:latest"],
                    },
                },
            }
        )

        self.assertIn("retrieval_only", response["result"]["content"][0]["text"])

    def test_memory_tools_record_and_search(self):
        path = Path(self.tmp.name) / "memory.jsonl"
        dispatch(
            {
                "jsonrpc": "2.0",
                "id": 49,
                "method": "tools/call",
                "params": {
                    "name": "harness_record_memory",
                    "arguments": {"path": str(path), "content": "auth token decision", "source": "handoff.md", "kind": "decision"},
                },
            }
        )
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 50,
                "method": "tools/call",
                "params": {"name": "harness_search_memory", "arguments": {"path": str(path), "query": "auth token"}},
            }
        )

        self.assertIn("handoff.md", response["result"]["content"][0]["text"])

    def test_memory_sync_tool_ingests_growth_cycle(self):
        root = Path(self.tmp.name) / "memory-sync"
        cycles = root / "production_artifacts" / "self_growth"
        cycles.mkdir(parents=True)
        (cycles / "cycle.json").write_text(
            '{"topic":"RAG","sources":[],"actions":["Add ranking"],"action_count":1}',
            encoding="utf-8",
        )
        path = root / "production_artifacts" / "memory.jsonl"

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 51,
                "method": "tools/call",
                "params": {"name": "harness_sync_artifact_memories", "arguments": {"root": str(root), "path": str(path)}},
            }
        )

        self.assertIn('"created_count": 1', response["result"]["content"][0]["text"])

    def test_command_policy_tool_denies_destructive_command(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 52,
                "method": "tools/call",
                "params": {"name": "harness_validate_command", "arguments": {"command": "git reset --hard", "actor": "autopilot"}},
            }
        )

        self.assertIn('"verdict": "DENY"', response["result"]["content"][0]["text"])

    def test_capability_evaluation_tool_default_fails_draft(self):
        root = Path(self.tmp.name) / "cap-eval"
        server.scaffold_capability(root, "draft-tool", "Draft")

        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 53,
                "method": "tools/call",
                "params": {"name": "harness_evaluate_capability", "arguments": {"root": str(root), "name": "draft-tool", "evidence": []}},
            }
        )

        self.assertIn('"verdict": "NEEDS_WORK"', response["result"]["content"][0]["text"])

    def test_mcp_conformance_tool_checks_server(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 54,
                "method": "tools/call",
                "params": {"name": "harness_mcp_conformance", "arguments": {"root": str(server.ROOT)}},
            }
        )

        self.assertIn('"verdict": "PASS"', response["result"]["content"][0]["text"])

    def test_health_aggregation_tool_reports_constraints(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 55,
                "method": "tools/call",
                "params": {
                    "name": "harness_aggregate_health",
                    "arguments": {
                        "tests": {"passed": True}, "doctor": {"ok": True}, "mcp": {"verdict": "PASS"},
                        "retrieval": {"verdict": "PASS"}, "research": {"due_count": 0, "changed_count": 0},
                        "readiness": {"ready_centers": []}, "campaign": {"verdict": "IN_PROGRESS"}
                    },
                },
            }
        )

        self.assertIn("PASS_WITH_CONSTRAINTS", response["result"]["content"][0]["text"])

    def test_experiment_queue_tools_plan_a_reproducible_baseline(self):
        queue_path = Path(self.tmp.name) / "experiment_queue.json"
        experiments_path = Path(self.tmp.name) / "experiments.jsonl"
        dispatch(
            {
                "jsonrpc": "2.0",
                "id": 56,
                "method": "tools/call",
                "params": {"name": "harness_init_experiment_queue", "arguments": {"path": str(queue_path)}},
            }
        )
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 57,
                "method": "tools/call",
                "params": {
                    "name": "harness_plan_next_experiment",
                    "arguments": {
                        "queue_path": str(queue_path),
                        "experiments_path": str(experiments_path),
                        "readiness": {"ready_centers": ["claude"], "centers": {}},
                    },
                },
            }
        )

        self.assertIn('"variant": "baseline"', response["result"]["content"][0]["text"])
        self.assertIn('"center": "claude"', response["result"]["content"][0]["text"])

    def test_experiment_quality_tool_scores_real_citations(self):
        root = Path(self.tmp.name) / "quality"
        root.mkdir()
        citations = []
        for index in range(5):
            path = root / f"evidence-{index}.md"
            path.write_text("evidence", encoding="utf-8")
            citations.append(path.name)
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 58,
                "method": "tools/call",
                "params": {
                    "name": "harness_evaluate_experiment_output",
                    "arguments": {
                        "root": str(root),
                        "output": {"summary": "summary", "citations": citations, "risks": ["one", "two", "three"]},
                    },
                },
            }
        )

        self.assertIn('"quality_score": 1.0', response["result"]["content"][0]["text"])

    def test_growth_planner_tool_prioritizes_ready_token_experiment(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 59,
                "method": "tools/call",
                "params": {
                    "name": "harness_plan_next_growth_action",
                    "arguments": {
                        "doctor": {"ok": True, "issues": []},
                        "readiness": {"ready_centers": ["claude"]},
                        "research": {"due_count": 0, "changed_count": 0},
                        "retrieval_eval": {"verdict": "PASS"},
                        "pending_feature": {"id": 2, "description": "Add report"},
                        "experiment_plan": {
                            "verdict": "READY",
                            "run": {"center": "claude", "variant": "baseline", "experiment_id": "task:claude"},
                        },
                    },
                },
            }
        )

        self.assertIn('"action": "run_token_experiment"', response["result"]["content"][0]["text"])

    def test_experiment_blueprint_tool_returns_dry_run_command(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 60,
                "method": "tools/call",
                "params": {
                    "name": "harness_build_experiment_blueprint",
                    "arguments": {
                        "root": str(Path(self.tmp.name)),
                        "run": {
                            "experiment_id": "task:codex",
                            "task_fingerprint": "abc",
                            "center": "codex",
                            "variant": "harness",
                            "context_mode": "compact_harness",
                            "prompt": "summarize",
                            "output_schema": {"type": "object"},
                        },
                    },
                },
            }
        )

        text = response["result"]["content"][0]["text"]
        self.assertIn('"execute": false', text)
        self.assertIn('"codex"', text)
        self.assertIn('"exec"', text)

    def test_experiment_prepare_tool_writes_manifest(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 61,
                "method": "tools/call",
                "params": {
                    "name": "harness_prepare_experiment_run",
                    "arguments": {
                        "root": str(Path(self.tmp.name)),
                        "run": {
                            "experiment_id": "task:claude",
                            "task_fingerprint": "abc",
                            "center": "claude",
                            "variant": "baseline",
                            "context_mode": "raw_repo",
                            "prompt": "summarize",
                            "output_schema": {"type": "object"},
                            "quality_rules": ["citation_count=5"],
                        },
                    },
                },
            }
        )

        text = response["result"]["content"][0]["text"]
        self.assertIn('"manifest_path"', text)
        self.assertIn('"execute": false', text)

    def test_codex_preflight_tool_builds_compact_payload(self):
        root = Path(self.tmp.name) / "preflight"
        root.mkdir()
        (root / "auth.py").write_text("def login():\n    return 'token'\n" * 100, encoding="utf-8")
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 62,
                "method": "tools/call",
                "params": {
                    "name": "harness_codex_preflight",
                    "arguments": {"root": str(root), "task": "fix login token", "max_codex_chars": 2000},
                },
            }
        )

        text = response["result"]["content"][0]["text"]
        self.assertIn('"must_use_before_codex": true', text)
        self.assertIn('"codex_payload_tokens_estimate"', text)

    def test_agent_rag_pack_tool_writes_shared_pack(self):
        root = Path(self.tmp.name) / "agent-rag"
        root.mkdir()
        (root / ".harness").mkdir()
        (root / "auth.py").write_text("def login():\n    return 'token'\n" * 40, encoding="utf-8")
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 63,
                "method": "tools/call",
                "params": {
                    "name": "harness_agent_rag_pack",
                    "arguments": {"root": str(root), "task": "fix login token", "center": "project"},
                },
            }
        )

        text = response["result"]["content"][0]["text"]
        self.assertIn('"context_pack_path"', text)
        self.assertIn('"commands"', text)
        self.assertTrue((root / ".harness" / "context_packs" / "last-rag-pack.md").exists())


if __name__ == "__main__":
    unittest.main()
