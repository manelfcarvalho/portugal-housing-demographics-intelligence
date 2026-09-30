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
                "year": [2021, 2021, 2022, 2022, 2023, 2023],
                "housing_price_m2_total": [200.0, 100.0, 110.0, 220.0, None, 242.0],
                "population_total": [2000, 1000, 1020, 2100, 1030, 2200],
                "aging_index": [200.0, 100.0, 105.0, 198.0, 108.0, 195.0],
                "migration_balance": [20, -10, 51, 42, 0, -22],
                "income_after_tax_per_tax_household": [20000.0, 10000.0, 10500.0, 21000.0, None, 22000.0],
            }
        )

    def test_features_are_sorted_and_calculated_without_mutating_input(self):
        original = self.panel.copy(deep=True)
        result = add_features(self.panel)
        pd.testing.assert_frame_equal(self.panel, original)

        a_2022 = result.query("municipality_code == '001' and year == 2022").iloc[0]
        self.assertAlmostEqual(a_2022["housing_price_growth_pct"], 10.0)
        self.assertAlmostEqual(a_2022["population_growth_pct"], 2.0)
        self.assertAlmostEqual(a_2022["income_growth_pct"], 5.0)
        self.assertAlmostEqual(a_2022["aging_index_change"], 5.0)
        self.assertAlmostEqual(a_2022["migration_rate_per_1000"], 50.0)
        self.assertAlmostEqual(a_2022["annual_income_needed_for_one_m2_pct"], 110 / 10500 * 100)
        self.assertEqual(result.iloc[0]["municipality_code"], "001")

    def test_first_year_and_missing_inputs_do_not_create_false_growth(self):
        result = add_features(self.panel)
        first_year = result.groupby("municipality_code", sort=False).head(1)
        self.assertTrue(first_year["housing_price_growth_pct"].isna().all())
        self.assertTrue(first_year["population_growth_pct"].isna().all())

        a_2023 = result.query("municipality_code == '001' and year == 2023").iloc[0]
        self.assertTrue(pd.isna(a_2023["housing_price_growth_pct"]))
        self.assertTrue(pd.isna(a_2023["income_growth_pct"]))
        self.assertTrue(pd.isna(a_2023["annual_income_needed_for_one_m2_pct"]))

    def test_nonconsecutive_years_are_not_compared(self):
        gap = self.panel.query("not (municipality_code == '001' and year == 2022)")
        result = add_features(gap)
        a_2023 = result.query("municipality_code == '001' and year == 2023").iloc[0]
        self.assertTrue(pd.isna(a_2023["population_growth_pct"]))

    def test_invalid_keys_and_denominators_fail(self):
        duplicate = pd.concat([self.panel, self.panel.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            add_features(duplicate)

        invalid_population = self.panel.copy()
        invalid_population.loc[0, "population_total"] = 0
        with self.assertRaisesRegex(ValueError, "Population"):
            add_features(invalid_population)

        invalid_income = self.panel.copy()
        invalid_income.loc[0, "income_after_tax_per_tax_household"] = 0
        with self.assertRaisesRegex(ValueError, "income"):
            add_features(invalid_income)

    def test_missing_required_column_fails(self):
        with self.assertRaisesRegex(ValueError, "aging_index"):
            add_features(self.panel.drop(columns="aging_index"))


if __name__ == "__main__":
    unittest.main()
