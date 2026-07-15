# Contributing

Thanks for improving Codex Auto Model Router.

## Before opening a pull request

1. Keep routing recommendations evidence-based and model availability claims verifiable.
2. Preserve the separation between actual execution, analysis runs, and recommended allocation.
3. Do not add API keys, external model gateways, telemetry, prompts, source code, or conversation content to the usage ledger.
4. Keep Query and Record on the deterministic no-agent fast path.
5. Add or update tests for script and distribution changes.

Run:

```bash
python3 -m unittest discover -s tests -v
python3 tests/validate_distribution.py
```

Use a focused pull request and explain the behavior change, evidence, and compatibility impact.
