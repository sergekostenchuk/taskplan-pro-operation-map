# Review workspace contract

## Purpose

Provide a local, portable review surface for understanding and discussing the operational graph. The workspace is a projection, not a new source of product truth.

## Required UI

- product overview as a fit-to-screen master pipeline, not a horizontally clipped card strip;
- data-driven lifecycle groups, ordered block path, main/all-relations modes, zoom, pan and fit controls;
- block cards with stable ID, short title, primary input/output, implementation state, gate count and review progress;
- block drill-down;
- node list and visual relations;
- search and type/implementation/review filters;
- node operational contract;
- implementation and concept traceability status;
- review progress and attention queue;
- five comment fields per node;
- configurable reviewer names;
- explicit review status;
- import/export review JSON;
- download self-contained reviewed HTML;
- orphan annotation visibility after graph-version changes.

The overview inspector is collapsed by default so the master pipeline receives the full working width. Selecting a block opens its detailed graph and node contract. Lifecycle groups and feedback transitions are presentation data; never hardcode project block IDs in the renderer.

## Locale projection

When the user requests multiple languages, generate one self-contained HTML with a locale selector. Do not fork the canonical graph or review state per language.

- bind the derived locale catalog to the canonical graph hash;
- bind comments to stable node IDs, independently of locale;
- translate all visible graph titles and operational-contract strings, not only navigation labels;
- preserve IDs, code spans, paths, commands, enum values, Markdown structure and product names literally;
- use local/offline translation by default; external translation requires explicit data-transfer approval;
- fail completeness checks when any requested locale is missing for a visible string;
- treat browser-native translation as an optional viewing aid, never as release evidence or a required runtime dependency.

The renderer accepts locale and presentation data as explicit inputs. It must not contain project block IDs, project-specific lifecycle groups or a fixed block count. UI strings for the five supported product locales are allowed product constants; project content is not.

If a graph uses another supported TASK-PLAN PRO schema, review-only rendering requires a deterministic readiness receipt bound to the exact graph ID, version and SHA-256. The generic renderer must not reinterpret or silently migrate that graph's product semantics.

## Review states

`unreviewed`, `questions`, `discussing`, `decision_made`, `change_required`, `change_applied`, `closed`.

Comments are annotations. Only an accepted `decision_made` record authorizes a separate change to concept/graph. Regeneration must preserve comments by stable node ID or show them as orphaned.

## Storage and privacy

- Embed graph and initial review JSON in the HTML.
- Autosave drafts to browser `localStorage` using graph ID/version/hash.
- Do not call remote endpoints or load CDN assets.
- Escape all graph/comment content; never execute it as HTML.
- Explain that a browser cannot silently overwrite the opened local file. The user must download/save a reviewed copy.

## Verification

Check at approximately 1280×800 and 390×844:

- non-blank overview;
- no horizontal overflow;
- block and node selection;
- exactly five comment text areas;
- visible keyboard focus;
- local restore after reload;
- JSON export/import;
- reviewed HTML contains the updated embedded review state;
- loading, empty, error, disabled, selected, saving and success states are represented or explicitly marked manual/not applicable.

`OPERATION-MAP-BUILD.json` records graph/concept hashes, output hashes, builder version, locales and the state of deterministic/browser checks. A generated manifest does not turn a `not_run` browser check into passed evidence.
