# Portugal Housing & Demographics Intelligence

A Data Science portfolio project to study housing and demographic patterns in
Portugal using official public data. Candidate sources include INE, dados.gov.pt,
PORDATA and potentially Eurostat.

**Current phase: Phase 1 — Data Quality and Exploratory Analysis.** The first
municipality-year ingestion pipeline and its structural validation are complete.
The initial notebook examines data quality, distributions, time trends and early
relationships; statistical findings and machine learning have not yet been produced.

## Project structure

```text
portugal-housing-demographics-intelligence/
├── data/
│   ├── raw/.gitkeep
│   ├── interim/.gitkeep
│   └── processed/.gitkeep
├── notebooks/
│   ├── 01_data_quality_and_eda.ipynb
│   └── 02_research_questions.ipynb
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── build_panel.py
│   │   ├── fetch_ine.py
│   │   ├── transform.py
│   │   └── validate_housing.py
│   ├── features/
│   │   ├── __init__.py
│   │   └── build_features.py
│   ├── models/.gitkeep
│   └── visualization/.gitkeep
├── tests/
│   ├── test_fetch_ine.py
│   ├── test_build_features.py
│   ├── test_build_panel.py
│   ├── test_transform.py
│   └── test_validate_housing.py
├── docs/
│   ├── data_sources.md
│   ├── coverage_validation.md
│   └── data_dictionary.md
├── app/.gitkeep
├── .gitignore
├── README.md
├── requirements.txt
├── requirements-analysis.txt
└── pyproject.toml
```

Datasets in `data/raw`, `data/interim` and `data/processed` are ignored by Git.
The feature, model, visualization, notebook and app directories are placeholders.

## Initial pipeline

```text
INE API
   ↓
Raw JSON
   ↓
Python / pandas
   ↓
Validation
   ↓
Processed CSV
```

## Setup

Use Python 3.11 or newer. Run commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Only `requests` and `pandas` are direct pipeline dependencies. Their tested versions
are pinned in `requirements.txt`; tests use Python's standard-library `unittest`.

To work with the analysis notebook, install the separate analysis dependencies and
start JupyterLab:

```bash
python -m pip install -r requirements-analysis.txt
```

In VS Code, open the notebook and select `.venv/bin/python` in the kernel selector
at the top right. JupyterLab is optional; to use it instead, run `jupyter lab`.

## Download the first indicator

INE indicator **0012255** has now been retrieved for all **seven declared years,
2019–2025**. All **308 municipality codes and names** in its official metadata
reference are present in each year/category. Price availability is incomplete:
for example, category Total has measurements for 286 municipalities in 2019 and
305 in 2025. Mixed geographic levels remain in the raw data.

See [source notes](docs/data_sources.md), the
[reproducible coverage audit](docs/coverage_validation.md). Geographic
coverage is validated against the indicator metadata, not independent boundary
files. A common municipality-year panel has been defined for 2021–2025.

The initial 2024 extraction has **2,793 rows, 8 columns and 1,114 missing
measurements** across 931 geographic codes and three categories.

Use the exact URL provided for the first extraction:

```bash
python -m src.data.fetch_ine --url "https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0012255&Dim1=S7A2024&lang=PT" --name housing_prices_2024
python -m src.data.transform data/raw/housing_prices_2024.json --records-path /0/Dados/2024 --value-column valor
```

The explicit record path excludes the separate API status-message list. The year
is stored in the JSON envelope; it is not automatically added as a CSV column.
Existing files are protected; use a new name to repeat an extraction.

Outputs default to `data/raw/housing_prices_2024.json` and
`data/processed/housing_prices_2024.csv`, relative to the installed source tree.
`--output-dir` allows a different destination. Keep downloaded data out of Git.

`fetch_ine.py` validates the JSON and saves the original response body bytes without
reserializing them (after HTTP content decompression performed by `requests`). It
uses a 30-second socket timeout and at most three retries after the initial attempt.
HTTP 429, 500, 502, 503 and 504, connection failures and timeouts are retried with
1-, 2- and 4-second backoff. A valid `Retry-After` can extend each wait. Other HTTP
errors and invalid JSON fail immediately. Retry messages are logged. Configure
`--timeout`, `--max-retries` and `--backoff-factor` as needed. The timeout applies
to connection/read inactivity, not total job duration. Existing raw files are
never overwritten; choose a new name for a new extraction.

## Structural validation and CSV export

`transform.py` discovers leaf lists of JSON objects without assuming INE field
names. It automatically selects a list only when exactly one candidate exists.
If several lists exist (for example, different periods or metadata tables), it
prints their JSON Pointer paths and row counts and exits without exporting.
Inspect the raw response, then pass the correct path with `--records-path`.

For **synthetic illustration only**, `{"records": [{"code": "001"}]}` has the
record path `/records`; `--records-path ''` selects a root list. These are not
claims about the actual INE schema. The tool does not combine separate periods.

The validation summary prints rows, columns, column names, first five rows, inferred
data types, missing values and unique counts for scalar categorical-like columns.
Nested dictionaries/lists are kept as JSON strings in CSV. Enclosing metadata,
including any period stored outside records, stays in the raw file and is not
automatically added as a column. CSV has no schema; when reading it later, explicitly
load confirmed identifier columns as strings to preserve leading zeros.

After inspecting the real file and confirming its semantics, optional arguments
`--municipality-column`, `--year-column` and `--value-column` enable municipality
counts, observed years and missing-measurement counts. These must name real scalar
columns; no municipality, year or measurement field is guessed. Geography codes
may include non-municipal totals and require separate validation before this count
can establish municipality coverage. Missing values mean JSON null or absent
fields; source-specific markers, empty strings and suppressed values require later
validation. A syntactically valid JSON or CSV is not proof of valid indicator data.

There is no filtering, imputation, numeric coercion, aggregation or heavy cleaning.
Existing CSV files are not overwritten; choose another `--output-dir` for another
record selection. Preserve the exact URL, extraction date and selected record path
when documenting the first real run.

## Reproducible coverage audit

After downloading the official metadata and annual JSON files as described in
[coverage validation](docs/coverage_validation.md):

```bash
python -m src.data.validate_housing --metadata data/raw/housing_prices_metadata_20260928.json --raw-files data/raw/housing_prices_20[12][0-9].json --output-dir data/interim/housing_validation_20260928
```

This checks periods, geography/category membership, labels, duplicate keys and
measurement availability. It writes an audit JSON with input hashes and a coverage
CSV; it does not clean prices or construct a research panel. Use a new output
directory for a rerun. The validator is scoped to the inspected indicator and
geography version and fails if that classification changes.

## First municipality-year panel

After the documented raw snapshots are present, build the 2021–2025 panel:

```bash
python -m src.data.build_panel
```

This writes `data/processed/municipality_year_panel_2021_2025.csv`: 1,540 unique
municipality-year rows with housing price (Total), population, ageing index,
migration balance and fiscal income per tax household. Missing housing prices and
unavailable 2025 income remain empty. The builder validates indicator IDs, API
status, municipal metadata, category filters, numeric values and join cardinality.
See [data dictionary](docs/data_dictionary.md) before interpreting the columns.

## Analysis notebooks

`notebooks/01_data_quality_and_eda.ipynb` checks the municipality-year key,
summarizes missing values, calculates descriptive statistics and creates initial
distribution, trend, scatter and correlation plots.

`notebooks/02_research_questions.ipynb` uses the engineered features to compare
municipal housing-price growth, examine the price-income relationship and test
same-year and lagged associations between migration rates and price growth.
Reusable data and feature logic remains in `src/`; notebooks document exploration
and interpretation.

## Feature engineering

Build the analysis features from the validated panel:

```bash
python -m src.features.build_features
```

This writes `data/processed/municipality_year_features_2021_2025.csv` with the
original 1,540 rows plus annual price, population and income growth; annual ageing
index change; migration balance per 1,000 residents; and the percentage of annual
fiscal household income represented by one square metre at the municipal median
sale price. Missing source measurements and first-year growth values remain empty.
See the [data dictionary](docs/data_dictionary.md) for definitions and limitations.

## Tests

```bash
python -m unittest discover -s tests -v
```

All HTTP calls are mocked and synthetic JSON fixtures are created in temporary
directories. Tests cover exact raw-byte preservation, HTTP errors, retries and
backoff, `Retry-After`, network failures, invalid JSON, file protection, record
selection and validation output. Passing tests does not validate INE coverage.

## Roadmap

- [x] Identify candidate official datasets
- [x] Validate API extraction
- [x] Validate temporal coverage
- [x] Validate municipality coverage
- [x] Determine common municipality-year panel
- [x] Define initial research questions
- [x] Data cleaning and integration
- [x] Initial data-quality EDA notebook
- [x] Initial feature engineering
- [ ] Statistical analysis
- [ ] Machine Learning
- [ ] Model explainability
- [ ] Interactive dashboard
- [ ] Testing and CI/CD
- [ ] Deployment

Coverage checks refer to the documented metadata snapshots. Missing measurements
remain explicit in the panel and are examined in the first notebook. Initial unit
and integration tests exist; broader testing and CI/CD remain on the roadmap.
