"""Synthetic coverage cases; do not depend on network access or real datasets."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from src.data.validate_housing import audit


def envelope(**fields):
    return [{"IndicadorCod": "0012255", "Sucesso": {"Verdadeiro": [{"Msg": "OK"}]}, **fields}]


def category(dim, code, label, level):
    return {"dim_num": dim, "cat_id": code, "categ_dsg": label, "categ_nivel": level}


class CoverageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        # Deliberately use arbitrary code lengths: classification must follow
        # metadata level, not seven-character heuristics or an assumed count 308.
        categories = [category("1", "S7A2024", "2024", "1"),
                      category("2", "M", "Synthetic municipality", "5"),
                      category("2", "ABCDEFG", "Synthetic aggregate", "4"),
                      category("3", "H1", "Total", "1")]
        self.metadata = envelope(
            Periodic="Anual", PrimeiroPeriodo="2024", UltimoPeriodo="2024",
            Dimensoes={"Descricao_Dim": [{"dim_num": "2", "versao": "05431"}],
                       "Categoria_Dim": [{str(i): [row] for i, row in enumerate(categories)}]},
        )
        self.records = [
            {"geocod": "M", "geodsg": "Synthetic municipality", "dim_3": "H1",
             "dim_3_t": "Total", "valor": "123", "ind_string": "123"},
            {"geocod": "ABCDEFG", "geodsg": "Synthetic aggregate", "dim_3": "H1",
             "dim_3_t": "Total", "valor": "456", "ind_string": "456"},
        ]

    def run_audit(self, records=None, metadata=None, year="2024"):
        meta_path = self.root / "metadata.json"
        raw_path = self.root / "raw.json"
        meta_path.write_text(json.dumps(metadata if metadata is not None else self.metadata))
        raw_path.write_text(json.dumps(envelope(Dados={year: self.records if records is None else records})))
        return audit(meta_path, [raw_path])

    def test_complete_coverage_uses_metadata_level_and_hashes(self):
        report, table = self.run_audit()
        self.assertTrue(report["structure_valid"])
        self.assertEqual(report["expected_municipalities"], 1)
        self.assertEqual(table.iloc[0]["rows"], 1)
        self.assertEqual(table.iloc[0]["values_present"], 1)
        self.assertEqual(len(report["metadata"]["sha256"]), 64)

    def test_null_measurement_is_not_missing_record(self):
        records = deepcopy(self.records)
        records[0].pop("valor")
        records[0].update(ind_string="-", sinal_conv="-", sinal_conv_desc="Dado nulo ou não aplicável")
        report, table = self.run_audit(records)
        self.assertTrue(report["structure_valid"])
        self.assertEqual(table.iloc[0]["municipalities_with_record"], 1)
        self.assertEqual(table.iloc[0]["values_present"], 0)
        self.assertEqual(table.iloc[0]["values_missing"], 1)

    def test_missing_municipality_record_fails(self):
        report, table = self.run_audit(self.records[1:])
        self.assertFalse(report["structure_valid"])
        self.assertEqual(table.iloc[0]["missing_municipality_records"], 1)
        self.assertIn("missing_keys", [i["kind"] for i in report["issues"]])

    def test_duplicate_keys_fail_even_if_unique_count_matches(self):
        report, table = self.run_audit(self.records + [deepcopy(self.records[0])])
        self.assertFalse(report["structure_valid"])
        self.assertEqual(table.iloc[0]["municipalities_with_record"], 1)
        self.assertIn("duplicate_keys", [i["kind"] for i in report["issues"]])

    def test_unknown_code_and_label_mismatch_are_reported(self):
        records = deepcopy(self.records)
        records[0]["geodsg"] = "Wrong name"
        records[1]["geocod"] = "UNKNOWN"
        report, _ = self.run_audit(records)
        self.assertFalse(report["structure_valid"])
        self.assertTrue({"unexpected_keys", "missing_keys", "label_mismatches"}.issubset(
            {i["kind"] for i in report["issues"]}))

    def test_missing_and_unexpected_years_fail(self):
        report, _ = self.run_audit(year="2023")
        self.assertFalse(report["structure_valid"])
        self.assertEqual(report["missing_years"], ["2024"])
        self.assertEqual(report["unexpected_years"], ["2023"])

    def test_wrong_indicator_fails(self):
        meta = deepcopy(self.metadata)
        meta[0]["IndicadorCod"] = "0000000"
        with self.assertRaisesRegex(ValueError, "Wrong indicator"):
            self.run_audit(metadata=meta)

    def test_changed_geography_version_requires_review(self):
        meta = deepcopy(self.metadata)
        meta[0]["Dimensoes"]["Descricao_Dim"][0]["versao"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "classification changed"):
            self.run_audit(metadata=meta)

    def test_api_error_is_not_treated_as_data(self):
        meta = deepcopy(self.metadata)
        meta[0]["Sucesso"] = {"Falso": [{"Msg": "Error"}]}
        with self.assertRaisesRegex(ValueError, "API did not report"):
            self.run_audit(metadata=meta)

    def test_invalid_numeric_value_and_unreviewed_marker_fail(self):
        for value in ("not a number", "NaN", "Infinity", ""):
            with self.subTest(value=value):
                records = deepcopy(self.records)
                records[0]["valor"] = value
                report, _ = self.run_audit(records)
                self.assertFalse(report["structure_valid"])

    def test_repeated_period_input_is_rejected(self):
        self.run_audit()
        with self.assertRaisesRegex(ValueError, "more than once"):
            audit(self.root / "metadata.json", [self.root / "raw.json"] * 2)

    def test_duplicate_metadata_categories_are_rejected(self):
        meta = deepcopy(self.metadata)
        group = meta[0]["Dimensoes"]["Categoria_Dim"][0]
        group["duplicate"] = deepcopy(group["0"])
        with self.assertRaisesRegex(ValueError, "duplicate metadata"):
            self.run_audit(metadata=meta)


if __name__ == "__main__":
    unittest.main()
