# Claude Code

Claude Code supports filesystem-based custom skills following the Agent Skills
format. Install the complete bundle at either scope:

```text
.claude/skills/taskplan-pro-operation-map/     # project scope
~/.claude/skills/taskplan-pro-operation-map/   # personal scope
```

The directory must contain `SKILL.md`, `references/`, `contracts/`, `scripts/`,
and all other published support files at their original relative paths. Do not
convert the bundle into a single prompt or copy only `SKILL.md`.

## Invoke

```text
/taskplan-pro-operation-map
```

Claude Code may also select the skill automatically when the request matches
its description. Provide the accepted concept path, output directory, graph
identity, and requested mode.

If the top-level skills directory did not exist when the session started,
restart Claude Code so it can discover the new directory. Normal changes inside
an already watched skills directory are detected live.

## Verify

- `/taskplan-pro-operation-map` is discoverable.
- Claude reads referenced files progressively from the same bundle.
- Python 3.10 or newer is available to the session.
- The self-hosted example validates with exit code zero.

Claude Code permission and workspace-trust settings remain authoritative. This
skill declares no vendor-specific `allowed-tools` override and does not require
an API upload, MCP server, backend, or telemetry.

Reference: [Claude Code skills documentation](https://code.claude.com/docs/en/slash-commands).
