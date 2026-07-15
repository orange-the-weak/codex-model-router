---
name: codex-auto-model-router
description: Deterministically analyze, apply, query, record, and retune project model routing inside Codex. Select one GPT-5.6 Sol, Terra, or Luna route and low, medium, high, or xhigh reasoning per request; prefer native same-task overrides, restore the original route afterward when known, fall back to an explicitly selectable subagent or the current model, write a full Markdown report, and maintain validated usage history. Use when the user invokes $codex-auto-model-router, asks which model should handle project work, requests routed implementation, queries usage ratios, records outcomes, or retunes assignments. Never create a new top-level Codex task.
---

# Codex Auto Model Router

Route each invocation through one deterministic policy. For Apply, select one model and effort for the whole user request, execute it once, and restore the original task model afterward when local Codex metadata exposes it. Skip model switching when its round-trip cost would dominate a tiny task. Query and Record stay local and fast. Never add API integration, estimate API spend, create a top-level Codex task, or commit/push unless the user separately requests it.

For Assess, Retune, or Apply, run `scripts/route_policy.py` before dispatch. Read [execution-state-machine.md](references/execution-state-machine.md) only for an audit, dispatch failure, or when the policy script is unavailable. Read [usage-ledger.md](references/usage-ledger.md) before changing history. Use [routing-criteria.md](references/routing-criteria.md) for assessment and efficiency estimates.

## Path dispatch

Choose exactly one path before doing any work:

- `ROUTE_PROJECT_MODELS_ROUTED_TURN=1` with `ROUTED_MODE=APPLY_ONESHOT`: execute only the supplied implementation request, then enter Restore.
- `ROUTE_PROJECT_MODELS_ROUTED_TURN=1` with `ROUTED_MODE=ASSESS` or `RETUNE`: perform only that analysis, save artifacts, then enter Restore.
- `ROUTE_PROJECT_MODELS_ROUTED_TURN=1` with `ROUTED_MODE=RETURN`: do no project work; return the prior routed result concisely.
- `ROUTE_PROJECT_MODELS_EXECUTOR=1`: execute only the supplied bounded request; do not assess or delegate.
- `ROUTE_PROJECT_MODELS_SUBAGENT=1`: use only the explicitly selected Subagent path.
- Otherwise use the Coordinator path.

Unknown `ROUTED_MODE` values are errors. Do not reinterpret them or recurse.

## Coordinator path

1. Classify exactly one mode:
   - **Apply:** build, change, fix, refactor, test, review, or other project execution. If analysis and implementation are both requested, this is Apply.
   - **Assess:** analyze or refresh repository routing without implementation.
   - **Query:** show usage, ratios, history, or current allocation.
   - **Record:** append a user-confirmed completed task and outcome.
   - **Retune:** adjust assignments using the report and observed history.
   - **Help:** a bare invocation with no actionable request. Show modes and examples in at most six lines; do not scan the repository.
2. Query, Record, and Help never switch models or spawn agents. Query and Record use `scripts/model_usage_ledger.py`; if the project-local ledger/report is not writable, report that persistence was skipped but do not block the user's main task.
3. Parse optional user overrides. Accept Sol, GPT-5.6, GPT-5.6 Sol, Terra, or Luna; accept low, medium, high, xhigh, and map `very high` or `extra high` to xhigh. One explicit supported choice wins. Ask only when values conflict or are unsupported.
4. Classify only the inputs needed by the policy script:
   - `task-kind=mechanical` for repetitive or copy-only work with deterministic checks; `ordinary` for bounded coding/test/review; `complex` for novel or cross-system work.
   - `risk=high` for security, privacy, money, production, migration, data-loss, or similarly consequential work; otherwise `low` or `normal`.
   - `size=tiny` only when the change is mechanical, normally one file, needs no broad investigation or build, and would likely finish within one model round trip; otherwise `normal` or `large`.
5. For Apply, inspect the existing report only when it is present and cheaply matches the task. Pass its matching model and effort to the policy script. A missing, stale, or uncovered report never triggers Assess.
6. Run the policy script with the mode, classifications, optional report route, and user overrides. It reads `CODEX_THREAD_ID` plus the matching local session's latest `turn_context` or `thread_settings_applied` settings to identify the current route without reading prompt content. Use its `route_id`, `recommended`, `execution`, `current`, and `restore_required` values as authoritative for dispatch. If the script cannot read runtime metadata, it returns an explicit unavailable state; do not guess.
7. Keep Apply as one segment and one route. Do not create a switching sequence, queue dependent model turns, or add an independent review turn unless the user explicitly requests separate stages.
8. Respect the policy's dispatch:
   - `local`: execute in this turn. For a tiny task, the execution route may intentionally differ from the recommendation because switching plus restoration would cost more than the work.
   - `same-task-switch`: dispatch once using the exact verified `current.thread_id`.
   - `selectable-subagent-or-local`: never make a persistent same-task switch because the original route cannot be restored; try an explicitly model-selectable subagent, otherwise execute locally.
9. If the script is missing or fails, use the same deterministic matrix: Luna low for mechanical work (medium when large), Terra medium for ordinary work (high when large), Sol high for complex/high-risk work, and keep the current route only for tiny mechanical Apply. Record the policy failure internally; do not block ordinary work.
10. Return a short answer. Full Assess/Retune detail belongs in the report; Apply returns the normal task result plus one compact route summary when useful.

## Query and Record fast path

Before Query or Record, show:

`Codex 自动路由｜任务段：<task segment>｜模型：local-script｜推理：none｜<reason>`

- Record the invocation as `skill_run` with the matching mode, `analysis_model=local-script`, and `effort=none`.
- Query runs `summary`, then `render` to update only the marked report section.
- Record appends only user-confirmed or reliable task-metadata execution, then runs `summary` and `render`.
- Return actual model and model-effort proportions, sample status, latest recommendation, and the report link.
- Never infer actual use from a recommendation or a configured-but-unverified route.

## Visible routing protocol

Immediately before Assess, Retune, Apply, Query, or Record, show exactly one compact commentary line:

`Codex 自动路由｜任务段：<task segment>｜模型：<model|current-route>｜推理：<low|medium|high|xhigh|none|keep>｜<reason>`

- This means Codex selected the route; do not use an ambiguous bare `路由提示` label.
- Do not repeat the line for commands, files, verification, Restore, or Return.
- A normal successful completion needs no separate model-identity or runtime-verification warning.
- For the tiny-task fast path, show the policy's execution route and say `任务较小，Codex 保持当前模型以避免切换延迟`; do not present the unused recommendation as the running model.
- Label a configured route as configured, not observed, when task metadata is unavailable.
- Only for a high-risk fallback, show: `Codex 自动路由状态｜目标：<model/effort>｜当前对话不支持带模型续接，已用当前可用模型继续｜<reason>`.

## Capability check and Dispatch

Use this fixed order once; never loop across routes:

1. Search available Codex task tools for `send_message_to_thread` (normally `codex_app__send_message_to_thread`) and use it only when it explicitly accepts `model` and `thinking`. Never call a thread/task creation capability. Use only the verified `current.thread_id` returned from `CODEX_THREAD_ID` metadata; never find the task by repository name or recency.
2. If same-task override is unavailable or rejected, use a subagent only when its interface explicitly accepts the requested model or named preset. Read [preset-mapping.md](references/preset-mapping.md). For Apply, select an executor preset and include only `ROUTE_PROJECT_MODELS_EXECUTOR=1`; for Assess/Retune, select a read-only router preset and include only `ROUTE_PROJECT_MODELS_SUBAGENT=1`. Both envelopes also carry mode, `route_id`, scope, paths, acceptance criteria, and validation budget. A task/agent name alone is not proof of model selection.
3. Otherwise continue with the current model. Keep low-risk fallback silent, disclose high-risk fallback once, and never claim the requested model actually ran.

For a same-task dispatch, send the entire user request and:

- `ROUTE_PROJECT_MODELS_ROUTED_TURN=1`
- `ROUTED_MODE=APPLY_ONESHOT`, `ASSESS`, or `RETUNE`
- a unique `route_id`
- repository path, exact scope, acceptance criteria, and validation budget
- selected model/effort and the reason
- verified `original_model` and `original_effort`; without both, do not use same-task dispatch
- report and ledger paths
- an instruction to read applicable `AGENTS.md`, this skill, and the state-machine reference

End the coordinator turn after the follow-up is accepted. The routed turn owns completion and Restore. Do not switch the same task when the original model or effort is unknown, because that would persistently change later turns.

## Routed Apply one-shot

When `ROUTED_MODE=APPLY_ONESHOT`:

1. Execute the entire supplied user request as one routed unit. Do not reassess routing, split it into model stages, delegate, or dispatch another implementation turn.
2. Read applicable repository instructions, preserve unrelated changes, implement, and verify proportionately.
3. Run `scripts/route_policy.py --inspect-current` after the switched turn starts. Record the Apply `skill_run` and actual execution only when this metadata matches the selected route or the user confirms it. Record verification as `deterministic`, `manual`, `none`, or `unknown`; only deterministic verification can support automatic lowering. Otherwise keep configured route and actual usage distinct.
4. On failure, diagnose and report it. Do not silently retry with a second model; a new route requires a new user or coordinator invocation.
5. Enter Restore after success or failure.

## Routed Assess and Retune

When `ROUTED_MODE=ASSESS` or `RETUNE`:

1. Perform only the requested read-only analysis. Do not implement project work or recursively dispatch.
2. Save the full report to `<repository>/docs/codex-model-routing-report.md`, unless repository instructions specify another report directory.
3. Maintain `<repository>/.codex/model-routing-history.jsonl` with the ledger script. Record the skill run, append the latest recommended allocation, then render the usage section. If persistence fails due permissions, finish the analysis and mention the skipped artifact once in the short result.
4. Enter Restore after success or failure.

## Restore and Return

- If no model switch occurred, return the result directly. A same-task switch is forbidden when the original route is unknown. Do not emit an identity warning on normal success.
- If a same-task switch occurred and both original values are known, send one same-task follow-up using the original `model` and `thinking`, with `ROUTE_PROJECT_MODELS_ROUTED_TURN=1`, `ROUTED_MODE=RETURN`, the same `route_id`, and the completed result. This is the only allowed post-execution continuation.
- If restoration is rejected, do not loop. Mention it only for high-risk work or when the user asks for an audit.
- A Return turn performs no tools, edits, tests, assessment, delegation, ledger writes, or additional routing. It presents the supplied completed result in the required concise format.

## Subagent path

The read-only Subagent path requires both `ROUTE_PROJECT_MODELS_SUBAGENT=1` and an interface-confirmed model or named router preset. Do not delegate again. Perform the supplied Assess or Retune request once and return results to the parent, which writes artifacts. Apply uses the separate Executor path and marker. A generic subagent may isolate work, but its model must remain unverified and it must not be counted as the requested model.

## Assessment workflow

1. Read applicable `AGENTS.md` and repository guidance.
2. Inventory with cheap read-only commands. Exclude generated output, dependencies, caches, binaries, and vendored code unless directly relevant.
3. Identify areas by responsibility and workflow; inspect representative entry points, manifests, tests, build/deploy files, and risk boundaries.
4. Classify recurring tasks by ambiguity, scope, coupling, verification difficulty, and consequence of error.
5. Select the smallest model and lowest effort likely to finish correctly in one pass. Lower routes after decomposition; raise only for concrete ambiguity, coupling, or consequences.

Do not compile or run tests merely to create a routing plan. For iOS repositories, respect local validation guidance and never launch a full build for a small routing assessment.

## Routing principles

- All three models default to medium when no task evidence supports another effort.
- Luna fits mechanical, repetitive, high-volume, locally verifiable work.
- Terra fits ordinary bounded implementation, test, and review work.
- Sol fits ambiguous, deeply coupled, high-risk, or novel work where a wrong plan costs more than extra reasoning.
- Prefer a bounded task over higher effort. Use xhigh only with an explicit reason.
- Route tasks, not permanent folder ownership. Reassess after architecture/model-picker changes, sensitive integrations, or diagnosed lower-tier failure.

## Report and ledger output

Lead the report with the recommended default execution model and effort. State the actual analysis model/effort separately from recommendations, and label fallback or uncertainty only when relevant. Include this table:

| Project area or task | Evidence | Model | Reasoning | Why | Upgrade trigger |
|---|---|---|---|---|---|

Then include Fast path, Use Sol only when, a minimal switching sequence for future independent tasks, Efficiency estimate, Usage proportions, and Confidence and gaps. The efficiency estimate must state baseline, task-mix assumptions, calculation, `预计增效：约 X–Y%`, highest-impact optimization, and whether it is heuristic or measured.

Under `## Usage proportions`, include exactly one empty marker pair:

`<!-- MODEL_USAGE_START -->`

`<!-- MODEL_USAGE_END -->`

The ledger script fills the markers. Do not generate statistics inside them. Retune raises only after at least 5 comparable attempts with at least 40% failure/escalation/rework pressure, and lowers only after at least 10 attempts with at least 90% completion and no pressure events. Otherwise hold unless the user explicitly asks for heuristic retuning.

The chat summary should contain about six bullets or fewer: default route, two or three highest-impact optimizations, estimated efficiency range and baseline, analysis route, report link, and actual versus recommended proportions for Query or Retune.
