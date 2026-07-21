# Other compatible coding agents

The canonical bundle uses the portable Agent Skills shape:

```text
taskplan-pro-operation-map/
├── SKILL.md
├── references/
├── contracts/
├── scripts/
├── evals/
└── release/
```

A host is compatible with the core workflow when it can:

1. discover a directory-based skill with YAML `name` and `description` in
   `SKILL.md`;
2. preserve and read relative bundled resources;
3. provide local filesystem access under user-controlled permissions;
4. execute Python 3.10 or newer, or allow the user to run the packaged CLI;
5. report missing tools and denied permissions instead of fabricating outputs;
6. return generated files to the user without silently uploading their content.

## Host adapter boundary

A vendor adapter may define installation, discovery, invocation syntax, and
permission mapping. It must not change:

- graph schema or readiness rules;
- `CODE FIRST`, `NO PLACEHOLDERS`, `NO HARDCODE`, or evidence-honesty rules;
- canonical JSON authority;
- review-state separation;
- output acceptance criteria.

If a host cannot load bundled references or execute the validator, it may use
the npm CLI externally, but it must report that the agent-side workflow is only
partially integrated. A prompt-only copy is not a supported full installation.
