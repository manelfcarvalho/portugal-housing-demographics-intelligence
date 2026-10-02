"""Build a validated annual Portuguese CPI reference for constant-2025 euros."""

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
DEFAULT_OUTPUT = ROOT / "data" / "interim" / "cpi_portugal_annual_2021_2025.csv"

INDICATOR = "0014642"
YEARS = list(range(2021, 2026))
METADATA_FILE = "cpi_annual_base2025_metadata_20261001.json"
ANNUAL_PATTERN = "cpi_annual_base2025_{year}.json"


def _load_one(path: Path) -> dict:
    payload = json.loads(path.read_bytes())
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError(f"Expected one indicator object in {path}")
    item = payload[0]
    if item.get("IndicadorCod") != INDICATOR:
        raise ValueError(f"Expected indicator {INDICATOR} in {path}")
    if item.get("Sucesso") != {"Verdadeiro": [{"Msg": "OK"}]}:
        raise ValueError(f"INE response did not report OK in {path}")
    return item


def build_cpi_reference(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Return one validated Portugal-total CPI observation per year."""
    raw_dir = Path(raw_dir)
    metadata = _load_one(raw_dir / METADATA_FILE)
    if metadata.get("Periodic") != "Anual":
        raise ValueError("Expected an annual CPI indicator")
    if metadata.get("PrimeiroPeriodo") > str(min(YEARS)) or metadata.get("UltimoPeriodo") < str(max(YEARS)):
        raise ValueError("CPI metadata does not cover every required year")

    records = []
    for year in YEARS:
        item = _load_one(raw_dir / ANNUAL_PATTERN.format(year=year))
        if set(item.get("Dados", {})) != {str(year)}:
            raise ValueError(f"Expected only period {year} in CPI response")
        frame = pd.DataFrame.from_records(item["Dados"][str(year)])
        selected = frame.loc[
            frame["geocod"].eq("PT") & frame["dim_3"].eq("T")
        ]
        if len(selected) != 1:
            raise ValueError(f"Expected one Portugal-total CPI observation in {year}")
        row = selected.iloc[0]
        if row["geodsg"] != "Portugal" or row["dim_3_t"] != "Total":
            raise ValueError(f"Unexpected Portugal-total CPI labels in {year}")
        try:
            value = float(row["valor"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"CPI must be numeric in {year}") from exc
        if value <= 0:
            raise ValueError(f"CPI must be greater than zero in {year}")
        records.append({"year": year, "cpi_index_2025_base": value})

    result = pd.DataFrame.from_records(records)
    if result["year"].duplicated().any() or result["year"].tolist() != YEARS:
        raise ValueError("CPI reference must contain one row for every required year")
    if result.loc[result["year"].eq(2025), "cpi_index_2025_base"].iloc[0] != 100:
        raise ValueError("Expected CPI base year 2025 to equal 100")
    result["inflation_adjustment_to_2025"] = 100 / result["cpi_index_2025_base"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        reference = build_cpi_reference(args.raw_dir)
        if args.output.exists():
            raise FileExistsError(f"Output already exists: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        reference.to_csv(args.output, index=False, mode="x", encoding="utf-8")
        print(reference.to_string(index=False))
        print(f"\nSaved {len(reference)} annual CPI rows to {args.output}")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"CPI build failed: {exc}\n")


if __name__ == "__main__":
    main()
