# Data sources — discovery register

Phase 0 — Data Discovery and Validation. The first live extraction and structural
validation are complete. Coverage for 2019–2025 has also been checked against
official indicator metadata; see [coverage audit](coverage_validation.md). No EDA, research results, cleaning or modeling is included.

## Housing sale prices

- **Source:** INE (Instituto Nacional de Estatística)
- **Indicator:** `0012255`
- **Description returned by INE:** Valor mediano das vendas de alojamentos familiares (Metodologia 2022 - €/ m²) por Localização geográfica (NUTS - 2024) e Categoria do alojamento familiar; Anual - INE, Estatísticas de preços da habitação ao nível local (Metodologia 2022)
- **Unit:** €/m²
- **Geographic classification in indicator title:** NUTS 2024
- **Geographic levels:** mixed; the response includes Portugal, regional aggregates,
  municipality codes and finer geographic units. It is not a municipality-only table.
- **Status:** 2024 extraction and CSV conversion reproduced; all declared years
  2019–2025 retrieved and audited against official metadata.
- **Exact API URL (provided by user):** [INE JSON response](https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0012255&Dim1=S7A2024&lang=PT)
- **Metadata URL returned by INE:** [Indicator metadata](https://www.ine.pt/bddXplorer/htdocs/minfo.jsp?var_cd=0012255&lingua=PT)
  (HTML page timed out; the [official JSON metadata](https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp?varcd=0012255&lang=PT) was successfully
  retrieved and preserved as `housing_prices_metadata_20260928.json`).
- **Local save time (UTC):** `2026-09-28T19:05:18.461849+00:00`
- **Source DataExtracao:** `2026-09-28T20:05:17.935+01:00`
- **Source DataUltimoAtualizacao:** `2026-04-24`
- **Source UltimoPref:** `2025`; this is metadata, not proof of
  any additional year's availability in this extraction.
- **API status:** `Sucesso.Verdadeiro[0].Msg = OK`
- **Raw file:** `data/raw/housing_prices_2024.json` (574,092 bytes)
- **Raw SHA-256:** `cefd314081364b311a25d3f5eb47510d8d499395a00e7e2f8005d14f2f72860c`
- **CSV file:** `data/processed/housing_prices_2024.csv`
- **Selected JSON Pointer:** `/0/Dados/2024`

The request recovered from an initial connection timeout through the existing retry
logic. The raw response is preserved unchanged. Both data files remain ignored by Git.

## Reproduce the extraction

From the repository root, with the dependencies installed:

```bash
python -m src.data.fetch_ine --url "https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0012255&Dim1=S7A2024&lang=PT" --name housing_prices_2024
python -m src.data.transform data/raw/housing_prices_2024.json --records-path /0/Dados/2024 --value-column valor
```

Existing files are protected from overwrite. For a new extraction, use a new
`--name` and transform the corresponding new raw filename. Official data may be
revised, so a later response can differ from this snapshot.

Explicit selection is necessary: the generic discovery also finds
`/0/Sucesso/Verdadeiro`, a list of status messages, which must not be exported as data.

## Observed schema and validation

The envelope contains one indicator. `Dados` contains only the key `2024` in this
filtered response. The year is enclosing metadata and is not a column of the CSV.
This section describes the initial 2024 file. Subsequent requests retrieved all
seven metadata-declared periods, 2019–2025; see [coverage audit](coverage_validation.md).

| Column | Observed meaning | Missing values | Unique non-missing values |
| --- | --- | ---: | ---: |
| geocod | Geographic code; mixed levels | 0 | 931 |
| geodsg | Geographic designation | 0 | 891 |
| dim_3 | Dwelling category code | 0 | 3 |
| dim_3_t | Dwelling category label | 0 | 3 |
| ind_string | Display value or source marker | 0 | 1269 |
| valor | Measurement, represented as a JSON string where present | 1114 | 1268 |
| sinal_conv | Conventional sign, where present | 1679 | 1 |
| sinal_conv_desc | Description of that sign, where present | 1679 | 1 |

- **Rows:** 2,793; **columns:** 8.
- **Categories:** `H1 = Total`, `H11 = Novos`, `H12 = Existentes`;
  each has 931 rows, one per geographic code.
- **Duplicate full rows:** 0.
- **Duplicate `(geocod, dim_3)` pairs:** 0 within 2024.
- **Missing measurements:** 1,114; 1,679 measurements are present.
- Every missing `valor` is accompanied by `ind_string = -`, `sinal_conv = -`
  and `sinal_conv_desc = Dado nulo ou não aplicável` in this response.
  Do not replace these with zero or infer a more specific cause.
- No empty strings were observed. Missing sign fields on rows with values are
  optional annotations, not missing measurements.
- All eight columns are read as strings with missing entries where fields are
  absent. No numeric conversion or imputation was applied to the exported data.
- CSV was read back as strings and checked against every extracted record.
  Raw and CSV shapes, column order, values and missing entries agree.

### Initial geographic observations and subsequent metadata validation

| Geographic code length | Unique codes |
| --- | ---: |
| 1 | 3 |
| 2 | 10 |
| 3 | 26 |
| 7 | 308 |
| 9 | 584 |

The initial seven-character candidate group was subsequently matched to all 308
level-5 municipality entries in official geography metadata version 05431. Every
code and name agrees, with no missing or unexpected entries, in each retrieved
year/category. Selection now uses metadata membership, not code length. This
confirms record coverage relative to the indicator's reference; it does not verify
independent geographic boundaries. Regional and freguesia rows coexist in the raw
file; unique geographic names must not be used as municipality counts.

For the **308 metadata-matched municipalities in 2024**, measurements present/missing are:

| Category | Rows | Present valor | Missing valor |
| --- | ---: | ---: | ---: |
| Total (H1) | 308 | 303 | 5 |
| Novos (H11) | 308 | 152 | 156 |
| Existentes (H12) | 308 | 300 | 8 |

Presence of geographic records does not establish complete measurement coverage.
No rows were filtered out of the exported CSV. No municipality count was passed
to the generic transform, because `geocod` covers several geographic levels.

## Next validation steps

Temporal record coverage (2019–2025) and municipal record coverage have been checked
against the official metadata snapshot. Full commands, hashes, checks and yearly
measurement availability are in [coverage validation](coverage_validation.md).

1. Review geographic boundary and methodology comparability before integration.
2. Confirm the dwelling category required for the eventual municipality-year panel.
3. Validate demographic datasets and their common geographic and temporal scope.
4. Decide how to handle unavailable measurements only after defining the research scope.
5. Determine the common panel after validating the other candidate datasets.

## Other candidate sources

dados.gov.pt, PORDATA and potentially Eurostat remain candidates for official
housing/demographic discovery. No additional dataset, endpoint, coverage or
compatibility is claimed or implemented at this stage.

## Population and candidate explanatory indicators

The proposed municipality-year schema and its plain-language interpretation are
documented in [data_dictionary.md](data_dictionary.md).

### Resident population

- **Source:** INE, Annual resident population estimates
- **Indicator:** `0012918`
- **Description:** Resident population by residence, sex and age group
- **Unit:** people
- **Official metadata periods:** 2021–2025
- **Selected categories:** `Dim3=T` (`HM`, both sexes) and `Dim4=T` (`Total`, all ages)
- **Geography version:** `05257`, NUTS 2024 / CAOP 2020 reference described in metadata
- **Status:** all five years downloaded and structurally checked
- **Coverage:** 308 municipal records per year, no duplicate municipality keys and
  no missing municipal values
- **Reconciliation:** municipal values sum exactly to the published Portugal total
  in each year
- **Metadata note:** estimates from 2021 use an administrative-data methodology;
  comparison from 2020 to 2021 requires care

The unfiltered response also contains Portugal and NUTS aggregates. Municipal rows
must be selected through the level-5 metadata reference, not by treating every
`geocod` as a municipality.

### Additional indicators with complete declared series retrieved

| Indicator | Code | Unit | Metadata periods | Municipal check |
| --- | --- | --- | --- | --- |
| Ageing index | `0012909` | persons aged 65+ per 100 aged 0–14 | 2021–2025 | 308 rows/year, no missing values |
| Migration balance | `0013179` | people | 2021–2025 | 308 rows/year, no missing values |
| Gross declared income less assessed IRS per tax household | `0012740` | euros | 2018–2024 | 308 rows/year, no missing values |

All declared years above were retrieved. Every municipal code/name set agrees
exactly, and no duplicate municipal keys, unknown codes, label disagreements or
missing municipal measurements were found. Income is based on anonymized fiscal
data from tax returns and should not be described as average salary or income for
every resident. Housing remains the only selected source with missing municipal
measurements in the common years.

## Consumer Price Index for constant euros

- **Source:** INE (Instituto Nacional de Estatística)
- **Indicator:** `0014642`
- **Description:** Consumer Price Index, Base 2025, by geographic location and
  special aggregates; annual
- **Selected geography:** `PT = Portugal`
- **Selected aggregate:** `T = Total`
- **Selected periods:** 2021–2025
- **Observed values:** 84.825, 91.469, 95.412, 97.717 and 100.000
- **Purpose:** convert the two monetary variables to constant 2025 euros
- **Metadata snapshot:** `cpi_annual_base2025_metadata_20261001.json`
- **Annual snapshots:** `cpi_annual_base2025_2021.json` through
  `cpi_annual_base2025_2025.json`
- **Official API:** [INE JSON response](https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0014642&lang=PT)
- **Official metadata:** [INE JSON metadata](https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp?varcd=0014642&lang=PT)

The INE introduced the Base 2025 series in 2026. Its metadata declares annual
coverage from 1948 to 2025. Annual responses were requested explicitly with
`Dim1=S7A<year>` because an unfiltered API request returns only the latest period.
The base-year observation is validated as exactly 100 before any conversion.

The pipeline writes `data/interim/cpi_portugal_annual_2021_2025.csv`, containing
one row per year, the CPI and `100 / CPI` adjustment factor. The CPI is national:
the same factor is joined to all 308 municipalities in a given year.
