# Portugal Housing & Demographics Intelligence

A Data Science portfolio project to study housing and demographic patterns in
Portugal using official public data. Candidate sources include INE, dados.gov.pt,
PORDATA and potentially Eurostat.

**Current phase: Phase 0 — Data Discovery and Validation.** This repository provides
the first ingestion pipeline. No exploratory analysis, visualization, research
findings or machine learning has been produced.

## Project structure

```text
portugal-housing-demographics-intelligence/
├── data/
│   ├── raw/.gitkeep
│   ├── interim/.gitkeep
│   └── processed/.gitkeep
├── notebooks/.gitkeep
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── fetch_ine.py
│   │   └── transform.py
│   ├── features/.gitkeep
│   ├── models/.gitkeep
│   └── visualization/.gitkeep
├── tests/
│   ├── test_fetch_ine.py
│   └── test_transform.py
├── docs/
│   └── data_sources.md
├── app/.gitkeep
├── .gitignore
├── README.md
├── requirements.txt
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

Only `requests` and `pandas` are direct runtime dependencies. Their tested versions
are pinned in `requirements.txt`; tests use Python's standard-library `unittest`.

## Download the first indicator

The target is INE indicator **0012255**, median sale value of family dwellings,
**€/m²**. The project brief reports a successful manual test with municipal records
for 2024. The exact API URL has not been supplied, and this pipeline has **not yet
been validated against a live INE response**. See [source notes](docs/data_sources.md).

Replace the placeholder with the actual working URL, including all query filters:

```bash
python -m src.data.fetch_ine --url "<INE_API_URL>" --name housing_prices_2024
python -m src.data.transform data/raw/housing_prices_2024.json
```

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
- [ ] Validate API extraction
- [ ] Validate temporal coverage
- [ ] Validate municipality coverage
- [ ] Determine common municipality-year panel
- [ ] Define final research questions
- [ ] Data cleaning and integration
- [ ] Exploratory Data Analysis
- [ ] Feature engineering
- [ ] Statistical analysis
- [ ] Machine Learning
- [ ] Model explainability
- [ ] Interactive dashboard
- [ ] Testing and CI/CD
- [ ] Deployment

Initial unit tests exist; broader testing and CI/CD remain on the roadmap.
