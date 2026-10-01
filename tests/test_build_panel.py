"""Integration and geography checks for the municipality-year panel."""

from pathlib import Path
import string
import unittest

from src.data.build_panel import _municipal_geography, build_panel


RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def synthetic_geography_metadata() -> dict:
    nuts2_codes = list(string.ascii_uppercase[:9])
    nuts3_codes = [f"{nuts2_codes[index % 9]}{index:02d}" for index in range(26)]
    rows = []
    rows.extend(
        {"dim_num": "2", "cat_id": code, "categ_dsg": f"NUTS II {code}", "categ_nivel": "3"}
        for code in nuts2_codes
    )
    rows.extend(
        {"dim_num": "2", "cat_id": code, "categ_dsg": f"NUTS III {code}", "categ_nivel": "4"}
        for code in nuts3_codes
    )
    rows.extend(
        {
            "dim_num": "2",
            "cat_id": f"{nuts3_codes[index % 26]}{index:04d}",
            "categ_dsg": f"Municipality {index:03d}",
            "categ_nivel": "5",
        }
        for index in range(308)
    )
    return {"Dimensoes": {"Categoria_Dim": [{f"row_{index}": [row]} for index, row in enumerate(rows)]}}


class GeographyTests(unittest.TestCase):
    def test_each_municipality_maps_to_one_nuts2_and_nuts3(self):
        geography = _municipal_geography(synthetic_geography_metadata())
        self.assertEqual(len(geography), 308)
        self.assertEqual(geography["nuts2_code"].nunique(), 9)
        self.assertEqual(geography["nuts3_code"].nunique(), 26)
        first = geography.iloc[0]
        self.assertTrue(first["municipality_code"].startswith(first["nuts2_code"]))
        self.assertTrue(first["municipality_code"].startswith(first["nuts3_code"]))


class PanelBuildTests(unittest.TestCase):
    @unittest.skipUnless((RAW / "population_metadata_20260928.json").exists(), "raw snapshots not present")
    def test_panel_keys_geography_and_intentional_missing_values(self):
        panel, audit = build_panel(RAW)
        self.assertEqual(len(panel), 1540)
        self.assertFalse(panel.duplicated(["municipality_code", "year"]).any())
        self.assertEqual(panel["municipality_code"].nunique(), 308)
        self.assertEqual(panel["nuts2_code"].nunique(), 9)
        self.assertEqual(panel["nuts3_code"].nunique(), 26)
        self.assertEqual(sorted(panel["year"].unique()), [2021, 2022, 2023, 2024, 2025])
        self.assertEqual(int(panel["housing_price_m2_total"].isna().sum()), 33)
        income_2025 = panel.loc[
            panel["year"] == 2025, "declared_income_less_irs_per_tax_household"
        ]
        self.assertEqual(int(income_2025.isna().sum()), 308)
        for column in ("population_total", "aging_index", "migration_balance"):
            self.assertFalse(panel[column].isna().any())
        self.assertEqual(audit.query("column == 'population_total'")["missing"].sum(), 0)

        lisbon = panel.query("municipality_name == 'Lisboa'").iloc[0]
        self.assertEqual((lisbon["nuts2_name"], lisbon["nuts3_name"]), ("Grande Lisboa", "Grande Lisboa"))
        arcos = panel.query("municipality_name == 'Arcos de Valdevez'").iloc[0]
        self.assertEqual((arcos["nuts2_name"], arcos["nuts3_name"]), ("Norte", "Alto Minho"))


if __name__ == "__main__":
    unittest.main()
