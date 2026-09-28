# Data sources — discovery register

Phase 0 records candidate sources and what has actually been validated. No
municipality-year panel or research result is established yet.

## Housing sale prices

- **Source:** INE (Instituto Nacional de Estatística)
- **Indicator:** `0012255`
- **Description:** Median value of sales of family dwellings
- **Unit:** €/m²
- **Geographic level:** municipal data observed in initial API test
- **Status:** extraction successfully tested for 2024, as reported in the user's
  prior manual Data Discovery step; not yet reproduced by this repository
- **Notes:** exact temporal coverage and municipality completeness still need validation
- **Exact API URL:** not supplied; must be provided before the first live run
- **Raw response/schema:** not supplied; no field mappings validated

Do not infer that all 308 municipalities, every year, or only municipal-level
records are present. The indicator's geographic classification, dimensions,
period definition, suppression/missing-value markers and measurement semantics
must be checked against the actual response and official metadata.

### Inputs and checks for the first reproducible run

1. Obtain the exact working API URL for indicator `0012255`, including the year
   and geography filters used in the successful 2024 test. Do not reconstruct a
   guessed endpoint from the indicator number.
2. Run the downloader and preserve the raw JSON. Record the URL and UTC extraction
   time here after checking that the response really is indicator data.
3. Inspect the response; record the selected JSON Pointer and verified column
   meanings. If the year exists only in enclosing metadata, document it rather
   than inventing a year column.
4. Run structural validation and record actual row counts, geographic levels,
   years, duplicates and missing measurements before assessing completeness.
5. Verify municipality coverage against an appropriate official municipality
   reference and classification vintage in a later validation step.

### Other candidate sources

dados.gov.pt, PORDATA and potentially Eurostat are candidates for further official
housing/demographic discovery. No additional dataset, API endpoint, coverage or
compatibility is claimed or implemented at this stage.
