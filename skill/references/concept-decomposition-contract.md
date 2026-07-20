# Concept decomposition contract

## Goal

Transform an accepted concept into an operational model that a human can inspect and an implementation system can consume. Decomposition is architecture, not formatting.

## Hierarchy

Use the smallest truthful hierarchy:

```text
product
└── block: a meaningful end-to-end stage with one accepted output
    ├── step: one observable transformation
    ├── artifact: versioned evidence/output consumed downstream
    ├── gate: machine/human-verifiable admission condition
    ├── decision: named authority choosing among bounded outcomes
    └── failure: explicit rejected state returning to the narrowest owner
```

Do not add subblocks only for visual symmetry. A block is justified by a distinct input/output boundary, owner, risk boundary or independently verifiable user outcome.

## Required questions

Every block and actionable node must answer:

- what happens;
- where it happens;
- when it starts;
- why it benefits the project/user;
- required input and input quality;
- expected output;
- success criteria;
- failure criteria;
- failure response and return target;
- executor, reviewer and acceptor;
- resources/tools;
- evidence;
- next allowed transition.

Answers must be specific enough to distinguish success from file existence or task completion.

## Traceability

- Every node has non-empty `implements` unless it is a terminal/external reference with an explicit exemption.
- Every accepted concept section has at least one implementing node or an explicit `coverage_exemption` with reason and owner.
- A node that cannot prove project benefit is removed, merged or returned for concept clarification.
- Derived artifacts identify producer, reviewer and downstream consumer.

## Control flow

- Each block has an accepted entry and one main output.
- Consecutive blocks connect through actual artifacts/conditions, not prose order.
- Every gate has explicit success and failure outcomes.
- Every failure returns to the narrowest responsible step/block.
- Cycles are allowed only for named correction or learning routes.
- Human decisions name the decision owner and cannot be silently made by the agent.

## Parallelism and Git

Discovery and independent evidence collection may run in parallel when lanes have no shared write zone. Meaning acceptance, graph identity/version assignment, readiness, integration and release remain sequential gates.

Parallel implementation branches/worktrees require disjoint write zones, one integration owner, merge order, test responsibility and conflict escalation. The operation map describes these contracts; it does not perform Git mutations.

## Anti-overprocessing

- One small change may use one block and a few nodes.
- Do not duplicate global rules inside each node.
- Do not create a document/artifact without a named downstream consumer.
- Do not create a verifier for another verifier unless a concrete defect/risk cannot be checked by the existing acceptance gate.
- Stop decomposition when every leaf is measurable, bounded and handoff-ready.
