# Execution state machine

Use this state machine for every Assess, Retune, or Apply invocation:

`CLASSIFY -> SELECT -> CAPABILITY_CHECK -> EXECUTE_LOCAL | DISPATCH_SWITCH | DISPATCH_SUBAGENT -> VERIFY -> RECORD -> RESTORE -> DONE`

## Invariants

- One invocation has one mode, one selected route, and one `route_id`.
- Apply contains the whole user request and uses one execution route. It never automatically becomes Assess and never chains model-specific implementation segments.
- Dispatch attempts at most one same-task model override and, if supported, at most one explicitly model-selectable subagent fallback.
- Only reliable task/thread metadata or explicit user confirmation establishes actual model identity.
- Never make a persistent same-task switch when the original model or effort is unknown.
- Tiny low-risk Apply work may keep the current route when switching plus restoration would dominate task time; an explicit user override bypasses this optimization.
- A switch with known original model and effort has exactly one Restore attempt.
- `RETURN` is terminal: it only presents the completed result and never performs work.
- Report or ledger persistence failure does not cancel otherwise valid Apply work.

## Transitions

| State | Success | Failure |
|---|---|---|
| CLASSIFY | SELECT | ask only for conflicting/unsupported explicit values |
| SELECT | CAPABILITY_CHECK | use deterministic Apply fallback when the report is absent |
| CAPABILITY_CHECK | EXECUTE_LOCAL when already matched or switch cost dominates; otherwise DISPATCH_SWITCH | DISPATCH_SUBAGENT only with an explicit selector; otherwise EXECUTE_LOCAL |
| EXECUTE_LOCAL | VERIFY | report task failure |
| DISPATCH_SWITCH | VERIFY inside routed turn | eligible subagent fallback, then current-route fallback |
| DISPATCH_SUBAGENT | VERIFY in parent | current-route fallback |
| VERIFY | RECORD | report verification failure without automatic rerouting |
| RECORD | RESTORE | note persistence failure internally and continue |
| RESTORE | DONE through RETURN when switched; otherwise DONE directly | stop after one failed restore attempt |

## Route envelope

Every same-task switched prompt carries:

- `route_id`
- selected model and effort
- verified `original_model` and `original_effort`
- mode and exact scope
- repository/report/ledger paths
- acceptance criteria and validation budget
- whether fallback disclosure is required by task risk

The routed result carries the same `route_id`, completion status, verification result, artifact paths, ledger status, and the concise user-facing result. This prevents unrelated continuations from being mistaken for the active route.

Local and isolated-subagent envelopes may mark the original route unknown because they do not persistently change the parent task.
