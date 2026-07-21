# Agent host compatibility

`taskplan-pro-operation-map` ships one canonical Agent Skills-compatible bundle
in `skill/`. Vendor integration changes discovery and invocation only; it must
not fork the skill's product rules, validators, schemas, or output semantics.

| Host | Installation guide | Invocation |
|---|---|---|
| Codex | [Codex](codex.md) | `$taskplan-pro-operation-map` |
| Claude Code | [Claude Code](claude-code.md) | `/taskplan-pro-operation-map` or automatic selection |
| Other compatible agents | [Generic Agent Skills host](compatible-agents.md) | Host-defined |

All hosts require:

- the complete `skill/` directory, not only `SKILL.md`;
- local read/write access to the selected project and output directory;
- Python 3.10 or newer for deterministic validation and rendering;
- explicit user authority for writes, installation, Git operations, or opening
  generated files;
- no claim of completion when a required tool or browser check was skipped.

The npm CLI is optional when the host can run `skill/scripts/operation_map.py`
directly. The npm launcher and the direct Python entry point execute the same
engine.
