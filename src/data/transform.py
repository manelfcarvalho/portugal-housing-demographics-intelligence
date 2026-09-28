"""Inspect a JSON record list and export it without guessing domain semantics."""

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT / "data" / "processed"


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def candidate_lists(value: Any, path: str = "") -> dict[str, list]:
    """Find leaf lists of objects; prefer nested records over outer envelopes."""
    candidates = {}
    children = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else []
    for key, child in children:
        candidates.update(candidate_lists(child, f"{path}/{_escape(str(key))}"))
    if not candidates and isinstance(value, list) and all(isinstance(row, dict) for row in value):
        candidates[path] = value
    return candidates


def select_records(payload: Any, records_path: str | None = None) -> tuple[list[dict], str]:
    """Resolve an explicit JSON Pointer, or the sole discovered candidate."""
    if records_path is None:
        candidates = candidate_lists(payload)
        if len(candidates) != 1:
            choices = ", ".join(f"{path!r} ({len(rows)} rows)" for path, rows in candidates.items()) or "none"
            raise ValueError(f"Cannot safely select a record list. Candidates: {choices}. Supply --records-path as a JSON Pointer.")
        records_path, records = next(iter(candidates.items()))
    else:
        records = payload
        if records_path and not records_path.startswith("/"):
            raise ValueError("--records-path must be a JSON Pointer starting with /, or '' for the root.")
        try:
            for part in records_path.split("/")[1:]:
                key = part.replace("~1", "/").replace("~0", "~")
                if isinstance(records, list):
                    if not key.isdigit():
                        raise ValueError("List indices must be non-negative integers")
                    records = records[int(key)]
                else:
                    records = records[key]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError(f"Record path not found: {records_path!r}") from exc
    if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
        raise ValueError("Selected value must be a list of JSON objects.")
    return records, records_path


def transform(
    raw_file: Path,
    output_dir: Path = PROCESSED_DIR,
    *,
    records_path: str | None = None,
    municipality_column: str | None = None,
    year_column: str | None = None,
    value_column: str | None = None,
) -> Path:
    """Print structural validation and save a CSV; mappings are explicitly supplied."""
    raw_file = Path(raw_file)
    records, selected_path = select_records(json.loads(raw_file.read_bytes()), records_path)
    frame = pd.DataFrame.from_records(records)
    for column in (municipality_column, year_column, value_column):
        if column is not None and column not in frame.columns:
            raise ValueError(f"Column {column!r} does not exist. Available columns: {list(frame.columns)}")
    destination = Path(output_dir) / f"{raw_file.stem}.csv"
    if destination.exists():
        raise FileExistsError(f"Processed file already exists; choose another output directory: {destination}")

    print(f"Selected JSON Pointer: {selected_path!r} (empty means root)")
    print("Only the selected records are exported; enclosing metadata is retained in raw JSON.")
    print(f"Total rows: {len(frame)}\nTotal columns: {len(frame.columns)}")
    print(f"Column names: {list(frame.columns)}")
    print("\nFirst 5 rows:\n", frame.head(5).to_string(index=False))
    print("\nData types:\n", frame.dtypes.to_string())
    print("\nMissing values per column (JSON null or absent fields):\n", frame.isna().sum().to_string())
    print("Source-specific missing-value markers are not interpreted yet.")
    nested = [column for column in frame if frame[column].map(lambda x: isinstance(x, (dict, list))).any()]
    print("\nUnique non-null values in categorical-like columns:")
    for column in frame.select_dtypes(include=["object", "string", "bool", "category"]):
        if column in nested:
            print(f"  {column}: skipped (nested JSON)")
        else:
            print(f"  {column}: {frame[column].nunique(dropna=True)}")
    for column in (municipality_column, year_column, value_column):
        if column in nested:
            raise ValueError(f"Semantic mapping {column!r} refers to nested JSON, not a scalar field.")
    if municipality_column is not None:
        print(f"Unique municipalities ({municipality_column}, supplied mapping): {frame[municipality_column].nunique(dropna=True)}")
    if year_column is not None:
        print(f"Years found ({year_column}, supplied mapping): {frame[year_column].dropna().unique().tolist()}")
    if value_column is not None:
        print(f"Missing measurement values ({value_column}): {int(frame[value_column].isna().sum())}")
    if all(column is None for column in (municipality_column, year_column, value_column)):
        print("Municipality/year/measurement mappings not validated; semantic coverage is not inferred.")

    # Preserve nested cells as JSON strings rather than Python repr; no explosion,
    # numeric coercion, filtering, imputation, aggregation or geographic inference.
    exported = frame.copy()
    for column in nested:
        exported[column] = exported[column].map(
            lambda value: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    exported.to_csv(destination, index=False, encoding="utf-8", mode="x")
    print(f"\nSaved CSV: {destination}")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_file", type=Path)
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--records-path", help="JSON Pointer selecting a record list; '' selects root")
    parser.add_argument("--municipality-column", help="Confirmed municipality identifier column")
    parser.add_argument("--year-column", help="Confirmed year column")
    parser.add_argument("--value-column", help="Confirmed measurement column")
    args = parser.parse_args()
    try:
        transform(**vars(args))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Transformation failed: {exc}\n")


if __name__ == "__main__":
    main()
