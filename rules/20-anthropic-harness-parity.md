# Anthropic Harness Parity

This harness intentionally matches Anthropic's long-running-agent principles where practical:

- persistent filesystem state instead of relying on chat memory only
- initializer/coding/evaluator separation through center routing and handoff files
- default-fail completion until evidence exists
- fresh-context evaluation for important reviews
- context engineering before model reasoning
- compact handoffs across context windows
- filesystem memory and research registries instead of replaying full conversation history
- iterative skill/tool development with separate evidence-based evaluation
- paired token experiments with quality guards
- aggregate health that refuses to hide missing or regressive tri-center token evidence
- chunk-level hybrid retrieval plus gated, cached semantic embeddings
- MCP protocol negotiation through stable `2025-11-25` while preserving supported legacy clients

Current gaps:

- local semantic embeddings are implemented but intentionally gated off when live swap/RAM pressure is unsafe
- evaluator is evidence-contract based, not a separate cloud model by default
- automatic tool-result clearing inside third-party UIs is not controlled directly
- MCP release candidates are monitored but are not treated as stable requirements until promoted
- live paired token evidence is still missing while all three cloud centers are unavailable or quota-blocked
