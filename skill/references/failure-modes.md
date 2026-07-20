# Failure modes and retries

| failure_mode | Meaning | Action | Retry limit |
| --- | --- | --- | --- |
| `tool_unavailable` | Python/filesystem/browser capability missing. | Use documented fallback or stop with the missing dependency. | Verify once. |
| `permission_blocked` | Required path is not readable/writable. | Ask for exact path authority. | None until authority changes. |
| `ambiguous_scope` | Concept, version, output boundary or human owner is unclear. | Ask one bounded question or stop. | None without new context. |
| `schema_mismatch` | Graph violates structural contract. | Correct the exact validator findings. | Two attempts. |
| `semantic_gap` | Required meaning cannot be proven. | Return to concept/owner decision; no placeholder. | None silently. |
| `traceability_gap` | Concept section or graph node is orphaned. | Link with evidence, exempt with reason, or remove unjustified node. | Two attempts. |
| `partial_output` | Required audit/projection is missing. | One bounded forward fix, then block acceptance. | One attempt. |
| `projection_drift` | Projection no longer matches graph hash. | Regenerate from canonical JSON. | One attempt. |
| `security_blocked` | Output would expose sensitive content or unsafe dependency. | Redact/block; never publish. | None until risk changes. |
| `regression_detected` | Previously proven behavior fails. | Reopen responsible implementation and rerun checks. | No recursive prerequisite creation. |

Never translate a failed gate into a new planning layer. Fix the bounded defect or return to the exact upstream semantic owner.
