# Municipality-year panel data dictionary

## Dataset purpose and grain

`data/processed/municipality_year_panel_2021_2025.csv` combines official INE
housing, demographic and fiscal indicators for exploratory analysis. Each row
represents one Portuguese municipality in one calendar year.

The composite key is:

```text
municipality_code + year
```

The panel contains 308 municipalities and five years (2021–2025), producing
1,540 unique municipality-year rows.

## Columns

| Column | Type | Definition | Unit | Source indicator | Coverage |
| --- | --- | --- | --- | --- | --- |
| `municipality_code` | string | Official municipality code from the indicator metadata | identifier | INE geography metadata | 308 codes |
| `municipality_name` | string | Municipality label associated with the official code | text | INE geography metadata | 308 names |
| `year` | integer | Calendar year of the observation | year | Time dimension | 2021–2025 |
| `housing_price_m2_total` | float | Median sale value of family dwellings, category `H1 = Total` | €/m² | `0012255` | 2021–2025; 33 measurements unavailable |
| `population_total` | integer | Resident population, both sexes and all ages | people | `0012918` | Complete for 2021–2025 |
| `aging_index` | float | People aged 65 or older per 100 people aged 0–14 | ratio | `0012909` | Complete for 2021–2025 |
| `migration_balance` | integer | Annual migration balance | people | `0013179` | Complete for 2021–2025 |
| `income_after_tax_per_tax_household` | float | Gross declared income less assessed personal income tax, per tax household | euros | `0012740` | Complete for 2021–2024; unavailable for 2025 |

CSV readers must load `municipality_code` as a string. It is an identifier rather
than a numeric measurement.

## Source filters

The processed panel applies the following selections to the raw indicator data:

- Housing: `dim_3 = H1`, labelled `Total`.
- Population: `dim_3 = T`, labelled `HM`, for both sexes combined.
- Population: `dim_4 = T`, labelled `Total`, for all ages combined.
- Municipalities: membership in the 308 level-5 categories declared by the
  housing metadata reference, with code and label agreement checked across sources.

The `Total` housing category is the median over sales of new and existing
dwellings together. It is not the sum of the two category medians.

## Missing values

The panel preserves missing measurements as empty CSV cells:

- 33 housing-price measurements are unavailable across 2021–2025.
- All 308 income measurements are unavailable in 2025 because the current source
  coverage ends in 2024.
- Population, ageing index and migration balance have no missing municipal values.

A missing measurement must not be replaced with zero. Analyses involving income
use the common 2021–2024 period. Other analyses may retain 2025.

## Interpretation constraints

- Housing values are medians in €/m², not total dwelling prices.
- An ageing index of 150 means 150 people aged 65 or older per 100 people aged
  0–14.
- Migration balance may be negative; a negative value is valid.
- The income measure comes from anonymised tax-return data and uses the tax
  household as its denominator. It is not average salary or income for every
  resident.
- Relationships between variables are observational and do not establish
  causality.
- Indicator geography versions differ internally. The builder verifies the exact
  municipality code and name set and must repeat this check when metadata changes.

## Validation

`python -m src.data.build_panel` validates indicator identifiers, API success
status, periods, category filters, municipal membership, numeric values,
duplicate keys and one-to-one joins before writing the panel. The integration
test confirms 1,540 unique keys and the expected missing-value pattern.
