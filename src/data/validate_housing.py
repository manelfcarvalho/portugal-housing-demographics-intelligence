"""Offline coverage audit for the inspected INE 0012255 / geography 05431 schema.

This module validates records against saved official metadata. It does not clean
prices, build a research panel or infer geography from code length.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INDICATOR = "0012255"
GEOGRAPHY_VERSION = "05431"
MUNICIPAL_LEVEL = "5"


def load_indicator(path: Path) -> tuple[dict, dict]:
    """Require the observed single-indicator success envelope; hash input bytes."""
    path = Path(path)
    content = path.read_bytes()
    payload = json.loads(content)
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise ValueError(f"Expected one indicator object in {path}")
    item = payload[0]
    if item.get("IndicadorCod") != INDICATOR:
        raise ValueError(f"Wrong indicator in {path}; expected {INDICATOR}")
    if item.get("Sucesso") != {"Verdadeiro": [{"Msg": "OK"}]}:
        raise ValueError(f"API did not report the observed OK status in {path}")
    provenance = {
        "file": path.name,
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "source_extracted_at": item.get("DataExtracao"),
    }
    return item, provenance


def metadata_reference(metadata: dict) -> dict:
    """Read the validated dimensions; fail if their version/schema changes."""
    try:
        dimensions = metadata["Dimensoes"]
        descriptions = {r["dim_num"]: r for r in dimensions["Descricao_Dim"]}
        if descriptions["2"]["versao"] != GEOGRAPHY_VERSION:
            raise ValueError("Geographic classification changed; review municipal level before use.")
        if metadata["Periodic"] != "Anual":
            raise ValueError("Expected annual data")
        reference = {"1": {}, "2": {}, "3": {}}
        for group in dimensions["Categoria_Dim"]:
            for entries in group.values():
                for entry in entries:
                    dim, code = entry["dim_num"], entry["cat_id"]
                    if dim not in reference or code in reference[dim]:
                        raise ValueError("Unexpected dimension or duplicate metadata category")
                    reference[dim][code] = entry
        if any(not values for values in reference.values()):
            raise ValueError("Metadata dimensions must not be empty")
        years = [entry["categ_dsg"] for entry in reference["1"].values()]
        if len(years) != len(set(years)) or any(not y.isdigit() or len(y) != 4 for y in years):
            raise ValueError("Expected unique four-digit annual periods")
        if min(years) != metadata["PrimeiroPeriodo"] or max(years) != metadata["UltimoPeriodo"]:
            raise ValueError("Metadata period bounds disagree with declared categories")
        municipalities = {
            code: entry for code, entry in reference["2"].items()
            if entry["categ_nivel"] == MUNICIPAL_LEVEL
        }
        if not municipalities:
            raise ValueError("No municipal-level reference categories found")
        return {"years": sorted(years), "geographies": reference["2"],
                "categories": reference["3"], "municipalities": municipalities}
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Metadata differs from the inspected schema") from exc


def audit(metadata_file: Path, raw_files: list[Path]) -> tuple[dict, pd.DataFrame]:
    """Compare every observed year/geo/category key against metadata expectations.

    Missing measurements are reported separately from missing records. Known
    missing measurements are not a structural failure and are never filled.
    """
    metadata, metadata_provenance = load_indicator(metadata_file)
    ref = metadata_reference(metadata)
    expected_keys = {(geo, category) for geo in ref["geographies"] for category in ref["categories"]}
    periods, sources, issues, coverage = {}, [], [], []

    for path in raw_files:
        payload, provenance = load_indicator(path)
        sources.append(provenance)
        data = payload.get("Dados")
        if not isinstance(data, dict) or not data:
            raise ValueError(f"No period data in {path}")
        for year, records in data.items():
            if year in periods:
                raise ValueError(f"Period {year} supplied more than once; avoid double counting")
            if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
                raise ValueError(f"Invalid record list for {year}")
            periods[year] = records

    def issue(kind: str, year: str, details: list) -> None:
        if details:
            issues.append({"kind": kind, "year": year, "count": len(details), "details": details})

    for year, records in sorted(periods.items()):
        keys = []
        label_mismatches, invalid_values, unknown_markers = [], [], []
        for row in records:
            required = ("geocod", "geodsg", "dim_3", "dim_3_t", "ind_string")
            if any(not isinstance(row.get(key), str) for key in required):
                raise ValueError(f"Record in {year} lacks required string fields")
            geo, category = row["geocod"], row["dim_3"]
            keys.append((geo, category))
            for code, label, mapping in ((geo, row["geodsg"], ref["geographies"]),
                                         (category, row["dim_3_t"], ref["categories"])):
                if code in mapping and label != mapping[code]["categ_dsg"]:
                    label_mismatches.append([code, label, mapping[code]["categ_dsg"]])
            value = row.get("valor")
            if value is None or value == "":
                if (row.get("ind_string"), row.get("sinal_conv"), row.get("sinal_conv_desc")) != (
                    "-", "-", "Dado nulo ou não aplicável"
                ):
                    unknown_markers.append([geo, category])
            else:
                try:
                    if not Decimal(str(value)).is_finite():
                        raise InvalidOperation
                except InvalidOperation:
                    invalid_values.append([geo, category, value])
        counts = Counter(keys)
        issue("duplicate_keys", year, [[*key, count] for key, count in counts.items() if count > 1])
        issue("unexpected_keys", year, [list(k) for k in sorted(set(keys) - expected_keys)])
        issue("missing_keys", year, [list(k) for k in sorted(expected_keys - set(keys))])
        issue("label_mismatches", year, label_mismatches)
        issue("invalid_measurements", year, invalid_values)
        issue("unreviewed_missing_markers", year, unknown_markers)

        for category, description in sorted(ref["categories"].items()):
            rows = [r for r in records if r["dim_3"] == category and r["geocod"] in ref["municipalities"]]
            represented = {r["geocod"] for r in rows}
            missing = [r for r in rows if r.get("valor") is None or r.get("valor") == ""]
            coverage.append({
                "year": year, "category_code": category,
                "category": description["categ_dsg"],
                "expected_municipalities": len(ref["municipalities"]),
                "municipalities_with_record": len(represented),
                "missing_municipality_records": len(ref["municipalities"].keys() - represented),
                "rows": len(rows), "values_present": len(rows) - len(missing),
                "values_missing": len(missing),
            })

    missing_years = sorted(set(ref["years"]) - periods.keys())
    unexpected_years = sorted(periods.keys() - set(ref["years"]))
    report = {
        "indicator": INDICATOR,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "geography_version": GEOGRAPHY_VERSION, "municipal_level": MUNICIPAL_LEVEL,
        "metadata": metadata_provenance, "raw_inputs": sources,
        "expected_years": ref["years"], "observed_years": sorted(periods),
        "missing_years": missing_years, "unexpected_years": unexpected_years,
        "geographic_levels": dict(Counter(r["categ_nivel"] for r in ref["geographies"].values())),
        "expected_municipalities": len(ref["municipalities"]),
        "total_records": sum(map(len, periods.values())), "issues": issues,
        "structure_valid": not (issues or missing_years or unexpected_years),
        "scope": "Coverage against this indicator's metadata snapshot; not boundary validation or a final research panel.",
    }
    return report, pd.DataFrame(coverage)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--raw-files", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/interim/housing_validation")
    args = parser.parse_args()
    try:
        report, coverage = audit(args.metadata, args.raw_files)
        json_path = args.output_dir / "audit.json"
        csv_path = args.output_dir / "municipal_coverage.csv"
        if json_path.exists() or csv_path.exists():
            raise FileExistsError("Audit outputs already exist; choose a new --output-dir")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        with json_path.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        coverage.to_csv(csv_path, index=False, mode="x")
        print(coverage.to_string(index=False))
        print(f"\nStructural validation passed: {report['structure_valid']}")
        print(f"Missing years: {report['missing_years']}; unexpected years: {report['unexpected_years']}")
        print(f"Issue groups: {len(report['issues'])}; full details: {json_path}")
        if not report["structure_valid"]:
            parser.exit(1, "Coverage validation found discrepancies; inspect audit.json.\n")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Validation failed: {exc}\n")


if __name__ == "__main__":
    main()
