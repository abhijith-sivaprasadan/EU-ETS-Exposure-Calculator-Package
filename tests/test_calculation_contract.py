import numpy as np
import pandas as pd
import pytest

from eu_ets_calc_io import (
    Factors,
    compute_scope1_total_tco2,
    validate_calc_dataframe,
    validate_factors,
    validate_scenarios,
)

FACTORS = Factors(0.2, 0.3, 0.1, 0.4, 10.0)


def test_unit_conversion_and_missing_optional_fuel_column():
    frame = pd.DataFrame({"Gas_Nm3": [1000.0]})
    # 1000 Nm3 * 10 kWh/Nm3 / 1000 * 0.2 tCO2/MWh = 2 tCO2.
    assert compute_scope1_total_tco2(frame, FACTORS) == pytest.approx(2.0)


def test_partial_gas_and_scope1_caches_use_rowwise_fallback():
    frame = pd.DataFrame(
        {
            "Gas_Nm3": [1000.0, 2000.0],
            "Gas_MWh_in": [5.0, np.nan],
            "OtherFuel_MWh": [2.0, 3.0],
            "Scope1_tCO2": [1.6, np.nan],
        }
    )
    assert compute_scope1_total_tco2(frame, FACTORS) == pytest.approx(6.5)


def test_scope2_and_steam_do_not_inflate_scope1():
    frame = pd.DataFrame(
        {
            "Gas_Nm3": [1000.0],
            "OtherFuel_MWh": [2.0],
            "Elec_MWh": [10000.0],
            "Steam_MWh": [10000.0],
        }
    )
    assert compute_scope1_total_tco2(frame, FACTORS) == pytest.approx(2.6)


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_nonfinite_factors_rejected(value):
    factors = Factors(value, 0.3, 0.1, 0.4, 10.0)
    errors, _ = validate_factors(factors)
    assert errors


def test_infinite_eua_price_rejected():
    errors, _ = validate_scenarios(
        pd.DataFrame({"Scenario": ["High"], "EUA_EUR_per_tCO2": [float("inf")]})
    )
    assert errors


@pytest.mark.parametrize("period", ["2024-00", "2024-13"])
def test_invalid_calendar_month_rejected(period):
    errors, _ = validate_calc_dataframe(
        pd.DataFrame({"Period": [period], "Elec_MWh": [1.0], "Gas_Nm3": [1.0]})
    )
    assert errors


def test_duplicate_months_rejected():
    errors, _ = validate_calc_dataframe(
        pd.DataFrame(
            {
                "Period": ["2024-01", "2024-01"],
                "Elec_MWh": [1.0, 1.0],
                "Gas_Nm3": [1.0, 1.0],
            }
        )
    )
    assert errors
