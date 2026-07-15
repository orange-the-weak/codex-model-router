# Codex Auto Model Router

[![Codex Skill](https://img.shields.io/badge/OpenAI%20Codex-Skill-111827)](https://github.com/openai/skills)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Task-aware model routing and execution for OpenAI Codex.** Analyze a repository, select one GPT-5.6 Sol, Terra, or Luna route per request, tune reasoning effort from `low` to `xhigh`, track actual usage, and continuously improve the allocation from observed outcomes.

[Chinese README](README.zh-CN.md)

Codex Auto Model Router is a reusable Codex skill for developers who want faster AI-assisted engineering without sending requests through an external API. It combines repository analysis, deterministic model routing, adaptive reasoning effort, usage analytics, safe fallback behavior, and Markdown efficiency reports inside Codex.

## Why use it?

Using the strongest model at high reasoning for every task is usually unnecessary. This skill routes work by ambiguity, scope, coupling, verification difficulty, and consequence of error:

- **Luna** for mechanical, repetitive, high-volume work with deterministic checks.
- **Terra** for ordinary features, localized bugs, UI iteration, tests, and bounded refactors.
- **Sol** for architecture, security, migrations, concurrency, cross-system diagnosis, and high-risk review.
- **Adaptive reasoning** uses `medium` as the normal default, then moves to `low`, `high`, or `xhigh` only when task scope, risk, and verification difficulty justify it.

The generated report estimates productivity improvement against an all-Sol/medium baseline. Repository-specific measurements replace the heuristic after enough comparable history exists.

## Features

- Repository-aware model and reasoning-effort recommendations.
- Apply mode selects one route for the whole request and, when the current Codex surface exposes a same-task `model` x `thinking` override, executes it there and restores the original route afterward.
- A missing or stale report no longer inserts a separate Assess turn; bounded work uses a deterministic fallback route to reduce latency.
- Tiny mechanical changes keep the current route when switching and restoration would cost more than the work; explicit user overrides always win.
- Current task identity and route are verified from `CODEX_THREAD_ID` and local `turn_context` or `thread_settings_applied` settings metadata without reading prompt content.
- One visible route notice per request in the Codex conversation, including model, reasoning effort, and purpose.
- Same-task routed continuations; no new top-level Codex task.
- Fast local Query and Record modes that do not start an analysis agent.
- Persistent model x effort usage ratios in `.codex/model-routing-history.jsonl`.
- Evidence-based Retune mode using success, failure, escalation, rework, median duration, and P75 duration.
- Deterministic report updates that preserve unrelated Markdown content.
- GPT-5.6 availability fallback with honest model labeling.
- Optional custom-agent presets for Codex surfaces that explicitly support selecting named agents; generic subagent names are never treated as proof of a model switch.
- No API key, external model gateway, or API integration required.

## Install

### Install the Skill from a Codex conversation

In Codex, send:

```text
$skill-installer Install the Codex Auto Model Router skill from https://github.com/orange-the-weak/codex-auto-model-router
```

The Skill installer places the Skill in `~/.codex/skills/codex-auto-model-router`. It does not run this repository's `install.sh`, install the optional 24 custom-agent presets, or remove the legacy Skill name. For a first pure-Skill installation this is sufficient; use the terminal method for a full installation or rename migration. Restart Codex afterward.

### Install from a terminal

Clone the repository and run the installer:

```bash
git clone https://github.com/orange-the-weak/codex-auto-model-router.git
cd codex-auto-model-router
./install.sh
```

The installer copies:

- this skill to `${CODEX_HOME:-~/.codex}/skills/codex-auto-model-router`
- the twelve router and twelve executor agents to `${CODEX_HOME:-~/.codex}/agents`

Restart Codex after installation so it refreshes skills and custom agents.

The installer only changes this Skill's files inside `CODEX_HOME`; it does not modify project code, call an API, or remove unrelated files.
When upgrading from the former `codex-model-router` name, it removes only that legacy Skill folder and its `project-model-*` agent presets to prevent duplicate entries in Codex.

## Usage

Invoke the skill in Codex with `$codex-auto-model-router`.

```text
$codex-auto-model-router Analyze this repository and optimize model routing.

$codex-auto-model-router Query the actual model usage ratio.

$codex-auto-model-router Record: Terra low completed a UI task in 90 seconds.

$codex-auto-model-router Retune task allocation from the observed history.

$codex-auto-model-router Use GPT-5.6 Terra high for this assessment.

$codex-auto-model-router Apply the saved routing plan and implement the requested feature.
```

Before routed work starts, the skill shows one compact notice such as:

```text
Codex automatic routing | Segment: Repository assessment | Model: GPT-5.6 Sol | Reasoning: medium | Selected automatically from repository scope
```

It does not repeat the notice for commands, files, verification, or route restoration. On Codex surfaces that expose model-aware same-task follow-ups, routed work is sent back to the same task and the verified original route is restored after completion. Otherwise the skill uses an explicitly model-selectable subagent when available, then falls back honestly to the current model. It never creates a separate top-level task. A separate future Codex task must invoke the skill again or explicitly continue under the saved report.

Chinese prompts work too:

```text
$codex-auto-model-router Analyze this repository and optimize model routing.
$codex-auto-model-router Query actual model usage ratios.
$codex-auto-model-router Retune task allocation from success, failure, and duration history.
```

## Outputs

The skill keeps the chat response short and writes the full evidence to:

```text
docs/codex-model-routing-report.md
```

Confirmed usage history is stored as append-only JSONL:

```text
.codex/model-routing-history.jsonl
```

Actual execution, router-analysis usage, and recommended allocation are reported separately. Recommendations are never counted as actual use.

## Retuning thresholds

- Raise a route after at least five comparable attempts with at least 40% failure, escalation, or rework pressure.
- Lower a route after at least ten comparable attempts, at least 90% completion, no pressure events, and deterministic verification.
- Preserve assignments when evidence is below threshold.

## Repository layout

```text
SKILL.md                       Codex workflow and routing contract
agents/openai.yaml             Skill UI metadata
references/                    Routing and usage-ledger rules
scripts/model_usage_ledger.py  Safe append, aggregation, and report rendering
scripts/route_policy.py         Deterministic route selection and current-task metadata inspection
codex-agents/                  Optional named-agent compatibility presets
tests/                         Distribution and ledger tests
install.sh                     Local Codex installer
```

## Privacy and safety

- The ledger stores model, effort, task class, outcome, optional duration, and fallback metadata.
- It does not store prompts, source code, secrets, or conversation text.
- Runtime inspection reads only the matching task's local settings events; it does not copy conversation content into reports or ledgers.
- Repository analysis is read-only and does not run builds or tests merely to create a routing plan.
- The skill cannot silently observe unrelated Codex tasks; actual use is recorded only from reliable task metadata or user confirmation.

## Compatibility

This project is designed for Codex installations that support personal skills and custom subagents. If a named GPT-5.6 preset is unavailable, the workflow continues with the current available Codex model and records the fallback instead of pretending the requested model ran.

## Development

Run the standard-library tests:

```bash
python3 -m unittest discover -s tests -v
```

Validate the public distribution:

```bash
python3 tests/validate_distribution.py
```

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).

This is an independent community project and is not affiliated with or endorsed by OpenAI.
