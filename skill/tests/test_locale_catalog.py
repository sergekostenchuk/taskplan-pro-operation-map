import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "locale_catalog.py"
FIXTURE = ROOT / "evals" / "fixtures" / "valid-operation-map.json"


def load_module():
    spec = importlib.util.spec_from_file_location("locale_catalog", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class LocaleCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_standard_library_catalog_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            _, catalog = self.module.load_or_create(FIXTURE, output, "ru", [])
            self.module.save_catalog(output, catalog)
            report = self.module.validate_catalog(FIXTURE, output)
            self.assertTrue(report["valid"], report["errors"])
            self.assertEqual(report["locales"], ["ru"])

    def test_missing_requested_translation_fails_completeness(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            _, catalog = self.module.load_or_create(FIXTURE, output, "ru", ["en"])
            self.module.save_catalog(output, catalog)
            report = self.module.validate_catalog(FIXTURE, output)
            self.assertFalse(report["valid"])
            self.assertTrue(any("missing locales" in error for error in report["errors"]))

    def test_literal_protection_round_trips(self):
        source = "CODE FIRST / NO HARDCODE; `B01-S01`; scripts/check.py"
        protected, literals = self.module.protect_literals(source)
        self.assertNotIn("CODE FIRST", protected)
        self.assertEqual(self.module.restore_literals(protected, literals), source)

    def test_resume_preserves_translation_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            _, catalog = self.module.load_or_create(FIXTURE, output, "ru", ["en"])
            catalog["translation_provenance"]["en"] = {"provider": "test", "human_reviewed": False}
            for entry in catalog["entries"].values():
                entry["translations"]["en"] = entry["source"]
            self.module.save_catalog(output, catalog)
            _, resumed = self.module.load_or_create(FIXTURE, output, "ru", ["en"])
            self.assertEqual(resumed["translation_provenance"]["en"]["provider"], "test")


if __name__ == "__main__":
    unittest.main()
