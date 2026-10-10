# EU ETS Exposure Calculator (Excel + Streamlit) | 2026

A focused EU ETS decision-support toolkit to estimate:
- Scope 1 / Scope 2 / steam emissions over time
- EU ETS cost exposure for Scope 1 emissions under EUA scenarios
- EUA price sensitivity and carbon-intensity trends

This repository is intentionally EU ETS-focused. KPI/normalization workflows from separate projects are not included here.

## Files
- `app_streamlit.py` - Streamlit app (primary interface)
- `eu_ets_calc_io.py` - workbook parsing, validation, and fallback calculations
- `eu_ets_cli.py` - optional CLI runner
- `EU_ETS_Exposure_Calculator_Template.xlsx` - blank template
- `EU_ETS_Exposure_Calculator_Demo.xlsx` - demo workbook
- `demo_activity_data.csv` - demo activity data
- `tests/test_workbook_parsing.py` - regression tests
- `.github/workflows/ci.yml` - CI (lint/format/tests)

## Setup
1. Create and activate a virtual environment.
2. Install runtime dependencies:
   `python -m pip install -r requirements.txt`
3. Install dev dependencies:
   `python -m pip install -r requirements-dev.txt`

## Run Streamlit app
`streamlit run app_streamlit.py`

## EU ETS-specialized plots in the app
- Annualized ETS scenario summary (Low/Mid/High)
- Emissions breakdown over time (Scope 1, Scope 2, steam)
- ETS cost over time for each EUA scenario
- Carbon intensity trends (`tCO2 / t production`)
- EUA sensitivity curve + cost delta for `+10 EUR/tCO2`
- One-click PDF export of the analysis summary

## Optional CLI
`python eu_ets_cli.py --workbook EU_ETS_Exposure_Calculator_Demo.xlsx`

## Quality checks
`ruff check app_streamlit.py eu_ets_cli.py eu_ets_calc_io.py tests`
`black --check app_streamlit.py eu_ets_cli.py eu_ets_calc_io.py tests`
`python -m pytest -q`

## Scope note

This is a synthetic scenario/exposure analysis tool, **not legal or compliance advice**.
Direct fuel-combustion emissions define the Scope 1 exposure boundary in this model.
Electricity and purchased steam are contextual emissions, not added to that exposure.
All factors and EUA prices are editable demonstration assumptions, not current
regulatory values. See [data provenance](docs/data_provenance.md).

## License
MIT License. See `LICENSE`.


<!-- ci-workflow-coverage -->
## Continuous integration

[![CI](https://github.com/abhijith-sivaprasadan/EU-ETS-Exposure-Calculator-Package/actions/workflows/ci.yml/badge.svg?branch=codex%2Fci-publication)](https://github.com/abhijith-sivaprasadan/EU-ETS-Exposure-Calculator-Package/actions/workflows/ci.yml)

See [CI coverage and limitations](CI.md) for the automated checks. The status badge tracks the published CI review branch.
