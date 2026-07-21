# Self-hosted runnable example

This is a real, source-backed example of the `taskplan-pro-operation-map`
module describing its own implemented workflow. It is not a fictional product
scenario and it is not a representation of the complete TASK-PLAN PRO
framework.

The accepted concept is derived from the released skill contract, validators,
tests, and package metadata. [`source-provenance.json`](source-provenance.json)
records which repository sources support each concept section.

## Run it

From the package root:

```bash
node bin/taskplan-operation-map.js validate \
  --graph examples/self-hosted/OPERATION-MAP.json \
  --concept examples/self-hosted/CONCEPT.md \
  --report examples/self-hosted/generated/OPERATION-MAP-AUDIT.json
```

Build all projections:

```bash
node bin/taskplan-operation-map.js finalize \
  --graph examples/self-hosted/OPERATION-MAP.json \
  --concept examples/self-hosted/CONCEPT.md \
  --output-dir examples/self-hosted/generated
```

Open `examples/self-hosted/generated/OPERATION-MAP-REVIEW.html` in a modern
browser. The generated directory is reproducible output; the concept,
provenance record, and canonical graph are the maintained example sources.

## Expected result

- validation exits with code `0` and reports `ready: true`;
- the build emits the audit, Markdown map, presentation and locale catalogs,
  self-contained HTML, and build manifest;
- the overview shows the validated-graph stage followed by the local review
  stage;
- implementation claims resolve to files included in this package.
