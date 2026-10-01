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
| `nuts2_code` | string | NUTS II code associated with the municipality | identifier | INE NUTS 2024 geography metadata | 9 codes |
| `nuts2_name` | string | NUTS II regional label | text | INE NUTS 2024 geography metadata | 9 names |
| `nuts3_code` | string | NUTS III code associated with the municipality | identifier | INE NUTS 2024 geography metadata | 26 codes |
| `nuts3_name` | string | NUTS III subregional label | text | INE NUTS 2024 geography metadata | 26 names |
| `year` | integer | Calendar year of the observation | year | Time dimension | 2021–2025 |
| `housing_price_m2_total` | float | Median sale value of family dwellings, category `H1 = Total` | €/m² | `0012255` | 2021–2025; 33 measurements unavailable |
| `population_total` | integer | Resident population, both sexes and all ages | people | `0012918` | Complete for 2021–2025 |
| `aging_index` | float | People aged 65 or older per 100 people aged 0–14 | ratio | `0012909` | Complete for 2021–2025 |
| `migration_balance` | integer | Annual migration balance | people | `0013179` | Complete for 2021–2025 |
| `declared_income_less_irs_per_tax_household` | float | Gross declared income less assessed personal income tax, per tax household | euros | `0012740` | Complete for 2021–2024; unavailable for 2025 |

CSV readers must load `municipality_code`, `nuts2_code` and `nuts3_code` as
strings. They are identifiers rather than numeric measurements.

## Geographic hierarchy

The housing metadata uses the NUTS 2024 classification and declares a hierarchy
of 9 NUTS II regions, 26 NUTS III subregions and 308 municipalities. The panel
maps each municipality to exactly one NUTS II and one NUTS III entry by validated
metadata code ancestry. The mapping is not inferred from municipality names.

For example, Arcos de Valdevez belongs to NUTS III Alto Minho and NUTS II Norte.
Lisboa belongs to Grande Lisboa at both levels. Repeated labels are valid where a
NUTS II region and its single NUTS III subdivision cover the same territory.

## Derived analysis features

`data/processed/municipality_year_features_2021_2025.csv` preserves the original
panel columns and adds:

| Column | Definition | Unit | Expected missing values |
| --- | --- | --- | --- |
| `housing_price_growth_pct` | Consecutive year-on-year change in median housing price | percent | First year and any pair containing an unavailable price |
| `population_growth_pct` | Consecutive year-on-year change in resident population | percent | First year for every municipality |
| `income_growth_pct` | Consecutive year-on-year change in fiscal household income | percent | First year and 2025, where income is unavailable |
| `aging_index_change` | Current ageing index minus the previous consecutive year's index | index points | First year for every municipality |
| `migration_rate_per_1000` | Migration balance divided by resident population, multiplied by 1,000 | people per 1,000 residents | None in the current panel |
| `one_m2_price_as_declared_income_pct` | Median price of one m² divided by declared income less IRS per tax household, multiplied by 100 | percent | Any row with unavailable price or income |

Growth is calculated only between consecutive years for the same municipality.
The price-income feature is an exploratory comparison: it is not an official
housing affordability measure or household effort rate because the dataset does
not contain total dwelling prices, dwelling size or household expenditure.

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
status, periods, category filters, municipal membership, NUTS II and NUTS III hierarchy,
numeric values, duplicate keys and one-to-one joins before writing the panel. The integration
test confirms 1,540 unique keys and the expected missing-value pattern.
