"""Workbook loaders and validation helpers for EU ETS exposure demo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np
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
    """Load the Calc table, deriving inputs when formula caches are unavailable.

    Spreadsheet formulas are not evaluated by pandas/openpyxl. Some workbook editors
    save formula cells without cached values, so a clean checkout may otherwise appear
    to have an empty Calc sheet.
    """
    raw = pd.read_excel(workbook_path, sheet_name="Calc", header=None)
    header_idx = _find_header_row(raw, {"period", "elec_mwh", "gas_nm3"})

    headers = raw.iloc[header_idx].astype(str).str.strip().tolist()
    df = raw.iloc[header_idx + 1 :].copy()
    df.columns = headers
    df = df[df["Period"].notna()].reset_index(drop=True)
    df["Period"] = df["Period"].astype(str)

    # Calc caches can be incomplete by row or column. Join on Period (never
    # row position), preserving existing caches while recovering Inputs-only rows.
    with pd.ExcelFile(workbook_path) as workbook:
        if "Inputs" in workbook.sheet_names:
            inputs = pd.read_excel(workbook, sheet_name="Inputs", header=None)
            input_header_idx = _find_header_row(
                inputs, {"period", "electricity (mwh)", "natural gas (nm3)"}
            )
            input_df = inputs.iloc[input_header_idx + 1 :].copy()
            input_df.columns = inputs.iloc[input_header_idx].astype(str).str.strip()
            input_df = input_df[input_df["Period"].notna()].copy()
            rename = {
                "Electricity (MWh)": "Elec_MWh",
                "Natural gas (Nm3)": "Gas_Nm3",
                "Natural gas (Nm³)": "Gas_Nm3",
                "Natural gas (MWh) [optional]": "Gas_MWh_in",
                "Other fuel (MWh)": "OtherFuel_MWh",
                "Steam (MWh)": "Steam_MWh",
                "Production (t) [optional]": "Prod_t",
            }
            input_df = input_df.rename(columns=rename)
            input_df = input_df.reindex(
                columns=["Period", *dict.fromkeys(rename.values())]
            )
            input_df["Period"] = input_df["Period"].astype(str).str.strip()
            df["Period"] = df["Period"].str.strip()
            for label, table in [("Calc", df), ("Inputs", input_df)]:
                if table["Period"].duplicated().any():
                    raise WorkbookValidationError(f"{label}.Period has duplicates")
            df = (
                df.set_index("Period")
                .combine_first(input_df.set_index("Period"))
                .reset_index()
            )

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
    df = _coerce_numeric(df, numeric_cols)
    # Expose the same derived columns whether caches were complete or absent.
    rows = compute_emission_rows(df, load_factors(workbook_path))
    for target, source in [
        ("Gas_MWh_calc", "Gas_MWh_calc"),
        ("Scope1_tCO2", "Scope1_tCO2_effective"),
        ("Scope2_tCO2", "Scope2_tCO2_effective"),
        ("Steam_tCO2", "Steam_tCO2_effective"),
        ("Total_tCO2", "Total_tCO2_effective"),
    ]:
        df[target] = rows[source]
    return df


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
    period_is_yyyy_mm = period.str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", na=False)
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

    for name, value in vars(factors).items():
        if not np.isfinite(value):
            errors.append(f"Factors: {name} must be finite.")

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

    bad_price_rows = scenarios.index[(~np.isfinite(prices)) | (prices <= 0)].tolist()
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


def compute_emission_rows(calc_df: pd.DataFrame, factors: Factors) -> pd.DataFrame:
    """Shared pure rowwise calculations for the CLI and dashboard.

    Existing finite caches take precedence; this is not a stale-cache detector.
    Missing gas is an error unless Scope 1 is cached. Optional other fuel/steam
    blanks mean zero; missing electricity remains unknown, not zero.
    """
    errors, _ = validate_factors(factors)
    if errors:
        raise WorkbookValidationError("; ".join(errors))
    rows = calc_df.copy()

    def column(name):
        return pd.to_numeric(
            rows.get(name, pd.Series(np.nan, index=rows.index)), errors="coerce"
        )

    rows["Gas_MWh_calc"] = column("Gas_MWh_calc").fillna(
        column("Gas_Nm3") * factors.gas_kwh_per_nm3 / 1000.0
    )
    rows["Gas_MWh_effective"] = column("Gas_MWh_in").fillna(rows["Gas_MWh_calc"])
    for name in ["OtherFuel_MWh", "Steam_MWh"]:
        rows[name] = column(name).fillna(0)
    for name in ["Elec_MWh", "Prod_t"]:
        rows[name] = column(name)
    rows["Scope1_tCO2_calc"] = (
        rows["Gas_MWh_effective"] * factors.gas_ef_tco2_per_mwh
        + rows["OtherFuel_MWh"] * factors.other_fuel_ef_tco2_per_mwh
    )
    rows["Scope2_tCO2_calc"] = (
        rows["Elec_MWh"] * factors.electricity_grid_ef_tco2_per_mwh
    )
    rows["Steam_tCO2_calc"] = rows["Steam_MWh"] * factors.steam_ef_tco2_per_mwh
    for scope in ["Scope1", "Scope2", "Steam"]:
        rows[f"{scope}_tCO2_effective"] = column(f"{scope}_tCO2").fillna(
            rows[f"{scope}_tCO2_calc"]
        )
    scope1 = rows["Scope1_tCO2_effective"]
    if not np.isfinite(scope1).all() or (scope1 < 0).any():
        raise WorkbookValidationError(
            "Scope 1 requires finite non-negative data for every row"
        )
    rows["Total_tCO2_effective"] = (
        scope1 + rows["Scope2_tCO2_effective"] + rows["Steam_tCO2_effective"]
    )
    return rows


def compute_scope1_total_tco2(calc_df: pd.DataFrame, factors: Factors) -> float:
    """Sum shared rowwise Scope 1; exclude Scope 2 electricity and steam."""
    return float(compute_emission_rows(calc_df, factors)["Scope1_tCO2_effective"].sum())
