---
name: taskplan-pro-operation-map
description: Turn an accepted product concept into a traceable operational graph and a self-contained multi-reviewer HTML workspace. Use when a user asks to decompose a concept into blocks, subblocks, steps, artifacts, gates, decisions and failure routes; assess whether the concept is operationally complete; build or audit an operation map; generate Markdown/HTML graph projections; or collect structured comments from an owner and two reviewers without creating a second source of truth.
compatibility: Requires local filesystem access and Python 3 standard library. Browser is optional for visual verification only.
---

# TASKPLAN-PRO-operation-map

Convert product meaning into a machine-checkable operating model, then generate review projections from that model. The skill has one user journey and two isolated phases. Never allow a polished visualization to hide an incomplete concept.

## Modes

Choose the smallest mode matching the request:

- `full`: accepted concept → operational graph → readiness audit → Markdown and review HTML.
- `graph-only`: create or revise the canonical graph and audit it.
- `review-only`: validate an existing graph and regenerate its projections without changing meaning.
- `audit`: report semantic, traceability, hierarchy, transition and projection defects without writing unless the user also asks for fixes.

If the concept is not accepted or its current version cannot be identified, do not begin `full`; return `ambiguous_scope` with the exact missing decision.

## Inputs

Required for `full`:

- current concept file or explicitly bounded concept content;
- output directory;
- graph identity and version;
- evidence-backed implementation status when implementation claims are requested.

Required for `review-only`:

- canonical graph JSON conforming to `contracts/operation-map.schema.json`, or a graph from another deterministic TASK-PLAN PRO schema accompanied by a passing hash-bound readiness receipt;
- output directory.

Optional projection inputs:

- presentation JSON conforming to `contracts/operation-presentation.schema.json`;
- graph-bound locale catalog conforming to `contracts/operation-locale-catalog.schema.json`;
- review-state JSON conforming to `contracts/operation-review.schema.json`;
- one source UI locale from `ru`, `en`, `es`, `fr`, `de`.

Optional reviewer names are configuration. Never hardcode machine paths, project names, block counts, reviewer identities or concept section numbers.

## Phase 1 — Concept Graph Architecture

Read [`references/concept-decomposition-contract.md`](references/concept-decomposition-contract.md), then [`references/graph-contract.md`](references/graph-contract.md).

1. Read the accepted concept completely. Identify its stable section IDs and source hash.
2. Reconstruct the end-to-end product/user journey before choosing blocks.
3. Decompose only as far as an operational boundary exists:

   ```text
   Product → block → subblock/step → artifact, gate, decision, failure route
   ```

4. For every block and actionable node, record all mandatory operational fields from the graph contract.
5. Link each node to the concept sections it implements. Link every non-exempt concept section back to at least one node.
6. Add explicit success transitions, failure transitions, narrow correction returns and human-owned decisions.
7. Mark implementation state only from real repository evidence. Use `designed_only` when implementation evidence is absent.
8. Write the canonical JSON directly. Markdown and Mermaid are never canonical inputs.
9. Run the Graph Readiness Gate in [`references/graph-readiness-gate.md`](references/graph-readiness-gate.md).

### Meaning boundary

Research, inspect the repository and propose solutions when facts are discoverable. Ask the user only for a genuinely human-owned product decision. If a required meaning cannot be established, record a readiness finding and stop. Do not write `TBD`, placeholders, generic success criteria, invented owners, fake evidence or decorative failure routes.

## Graph Readiness Gate

Run:

```bash
python3 scripts/operation_map.py validate \
  --graph <operation-map.json> \
  --concept <accepted-concept.md> \
  --report <operation-map-audit.json>
```

The graph may proceed only when the command returns zero and the report has `ready: true`. Two correction attempts are allowed for `schema_mismatch`; then stop and show the unresolved findings. A semantic gap requiring owner judgment cannot be retried silently.

## Phase 2 — Review Workspace

Read [`references/review-workspace-contract.md`](references/review-workspace-contract.md).

After readiness passes, generate deterministic projections:

```bash
python3 scripts/operation_map.py finalize \
  --graph <operation-map.json> \
  --concept <accepted-concept.md> \
  --presentation <operation-presentation.json> \
  --i18n <operation-i18n.json> \
  --output-dir <projection-directory>
```

The command produces:

- `OPERATION-MAP-AUDIT.json`;
- `OPERATION-MAP.md`;
- `OPERATION-MAP-PRESENTATION.json`;
- `OPERATION-MAP-I18N.json`;
- `OPERATION-MAP-REVIEW.html`.
- `OPERATION-MAP-BUILD.json`.

For review-only projection of a graph validated by another TASK-PLAN PRO validator, do not pretend the generic validator checked that schema. Require a passing receipt conforming to `contracts/operation-readiness-receipt.schema.json`:

```bash
python3 scripts/operation_map.py review \
  --graph <operation-graph.json> \
  --readiness-receipt <passing-audit.json> \
  --presentation <operation-presentation.json> \
  --i18n <operation-i18n.json> \
  --output-dir <projection-directory>
```

This route generates review projections and a normalized audit record but does not regenerate schema-specific Markdown.

The HTML must remain self-contained and local-first. It visualizes the graph, supports block/node drill-down, and gives every node five review fields:

1. owner observation;
2. owner question;
3. owner proposal;
4. reviewer 1 comment;
5. reviewer 2 comment.

Comments bind to stable node IDs and graph hash. They autosave to browser local storage and can be exported/imported as JSON or embedded into a downloaded HTML copy. Comments never mutate the canonical graph automatically.

When a multilingual workspace is requested, read [`references/localization-contract.md`](references/localization-contract.md). Keep one HTML and one review state. Generate a graph-hash-bound locale catalog for every visible content string, preserve technical literals exactly, and render locale changes as projections over stable IDs. The overview must be a large data-driven SVG master pipeline with lifecycle groups, main/all-relations modes, zoom, pan and fit-to-screen; a clipped horizontal card strip is not an acceptable overview.

The standard-library path builds a monolingual catalog. Translation is a separate optional build step:

```bash
python3 scripts/locale_catalog.py \
  --graph <operation-map.json> \
  --output <operation-i18n.json> \
  --provider <argos|ollama> \
  --locales en es fr de
```

Never install a translation provider or model silently. A prebuilt complete catalog is equally valid.

## Invariants

- `CODE FIRST`: completion means a validated graph and working projection files, not another plan describing them.
- `NO PLANS FOR PLANS`: do not create planning tasks as output.
- `NO PLACEHOLDERS`: unresolved meaning blocks readiness.
- `NO HARDCODE`: environment/project values are arguments or graph data; literal product constants require an explicit rationale.
- `KEEP IT SIMPLE`: add nodes, fields or validators only when they have a downstream consumer or prevent a named acceptance risk.
- `ONE CANON`: JSON graph is canonical; Markdown, Mermaid, VS Code and HTML are projections.
- `TRACEABILITY`: every element proves its contribution to the project goal and accepted concept.
- `USER JOURNEY`: the complete user/operator journey must be traversable, including success and recovery.
- `EVIDENCE HONESTY`: file existence is not implementation evidence.
- `LOCAL PRIVACY`: do not upload concepts, comments, screenshots or private paths.
- `GIT HYGIENE`: do not commit generated review state, private workbench data or unrelated changes unless the user requests it; never use a broad staging command in a dirty tree.
- `CLEANUP`: remove obsolete generated projections when superseded only after confirming they are derived and not canonical.

## Non-goals

This skill does not:

- execute TASK-PLAN implementation tasks;
- replace concept discovery or owner acceptance;
- invent missing product semantics;
- turn review comments directly into requirements;
- claim live agent execution or runtime animation;
- install itself into Codex, Claude or another runtime;
- require a server, API, database or external package for its core monolingual path;
- automatically commit, tag, upload or publish generated artifacts.

## Tool Verification

Runtime dependency states:

- filesystem: required;
- Python 3 standard library: required and must be verified before commands;
- browser: optional for visual evidence, with manual open as fallback;
- Argos or local Ollama: optional translation adapters, never core dependencies;
- network/MCP/API/package manager: not required by the core path.

If Python is unavailable, return `tool_unavailable`; do not pretend projections were validated. Follow [`references/production-skill-architecture.md`](references/production-skill-architecture.md).

## Failure Modes And Retry Policy

Use the closed rules in [`references/failure-modes.md`](references/failure-modes.md). Important stops:

- `ambiguous_scope`: concept/version not identified;
- `schema_mismatch`: structural graph defect, at most two correction attempts;
- `semantic_gap`: missing operational meaning or human decision, no silent retry;
- `traceability_gap`: concept or graph element is orphaned;
- `projection_drift`: regenerate projections from canonical JSON;
- `partial_output`: requested locale coverage or projection artifact is incomplete; do not call the workspace multilingual-ready;
- `security_blocked`: optional translation dependency is unpinned, unapproved or fails the dependency gate;
- `regression_detected`: reopen the responsible script/change and rerun all checks;
- `permission_blocked`: ask only for the exact missing write/read authority.

## Evidence And Acceptance

Completion is not acceptance. Report:

- input concept and graph paths plus source hashes;
- audit report path and `ready` result;
- projection paths;
- build-manifest path and artifact hashes;
- exact commands and exit codes;
- test results;
- desktop/mobile visual evidence when a browser is available;
- skipped checks and remaining risks.

Before packaging or calling the skill release-ready, run a separated final user-journey review and save `review.json` with score at least 9/10. Package only clean source; exclude concepts, comments, screenshots, local paths and workbench traces. For recovery and versioning rules, read [`references/versioning-and-backup.md`](references/versioning-and-backup.md).
