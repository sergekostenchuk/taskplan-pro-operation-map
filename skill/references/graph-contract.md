# Canonical graph contract

The canonical file conforms to `contracts/operation-map.schema.json` and uses schema version `taskplan-pro.operation-map/v1`.

## Canonical fields

- `graph_id`, `graph_version`, `status`.
- `concept_source`: relative path, SHA-256 and stable section registry.
- `blocks`: ordered stage records.
- `nodes`: all blocks, steps, artifacts, gates, decisions, failures and terminals.
- `edges`: typed direct relations with reverse labels.
- `coverage_exemptions`: reviewed concept sections intentionally outside this map.

## Node operational fields

The canonical keys are:

```text
what
where
when
why
input
input_requirements
expected_output
success_criteria
failure_criteria
failure_action
executor
reviewer
acceptor
resources
evidence
next_transition
```

All values are non-empty factual strings. Lists belong in structured node fields where the schema supplies them; do not encode machine state in decorative Markdown.

## Relations

Use a small closed vocabulary:

- `contains`;
- `on_success`;
- `on_failure`;
- `returns_to`;
- `produces`;
- `consumed_by`;
- `validated_by`;
- `accepted_by`;
- `unblocks`;
- `conditionally_unblocks`;
- `implements`;
- `realizes`.

Each edge has a stable ID, source, target, origin and reverse label. Conditions are required for conditional transitions.

## Implementation states

- `designed_only`;
- `partially_implemented`;
- `implemented`;
- `not_applicable`.

`implemented` and `partially_implemented` require non-empty repository evidence. No evidence means `designed_only`.

## Compatibility

Legacy localized field names may be migrated before validation, but new canonical graphs use the English keys above. Compatibility adapters must be explicit and versioned; they are not permission to hardcode one project structure into the validator.
