# Benchmark evidence and routing implications

Snapshot: `gpt56-routing-evidence-2026-07-15`. The machine-readable source is
[`benchmark-evidence.json`](benchmark-evidence.json). It expires after 90 days; a stale,
missing, or invalid snapshot disables evidence-derived lanes and falls back to the
deterministic task policy. Apply never fetches the network.

## What counts as evidence

Evidence is ranked by how closely it matches Codex work:

1. **High weight:** OpenAI's coding results and Artificial Analysis's Coding Agent Index,
   which use coding-agent harnesses and repository/terminal tasks.
2. **Medium weight:** Artificial Analysis Intelligence Index results by reasoning effort.
   These are API measurements, so they inform relative capability, latency, and output
   growth only. They are not Codex wall time or Codex subscription cost.
3. **Supporting:** the original DeepSWE, Terminal-Bench, and SWE-Bench Pro papers explain
   task construction and validity. Community anecdotes and this repository's easy local
   fixtures do not create hard routing rules.

The Coding Agent Index v1.1 covers 321 tasks across DeepSWE (113), Terminal-Bench v2
(84 compatible tasks), and SWE-Atlas-QnA (124), with three repeats per task. Its public
methodology reports pass@1 plus pooled token and wall-time telemetry.

## Coding-agent results

| Model | AA Coding Agent Index | SWE-Bench Pro | DeepSWE v1.1 | Terminal-Bench 2.1 |
| --- | ---: | ---: | ---: | ---: |
| GPT-5.6 Sol | 80.0 | 64.6% | 72.7% | 88.8% |
| GPT-5.6 Terra | 77.4 | 63.4% | 69.6% | 87.4% |
| GPT-5.6 Luna | 74.6 | 62.7% | 67.2% | 84.7% |
| GPT-5.5 | 76.4 | 59.4% | 67.0% | 85.6% |

This supports three tiers, but not a blanket rule that every complex task needs Sol/high:
Terra and Luna remain close on coding-agent pass rates, while Sol is the strongest choice
when ambiguity, coupling, or consequences increase.

Sol Ultra's 91.9% Terminal-Bench 2.1 result is excluded from the routing matrix because it
is a multi-agent variant. `max` and `ultra` are also outside the automatic low/medium/high/
xhigh matrix; mixing them into the main table would overstate single-route performance.

## Effort findings

The independent API surface shows a consistent trade-off. Sol rises from 49 intelligence
at low to 54/56/58 at medium/high/xhigh, while time to first answer rises from 3.71 seconds
to 4.65/9.17/35.82 seconds. Terra xhigh scores 52, still below Sol medium at 54. Luna
xhigh scores 49, equal to Sol low, but used about ten times the total benchmark output of
Sol low in this snapshot. These figures are cross-surface priors, not promises for Codex.

Therefore:

- use Luna/low for clear mechanical edits and Luna/medium only for larger repetitive work;
- use Terra/low for bounded, deterministic ordinary work and Terra/medium when files or
  constraints interact;
- use Sol/medium for bounded complex work;
- use Sol/high for high ambiguity, high coupling, judgment-heavy verification, or high
  consequences;
- use Sol/xhigh only when a complex attempt has already failed or the user explicitly asks.

GPT-5.5 is retained as a comparison baseline. This snapshot has stable low, medium, and
high observations, but no stable xhigh observation; that cell is deliberately missing
rather than inferred. GPT-5.5 is not a normal routing lane: while any GPT-5.6 model is
available, availability fallback must remain inside Sol, Terra, or Luna. After verified
GPT-5.6 execution, an original GPT-5.5 setting is audit metadata, not a Restore target.

## Efficiency hypothesis

Against an all-Sol/medium baseline, an illustrative mix of 25% mechanical, 45% bounded
ordinary, 25% bounded complex, and 5% uncertain/high-consequence work reduces the weighted
API TTFT proxy by about 44% and the Intelligence Index output proxy by about 30%. Those are
not Codex end-to-end measurements: tools, builds, and verification dilute the gain. The
conservative planning estimate is therefore **15–30% faster AI-work turnaround** for a
similar mixed workload. Treat this as a hypothesis to validate from the local Segment
ledger, not a universal benchmark. The largest gain comes from moving routine work away
from Sol/medium without weakening the high-consequence lane.

Task evidence and user overrides always outrank this snapshot. A benchmark prior never
weakens a high-consequence route and never forces a runtime network request.

## Sources

- [OpenAI: GPT-5.6](https://openai.com/index/gpt-5-6/)
- [Artificial Analysis: Coding Agent Index methodology](https://artificialanalysis.ai/methodology/coding-agents-benchmarking)
- [Artificial Analysis: Coding Agent leaderboard](https://artificialanalysis.ai/agents/coding-agents)
- [Artificial Analysis: Intelligence Index methodology](https://artificialanalysis.ai/methodology/intelligence-benchmarking)
- [DeepSWE paper](https://arxiv.org/abs/2607.07946)
- [Terminal-Bench paper](https://arxiv.org/abs/2601.11868)
- [SWE-Bench Pro paper](https://arxiv.org/abs/2509.16941)

The per-effort source URL pattern is stored with the metrics in the JSON snapshot. Refresh
the snapshot before its expiry and rerun the full validators before publishing a new policy.
