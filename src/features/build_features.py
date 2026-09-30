"""Create analysis features from the validated municipality-year panel."""

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data/processed/municipality_year_panel_2021_2025.csv"
DEFAULT_OUTPUT = ROOT / "data/processed/municipality_year_features_2021_2025.csv"

KEY = ["municipality_code", "year"]
REQUIRED_COLUMNS = [
    "municipality_code",
    "municipality_name",
    "year",
    "housing_price_m2_total",
    "population_total",
    "aging_index",
    "migration_balance",
    "income_after_tax_per_tax_household",
]
MEASUREMENT_COLUMNS = REQUIRED_COLUMNS[3:]


def _annual_change_percent(frame: pd.DataFrame, column: str) -> pd.Series:
    """Return consecutive year-on-year percentage change within municipality."""
    groups = frame.groupby("municipality_code", sort=False)
    previous_value = groups[column].shift()
    previous_year = groups["year"].shift()
    change = frame[column].div(previous_value).sub(1).mul(100)
    return change.where(frame["year"].sub(previous_year).eq(1))


def add_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Validate a municipality-year panel and return it with derived features."""
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(panel.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    result = panel[REQUIRED_COLUMNS].copy()
    if result[KEY].isna().any().any():
        raise ValueError("Municipality code and year cannot be missing")
    if result.duplicated(KEY).any():
        raise ValueError("Duplicate municipality-year keys")

    try:
        result["year"] = pd.to_numeric(result["year"], errors="raise").astype(int)
        for column in MEASUREMENT_COLUMNS:
            result[column] = pd.to_numeric(result[column], errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError("Year and measurement columns must be numeric") from exc

    if result["population_total"].isna().any() or result["population_total"].le(0).any():
        raise ValueError("Population must be present and greater than zero")
    invalid_income = result["income_after_tax_per_tax_household"].notna() & result[
        "income_after_tax_per_tax_household"
    ].le(0)
    if invalid_income.any():
        raise ValueError("Present income values must be greater than zero")

    result = result.sort_values(KEY, kind="stable").reset_index(drop=True)
    result["housing_price_growth_pct"] = _annual_change_percent(
        result, "housing_price_m2_total"
    )
    result["population_growth_pct"] = _annual_change_percent(result, "population_total")
    result["income_growth_pct"] = _annual_change_percent(
        result, "income_after_tax_per_tax_household"
    )
    result["aging_index_change"] = result.groupby("municipality_code", sort=False)[
        "aging_index"
    ].diff()
    result["migration_rate_per_1000"] = (
        result["migration_balance"].div(result["population_total"]).mul(1000)
    )
    result["annual_income_needed_for_one_m2_pct"] = (
        result["housing_price_m2_total"]
        .div(result["income_after_tax_per_tax_household"])
        .mul(100)
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        panel = pd.read_csv(args.input, dtype={"municipality_code": "string"})
        features = add_features(panel)
        if args.output.exists():
            raise FileExistsError(f"Output already exists: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        features.to_csv(args.output, index=False, mode="x", encoding="utf-8")
        print(f"Saved {len(features)} municipality-year rows to {args.output}")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Feature build failed: {exc}\n")


if __name__ == "__main__":
    main()
