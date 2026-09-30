"""Integration checks against the preserved official snapshots."""

from pathlib import Path
import unittest

from src.data.build_panel import build_panel


RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


class PanelBuildTests(unittest.TestCase):
    @unittest.skipUnless((RAW / "population_metadata_20260928.json").exists(), "raw snapshots not present")
    def test_panel_keys_and_intentional_missing_values(self):
        panel, audit = build_panel(RAW)
        self.assertEqual(len(panel), 1540)
        self.assertFalse(panel.duplicated(["municipality_code", "year"]).any())
        self.assertEqual(panel["municipality_code"].nunique(), 308)
        self.assertEqual(sorted(panel["year"].unique()), [2021, 2022, 2023, 2024, 2025])
        self.assertEqual(int(panel["housing_price_m2_total"].isna().sum()), 33)
        income_2025 = panel.loc[panel["year"] == 2025, "income_after_tax_per_tax_household"]
        self.assertEqual(int(income_2025.isna().sum()), 308)
        for column in ("population_total", "aging_index", "migration_balance"):
            self.assertFalse(panel[column].isna().any())
        self.assertEqual(audit.query("column == 'population_total'")["missing"].sum(), 0)


if __name__ == "__main__":
    unittest.main()
