"""Tests for municipality-year feature engineering."""

import unittest

import pandas as pd

from src.features.build_features import add_features


class FeatureBuildTests(unittest.TestCase):
    def setUp(self):
        self.panel = pd.DataFrame(
            {
                "municipality_code": ["002", "001", "001", "002", "001", "002"],
                "municipality_name": ["B", "A", "A", "B", "A", "B"],
                "nuts2_code": ["N2B", "N2A", "N2A", "N2B", "N2A", "N2B"],
                "nuts2_name": ["Region B", "Region A", "Region A", "Region B", "Region A", "Region B"],
                "nuts3_code": ["N3B", "N3A", "N3A", "N3B", "N3A", "N3B"],
                "nuts3_name": ["Subregion B", "Subregion A", "Subregion A", "Subregion B", "Subregion A", "Subregion B"],
                "year": [2021, 2021, 2022, 2022, 2023, 2023],
                "housing_price_m2_total": [200.0, 100.0, 110.0, 220.0, None, 242.0],
                "population_total": [2000, 1000, 1020, 2100, 1030, 2200],
                "aging_index": [200.0, 100.0, 105.0, 198.0, 108.0, 195.0],
                "migration_balance": [20, -10, 51, 42, 0, -22],
                "declared_income_less_irs_per_tax_household": [
                    20000.0, 10000.0, 10500.0, 21000.0, None, 22000.0
                ],
            }
        )
        self.cpi = pd.DataFrame(
            {
                "year": [2021, 2022, 2023],
                "cpi_index_2025_base": [80.0, 88.0, 100.0],
            }
        )

    def test_features_are_sorted_and_calculated_without_mutating_input(self):
        original = self.panel.copy(deep=True)
        result = add_features(self.panel, self.cpi)
        pd.testing.assert_frame_equal(self.panel, original)

        a_2022 = result.query("municipality_code == '001' and year == 2022").iloc[0]
        self.assertAlmostEqual(a_2022["housing_price_growth_pct"], 10.0)
        self.assertAlmostEqual(a_2022["population_growth_pct"], 2.0)
        self.assertAlmostEqual(a_2022["income_growth_pct"], 5.0)
        self.assertAlmostEqual(a_2022["aging_index_change"], 5.0)
        self.assertAlmostEqual(a_2022["migration_rate_per_1000"], 50.0)
        self.assertAlmostEqual(a_2022["one_m2_price_as_declared_income_pct"], 110 / 10500 * 100)
        self.assertAlmostEqual(a_2022["inflation_adjustment_to_2025"], 100 / 88)
        self.assertAlmostEqual(a_2022["housing_price_m2_total_2025_eur"], 110 * 100 / 88)
        self.assertAlmostEqual(
            a_2022["housing_price_real_growth_pct"],
            ((110 * 100 / 88) / (100 * 100 / 80) - 1) * 100,
        )
        self.assertEqual(result.iloc[0]["municipality_code"], "001")
        self.assertEqual(a_2022["nuts3_name"], "Subregion A")

    def test_first_year_and_missing_inputs_do_not_create_false_growth(self):
        result = add_features(self.panel, self.cpi)
        first_year = result.groupby("municipality_code", sort=False).head(1)
        self.assertTrue(first_year["housing_price_growth_pct"].isna().all())
        self.assertTrue(first_year["population_growth_pct"].isna().all())

        a_2023 = result.query("municipality_code == '001' and year == 2023").iloc[0]
        self.assertTrue(pd.isna(a_2023["housing_price_growth_pct"]))
        self.assertTrue(pd.isna(a_2023["income_growth_pct"]))
        self.assertTrue(pd.isna(a_2023["one_m2_price_as_declared_income_pct"]))

    def test_nonconsecutive_years_are_not_compared(self):
        gap = self.panel.query("not (municipality_code == '001' and year == 2022)")
        result = add_features(gap, self.cpi)
        a_2023 = result.query("municipality_code == '001' and year == 2023").iloc[0]
        self.assertTrue(pd.isna(a_2023["population_growth_pct"]))

    def test_invalid_keys_and_denominators_fail(self):
        duplicate = pd.concat([self.panel, self.panel.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            add_features(duplicate, self.cpi)

        invalid_population = self.panel.copy()
        invalid_population.loc[0, "population_total"] = 0
        with self.assertRaisesRegex(ValueError, "Population"):
            add_features(invalid_population, self.cpi)

        invalid_income = self.panel.copy()
        invalid_income.loc[0, "declared_income_less_irs_per_tax_household"] = 0
        with self.assertRaisesRegex(ValueError, "income"):
            add_features(invalid_income, self.cpi)

    def test_missing_required_column_fails(self):
        with self.assertRaisesRegex(ValueError, "nuts3_name"):
            add_features(self.panel.drop(columns="nuts3_name"), self.cpi)

    def test_cpi_reference_must_match_panel_years(self):
        with self.assertRaisesRegex(ValueError, "CPI years"):
            add_features(self.panel, self.cpi.query("year != 2023"))

        duplicate = pd.concat([self.cpi, self.cpi.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "Duplicate CPI"):
            add_features(self.panel, duplicate)


if __name__ == "__main__":
    unittest.main()
