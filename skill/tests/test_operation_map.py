import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "operation_map.py"
FIXTURE = ROOT / "evals" / "fixtures" / "valid-operation-map.json"
CONCEPT = ROOT / "evals" / "fixtures" / "accepted-concept.md"


def load_module():
    spec = importlib.util.spec_from_file_location("operation_map", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class OperationMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.graph = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def validate(self, graph, concept=CONCEPT):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.json"
            path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
            return self.module.validate_graph(graph, path, concept)

    def test_valid_graph_is_ready(self):
        report = self.validate(deepcopy(self.graph))
        self.assertTrue(report["ready"], report["errors"])

    def test_semantic_gap_blocks_readiness(self):
        graph = deepcopy(self.graph)
        del graph["nodes"][0]["operational_fields"]["success_criteria"]
        report = self.validate(graph)
        self.assertFalse(report["ready"])
        self.assertIn("semantic_gap", {item["code"] for item in report["errors"]})

    def test_placeholder_blocks_readiness(self):
        graph = deepcopy(self.graph)
        graph["nodes"][0]["operational_fields"]["what"] = "TBD"
        report = self.validate(graph)
        self.assertIn("placeholder", {item["code"] for item in report["errors"]})

    def test_gate_requires_failure_route(self):
        graph = deepcopy(self.graph)
        graph["edges"] = [edge for edge in graph["edges"] if not (edge["source"] == "B01-G01" and edge["relation"] == "on_failure")]
        report = self.validate(graph)
        self.assertIn("gate_route_missing", {item["code"] for item in report["errors"]})

    def test_implemented_claim_requires_evidence(self):
        graph = deepcopy(self.graph)
        graph["nodes"][0]["implementation_status"] = "implemented"
        report = self.validate(graph)
        self.assertIn("implementation_evidence_missing", {item["code"] for item in report["errors"]})

    def test_ids_and_block_count_are_not_hardcoded(self):
        graph = deepcopy(self.graph)
        mapping = {node["id"]: node["id"].replace("B01", "DISCOVERY").replace("B02", "ACCEPTANCE") for node in graph["nodes"]}
        for block in graph["blocks"]:
            block["id"] = mapping[block["id"]]
            if block["next_block"]:
                block["next_block"] = mapping[block["next_block"]]
        for node in graph["nodes"]:
            node["id"] = mapping[node["id"]]
            if node["parent_id"]:
                node["parent_id"] = mapping[node["parent_id"]]
        for edge in graph["edges"]:
            edge["source"] = mapping[edge["source"]]
            edge["target"] = mapping[edge["target"]]
        report = self.validate(graph)
        self.assertTrue(report["ready"], report["errors"])

        single = deepcopy(self.graph)
        single["blocks"] = [single["blocks"][0]]
        single["blocks"][0]["next_block"] = None
        single["nodes"] = [node for node in single["nodes"] if node["id"].startswith("B01")]
        retained = {node["id"] for node in single["nodes"]}
        single["edges"] = [edge for edge in single["edges"] if edge["source"] in retained and edge["target"] in retained]
        success = next(edge for edge in self.graph["edges"] if edge["source"] == "B01-G01" and edge["relation"] == "on_success")
        success = deepcopy(success)
        success["target"] = "B01-A01"
        single["edges"].append(success)
        single["concept_source"]["sections"]["C02"]["required"] = False
        report = self.validate(single)
        self.assertTrue(report["ready"], report["errors"])

    def test_finalize_builds_self_contained_review_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_path = root / "graph.json"
            graph_path.write_text(json.dumps(self.graph, ensure_ascii=False), encoding="utf-8")
            output = root / "output"
            result = self.module.execute(SimpleNamespace(
                command="finalize", graph=graph_path, concept=CONCEPT,
                output_dir=output, report=None, presentation=None, i18n=None,
                review_state=None, source_locale="en",
            ))
            self.assertEqual(result, 0)
            html = (output / "OPERATION-MAP-REVIEW.html").read_text(encoding="utf-8")
            self.assertIn('id="graph-data"', html)
            self.assertIn('id="overviewGraph"', html)
            self.assertIn("renderOverviewSvg", html)
            self.assertIn("overviewRelationMode", html)
            for field in ("owner_question", "owner_proposal", "reviewer_1", "reviewer_2"):
                self.assertIn(field, html)
            self.assertNotIn("https://", html)
            self.assertNotRegex(html, r'<script[^>]+src=')
            presentation = json.loads((output / "OPERATION-MAP-PRESENTATION.json").read_text(encoding="utf-8"))
            self.assertEqual(presentation["overview_groups"][0]["block_ids"], ["B01", "B02"])
            manifest = json.loads((output / "OPERATION-MAP-BUILD.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["builder_version"], "0.2.1")
            self.assertEqual(manifest["checks"]["graph_readiness"], "passed")
            self.assertEqual(manifest["checks"]["browser_smoke"], "not_run")

    def test_multilingual_projection_uses_catalog_and_presentation_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_path = root / "graph.json"
            graph_path.write_text(json.dumps(self.graph, ensure_ascii=False), encoding="utf-8")
            graph_hash = self.module.sha256_bytes(graph_path.read_bytes())
            catalog = self.module.default_catalog(self.graph, graph_hash, "en")
            catalog["locales"] = ["en", "ru", "es", "fr", "de"]
            for entry in catalog["entries"].values():
                for locale in catalog["locales"]:
                    entry["translations"][locale] = entry["source"]
            catalog_path = root / "i18n.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            presentation = {
                "schema_version": "1.0",
                "overview_groups": [
                    {"id": "intake", "block_ids": ["B01"], "labels": {"en": "Intake"}},
                    {"id": "acceptance", "block_ids": ["B02"], "labels": {"en": "Acceptance"}}
                ],
                "feedback_transition": {"source": "B02", "target": "B01"}
            }
            presentation_path = root / "presentation.json"
            presentation_path.write_text(json.dumps(presentation), encoding="utf-8")
            output = root / "output"
            result = self.module.execute(SimpleNamespace(
                command="finalize", graph=graph_path, concept=CONCEPT,
                output_dir=output, report=None, presentation=presentation_path,
                i18n=catalog_path, review_state=None, source_locale="en",
            ))
            self.assertEqual(result, 0)
            html = (output / "OPERATION-MAP-REVIEW.html").read_text(encoding="utf-8")
            self.assertIn('"locales":["en","ru","es","fr","de"]', html)
            self.assertIn("contentCatalog.locales", html)
            self.assertIn('"id":"intake"', html)
            self.assertIn('"feedback_transition"', html)

    def test_hash_mismatched_catalog_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_path = root / "graph.json"
            graph_path.write_text(json.dumps(self.graph), encoding="utf-8")
            catalog = self.module.default_catalog(self.graph, "0" * 64, "en")
            catalog_path = root / "i18n.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "graph hash"):
                self.module.execute(SimpleNamespace(
                    command="finalize", graph=graph_path, concept=CONCEPT,
                    output_dir=root / "output", report=None, presentation=None,
                    i18n=catalog_path, review_state=None, source_locale="en",
                ))

    def test_import_path_contains_strict_review_validation(self):
        source = (ROOT / "scripts" / "review_workspace.py").read_text(encoding="utf-8")
        self.assertIn("invalid review state", source)
        self.assertIn("invalid annotation", source)
        self.assertIn("reviewStatuses", source)

    def test_review_only_accepts_hash_bound_external_readiness_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_path = root / "legacy-graph.json"
            legacy = deepcopy(self.graph)
            legacy["schema_version"] = "task-plan-pro.operational-graph/v1"
            legacy.pop("coverage_exemptions")
            graph_path.write_text(json.dumps(legacy), encoding="utf-8")
            receipt = {
                "schema_version": "task-plan-pro.operational-graph-audit/v1",
                "graph_id": legacy["graph_id"],
                "graph_version": legacy["graph_version"],
                "status": "PASS",
                "source_hashes": {"graph_sha256": self.module.sha256_bytes(graph_path.read_bytes())},
                "checks": [{"id": "LEGACY_VALIDATOR", "status": "PASS"}],
                "errors": [],
            }
            receipt_path = root / "receipt.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            output = root / "output"
            result = self.module.execute(SimpleNamespace(
                command="review", graph=graph_path, concept=None, output_dir=output,
                readiness_receipt=receipt_path, presentation=None, i18n=None,
                review_state=None, source_locale="en", report=None,
            ))
            self.assertEqual(result, 0)
            self.assertTrue((output / "OPERATION-MAP-REVIEW.html").exists())
            self.assertFalse((output / "OPERATION-MAP.md").exists())
            audit = json.loads((output / "OPERATION-MAP-AUDIT.json").read_text(encoding="utf-8"))
            self.assertEqual(audit["validation_mode"], "external_readiness_receipt")

    def test_review_only_rejects_stale_readiness_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_path = root / "graph.json"
            graph_path.write_text(json.dumps(self.graph), encoding="utf-8")
            receipt = {
                "schema_version": "audit/v1", "graph_id": self.graph["graph_id"],
                "graph_version": self.graph["graph_version"], "status": "PASS",
                "source_hashes": {"graph_sha256": "0" * 64}, "checks": [], "errors": [],
            }
            receipt_path = root / "receipt.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            audit = self.module.validate_readiness_receipt(self.graph, graph_path, receipt_path)
            self.assertFalse(audit["ready"])
            self.assertIn("source_hash_mismatch", {item["code"] for item in audit["errors"]})


if __name__ == "__main__":
    unittest.main()
