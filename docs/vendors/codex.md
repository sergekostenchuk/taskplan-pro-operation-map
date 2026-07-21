# Codex

## Install

Copy the complete published `skill/` directory to:

```text
$CODEX_HOME/skills/taskplan-pro-operation-map/
```

Codex defaults `CODEX_HOME` to `~/.codex`. The resulting directory must contain
`SKILL.md`, `references/`, `contracts/`, `scripts/`, and the remaining bundled
support files at the same relative paths.

For installation from GitHub, Codex's skill installer can install the
repository path `skill` and name the destination
`taskplan-pro-operation-map`. Review the repository and pin the intended tag or
commit before installation.

## Invoke

```text
$taskplan-pro-operation-map
```

Then provide the accepted concept path, output directory, graph identity, and
requested mode. A new installation is available to Codex after skill discovery
refresh; if the current session does not list it, start the next turn or reload
the host.

## Verify

- Codex lists `taskplan-pro-operation-map` as available.
- The skill reads its bundled references before graph work.
- `python3 skill/scripts/operation_map.py --help` succeeds from a package
  checkout, or the installed equivalent path succeeds.
- The self-hosted example validates with exit code zero.

Codex tool permissions remain authoritative. The skill does not bypass sandbox,
network, filesystem, or approval boundaries.
