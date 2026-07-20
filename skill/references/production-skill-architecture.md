# Production architecture

## Boundary

`SKILL.md` routes the workflow. Domain rules live in `references/`, deterministic validation/rendering in `scripts/`, schemas in `contracts/`, and examples/evals in `evals/`.

The source package must contain no user concept, review comments, screenshots, local absolute paths, secrets or workbench traces.

## Dependencies

The core runtime implementation uses only Python 3 standard library and browser-native HTML/CSS/JavaScript. No package installation, network, API, MCP, database or local server is required for graph validation, monolingual projection or locale-catalog validation. Argos and local Ollama are optional translation adapters and must pass their own tool/dependency gates.

## Executable modules

- `scripts/operation_map.py`: graph validation, projection orchestration and build manifest.
- `scripts/review_workspace.py`: presentation-driven SVG/HTML renderer and review-state validation.
- `scripts/locale_catalog.py`: standard-library catalog validation plus explicitly optional local translation adapters.

Project-specific graphs, lifecycle groups, locale content and comments remain inputs or derived artifacts. They must not be copied into the clean skill source.

## Evidence boundary

- Semantic correctness: concept traceability and human acceptance.
- Structural correctness: validator output.
- Projection correctness: deterministic hashes/tests.
- Visual correctness: rendered desktop/mobile artifact when browser access exists.
- Installation correctness: separate runtime smoke after explicit installation approval.

## Rollback

The skill writes only declared output files. Rollback is deletion of newly generated projections or restoration from Git. Canonical concept and graph files are never overwritten by `finalize`.
