# EU ETS CO2 + Cost Exposure Pack | 2026

Demonstration project for an industrial monthly **Energy + ETS Close** process.
It converts plant activity and energy inputs into planning-oriented ETS cost exposure, diagnostics, and follow-up actions.

Tools: Excel-first workflow + Python (Streamlit) for analysis/reporting; optional web interface for portfolio view.
Boundary statement: ETS cost exposure is based on Scope 1; Scope 2/3 are included for performance context (Scope 3 as optional proxy).

## Engineering Deliverables
- `EU_ETS_Exposure_Calculator_Template.xlsx`
  Editable site input template (activity, factors, EUA scenarios).
- `EU_ETS_Exposure_Calculator_Demo.xlsx`
  Demo workbook with sample values.
- `EU_ETS_Exposure_Calculator_Demo_Insights.xlsx`
  Enhanced demo workbook with richer seasonal variation and stress events for better chart insight.
- `demo_portfolio/*.xlsx`
  Portfolio site demo pack (`Site_A`, `Site_B`, `Site_C`) for multi-workbook analysis mode.
- `EU_ETS_Portfolio_Demo_Worksheet.xlsx`
  Portfolio worksheet describing scenarios, expected signals, and recommended test settings.
- `app_streamlit.py`
  Analyst-facing review dashboard for scenario testing and reporting.
- `eu_ets_calc_io.py`
  Workbook ingestion, validation, and controlled recomputation when formula cells are blank.
- `eu_ets_cli.py`
  Optional command-line run path for reproducible batch checks.
- `demo_activity_data.csv`
  Sample monthly activity data for quick demonstration.

## What The App Produces
- CO2 + cost exposure dashboard for monthly review meetings
- Scenario exposure table (CSV export)
- Management report (PDF) with summary, plots, interpretation notes, and generated-by/date metadata
- Portfolio planner outputs for multi-site screening (summary CSV + editable review log CSV)
- Monthly close pack handover artifact: 1-page management summary + investigate list + actions register export

## Analysis Views (EU ETS-focused)
- Annualized ETS scenario comparison (Low/Mid/High/custom)
- Planning-case view (Base/Stress/High-price) with delta-to-base exposure
- Emissions profile over time (Scope 1/2 and optional Scope 3 proxy, assumption-driven)
- ETS cost trend lines by scenario
- Carbon intensity trends (`tCO2 / t product`)
- EUA sensitivity curve and `+10 EUR/tCO2` cost impact
- Period comparisons: month vs previous month and YTD vs prior YTD
- Action support: top driver shortlist and monthly investigate list for coordination with production/maintenance
- Dynamic risk view: live EUA shock slider, exposure risk badge, and narrative updates

## Monthly Energy + ETS Close
- Inputs example: natural gas (`Nm3`), electricity/steam (`MWh`), production (`t`), with configurable emission factors and conversion constants.
- Scope 3 proxy factor can be set in workbook assumptions (`Factors` sheet) and optionally overridden in the app.
- Monthly close KPIs:
  - Scope 1 ETS emissions and net EUA requirement (planning): `Scope1 - free allocation input (annualised)`
  - ETS EUR exposure by scenario
  - CO2 intensity and energy intensity (`MWh/t`, `tCO2/t`)
- Variance decomposition table:
  - `Delta CO2 = production effect + energy intensity effect + fuel mix effect + factor/assumption effect`
- Quality and governance:
  - monthly data quality grade (`A/B/C`) with investigate flags
  - energy/CO2 reconciliation check: fuel energy to expected CO2 range
  - assumptions register (factor value, unit, source, validity date)
- Actions and market layer:
  - action register (owner, due date, expected vs actual savings, CO2/EUR impact, CAPEX, payback)
  - electricity price sensitivity scenarios and break-even EUA indicator
  - KPI: total cost sensitivity to `+20%` electricity price

## Workspace Modes
- `Single Site Review`: full deep-dive with ETS charts, sensitivity analysis, and PDF report.
- `Portfolio Planner`: multi-workbook upload, central procurement scenarios, site guardrail alerts, site-comparison curves, and monthly action log editing.

## Optional Web Interface
- Optional API + web UI are included for portfolio and interactive close views:
  - `POST /api/ets/analyze`
  - `POST /api/ets/portfolio`
  - `POST /api/ets/report` (PDF management report export)

## Review Workflow In App
1. Inputs check
2. Exposure summary
3. Drivers and causes
4. Actions
5. Report export

## How To Run
1. Create and activate a virtual environment.
2. Install runtime dependencies:
   `python -m pip install -r requirements.txt`
3. Launch the dashboard:
   `streamlit run app_streamlit.py`

Optional CLI run:
`python eu_ets_cli.py --workbook EU_ETS_Exposure_Calculator_Demo.xlsx`

Generate the latest demo pack (single-site + portfolio):
`python scripts/generate_demo_pack.py`

## Method Notes
- ETS cost exposure is calculated on direct combustion emissions (Scope 1).
- Electricity-related emissions are shown as Scope 2 context and are not treated as direct allowance liability by default.
- Scope 3 is optional and modeled as a proxy factor for planning only.
- Assumptions (factors, conversions, EUA prices) are explicit and editable in workbook inputs.
- `docs/data_provenance.md` defines the source, unit, vintage, and boundary records required before operational use.

## Reliability / QA
- Input schema and range validation
- Regression tests for parser and calculations
- Lint/format/test checks in CI

## License
MIT License. See `LICENSE`.
