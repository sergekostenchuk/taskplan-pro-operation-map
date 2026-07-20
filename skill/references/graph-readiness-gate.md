# Graph Readiness Gate

Readiness is blocked by any error below:

## Structure

- duplicate/missing IDs;
- missing parents or edge endpoints;
- invalid relation/status;
- block order collision;
- graph/concept hash mismatch;
- projection source not canonical JSON.

## Meaning

- missing operational field;
- placeholder or generic non-verifiable wording;
- gate without both success and failure route;
- failure without a `returns_to` route;
- decision without a named acceptor;
- artifact without producer, reviewer or consumer;
- implemented claim without evidence.

## Traceability

- node without concept implementation reference;
- concept section without implementing node or approved exemption;
- node with unknown concept reference;
- block whose output is not consumed downstream;
- consecutive blocks without a connecting transition.

## Acceptance

`ready: true` means the graph is structurally admissible and has no detectable semantic omissions. It does not mean the concept is commercially correct or owner-accepted. Owner acceptance remains separate evidence.

Warnings may cover dense graphs, unusually large blocks or review ergonomics. A warning never silently overrides an error.
