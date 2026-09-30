# Housing coverage validation — 2026-09-28

Scope: INE indicator `0012255`, official metadata snapshot, all seven declared
annual periods. This is a data-quality audit, not EDA or a final research panel.

## Official evidence and geographic interpretation

The [dados.gov.pt catalogue](https://dados.gov.pt/pt/datasets/valor-mediano-das-vendas-de-alojamentos-familiares-metodologia-2022-eur-m2-7) publishes the exact
[JSON metadata endpoint](https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp?varcd=0012255&lang=PT) used in this audit.
Metadata was saved unchanged as `data/raw/housing_prices_metadata_20260928.json`.
It declares annual periods 2019–2025 and geography version **05431**, described as
Localização geográfica (NUTS - 2024).

The metadata geography hierarchy contains:

| Metadata categ_nivel | Interpretation in this indicator | Codes |
| --- | --- | ---: |
| 1 | Portugal | 1 |
| 2 | NUTS I | 3 |
| 3 | NUTS II | 9 |
| 4 | NUTS III | 26 |
| 5 | Municipalities | 308 |
| 6 | Selected freguesias | 584 |

The municipal mapping follows the metadata hierarchy and category labels. It uses
membership in the 308 level-5 categories, **not code length**. It is deliberately
scoped to version 05431; the validator stops if the classification version changes.
All 931 observed geographic codes and labels match this official indicator
reference in every retrieved year, including all 308 municipal entries.
This validates coverage against the indicator's metadata, not an independent
CAOP boundary crosswalk or stability of geographic boundaries over time.

The metadata note limits freguesia dissemination to selected municipalities
(metropolitan Lisbon/Porto areas, Algarve and other municipalities above 100,000
residents at the 2021 Census). Therefore, 584 must not be described as all
Portuguese freguesias. The HTML metadata page timed out; the JSON metadata
request succeeded and is the source used here.

## Temporal and measurement coverage

All **seven declared years, 2019–2025**, were requested individually using their
actual metadata `cat_id` values (`S7A2019` through `S7A2025`). Each response contains
only its requested year and has **2,793 rows**: 931 geographies × 3 categories.
There are **19,551 raw records** across the seven saved responses.

Each year has 308 municipal records in each category. Available measurements differ:

| Year | Municipal records per category | Total: present | Total: missing | Novos: present | Existentes: present |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2019 | 308 | 286 | 22 | 138 | 272 |
| 2020 | 308 | 282 | 26 | 139 | 277 |
| 2021 | 308 | 298 | 10 | 141 | 288 |
| 2022 | 308 | 301 | 7 | 150 | 293 |
| 2023 | 308 | 300 | 8 | 146 | 294 |
| 2024 | 308 | 303 | 5 | 152 | 300 |
| 2025 | 308 | 305 | 3 | 164 | 302 |

The local coverage CSV reports missing measurements for every year/category.
A missing `valor` is accompanied by the source sign `-`, described as
“Dado nulo ou não aplicável”. These observations are retained, not set to zero.
Optional sign columns absent on measured rows are not measurement failures.

Checks passed across all input files:

- Correct indicator and explicit API success status.
- Exact agreement between observed and metadata-declared periods.
- No duplicate `(geocod, dim_3)` keys within a year.
- No unexpected or absent geography/category pairs relative to metadata.
- Geographic and category labels agree with the reference.
- Present measurements are finite numeric strings; original strings are preserved.
- Missing-measurement markers match the inspected convention.

A successful structural audit permits missing prices; it certifies that their
presence is explicitly measured and that records match the reference. It does
not make this a complete panel of observed prices or establish comparability with
population, income or other indicators. No imputation or category selection was done.

## Reproduce

Install the existing requirements and run from the repository root. Fetch metadata:

```bash
python -m src.data.fetch_ine --url "https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp?varcd=0012255&lang=PT" --name housing_prices_metadata_20260928
```

The following snippet reads period codes from that saved metadata and changes
only `Dim1` in the already validated URL. It preserves existing downloads and
checks reused or downloaded files against the requested indicator and period.

```python
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from src.data.fetch_ine import fetch_ine

metadata = json.loads(Path("data/raw/housing_prices_metadata_20260928.json").read_bytes())[0]
parts = urlsplit("https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0012255&Dim1=S7A2024&lang=PT")
for group in metadata["Dimensoes"]["Categoria_Dim"]:
    for entries in group.values():
        for entry in entries:
            if entry["dim_num"] != "1":
                continue
            year = entry["categ_dsg"]
            name = f"housing_prices_{year}"
            path = Path("data/raw") / f"{name}.json"
            if not path.exists():
                query = dict(parse_qsl(parts.query))
                query["Dim1"] = entry["cat_id"]
                fetch_ine(urlunsplit(parts._replace(query=urlencode(query))), name)
            data = json.loads(path.read_bytes())[0]
            if data["IndicadorCod"] != "0012255" or set(data["Dados"]) != {year}:
                raise ValueError(f"Unexpected indicator/period in {path}")
```

Run the offline audit:

```bash
python -m src.data.validate_housing \
  --metadata data/raw/housing_prices_metadata_20260928.json \
  --raw-files data/raw/housing_prices_20[12][0-9].json \
  --output-dir data/interim/housing_validation_20260928
python -m unittest discover -s tests -v
```

The file pattern selects the saved annual files and excludes metadata. The audit
reports unexpected years if other annual files are later added; pass explicit
filenames to reproduce this snapshot. Outputs are `audit.json` (checks, detailed
issues and source hashes) and `municipal_coverage.csv` (21 year/category summaries).
Both are ignored by Git. Existing outputs are protected: use a new output directory
for a rerun. The validator exits nonzero for structural discrepancies.

The scope is intentionally specific: `validate_housing.py` implements the observed
indicator schema, while `fetch_ine.py` and `transform.py` remain generic. No new
runtime dependency was added. The additional six annual files are audited directly
from JSON; no combined cleaned table has been created.

## Snapshot provenance

Each row below identifies an unchanged raw response. The 2024 file is the original
first extraction; the others were downloaded during this validation step. The
catalogue's update date is not the extraction date or observation year.

| Raw file | Source extraction time | SHA-256 |
| --- | --- | --- |
| `housing_prices_metadata_20260928.json` | 2026-09-28T20:15:22.103+01:00 | `e1d7eabd29bdcbc9ff2b0422d97112d1e0b87060b932bfab0a941df6731286b0` |
| `housing_prices_2019.json` | 2026-09-28T20:16:29.681+01:00 | `7a34f67e74175a76ce3b40fce4aae9db412bf781bd4be33db245607c0736492e` |
| `housing_prices_2020.json` | 2026-09-28T20:16:31.710+01:00 | `be3b459a5a5c34ba4a246364905ce9632a872220781e95626c59f7a3ff25de74` |
| `housing_prices_2021.json` | 2026-09-28T20:16:32.416+01:00 | `8c44dad2cbf5c139097f2c4adc7b1dfc96e2862f3be9025c7465b1f7445e08ab` |
| `housing_prices_2022.json` | 2026-09-28T20:16:34.598+01:00 | `329564e5253a930bdc81258a41963336fe63f3016029fe91fcf1852b959486c0` |
| `housing_prices_2023.json` | 2026-09-28T20:16:35.429+01:00 | `d757ec45d27ab699e26fe65efca58e17e2a9668265da4e1d8874273dc9cc29a6` |
| `housing_prices_2024.json` | 2026-09-28T20:05:17.935+01:00 | `cefd314081364b311a25d3f5eb47510d8d499395a00e7e2f8005d14f2f72860c` |
| `housing_prices_2025.json` | 2026-09-28T20:16:36.379+01:00 | `41766833d2fcfb48f9b94943c912f0223f88f9db8ff8a587e9cc6a51fcccfdcf` |

## Remaining work

- Review methodology and geographic boundary comparability before combining sources.
- Select the dwelling category for the eventual research question.
- Discover and validate demographic datasets, including codes, years and missing values.
- Determine a common municipality-year panel after those validations.
