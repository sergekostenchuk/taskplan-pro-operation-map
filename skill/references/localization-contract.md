# Localization contract

## Boundary

Localization is a derived projection over stable graph IDs. It must never fork the canonical operation graph or create language-specific review states.

The built-in review UI supports `ru`, `en`, `es`, `fr` and `de`. This is an explicit product capability, not a project-specific constant. Requested content locales must be listed in the locale catalog and must have complete translations for every visible graph string.

## Core path

The core Python-standard-library path may:

- create a monolingual catalog from the graph;
- validate catalog identity, graph hash and completeness;
- embed a complete catalog into one self-contained HTML;
- preserve comments while switching locale.

The core path does not translate text.

## Optional translation adapters

- `argos`: offline translation; requires an explicitly approved pinned package and installed language models.
- `ollama`: local model adapter; requires a verified local command/service and declared model.
- prebuilt catalog: no translation tool dependency; validate before use.

Never upload graph content to an external translation service without explicit data-transfer approval. Browser-native translation is an optional viewing aid, not release evidence.

## Literal preservation

Preserve identifiers, paths, commands, code spans, URLs, enum values, Markdown structure and product names. A catalog that loses a protected literal fails validation.

## Provenance

For every non-source locale record provider, engine/model version where available, language-model/package version where available, and `human_reviewed`. Machine-translated content remains visibly marked until human review.

## Failure rules

- graph-hash mismatch: `schema_mismatch`;
- missing requested locale or visible string: `partial_output`;
- unavailable optional adapter: `tool_unavailable` with prebuilt-catalog fallback;
- unapproved or unsafe package: `security_blocked`;
- browser translation only: check is `not_run`, never passed.
