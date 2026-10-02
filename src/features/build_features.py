"""Create analysis features from the validated municipality-year panel."""

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data/processed/municipality_year_panel_2021_2025.csv"
DEFAULT_CPI_INPUT = ROOT / "data/interim/cpi_portugal_annual_2021_2025.csv"
DEFAULT_OUTPUT = ROOT / "data/processed/municipality_year_features_2021_2025.csv"

KEY = ["municipality_code", "year"]
DIMENSION_COLUMNS = [
    "municipality_code",
    "municipality_name",
    "nuts2_code",
    "nuts2_name",
    "nuts3_code",
    "nuts3_name",
    "year",
]
MEASUREMENT_COLUMNS = [
    "housing_price_m2_total",
    "population_total",
    "aging_index",
    "migration_balance",
    "declared_income_less_irs_per_tax_household",
]
REQUIRED_COLUMNS = DIMENSION_COLUMNS + MEASUREMENT_COLUMNS


def _annual_change_percent(frame: pd.DataFrame, column: str) -> pd.Series:
    """Return consecutive year-on-year percentage change within municipality."""
    groups = frame.groupby("municipality_code", sort=False)
    previous_value = groups[column].shift()
    previous_year = groups["year"].shift()
    change = frame[column].div(previous_value).sub(1).mul(100)
    return change.where(frame["year"].sub(previous_year).eq(1))


def add_features(panel: pd.DataFrame, cpi_reference: pd.DataFrame) -> pd.DataFrame:
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
    income_column = "declared_income_less_irs_per_tax_household"
    invalid_income = result[income_column].notna() & result[income_column].le(0)
    if invalid_income.any():
        raise ValueError("Present income values must be greater than zero")

    required_cpi = {"year", "cpi_index_2025_base"}
    missing_cpi = sorted(required_cpi - set(cpi_reference.columns))
    if missing_cpi:
        raise ValueError(f"Missing CPI columns: {', '.join(missing_cpi)}")
    cpi = cpi_reference[["year", "cpi_index_2025_base"]].copy()
    try:
        cpi["year"] = pd.to_numeric(cpi["year"], errors="raise").astype(int)
        cpi["cpi_index_2025_base"] = pd.to_numeric(
            cpi["cpi_index_2025_base"], errors="raise"
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("CPI year and index must be numeric") from exc
    if cpi["year"].duplicated().any():
        raise ValueError("Duplicate CPI year")
    if cpi["cpi_index_2025_base"].isna().any() or cpi["cpi_index_2025_base"].le(0).any():
        raise ValueError("CPI index must be present and greater than zero")
    panel_years = set(result["year"])
    if set(cpi["year"]) != panel_years:
        raise ValueError("CPI years must match panel years exactly")

    result = result.sort_values(KEY, kind="stable").reset_index(drop=True)
    result = result.merge(cpi, on="year", how="left", validate="many_to_one")
    result["inflation_adjustment_to_2025"] = 100 / result["cpi_index_2025_base"]
    result["housing_price_m2_total_2025_eur"] = (
        result["housing_price_m2_total"] * result["inflation_adjustment_to_2025"]
    )
    result["declared_income_less_irs_per_tax_household_2025_eur"] = (
        result[income_column] * result["inflation_adjustment_to_2025"]
    )
    result["housing_price_growth_pct"] = _annual_change_percent(
        result, "housing_price_m2_total"
    )
    result["population_growth_pct"] = _annual_change_percent(result, "population_total")
    result["income_growth_pct"] = _annual_change_percent(result, income_column)
    result["housing_price_real_growth_pct"] = _annual_change_percent(
        result, "housing_price_m2_total_2025_eur"
    )
    result["income_real_growth_pct"] = _annual_change_percent(
        result, "declared_income_less_irs_per_tax_household_2025_eur"
    )
    result["aging_index_change"] = result.groupby("municipality_code", sort=False)[
        "aging_index"
    ].diff()
    result["migration_rate_per_1000"] = (
        result["migration_balance"].div(result["population_total"]).mul(1000)
    )
    result["one_m2_price_as_declared_income_pct"] = (
        result["housing_price_m2_total"].div(result[income_column]).mul(100)
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--cpi-input", type=Path, default=DEFAULT_CPI_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        panel = pd.read_csv(
            args.input,
            dtype={"municipality_code": "string", "nuts2_code": "string", "nuts3_code": "string"},
        )
        cpi_reference = pd.read_csv(args.cpi_input)
        features = add_features(panel, cpi_reference)
        if args.output.exists():
            raise FileExistsError(f"Output already exists: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        features.to_csv(args.output, index=False, mode="x", encoding="utf-8")
        print(f"Saved {len(features)} municipality-year rows to {args.output}")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Feature build failed: {exc}\n")


if __name__ == "__main__":
    main()
