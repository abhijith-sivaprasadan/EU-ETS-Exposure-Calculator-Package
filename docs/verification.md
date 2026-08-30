# Numerical verification

`python -m pytest -q` checks gas conversion, rowwise fallback of partial workbook
caches, optional fuel columns, the Scope 1 boundary, invalid months, duplicate
periods, non-finite factors/prices, and the retained workbook regression cases.

The hand oracle `1000 Nm3 * 10 kWh/Nm3 / 1000 * 0.2 tCO2/MWh = 2 tCO2`
checks the conversion explicitly. Electricity and steam are not added to Scope 1.
For partial caches, missing rows are recomputed, not silently counted as zero.
Optional other-fuel blanks mean zero; missing gas/Scope 1 information must not
silently produce a valid total.

Before and after the correction, the retained main-branch demo workbook reports
Scope 1 = 56187.70 tCO2 (rounded to two decimals). The synthetic partial-cache
regression case changed from an incorrect 1.6 to 6.5 tCO2.

This is model/software verification with synthetic inputs, not regulatory or
facility-data validation. The CLI total and dashboard time series now share a
pure rowwise emissions core; regression tests check monthly and quarterly Scope 1
and costs against the CLI on partial caches. Workbook fixtures cover missing
optional columns, cached periods with blank formula values, and missing Calc rows.
Existing caches are preserved: detecting stale but non-empty formula caches is not
implemented. Fully versioned factors and a complete interactive UI/PDF audit
remain research-release work.
