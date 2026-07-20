#!/usr/bin/env python3
"""Validate a TASKPLAN-PRO operation graph and build deterministic projections."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from review_workspace import build as build_review_workspace
from review_workspace import default_catalog, default_presentation


SCHEMA_VERSION = "taskplan-pro.operation-map/v1"
BUILDER_VERSION = "0.2.0"
NODE_TYPES = {"block", "step", "artifact", "gate", "decision", "failure", "terminal", "external_reference"}
STATUSES = {"designed_only", "partially_implemented", "implemented", "not_applicable"}
RELATIONS = {"contains", "on_success", "on_failure", "returns_to", "produces", "consumed_by", "validated_by", "accepted_by", "unblocks", "conditionally_unblocks", "implements", "realizes"}
ACTIONABLE = {"block", "step", "gate", "decision", "failure"}
OPERATIONAL_FIELDS = (
    "what", "where", "when", "why", "input", "input_requirements", "expected_output",
    "success_criteria", "failure_criteria", "failure_action", "executor", "reviewer",
    "acceptor", "resources", "evidence", "next_transition",
)
PLACEHOLDER = re.compile(r"(?i)(\b(?:tbd|todo|fixme|placeholder|lorem|xxx)\b|<[^>]+>|заполнить|уточнить\s+позже|заглушк)")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("graph root must be a JSON object")
    return value


def add(findings: list[dict[str, str]], code: str, path: str, message: str) -> None:
    findings.append({"code": code, "path": path, "message": message})


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def strings(value: Any) -> bool:
    return isinstance(value, list) and all(nonempty(item) for item in value) and len(value) == len(set(value))


def validate_graph(graph: dict[str, Any], graph_path: Path, concept_path: Path | None) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    required = ("schema_version", "graph_id", "graph_version", "status", "canonical_source", "concept_source", "blocks", "nodes", "edges", "coverage_exemptions")
    for key in required:
        if key not in graph:
            add(errors, "missing_field", key, f"required top-level field {key!r} is missing")
    if errors:
        return report(graph, graph_path, errors, warnings, concept_path)
    if graph.get("schema_version") != SCHEMA_VERSION:
        add(errors, "schema_mismatch", "schema_version", f"expected {SCHEMA_VERSION}")
    for key in ("graph_id", "graph_version", "canonical_source"):
        if not nonempty(graph.get(key)):
            add(errors, "invalid_field", key, "must be a non-empty string")
    if graph.get("status") not in {"draft", "review", "ready", "superseded"}:
        add(errors, "invalid_status", "status", "unknown graph status")

    concept = graph.get("concept_source")
    sections: dict[str, Any] = {}
    if not isinstance(concept, dict):
        add(errors, "schema_mismatch", "concept_source", "must be an object")
    else:
        if not nonempty(concept.get("path")):
            add(errors, "invalid_field", "concept_source.path", "must be non-empty")
        if not re.fullmatch(r"[a-f0-9]{64}", str(concept.get("sha256", ""))):
            add(errors, "invalid_hash", "concept_source.sha256", "must be lowercase SHA-256")
        if isinstance(concept.get("sections"), dict) and concept["sections"]:
            sections = concept["sections"]
            for section_id, section in sections.items():
                if not isinstance(section, dict) or section.get("id") != section_id:
                    add(errors, "schema_mismatch", f"concept_source.sections.{section_id}", "section key and id must match")
                elif not all(nonempty(section.get(k)) for k in ("id", "title", "anchor")) or not isinstance(section.get("required"), bool):
                    add(errors, "invalid_field", f"concept_source.sections.{section_id}", "id/title/anchor/required contract is incomplete")
        else:
            add(errors, "missing_sections", "concept_source.sections", "at least one stable concept section is required")
    if concept_path:
        if not concept_path.is_file():
            add(errors, "source_missing", "concept_source.path", f"concept file not found: {concept_path}")
        elif isinstance(concept, dict):
            actual = sha256_bytes(concept_path.read_bytes())
            if actual != concept.get("sha256"):
                add(errors, "source_hash_mismatch", "concept_source.sha256", f"declared {concept.get('sha256')} but actual is {actual}")

    blocks = graph.get("blocks")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    exemptions = graph.get("coverage_exemptions")
    if not isinstance(blocks, list) or not blocks:
        add(errors, "schema_mismatch", "blocks", "must be a non-empty array")
        blocks = []
    if not isinstance(nodes, list) or not nodes:
        add(errors, "schema_mismatch", "nodes", "must be a non-empty array")
        nodes = []
    if not isinstance(edges, list):
        add(errors, "schema_mismatch", "edges", "must be an array")
        edges = []
    if not isinstance(exemptions, list):
        add(errors, "schema_mismatch", "coverage_exemptions", "must be an array")
        exemptions = []

    block_ids: set[str] = set()
    orders: set[int] = set()
    ordered_blocks: list[tuple[int, str]] = []
    for index, block in enumerate(blocks):
        path = f"blocks[{index}]"
        if not isinstance(block, dict):
            add(errors, "schema_mismatch", path, "block must be an object")
            continue
        block_id = block.get("id")
        if not nonempty(block_id) or block_id in block_ids:
            add(errors, "duplicate_or_invalid_id", f"{path}.id", "block id must be non-empty and unique")
        else:
            block_ids.add(block_id)
        order = block.get("order")
        if not isinstance(order, int) or order < 1 or order in orders:
            add(errors, "invalid_order", f"{path}.order", "order must be a unique positive integer")
        else:
            orders.add(order); ordered_blocks.append((order, block_id))
        validate_common(block, path, sections, errors)
        if not nonempty(block.get("main_output")):
            add(errors, "missing_output", f"{path}.main_output", "block requires one accepted main output")
        if block.get("next_block") is not None and not nonempty(block.get("next_block")):
            add(errors, "invalid_transition", f"{path}.next_block", "must be a block id or null")

    node_ids: set[str] = set()
    node_by_id: dict[str, dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        path = f"nodes[{index}]"
        if not isinstance(node, dict):
            add(errors, "schema_mismatch", path, "node must be an object"); continue
        node_id = node.get("id")
        if not nonempty(node_id) or node_id in node_ids:
            add(errors, "duplicate_or_invalid_id", f"{path}.id", "node id must be non-empty and unique"); continue
        node_ids.add(node_id); node_by_id[node_id] = node
        if node.get("type") not in NODE_TYPES:
            add(errors, "invalid_node_type", f"{path}.type", "unknown node type")
        if not nonempty(node.get("title")):
            add(errors, "invalid_field", f"{path}.title", "title must be non-empty")
        parent = node.get("parent_id")
        if parent is not None and parent not in block_ids:
            add(errors, "missing_parent", f"{path}.parent_id", f"unknown parent block {parent!r}")
        validate_common(node, path, sections, errors)
        if node.get("type") in ACTIONABLE:
            fields = node.get("operational_fields")
            if not isinstance(fields, dict):
                add(errors, "missing_operational_fields", f"{path}.operational_fields", "actionable node requires operational fields")
            else:
                for field in OPERATIONAL_FIELDS:
                    value = fields.get(field)
                    if not nonempty(value):
                        add(errors, "semantic_gap", f"{path}.operational_fields.{field}", "required meaning is missing")
                    elif PLACEHOLDER.search(value):
                        add(errors, "placeholder", f"{path}.operational_fields.{field}", "placeholder wording is forbidden")
                    elif len(value.strip()) < 8:
                        add(warnings, "weak_semantics", f"{path}.operational_fields.{field}", "value may be too short to be verifiable")
        if node.get("type") == "artifact":
            contract = node.get("artifact_contract")
            if not isinstance(contract, dict) or not nonempty(contract.get("producer")) or not nonempty(contract.get("reviewer")) or not strings(contract.get("consumers")):
                add(errors, "artifact_contract_missing", f"{path}.artifact_contract", "producer, reviewer and non-empty consumers are required")
        if node.get("type") == "block" and node_id not in block_ids:
            add(errors, "orphan_block_node", path, "block node has no matching blocks entry")
    for block_id in block_ids:
        if block_id not in node_by_id or node_by_id[block_id].get("type") != "block":
            add(errors, "missing_block_node", f"blocks.{block_id}", "every block requires a matching block node")

    edge_ids: set[str] = set()
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    edge_keys: set[tuple[str, str, str]] = set()
    for index, edge in enumerate(edges):
        path = f"edges[{index}]"
        if not isinstance(edge, dict):
            add(errors, "schema_mismatch", path, "edge must be an object"); continue
        edge_id = edge.get("id")
        if not nonempty(edge_id) or edge_id in edge_ids:
            add(errors, "duplicate_or_invalid_id", f"{path}.id", "edge id must be non-empty and unique")
        else: edge_ids.add(edge_id)
        source, target, relation = edge.get("source"), edge.get("target"), edge.get("relation")
        if source not in node_ids: add(errors, "missing_endpoint", f"{path}.source", f"unknown node {source!r}")
        if target not in node_ids: add(errors, "missing_endpoint", f"{path}.target", f"unknown node {target!r}")
        if relation not in RELATIONS: add(errors, "invalid_relation", f"{path}.relation", "relation is not in the closed vocabulary")
        if not nonempty(edge.get("origin")) or not nonempty(edge.get("reverse_label")):
            add(errors, "invalid_edge_contract", path, "origin and reverse_label are required")
        if relation == "conditionally_unblocks" and not nonempty(edge.get("condition")):
            add(errors, "missing_condition", f"{path}.condition", "conditional transition requires a condition")
        key = (str(source), str(relation), str(target))
        if key in edge_keys: add(errors, "duplicate_edge", path, f"duplicate relation {key}")
        edge_keys.add(key); outgoing[str(source)].append(edge)

    for node_id, node in node_by_id.items():
        local = outgoing.get(node_id, [])
        if node.get("type") == "gate":
            if not any(e.get("relation") in {"on_success", "unblocks", "conditionally_unblocks", "accepted_by"} for e in local):
                add(errors, "gate_route_missing", f"nodes.{node_id}", "gate has no success route")
            if not any(e.get("relation") == "on_failure" for e in local):
                add(errors, "gate_route_missing", f"nodes.{node_id}", "gate has no failure route")
        if node.get("type") == "failure" and not any(e.get("relation") == "returns_to" for e in local):
            add(errors, "failure_return_missing", f"nodes.{node_id}", "failure must return to the narrowest responsible node")

    exemption_ids: set[str] = set()
    for index, exemption in enumerate(exemptions):
        path = f"coverage_exemptions[{index}]"
        if not isinstance(exemption, dict) or not all(nonempty(exemption.get(k)) for k in ("concept_section_id", "reason", "owner")):
            add(errors, "invalid_exemption", path, "section id, reason and owner are required"); continue
        section_id = exemption["concept_section_id"]
        if section_id not in sections: add(errors, "unknown_concept_ref", path, f"unknown section {section_id}")
        exemption_ids.add(section_id)
    covered = {ref for node in nodes if isinstance(node, dict) for ref in node.get("implements", []) if isinstance(ref, str)}
    for section_id, section in sections.items():
        if section.get("required") and section_id not in covered and section_id not in exemption_ids:
            add(errors, "traceability_gap", f"concept_source.sections.{section_id}", "required concept section is not implemented or exempted")

    ordered = [block_id for _, block_id in sorted(ordered_blocks)]
    for index, block_id in enumerate(ordered[:-1]):
        expected = ordered[index + 1]
        declared = next((b.get("next_block") for b in blocks if isinstance(b, dict) and b.get("id") == block_id), None)
        if declared != expected:
            add(errors, "block_sequence_mismatch", f"blocks.{block_id}.next_block", f"expected {expected!r} from block order")
        if not any(e.get("source") == block_id and e.get("target") == expected and e.get("relation") in {"on_success", "unblocks", "conditionally_unblocks"} for e in edges if isinstance(e, dict)):
            add(errors, "block_transition_missing", f"blocks.{block_id}", f"no accepted transition to {expected}")
    if ordered:
        last = next((b for b in blocks if isinstance(b, dict) and b.get("id") == ordered[-1]), {})
        if last.get("next_block") is not None:
            add(errors, "block_sequence_mismatch", f"blocks.{ordered[-1]}.next_block", "last block must use null")
    return report(graph, graph_path, errors, warnings, concept_path)


def validate_common(value: dict[str, Any], path: str, sections: dict[str, Any], errors: list[dict[str, str]]) -> None:
    if not strings(value.get("implements")):
        add(errors, "traceability_gap", f"{path}.implements", "must be a non-empty unique list")
    else:
        for ref in value["implements"]:
            if ref not in sections: add(errors, "unknown_concept_ref", f"{path}.implements", f"unknown section {ref}")
    status = value.get("implementation_status")
    evidence = value.get("implementation_evidence")
    if status not in STATUSES: add(errors, "invalid_status", f"{path}.implementation_status", "unknown implementation status")
    if not isinstance(evidence, list) or not strings(evidence) and evidence != []:
        add(errors, "invalid_evidence", f"{path}.implementation_evidence", "must be a unique string list")
    if status in {"implemented", "partially_implemented"} and not evidence:
        add(errors, "implementation_evidence_missing", f"{path}.implementation_evidence", "implementation claim requires evidence")


def report(graph: dict[str, Any], graph_path: Path, errors: list[dict[str, str]], warnings: list[dict[str, str]], concept_path: Path | None) -> dict[str, Any]:
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    return {
        "report_version": "taskplan-pro.operation-map-audit/v1",
        "graph_id": graph.get("graph_id"), "graph_version": graph.get("graph_version"),
        "graph_path": str(graph_path), "graph_sha256": sha256_bytes(graph_path.read_bytes()),
        "concept_path_checked": str(concept_path) if concept_path else None,
        "ready": not errors, "errors": errors, "warnings": warnings,
        "stats": {"blocks": len(graph.get("blocks", [])) if isinstance(graph.get("blocks"), list) else 0, "nodes": len(nodes), "edges": len(edges), "node_types": dict(Counter(n.get("type") for n in nodes if isinstance(n, dict)))},
    }


def render_markdown(graph: dict[str, Any], audit: dict[str, Any]) -> str:
    node_by_id = {n["id"]: n for n in graph["nodes"]}
    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in graph["nodes"]:
        if node.get("parent_id"): children[node["parent_id"]].append(node)
    lines = [f"# {graph['graph_id']} — Operation Map", "", f"- Graph version: `{graph['graph_version']}`", f"- Graph SHA-256: `{audit['graph_sha256']}`", f"- Readiness: `{'ready' if audit['ready'] else 'blocked'}`", "- Canonical source: JSON; this Markdown is generated and must not be edited.", ""]
    for block in sorted(graph["blocks"], key=lambda b: b["order"]):
        node = node_by_id[block["id"]]; lines += [f"## {block['id']} · {block['title']}", "", f"Implements: {', '.join(block['implements'])}", f"Main output: {block['main_output']}", f"Next: {block['next_block'] or 'END'}", ""]
        lines += fields_markdown(node.get("operational_fields", {}))
        lines += ["", "### Nodes", "", "| ID | Type | Title | Implements | Status |", "| --- | --- | --- | --- | --- |"]
        for child in sorted(children.get(block["id"], []), key=lambda n: n["id"]):
            lines.append(f"| `{child['id']}` | {child['type']} | {child['title']} | {', '.join(child['implements'])} | {child['implementation_status']} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def fields_markdown(fields: dict[str, str]) -> list[str]:
    labels = {"what":"What", "where":"Where", "when":"When", "why":"Why", "input":"Input", "input_requirements":"Input requirements", "expected_output":"Expected output", "success_criteria":"Success", "failure_criteria":"Failure", "failure_action":"On failure", "executor":"Executor", "reviewer":"Reviewer", "acceptor":"Acceptor", "resources":"Resources", "evidence":"Evidence", "next_transition":"Next transition"}
    return [f"- **{labels[key]}:** {fields.get(key, '')}" for key in OPERATIONAL_FIELDS]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def artifact(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": sha256_bytes(path.read_bytes())}


def validate_readiness_receipt(graph: dict[str, Any], graph_path: Path, receipt_path: Path) -> dict[str, Any]:
    receipt = load_json(receipt_path)
    graph_hash = sha256_bytes(graph_path.read_bytes())
    receipt_hash = receipt.get("graph_sha256") or (receipt.get("source_hashes") or {}).get("graph_sha256")
    receipt_ready = receipt.get("ready") is True or receipt.get("status") == "PASS"
    receipt_checks = receipt.get("checks") or []
    failed_checks = [item.get("id", "unknown") for item in receipt_checks if item.get("status") != "PASS"] if isinstance(receipt_checks, list) else ["invalid_checks"]
    errors: list[dict[str, str]] = []
    if receipt.get("graph_id") != graph.get("graph_id"):
        add(errors, "schema_mismatch", "receipt.graph_id", "readiness receipt belongs to another graph")
    if receipt.get("graph_version") != graph.get("graph_version"):
        add(errors, "schema_mismatch", "receipt.graph_version", "readiness receipt belongs to another graph version")
    if receipt_hash != graph_hash:
        add(errors, "source_hash_mismatch", "receipt.graph_sha256", "readiness receipt does not match the graph bytes")
    if not receipt_ready or receipt.get("errors") or failed_checks:
        add(errors, "regression_detected", "receipt.status", f"readiness receipt is not passing; failed checks: {failed_checks}")
    return {
        "report_version": "taskplan-pro.operation-map-audit/v1",
        "validation_mode": "external_readiness_receipt",
        "receipt_schema_version": receipt.get("schema_version"),
        "receipt_path": str(receipt_path.resolve()),
        "receipt_sha256": sha256_bytes(receipt_path.read_bytes()),
        "graph_id": graph.get("graph_id"),
        "graph_version": graph.get("graph_version"),
        "graph_path": str(graph_path.resolve()),
        "graph_sha256": graph_hash,
        "ready": not errors,
        "errors": errors,
        "warnings": [],
        "stats": {
            "blocks": len(graph.get("blocks") or []),
            "nodes": len(graph.get("nodes") or []),
            "edges": len(graph.get("edges") or []),
        },
    }


def execute(args: argparse.Namespace) -> int:
    graph_path = args.graph.resolve(); concept_path = args.concept.resolve() if args.concept else None
    try: graph = load_json(graph_path)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"ready": False, "failure_mode": "schema_mismatch", "message": str(error)}, ensure_ascii=False)); return 2
    if args.command == "review":
        audit = validate_readiness_receipt(graph, graph_path, args.readiness_receipt.resolve())
    else:
        audit = validate_graph(graph, graph_path, concept_path)
    if getattr(args, "report", None): write_json(args.report.resolve(), audit)
    if args.command == "validate":
        print(json.dumps({"ready": audit["ready"], "errors": len(audit["errors"]), "warnings": len(audit["warnings"])}, ensure_ascii=False)); return 0 if audit["ready"] else 1
    if not audit["ready"]:
        print(json.dumps({"ready": False, "failure_mode": "schema_mismatch", "report": str((args.output_dir / "OPERATION-MAP-AUDIT.json").resolve())}, ensure_ascii=False));
        output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True); write_json(output / "OPERATION-MAP-AUDIT.json", audit); return 1
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True)
    audit_path = output / "OPERATION-MAP-AUDIT.json"
    markdown_path = output / "OPERATION-MAP.md"
    html_path = output / "OPERATION-MAP-REVIEW.html"
    locale_path = output / "OPERATION-MAP-I18N.json"
    presentation_path = output / "OPERATION-MAP-PRESENTATION.json"
    manifest_path = output / "OPERATION-MAP-BUILD.json"
    write_json(audit_path, audit)
    if args.command == "finalize":
        markdown_path.write_text(render_markdown(graph, audit), encoding="utf-8")
    graph_hash = sha256_bytes(graph_path.read_bytes())
    if args.i18n:
        locale_catalog = load_json(args.i18n.resolve())
    else:
        locale_catalog = default_catalog(graph, graph_hash, args.source_locale)
    if args.presentation:
        presentation = load_json(args.presentation.resolve())
    else:
        presentation = default_presentation(graph)
    write_json(locale_path, locale_catalog)
    write_json(presentation_path, presentation)
    build_result = build_review_workspace(
        graph_path,
        html_path,
        locale_path,
        presentation_path,
        args.review_state.resolve() if args.review_state else None,
        args.source_locale,
    )
    outputs = {
        "audit": artifact(audit_path),
        "html": artifact(html_path),
        "locale_catalog": artifact(locale_path),
        "presentation": artifact(presentation_path),
    }
    if args.command == "finalize":
        outputs["markdown"] = artifact(markdown_path)
    manifest = {
        "schema_version": "1.0",
        "builder_version": BUILDER_VERSION,
        "graph": artifact(graph_path),
        "concept": artifact(concept_path) if concept_path else None,
        "outputs": outputs,
        "locales": build_result["locales"],
        "checks": {
            "graph_readiness": "passed",
            "locale_catalog": "passed",
            "presentation": "passed",
            "browser_smoke": "not_run",
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps({
        "ready": True,
        "audit": str(audit_path),
        "html": str(html_path),
        "i18n": str(locale_path),
        "presentation": str(presentation_path),
        "manifest": str(manifest_path),
        **({"markdown": str(markdown_path)} if args.command == "finalize" else {}),
    }, ensure_ascii=False)); return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__); sub = root.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate"); validate.add_argument("--graph", type=Path, required=True); validate.add_argument("--concept", type=Path); validate.add_argument("--report", type=Path)
    finalize = sub.add_parser("finalize"); finalize.add_argument("--graph", type=Path, required=True); finalize.add_argument("--concept", type=Path); finalize.add_argument("--output-dir", type=Path, required=True)
    finalize.add_argument("--presentation", type=Path)
    finalize.add_argument("--i18n", type=Path)
    finalize.add_argument("--review-state", type=Path)
    finalize.add_argument("--source-locale", choices=("ru", "en", "es", "fr", "de"), default="en")
    review = sub.add_parser("review"); review.add_argument("--graph", type=Path, required=True); review.add_argument("--concept", type=Path); review.add_argument("--output-dir", type=Path, required=True)
    review.add_argument("--readiness-receipt", type=Path, required=True)
    review.add_argument("--presentation", type=Path)
    review.add_argument("--i18n", type=Path)
    review.add_argument("--review-state", type=Path)
    review.add_argument("--source-locale", choices=("ru", "en", "es", "fr", "de"), default="en")
    return root


if __name__ == "__main__":
    sys.exit(execute(parser().parse_args()))
