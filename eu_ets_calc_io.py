"""Workbook loaders and validation helpers for EU ETS exposure demo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import pandas as pd


class WorkbookValidationError(ValueError):
    """Raised when workbook data fails schema/content checks."""


@dataclass(frozen=True)
class Factors:
    gas_ef_tco2_per_mwh: float
    other_fuel_ef_tco2_per_mwh: float
    steam_ef_tco2_per_mwh: float
    electricity_grid_ef_tco2_per_mwh: float
    gas_kwh_per_nm3: float


def _normalize(text: str) -> str:
    text = str(text).strip().lower()
    text = text.replace("€", "eur").replace("₂", "2").replace("³", "3")
    return re.sub(r"\s+", " ", text)


def _find_header_row(df: pd.DataFrame, expected: set[str]) -> int:
    for i in range(min(30, len(df))):
        row_values = {_normalize(v) for v in df.iloc[i].tolist() if pd.notna(v)}
        if expected.issubset(row_values):
            return i
    raise ValueError(f"Header row not found for expected columns: {expected}")


def _coerce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_calc_table(workbook_path: str | Path) -> pd.DataFrame:
    """Load Calc table by detecting the row that contains the table header."""
    raw = pd.read_excel(workbook_path, sheet_name="Calc", header=None)
    header_idx = _find_header_row(raw, {"period", "elec_mwh", "gas_nm3"})

    headers = raw.iloc[header_idx].astype(str).str.strip().tolist()
    df = raw.iloc[header_idx + 1 :].copy()
    df.columns = headers
    df = df[df["Period"].notna()].reset_index(drop=True)
    df["Period"] = df["Period"].astype(str)

    numeric_cols = [
        "Elec_MWh",
        "Gas_Nm3",
        "Gas_MWh_in",
        "Gas_MWh_calc",
        "OtherFuel_MWh",
        "Steam_MWh",
        "Prod_t",
        "Scope1_tCO2",
        "Scope2_tCO2",
        "Steam_tCO2",
        "Total_tCO2",
        "ETS_cost_selected_€",
        "ETS_cost_Low_€",
        "ETS_cost_Mid_€",
        "ETS_cost_High_€",
    ]
    return _coerce_numeric(df, numeric_cols)


def load_factors(workbook_path: str | Path) -> Factors:
    """Load factors from the Factors sheet by matching parameter labels."""
    raw = pd.read_excel(workbook_path, sheet_name="Factors", header=None)

    mapping: dict[str, float] = {}
    wanted = {
        "natural gas ef (tco2/mwh)": "gas_ef_tco2_per_mwh",
        "other fuel ef (tco2/mwh)": "other_fuel_ef_tco2_per_mwh",
        "steam ef (tco2/mwh)": "steam_ef_tco2_per_mwh",
        "electricity grid ef (tco2/mwh)": "electricity_grid_ef_tco2_per_mwh",
        "gas conversion (kwh per nm3)": "gas_kwh_per_nm3",
    }

    for _, row in raw.iterrows():
        name = _normalize(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
        value = row.iloc[1] if len(row) > 1 else None
        if name in wanted and pd.notna(value):
            mapping[wanted[name]] = float(value)

    missing = [v for v in wanted.values() if v not in mapping]
    if missing:
        raise ValueError(f"Missing required factors: {missing}")

    return Factors(**mapping)


def load_eua_scenarios(workbook_path: str | Path) -> pd.DataFrame:
    """Load scenario name and EUA price from the Factors sheet."""
    raw = pd.read_excel(workbook_path, sheet_name="Factors", header=None)
    header_idx = _find_header_row(raw, {"scenario", "eua price (eur/tco2)"})

    scenarios = raw.iloc[header_idx + 1 :, [0, 1]].copy()
    scenarios.columns = ["Scenario", "EUA_EUR_per_tCO2"]
    scenarios = scenarios[scenarios["Scenario"].notna()].copy()
    scenarios["Scenario"] = scenarios["Scenario"].astype(str).str.strip()
    scenarios["EUA_EUR_per_tCO2"] = pd.to_numeric(
        scenarios["EUA_EUR_per_tCO2"], errors="coerce"
    )
    scenarios = scenarios.dropna(subset=["EUA_EUR_per_tCO2"]).reset_index(drop=True)

    return scenarios


def validate_calc_dataframe(calc_df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Validate calc dataframe schema and value ranges."""
    errors: list[str] = []
    warnings: list[str] = []

    required_columns = ["Period", "Elec_MWh", "Gas_Nm3"]
    missing_columns = [col for col in required_columns if col not in calc_df.columns]
    if missing_columns:
        errors.append(f"Calc sheet is missing required columns: {missing_columns}")
        return errors, warnings

    if calc_df.empty:
        errors.append("Calc sheet contains no data rows.")
        return errors, warnings

    period = calc_df["Period"].astype(str).str.strip()
    period_is_yyyy_mm = period.str.fullmatch(r"\d{4}-\d{2}", na=False)
    invalid_period_rows = calc_df.index[~period_is_yyyy_mm].tolist()
    if invalid_period_rows:
        errors.append(
            "Calc.Period must use YYYY-MM format. Invalid row indices: "
            + ", ".join(str(i) for i in invalid_period_rows[:10])
        )

    duplicate_periods = period[period.duplicated(keep=False)].unique().tolist()
    if duplicate_periods:
        errors.append(f"Calc.Period has duplicates: {duplicate_periods}")

    for col in [
        "Elec_MWh",
        "Gas_Nm3",
        "Gas_MWh_in",
        "Gas_MWh_calc",
        "OtherFuel_MWh",
        "Steam_MWh",
    ]:
        if col in calc_df.columns:
            series = pd.to_numeric(calc_df[col], errors="coerce")
            bad_rows = calc_df.index[series < 0].tolist()
            if bad_rows:
                errors.append(
                    f"Calc.{col} contains negative values at row indices: {bad_rows[:10]}"
                )

    gas_candidates = []
    for col in ["Gas_Nm3", "Gas_MWh_in", "Gas_MWh_calc"]:
        if col in calc_df.columns:
            gas_candidates.append(
                pd.to_numeric(calc_df[col], errors="coerce").fillna(0)
            )
    if gas_candidates:
        gas_signal = sum(gas_candidates)
        if (gas_signal > 0).sum() == 0:
            warnings.append(
                "Calc has no positive gas activity values in Gas_Nm3/Gas_MWh_in/Gas_MWh_calc."
            )

    return errors, warnings


def validate_factors(factors: Factors) -> tuple[list[str], list[str]]:
    """Validate factor ranges and plausibility."""
    errors: list[str] = []
    warnings: list[str] = []

    if factors.gas_ef_tco2_per_mwh <= 0:
        errors.append("Factors: Natural gas EF must be > 0.")
    if factors.other_fuel_ef_tco2_per_mwh < 0:
        errors.append("Factors: Other fuel EF must be >= 0.")
    if factors.steam_ef_tco2_per_mwh < 0:
        errors.append("Factors: Steam EF must be >= 0.")
    if factors.electricity_grid_ef_tco2_per_mwh < 0:
        errors.append("Factors: Electricity grid EF must be >= 0.")
    if factors.gas_kwh_per_nm3 <= 0:
        errors.append("Factors: Gas conversion (kWh per Nm3) must be > 0.")

    if factors.gas_ef_tco2_per_mwh > 0.5:
        warnings.append(
            "Factors: Natural gas EF appears unusually high (>0.5 tCO2/MWh)."
        )
    if factors.gas_kwh_per_nm3 < 8 or factors.gas_kwh_per_nm3 > 13:
        warnings.append(
            "Factors: Gas conversion is outside common range (~8-13 kWh/Nm3)."
        )

    return errors, warnings


def validate_scenarios(scenarios: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Validate EUA scenario table schema and values."""
    errors: list[str] = []
    warnings: list[str] = []

    required_columns = ["Scenario", "EUA_EUR_per_tCO2"]
    missing_columns = [col for col in required_columns if col not in scenarios.columns]
    if missing_columns:
        errors.append(f"Scenario table is missing required columns: {missing_columns}")
        return errors, warnings

    if scenarios.empty:
        errors.append("Scenario table is empty.")
        return errors, warnings

    names = scenarios["Scenario"].astype(str).str.strip()
    prices = pd.to_numeric(scenarios["EUA_EUR_per_tCO2"], errors="coerce")

    if names.duplicated().any():
        duplicates = names[names.duplicated(keep=False)].unique().tolist()
        errors.append(f"Scenario names must be unique. Duplicates: {duplicates}")

    bad_price_rows = scenarios.index[(prices.isna()) | (prices <= 0)].tolist()
    if bad_price_rows:
        errors.append(
            f"Scenario prices must be positive numbers. Invalid row indices: {bad_price_rows}"
        )

    canonical = {"low", "mid", "high"}
    present = {n.lower() for n in names.tolist()}
    if not canonical.issubset(present):
        warnings.append("Scenario names do not include the canonical Low/Mid/High set.")

    return errors, warnings


def validate_workbook(workbook_path: str | Path) -> list[str]:
    """Validate workbook inputs and raise WorkbookValidationError on errors.

    Returns a list of warnings when validation succeeds.
    """
    calc = load_calc_table(workbook_path)
    factors = load_factors(workbook_path)
    scenarios = load_eua_scenarios(workbook_path)

    return validate_loaded_data(calc, factors, scenarios)


def validate_loaded_data(
    calc: pd.DataFrame, factors: Factors, scenarios: pd.DataFrame
) -> list[str]:
    """Validate preloaded structures and raise WorkbookValidationError on errors."""
    errors: list[str] = []
    warnings: list[str] = []

    for validator, payload in [
        (validate_calc_dataframe, calc),
        (validate_factors, factors),
        (validate_scenarios, scenarios),
    ]:
        v_errors, v_warnings = validator(payload)
        errors.extend(v_errors)
        warnings.extend(v_warnings)

    if errors:
        bullet_errors = "\n".join(f"- {item}" for item in errors)
        raise WorkbookValidationError(f"Workbook validation failed:\n{bullet_errors}")

    return warnings


def compute_scope1_total_tco2(calc_df: pd.DataFrame, factors: Factors) -> float:
    """Compute Scope 1 emissions with fallback when formula result columns are empty."""
    if "Scope1_tCO2" in calc_df.columns:
        scope1_series = pd.to_numeric(calc_df["Scope1_tCO2"], errors="coerce")
        if scope1_series.notna().any():
            return float(scope1_series.fillna(0).sum())

    gas_mwh = pd.to_numeric(calc_df.get("Gas_MWh_in"), errors="coerce")
    if gas_mwh.isna().all():
        gas_mwh = pd.to_numeric(calc_df.get("Gas_MWh_calc"), errors="coerce")
    if gas_mwh.isna().all():
        gas_nm3 = pd.to_numeric(calc_df.get("Gas_Nm3"), errors="coerce").fillna(0)
        gas_mwh = gas_nm3 * factors.gas_kwh_per_nm3 / 1000.0

    other_fuel_mwh = pd.to_numeric(
        calc_df.get("OtherFuel_MWh"), errors="coerce"
    ).fillna(0)

    scope1 = (
        gas_mwh.fillna(0) * factors.gas_ef_tco2_per_mwh
        + other_fuel_mwh * factors.other_fuel_ef_tco2_per_mwh
    )
    return float(scope1.sum())
