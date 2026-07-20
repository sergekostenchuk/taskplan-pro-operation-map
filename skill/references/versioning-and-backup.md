# Versioning and backup

## Artifact classes

- Canonical: accepted concept and operation graph JSON.
- Derived configuration: presentation JSON and locale catalog bound to the graph hash.
- Review data: exported review JSON or reviewed HTML containing user comments.
- Rebuild evidence: build manifest with source/output hashes and check states.
- Projection: Markdown and self-contained review HTML.

## Safe save sequence

1. Run graph readiness and finalize.
2. Verify `OPERATION-MAP-BUILD.json` and artifact hashes.
3. Export review JSON or save reviewed HTML when comments exist.
4. If the user requests Git persistence, inspect status and stage exact canonical/source paths only.
5. Keep private comments and workbench evidence outside a public package unless explicitly approved.

Do not run `git add .` in a dirty worktree. Do not commit, tag, push, archive or overwrite user files without task authority.

## Recovery

Rebuild projections from the tagged canonical graph, presentation and locale catalog. Review comments are separate user data: recover them from exported review JSON or a reviewed HTML snapshot and import by stable node ID. Hash mismatches require explicit human confirmation and orphan annotations must remain visible.
