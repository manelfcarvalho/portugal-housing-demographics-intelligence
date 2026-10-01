"""Build the validated municipality-year panel from preserved INE JSON."""

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "municipality_year_panel_2021_2025.csv"
YEARS = [str(year) for year in range(2021, 2026)]

SOURCES = {
    "housing_price_m2_total": {
        "indicator": "0012255", "metadata": "housing_prices_metadata_20260928.json",
        "pattern": "housing_prices_{year}.json", "years": YEARS,
        "filters": {"dim_3": "H1"},
    },
    "population_total": {
        "indicator": "0012918", "metadata": "population_metadata_20260928.json",
        "pattern": "population_total_{year}.json", "years": YEARS,
        "filters": {"dim_3": "T", "dim_4": "T"},
    },
    "aging_index": {
        "indicator": "0012909", "metadata": "aging_index_metadata_20260930.json",
        "pattern": "aging_index_{year}.json", "years": YEARS, "filters": {},
    },
    "migration_balance": {
        "indicator": "0013179", "metadata": "migration_balance_metadata_20260930.json",
        "pattern": "migration_balance_{year}.json", "years": YEARS, "filters": {},
    },
    "declared_income_less_irs_per_tax_household": {
        "indicator": "0012740", "metadata": "income_household_metadata_20260930.json",
        "pattern": "income_household_{year}.json", "years": YEARS[:-1], "filters": {},
    },
}


def _load_one(path: Path, indicator: str) -> dict:
    payload = json.loads(path.read_bytes())
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError(f"Expected one indicator object in {path}")
    item = payload[0]
    if item.get("IndicadorCod") != indicator:
        raise ValueError(f"Expected indicator {indicator} in {path}")
    if item.get("Sucesso") != {"Verdadeiro": [{"Msg": "OK"}]}:
        raise ValueError(f"INE response did not report OK in {path}")
    return item


def _geography_categories(metadata: dict) -> list[dict]:
    try:
        return [
            row
            for group in metadata["Dimensoes"]["Categoria_Dim"]
            for entries in group.values()
            for row in entries
            if row["dim_num"] == "2"
        ]
    except (KeyError, TypeError) as exc:
        raise ValueError("Metadata differs from the inspected INE schema") from exc


def _municipal_reference(metadata: dict) -> dict[str, str]:
    categories = _geography_categories(metadata)
    reference = {
        row["cat_id"]: row["categ_dsg"]
        for row in categories
        if row["categ_nivel"] == "5"
    }
    if len(reference) != 308:
        raise ValueError(f"Expected 308 municipal metadata categories, found {len(reference)}")
    return reference


def _municipal_geography(metadata: dict) -> pd.DataFrame:
    """Map every municipality to one NUTS II and one NUTS III in NUTS 2024."""
    categories = _geography_categories(metadata)
    by_level = {
        level: [row for row in categories if row["categ_nivel"] == level]
        for level in ("3", "4", "5")
    }
    if len(by_level["3"]) != 9 or len(by_level["4"]) != 26 or len(by_level["5"]) != 308:
        raise ValueError("Expected 9 NUTS II, 26 NUTS III and 308 municipalities")

    records = []
    for municipality in by_level["5"]:
        municipality_code = municipality["cat_id"]
        nuts2_matches = [row for row in by_level["3"] if municipality_code.startswith(row["cat_id"])]
        nuts3_matches = [row for row in by_level["4"] if municipality_code.startswith(row["cat_id"])]
        if len(nuts2_matches) != 1 or len(nuts3_matches) != 1:
            raise ValueError(f"Ambiguous NUTS hierarchy for municipality {municipality_code}")
        nuts2, nuts3 = nuts2_matches[0], nuts3_matches[0]
        records.append(
            {
                "municipality_code": municipality_code,
                "municipality_name": municipality["categ_dsg"],
                "nuts2_code": nuts2["cat_id"],
                "nuts2_name": nuts2["categ_dsg"],
                "nuts3_code": nuts3["cat_id"],
                "nuts3_name": nuts3["categ_dsg"],
            }
        )

    geography = pd.DataFrame.from_records(records)
    if geography["municipality_code"].duplicated().any():
        raise ValueError("Duplicate municipality in NUTS hierarchy")
    return geography


def _source_table(raw_dir: Path, column: str, spec: dict, canonical: dict[str, str]) -> pd.DataFrame:
    metadata = _load_one(raw_dir / spec["metadata"], spec["indicator"])
    reference = _municipal_reference(metadata)
    if reference != canonical:
        raise ValueError(f"Municipal reference for {column} does not match the canonical reference")

    frames = []
    for year in spec["years"]:
        item = _load_one(raw_dir / spec["pattern"].format(year=year), spec["indicator"])
        if set(item.get("Dados", {})) != {year}:
            raise ValueError(f"Expected only period {year} for {column}")
        frame = pd.DataFrame.from_records(item["Dados"][year])
        for field, expected in spec["filters"].items():
            if field not in frame:
                raise ValueError(f"Missing filter field {field} for {column}")
            frame = frame[frame[field] == expected]
        frame = frame[frame["geocod"].isin(canonical)].copy()
        frame["year"] = int(year)
        if len(frame) != 308 or frame["geocod"].nunique() != 308:
            raise ValueError(f"Expected one {column} row for each municipality in {year}")
        expected_names = frame["geocod"].map(canonical)
        if not frame["geodsg"].equals(expected_names):
            raise ValueError(f"Municipality names disagree for {column} in {year}")
        if column == "housing_price_m2_total":
            missing = frame["valor"].isna() | frame["valor"].eq("")
            markers = frame.loc[missing, ["ind_string", "sinal_conv", "sinal_conv_desc"]]
            expected_marker = (
                markers["ind_string"].eq("-")
                & markers["sinal_conv"].eq("-")
                & markers["sinal_conv_desc"].eq("Dado nulo ou não aplicável")
            )
            if not expected_marker.all():
                raise ValueError(f"Unreviewed housing missing-value marker in {year}")
        numeric = pd.to_numeric(frame["valor"], errors="coerce")
        unexpected = frame["valor"].notna() & frame["valor"].ne("") & numeric.isna()
        if unexpected.any():
            raise ValueError(f"Non-numeric measurement for {column} in {year}")
        part = pd.DataFrame(
            {"municipality_code": frame["geocod"], "year": frame["year"], column: numeric}
        )
        frames.append(part)

    result = pd.concat(frames, ignore_index=True)
    if result.duplicated(["municipality_code", "year"]).any():
        raise ValueError(f"Duplicate municipality-year key in {column}")
    return result


def build_panel(raw_dir: Path = RAW_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return the panel and a missing-value audit without imputing observations."""
    raw_dir = Path(raw_dir)
    housing_spec = SOURCES["housing_price_m2_total"]
    housing_meta = _load_one(raw_dir / housing_spec["metadata"], housing_spec["indicator"])
    geography = _municipal_geography(housing_meta)
    canonical = dict(zip(geography["municipality_code"], geography["municipality_name"], strict=True))

    years = pd.DataFrame({"year": [int(year) for year in YEARS]})
    base = geography.merge(years, how="cross")
    panel = base
    audits = []
    for column, spec in SOURCES.items():
        table = _source_table(raw_dir, column, spec, canonical)
        panel = panel.merge(table, on=["municipality_code", "year"], how="left", validate="one_to_one")
        for year in map(int, YEARS):
            values = panel.loc[panel["year"] == year, column]
            audits.append(
                {
                    "column": column,
                    "year": year,
                    "rows": len(values),
                    "present": int(values.notna().sum()),
                    "missing": int(values.isna().sum()),
                }
            )

    if len(panel) != 1540 or panel.duplicated(["municipality_code", "year"]).any():
        raise ValueError("Panel must contain exactly 1,540 unique municipality-year rows")
    panel = panel.sort_values(["year", "municipality_code"], kind="stable").reset_index(drop=True)
    return panel, pd.DataFrame(audits)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        panel, audit = build_panel(args.raw_dir)
        if args.output.exists():
            raise FileExistsError(f"Output already exists: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        panel.to_csv(args.output, index=False, mode="x", encoding="utf-8")
        print(audit.to_string(index=False))
        print(f"\nSaved {len(panel)} unique municipality-year rows to {args.output}")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Panel build failed: {exc}\n")


if __name__ == "__main__":
    main()
