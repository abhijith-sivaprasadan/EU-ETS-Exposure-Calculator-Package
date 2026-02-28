from pathlib import Path

import pandas as pd
import pytest

from eu_ets_calc_io import (
    Factors,
    WorkbookValidationError,
    compute_scope1_total_tco2,
    load_calc_table,
    load_eua_scenarios,
    load_factors,
    validate_calc_dataframe,
    validate_loaded_data,
    validate_scenarios,
    validate_workbook,
)

WORKBOOK = Path("EU_ETS_Exposure_Calculator_Demo.xlsx")


def test_load_calc_table_has_expected_columns():
    calc = load_calc_table(WORKBOOK)
    assert "Period" in calc.columns
    assert "Gas_Nm3" in calc.columns
    assert len(calc) >= 24


def test_load_factors_parses_key_parameters():
    factors = load_factors(WORKBOOK)
    assert factors.gas_ef_tco2_per_mwh > 0
    assert factors.gas_kwh_per_nm3 > 0


def test_load_eua_scenarios_from_workbook():
    scenarios = load_eua_scenarios(WORKBOOK)
    assert set(scenarios["Scenario"]) == {"Low", "Mid", "High"}
    assert scenarios["EUA_EUR_per_tCO2"].tolist() == [50, 85, 120]


def test_scope1_computation_returns_positive_total():
    calc = load_calc_table(WORKBOOK)
    factors = load_factors(WORKBOOK)
    scope1_total = compute_scope1_total_tco2(calc, factors)
    assert scope1_total > 0


def test_validate_workbook_passes_demo_file():
    warnings = validate_workbook(WORKBOOK)
    assert isinstance(warnings, list)


def test_validate_calc_dataframe_rejects_negative_values():
    calc = load_calc_table(WORKBOOK)
    calc.loc[0, "Elec_MWh"] = -1
    errors, _ = validate_calc_dataframe(calc)
    assert any("Calc.Elec_MWh contains negative values" in msg for msg in errors)


def test_validate_scenarios_requires_positive_price():
    scenarios = pd.DataFrame(
        {
            "Scenario": ["Low", "Mid", "High"],
            "EUA_EUR_per_tCO2": [50, 0, 120],
        }
    )
    errors, _ = validate_scenarios(scenarios)
    assert any("Scenario prices must be positive numbers" in msg for msg in errors)


def test_validate_loaded_data_raises_on_bad_factor_values():
    calc = load_calc_table(WORKBOOK)
    scenarios = load_eua_scenarios(WORKBOOK)
    bad_factors = Factors(
        gas_ef_tco2_per_mwh=0,
        other_fuel_ef_tco2_per_mwh=0.27,
        steam_ef_tco2_per_mwh=0.1,
        electricity_grid_ef_tco2_per_mwh=0.12,
        gas_kwh_per_nm3=10.55,
    )

    with pytest.raises(WorkbookValidationError):
        validate_loaded_data(calc, bad_factors, scenarios)
