"""Streamlit app for EU ETS exposure analysis and reporting visuals."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import streamlit as st

from eu_ets_calc_io import (
    WorkbookValidationError,
    compute_scope1_total_tco2,
    load_calc_table,
    load_eua_scenarios,
    load_factors,
    validate_loaded_data,
)

SCOPE1_COLOR = "#E4572E"
SCOPE2_COLOR = "#4C78A8"
STEAM_COLOR = "#54A24B"
COST_COLOR = "#00E6A8"
TOTAL_COLOR = "#B537F2"
PLOT_BG = "#000000"
PLOT_PANEL = "#0B0B0B"
PLOT_TEXT = "#E6EDF3"
PLOT_GRID = "#2A2A2A"

st.set_page_config(page_title="EU ETS CO2 + Cost Exposure Pack", layout="wide")
st.markdown(
    """
    <style>
    @keyframes gradientShift {
        0% { background-position: 0% 50%, 100% 50%, 50% 100%, 0 0; }
        50% { background-position: 18% 45%, 82% 55%, 50% 85%, 0 0; }
        100% { background-position: 0% 50%, 100% 50%, 50% 100%, 0 0; }
    }
    @keyframes fadeSlideUp {
        0% { opacity: 0; transform: translateY(18px) scale(0.995); filter: blur(2px); }
        100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0px); }
    }
    .stApp {
        background:
            radial-gradient(circle at 12% 18%, rgba(0, 230, 168, 0.18) 0%, rgba(0, 0, 0, 0) 30%),
            radial-gradient(circle at 88% 20%, rgba(181, 55, 242, 0.16) 0%, rgba(0, 0, 0, 0) 28%),
            radial-gradient(circle at 50% 92%, rgba(42, 245, 255, 0.12) 0%, rgba(0, 0, 0, 0) 24%),
            #000000;
        background-size: 120% 120%, 120% 120%, 130% 130%, auto;
        animation: gradientShift 16s ease-in-out infinite;
        color: #EDEDED;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #050505 0%, #000000 100%);
        border-right: 1px solid #1F1F1F;
        box-shadow:
            0 0 18px rgba(0, 255, 170, 0.2),
            0 0 24px rgba(181, 55, 242, 0.14);
    }
    h1, h2, h3 {
        color: #F5F5F5 !important;
        text-shadow:
            0 0 6px rgba(0, 255, 170, 0.28),
            0 0 10px rgba(42, 245, 255, 0.22);
    }
    @keyframes neonPulse {
        0% { box-shadow: 0 0 8px rgba(0, 230, 168, 0.15), 0 0 10px rgba(181, 55, 242, 0.08); }
        50% { box-shadow: 0 0 16px rgba(0, 230, 168, 0.35), 0 0 18px rgba(181, 55, 242, 0.2); }
        100% { box-shadow: 0 0 8px rgba(0, 230, 168, 0.15), 0 0 10px rgba(181, 55, 242, 0.08); }
    }
    .stMetric {
        border: 1px solid #2A2A2A;
        border-radius: 10px;
        background: #0A0A0A;
        box-shadow:
            inset 0 0 10px rgba(0, 255, 170, 0.08),
            0 0 10px rgba(42, 245, 255, 0.12);
        padding: 8px;
        animation: neonPulse 3.6s ease-in-out infinite;
    }
    [data-testid="stVerticalBlock"] > div {
        animation: fadeSlideUp 0.75s cubic-bezier(0.2, 0.7, 0.15, 1) both;
    }
    [data-testid="stVerticalBlock"] > div:nth-child(1) { animation-delay: 0.03s; }
    [data-testid="stVerticalBlock"] > div:nth-child(2) { animation-delay: 0.06s; }
    [data-testid="stVerticalBlock"] > div:nth-child(3) { animation-delay: 0.09s; }
    [data-testid="stVerticalBlock"] > div:nth-child(4) { animation-delay: 0.12s; }
    [data-testid="stVerticalBlock"] > div:nth-child(5) { animation-delay: 0.15s; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        transition: all 280ms ease;
    }
    .stTabs [data-baseweb="tab"] {
        background: #090909;
        border: 1px solid #252525;
        border-radius: 8px;
        color: #EDEDED;
        box-shadow: 0 0 8px rgba(0, 230, 168, 0.08);
        transition:
            transform 220ms cubic-bezier(0.2, 0.8, 0.2, 1),
            box-shadow 240ms ease,
            border-color 240ms ease,
            background-color 240ms ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        transform: translateY(-1px);
        border-color: #2AF5FF;
        box-shadow:
            0 0 14px rgba(42, 245, 255, 0.24),
            0 0 12px rgba(181, 55, 242, 0.16);
    }
    .stTabs [aria-selected="true"] {
        border-color: #00E6A8 !important;
        box-shadow:
            0 0 12px rgba(0, 230, 168, 0.28),
            0 0 10px rgba(181, 55, 242, 0.18) !important;
        color: #FFFFFF !important;
        transform: translateY(-1px);
    }
    .stButton > button, .stDownloadButton > button {
        background: #050505 !important;
        color: #DDFEF4 !important;
        border: 1px solid #00E6A8 !important;
        box-shadow:
            0 0 10px rgba(0, 230, 168, 0.35),
            0 0 14px rgba(181, 55, 242, 0.2);
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translateY(-1px);
        border-color: #2AF5FF !important;
        box-shadow:
            0 0 16px rgba(42, 245, 255, 0.55),
            0 0 18px rgba(181, 55, 242, 0.35);
    }
    .stButton > button, .stDownloadButton > button {
        transition:
            transform 180ms cubic-bezier(0.2, 0.8, 0.2, 1),
            box-shadow 220ms ease,
            border-color 220ms ease;
    }
    .stExpander {
        border: 1px solid #2A2A2A;
        border-radius: 10px;
        box-shadow: 0 0 10px rgba(0, 230, 168, 0.08);
        transition: box-shadow 240ms ease, border-color 240ms ease;
    }
    .stExpander:hover {
        border-color: #2AF5FF;
        box-shadow:
            0 0 14px rgba(42, 245, 255, 0.2),
            0 0 12px rgba(181, 55, 242, 0.14);
    }
    .stAlert {
        border: 1px solid #2A2A2A;
        box-shadow: 0 0 10px rgba(181, 55, 242, 0.12);
    }
    [data-baseweb="input"] input {
        background: #050505 !important;
        border: 1px solid #2A2A2A !important;
        color: #F5F5F5 !important;
        box-shadow: 0 0 8px rgba(0, 230, 168, 0.08);
    }
    [data-baseweb="select"] > div {
        background: #050505 !important;
        border: 1px solid #2A2A2A !important;
        box-shadow: 0 0 8px rgba(42, 245, 255, 0.1);
    }
    .section-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid #00E6A8;
        color: #B8FFF0;
        font-size: 0.75rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        box-shadow: 0 0 10px rgba(0, 230, 168, 0.18);
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("EU ETS CO2 + Cost Exposure Pack")
st.caption(
    "Energy-engineering review view for monthly CO2 exposure, ETS cost scenarios, and management reporting."
)


def _load_from_source(source: Path | bytes):
    if isinstance(source, bytes):
        calc = load_calc_table(BytesIO(source))
        factors = load_factors(BytesIO(source))
        scenarios = load_eua_scenarios(BytesIO(source))
        label = "Uploaded workbook"
    else:
        calc = load_calc_table(source)
        factors = load_factors(source)
        scenarios = load_eua_scenarios(source)
        label = str(source)

    warnings = validate_loaded_data(calc, factors, scenarios)
    scope1_total = compute_scope1_total_tco2(calc, factors)

    summary_scenarios = scenarios.copy()
    summary_scenarios["ETS_cost_EUR"] = (
        summary_scenarios["EUA_EUR_per_tCO2"] * scope1_total
    )
    return label, calc, factors, summary_scenarios, scope1_total, warnings


def _prepare_ets_timeseries(
    calc_df: pd.DataFrame, factors, scenarios: pd.DataFrame
) -> pd.DataFrame:
    ts = calc_df.copy()
    ts["Period_dt"] = pd.to_datetime(ts["Period"], errors="coerce")
    ts = ts.dropna(subset=["Period_dt"]).sort_values("Period_dt").reset_index(drop=True)

    gas_mwh = pd.to_numeric(ts.get("Gas_MWh_in"), errors="coerce")
    if gas_mwh.isna().all():
        gas_mwh = pd.to_numeric(ts.get("Gas_MWh_calc"), errors="coerce")
    if gas_mwh.isna().all():
        gas_nm3 = pd.to_numeric(ts.get("Gas_Nm3"), errors="coerce").fillna(0)
        gas_mwh = gas_nm3 * factors.gas_kwh_per_nm3 / 1000.0

    ts["Gas_MWh_effective"] = gas_mwh.fillna(0)
    ts["OtherFuel_MWh"] = pd.to_numeric(
        ts.get("OtherFuel_MWh"), errors="coerce"
    ).fillna(0)
    ts["Elec_MWh"] = pd.to_numeric(ts.get("Elec_MWh"), errors="coerce").fillna(0)
    ts["Steam_MWh"] = pd.to_numeric(ts.get("Steam_MWh"), errors="coerce").fillna(0)
    ts["Prod_t"] = pd.to_numeric(ts.get("Prod_t"), errors="coerce")

    scope1_loaded = pd.to_numeric(ts.get("Scope1_tCO2"), errors="coerce")
    ts["Scope1_tCO2_calc"] = (
        ts["Gas_MWh_effective"] * factors.gas_ef_tco2_per_mwh
        + ts["OtherFuel_MWh"] * factors.other_fuel_ef_tco2_per_mwh
    )
    ts["Scope1_tCO2_effective"] = np.where(
        scope1_loaded.notna(), scope1_loaded, ts["Scope1_tCO2_calc"]
    )

    scope2_loaded = pd.to_numeric(ts.get("Scope2_tCO2"), errors="coerce")
    ts["Scope2_tCO2_calc"] = ts["Elec_MWh"] * factors.electricity_grid_ef_tco2_per_mwh
    ts["Scope2_tCO2_effective"] = np.where(
        scope2_loaded.notna(), scope2_loaded, ts["Scope2_tCO2_calc"]
    )

    steam_loaded = pd.to_numeric(ts.get("Steam_tCO2"), errors="coerce")
    ts["Steam_tCO2_calc"] = ts["Steam_MWh"] * factors.steam_ef_tco2_per_mwh
    ts["Steam_tCO2_effective"] = np.where(
        steam_loaded.notna(), steam_loaded, ts["Steam_tCO2_calc"]
    )

    ts["Total_tCO2_effective"] = (
        ts["Scope1_tCO2_effective"]
        + ts["Scope2_tCO2_effective"]
        + ts["Steam_tCO2_effective"]
    )

    for _, row in scenarios.iterrows():
        scen = str(row["Scenario"]).strip()
        price = float(row["EUA_EUR_per_tCO2"])
        ts[f"ETS_{scen}_EUR"] = ts["Scope1_tCO2_effective"] * price

    ts["Scope1_tCO2_per_tProd"] = np.where(
        ts["Prod_t"].fillna(0) > 0,
        ts["Scope1_tCO2_effective"] / ts["Prod_t"],
        np.nan,
    )
    ts["Total_tCO2_per_tProd"] = np.where(
        ts["Prod_t"].fillna(0) > 0,
        ts["Total_tCO2_effective"] / ts["Prod_t"],
        np.nan,
    )

    return ts


def _aggregate_timeseries(ts_df: pd.DataFrame, granularity: str) -> pd.DataFrame:
    if granularity == "Monthly":
        out = ts_df.copy()
        out["Period_plot"] = out["Period_dt"]
        return out

    agg_map = {
        "Scope1_tCO2_effective": "sum",
        "Scope2_tCO2_effective": "sum",
        "Steam_tCO2_effective": "sum",
        "Total_tCO2_effective": "sum",
        "Prod_t": "sum",
    }
    cost_cols = [
        c for c in ts_df.columns if c.startswith("ETS_") and c.endswith("_EUR")
    ]
    for col in cost_cols:
        agg_map[col] = "sum"

    grouped = (
        ts_df.set_index("Period_dt")
        .resample("Q")
        .agg(agg_map)
        .reset_index()
        .rename(columns={"Period_dt": "Period_plot"})
    )
    grouped["Scope1_tCO2_per_tProd"] = np.where(
        grouped["Prod_t"].fillna(0) > 0,
        grouped["Scope1_tCO2_effective"] / grouped["Prod_t"],
        np.nan,
    )
    grouped["Total_tCO2_per_tProd"] = np.where(
        grouped["Prod_t"].fillna(0) > 0,
        grouped["Total_tCO2_effective"] / grouped["Prod_t"],
        np.nan,
    )
    return grouped


def _style_axis(ax, title: str, y_label: str, x_label: str = "Period") -> None:
    ax.set_facecolor(PLOT_PANEL)
    ax.set_title(title, fontsize=12, pad=12)
    ax.set_ylabel(y_label, fontsize=10)
    ax.set_xlabel(x_label, fontsize=10)
    ax.grid(color=PLOT_GRID, alpha=0.55)
    ax.tick_params(axis="x", labelsize=8, colors=PLOT_TEXT)
    ax.tick_params(axis="y", labelsize=9, colors=PLOT_TEXT)
    ax.title.set_color(PLOT_TEXT)
    ax.xaxis.label.set_color(PLOT_TEXT)
    ax.yaxis.label.set_color(PLOT_TEXT)
    for spine in ax.spines.values():
        spine.set_color(PLOT_GRID)


def _style_legend(legend) -> None:
    if legend is None:
        return
    legend.get_frame().set_facecolor(PLOT_PANEL)
    legend.get_frame().set_edgecolor(PLOT_GRID)
    for text in legend.get_texts():
        text.set_color(PLOT_TEXT)


def _set_sparse_ticks(ax, x_vals, step: int = 3) -> None:
    if len(x_vals) == 0:
        return
    idx = list(range(0, len(x_vals), max(step, 1)))
    ax.set_xticks([x_vals[i] for i in idx])


def _plot_scenario_bar(scenario_df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 3.2))
    fig.patch.set_facecolor(PLOT_BG)
    ax.bar(
        scenario_df["Scenario"],
        scenario_df["ETS_cost_EUR"],
        color=COST_COLOR,
        alpha=0.85,
    )
    _style_axis(ax, "Annualized ETS Cost by Scenario", "EUR", "Scenario")
    return fig


def _plot_emissions(
    ts_plot: pd.DataFrame, include_scope2_steam: bool, tick_step: int = 3
):
    fig, ax = plt.subplots(figsize=(11, 3.8))
    fig.patch.set_facecolor(PLOT_BG)
    x = ts_plot["Period_plot"].tolist()
    if include_scope2_steam:
        ax.stackplot(
            x,
            ts_plot["Scope1_tCO2_effective"],
            ts_plot["Scope2_tCO2_effective"],
            ts_plot["Steam_tCO2_effective"],
            labels=["Scope 1", "Scope 2", "Steam"],
            colors=[SCOPE1_COLOR, SCOPE2_COLOR, STEAM_COLOR],
            alpha=0.8,
        )
    else:
        ax.plot(
            x,
            ts_plot["Scope1_tCO2_effective"],
            color=SCOPE1_COLOR,
            linewidth=2.2,
            label="Scope 1",
        )
    _set_sparse_ticks(ax, x, tick_step)
    _style_axis(ax, "Emissions Breakdown Over Time", "tCO2")
    legend = ax.legend(loc="upper left", fontsize=9)
    _style_legend(legend)
    return fig


def _plot_costs(ts_plot: pd.DataFrame, tick_step: int = 3):
    fig, ax = plt.subplots(figsize=(11, 3.8))
    fig.patch.set_facecolor(PLOT_BG)
    x = ts_plot["Period_plot"].tolist()
    cost_cols = [
        c for c in ts_plot.columns if c.startswith("ETS_") and c.endswith("_EUR")
    ]
    palette = ["#2E86AB", "#7E57C2", "#A3BE8C", "#D08770"]
    for i, col in enumerate(cost_cols):
        label = col.replace("ETS_", "").replace("_EUR", "")
        ax.plot(
            x, ts_plot[col], linewidth=2.0, label=label, color=palette[i % len(palette)]
        )
    _set_sparse_ticks(ax, x, tick_step)
    _style_axis(ax, "ETS Cost Over Time by Scenario", "EUR")
    legend = ax.legend(fontsize=9)
    _style_legend(legend)
    return fig


def _plot_intensity(ts_plot: pd.DataFrame, tick_step: int = 3):
    fig, ax = plt.subplots(figsize=(11, 3.8))
    fig.patch.set_facecolor(PLOT_BG)
    x = ts_plot["Period_plot"].tolist()
    ax.plot(
        x,
        ts_plot["Scope1_tCO2_per_tProd"],
        label="Scope 1 intensity",
        color=SCOPE1_COLOR,
        linewidth=2.0,
    )
    ax.plot(
        x,
        ts_plot["Total_tCO2_per_tProd"],
        label="Total intensity",
        color=TOTAL_COLOR,
        linewidth=2.0,
    )
    _set_sparse_ticks(ax, x, tick_step)
    _style_axis(ax, "Carbon Intensity Trends", "tCO2 / t product")
    legend = ax.legend(fontsize=9)
    _style_legend(legend)
    return fig


def _plot_sensitivity(sens_df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(9, 3.6))
    fig.patch.set_facecolor(PLOT_BG)
    ax.plot(
        sens_df["EUA_EUR_per_tCO2"],
        sens_df["Annual_ETS_cost_EUR"],
        color=COST_COLOR,
        linewidth=2.2,
    )
    _style_axis(ax, "EUA Sensitivity Curve", "Annual ETS Cost EUR", "EUA EUR/tCO2")
    return fig


def _pick_scenario_price(scenario_df: pd.DataFrame, key: str, fallback: float) -> float:
    lower = key.lower()
    names = scenario_df["Scenario"].astype(str).str.lower()
    match = scenario_df.loc[names.str.contains(lower), "EUA_EUR_per_tCO2"]
    if not match.empty:
        return float(match.iloc[0])
    return float(fallback)


def _build_scenario_frame(scope1_total: float, base: float, stress: float, high: float):
    frame = pd.DataFrame(
        {
            "Case": ["Base", "Stress", "High-price"],
            "EUA_EUR_per_tCO2": [base, stress, high],
        }
    )
    frame["ETS_cost_EUR"] = frame["EUA_EUR_per_tCO2"] * scope1_total
    base_cost = float(frame.loc[frame["Case"] == "Base", "ETS_cost_EUR"].iloc[0])
    frame["Delta_vs_Base_EUR"] = frame["ETS_cost_EUR"] - base_cost
    return frame


def _build_period_comparison(ts_monthly: pd.DataFrame, selected_price: float):
    monthly = ts_monthly.copy()
    if monthly.empty:
        return {}
    monthly = monthly.sort_values("Period_dt").reset_index(drop=True)
    monthly["Selected_ETS_EUR"] = monthly["Scope1_tCO2_effective"] * float(
        selected_price
    )
    latest = monthly.iloc[-1]
    prev = monthly.iloc[-2] if len(monthly) >= 2 else None

    result = {
        "latest_period": latest["Period_dt"],
        "latest_scope1": float(latest["Scope1_tCO2_effective"]),
        "latest_cost": float(latest["Selected_ETS_EUR"]),
    }
    if prev is not None:
        result["mom_scope1_delta"] = float(
            latest["Scope1_tCO2_effective"] - prev["Scope1_tCO2_effective"]
        )
        result["mom_cost_delta"] = float(
            latest["Selected_ETS_EUR"] - prev["Selected_ETS_EUR"]
        )

    latest_year = int(latest["Period_dt"].year)
    latest_month = int(latest["Period_dt"].month)
    ytd_curr = monthly[
        (monthly["Period_dt"].dt.year == latest_year)
        & (monthly["Period_dt"].dt.month <= latest_month)
    ]
    ytd_prev = monthly[
        (monthly["Period_dt"].dt.year == latest_year - 1)
        & (monthly["Period_dt"].dt.month <= latest_month)
    ]
    if not ytd_curr.empty and not ytd_prev.empty:
        result["ytd_scope1_delta"] = float(
            ytd_curr["Scope1_tCO2_effective"].sum()
            - ytd_prev["Scope1_tCO2_effective"].sum()
        )
        result["ytd_cost_delta"] = float(
            ytd_curr["Selected_ETS_EUR"].sum() - ytd_prev["Selected_ETS_EUR"].sum()
        )
    return result


def _build_top_levers(ts_monthly: pd.DataFrame):
    df = ts_monthly.copy()
    gas_total = float(df["Gas_MWh_effective"].sum()) if not df.empty else 0.0
    other_total = float(df["OtherFuel_MWh"].sum()) if not df.empty else 0.0
    fuel_total = gas_total + other_total
    gas_share = 0.0 if fuel_total <= 0 else gas_total / fuel_total
    avg_intensity = (
        float(df["Scope1_tCO2_per_tProd"].dropna().mean()) if not df.empty else np.nan
    )
    intensity_vol = (
        float(df["Scope1_tCO2_per_tProd"].dropna().std()) if not df.empty else np.nan
    )

    levers = [
        {
            "Lever": "Combustion efficiency and burner tuning",
            "Why_it_matters": "Scope 1 emissions are dominated by fuel use; efficiency gains reduce allowance demand directly.",
            "Indicative_priority": "High" if gas_share >= 0.6 else "Medium",
            "Tracking_metric": "Gas_MWh_effective / t product",
        },
        {
            "Lever": "Production planning and load smoothing",
            "Why_it_matters": "Large month-to-month intensity swings often indicate operational instability.",
            "Indicative_priority": (
                "High" if pd.notna(intensity_vol) and intensity_vol > 0.03 else "Medium"
            ),
            "Tracking_metric": "Scope1_tCO2_per_tProd",
        },
        {
            "Lever": "EUA procurement and hedge timing",
            "Why_it_matters": "Exposure rises linearly with EUA price; planning window reduces budget shock risk.",
            "Indicative_priority": "High",
            "Tracking_metric": "EUR impact per +10 EUR/tCO2",
        },
    ]
    if pd.notna(avg_intensity):
        levers[1]["Current_intensity_avg"] = round(avg_intensity, 4)
    return pd.DataFrame(levers)


def _build_watchlist(ts_monthly: pd.DataFrame, selected_price: float):
    df = ts_monthly.copy()
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Period",
                "Flag",
                "Scope1_tCO2",
                "Selected_ETS_EUR",
                "Likely_driver_hint",
                "Suggested_action",
            ]
        )

    df["Selected_ETS_EUR"] = df["Scope1_tCO2_effective"] * float(selected_price)
    q_scope1 = df["Scope1_tCO2_effective"].quantile(0.9)
    q_cost = df["Selected_ETS_EUR"].quantile(0.9)
    q_intensity = df["Scope1_tCO2_per_tProd"].quantile(0.9)

    rows = []
    for _, row in df.iterrows():
        flags = []
        if row["Scope1_tCO2_effective"] >= q_scope1:
            flags.append("HIGH_SCOPE1")
        if row["Selected_ETS_EUR"] >= q_cost:
            flags.append("COST_SPIKE")
        if (
            pd.notna(row["Scope1_tCO2_per_tProd"])
            and row["Scope1_tCO2_per_tProd"] >= q_intensity
        ):
            flags.append("HIGH_INTENSITY")
        if not flags:
            continue

        hint = "Check gas demand, burner efficiency, and production mix."
        action = "Review operational logbook and maintenance records for this period."
        rows.append(
            {
                "Period": pd.to_datetime(row["Period_dt"]).strftime("%Y-%m"),
                "Flag": ";".join(flags),
                "Scope1_tCO2": float(row["Scope1_tCO2_effective"]),
                "Selected_ETS_EUR": float(row["Selected_ETS_EUR"]),
                "Likely_driver_hint": hint,
                "Suggested_action": action,
            }
        )
    return pd.DataFrame(rows).sort_values("Selected_ETS_EUR", ascending=False).head(10)


def _risk_label(selected_price: float, selected_cost: float) -> tuple[str, str]:
    if selected_price >= 130 or selected_cost >= 7_000_000:
        return "High", "#FF5F57"
    if selected_price >= 90 or selected_cost >= 4_000_000:
        return "Medium", "#F5A623"
    return "Low", "#2ECC71"


def _risk_narrative(
    selected_price: float,
    delta_plus_10: float,
    mom_cost_delta: float | None,
    ytd_cost_delta: float | None,
) -> str:
    parts = [
        f"At {selected_price:,.0f} EUR/tCO2, ETS exposure responds linearly; each +10 EUR/tCO2 adds about EUR {delta_plus_10:,.0f}.",
    ]
    if mom_cost_delta is not None:
        direction = "up" if mom_cost_delta >= 0 else "down"
        parts.append(
            f"Month-over-month ETS exposure is {direction} by EUR {abs(mom_cost_delta):,.0f}."
        )
    if ytd_cost_delta is not None:
        direction = "above" if ytd_cost_delta >= 0 else "below"
        parts.append(
            f"YTD exposure is {direction} prior year by EUR {abs(ytd_cost_delta):,.0f}."
        )
    return " ".join(parts)


def _build_pdf_report(
    workbook_label: str,
    scope1_total: float,
    scenario_df: pd.DataFrame,
    ts_plot: pd.DataFrame,
    selected_scenario_label: str,
    selected_price: float,
    granularity: str,
    include_scope2_steam: bool,
    sensitivity_df: pd.DataFrame,
    tick_step: int,
    report_user_name: str,
) -> bytes:
    generated_utc = datetime.now(timezone.utc)
    generated_label = generated_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    report_owner = report_user_name.strip() if report_user_name.strip() else "Analyst"

    bg_dark = colors.HexColor("#000000")
    panel_dark = colors.HexColor("#0B0B0B")
    accent = colors.HexColor("#8A8A8A")
    text_light = colors.HexColor("#E6EDF3")
    muted_text = colors.HexColor("#9FB3C8")

    def _fig_to_reader(fig) -> ImageReader:
        img_buf = BytesIO()
        fig.savefig(img_buf, format="png", dpi=180, bbox_inches="tight")
        plt.close(fig)
        img_buf.seek(0)
        return ImageReader(img_buf)

    def _paint_page_background(pdf_canvas: canvas.Canvas) -> None:
        pdf_canvas.saveState()
        pdf_canvas.setFillColor(bg_dark)
        pdf_canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        pdf_canvas.setFillColor(panel_dark)
        pdf_canvas.rect(24, 24, A4[0] - 48, A4[1] - 48, fill=1, stroke=0)
        pdf_canvas.setStrokeColor(accent)
        pdf_canvas.setLineWidth(2)
        pdf_canvas.line(28, A4[1] - 54, A4[0] - 28, A4[1] - 54)
        pdf_canvas.restoreState()

    def _draw_footer(pdf_canvas: canvas.Canvas) -> None:
        pdf_canvas.saveState()
        pdf_canvas.setFillColor(muted_text)
        pdf_canvas.setFont("Helvetica", 8.5)
        pdf_canvas.drawString(32, 14, f"Prepared by: {report_owner}")
        pdf_canvas.drawRightString(A4[0] - 32, 14, generated_label)
        pdf_canvas.restoreState()

    def _new_page(pdf_canvas: canvas.Canvas) -> float:
        pdf_canvas.showPage()
        _paint_page_background(pdf_canvas)
        _draw_footer(pdf_canvas)
        return A4[1] - 70

    def _draw_plot(
        pdf_canvas: canvas.Canvas,
        img: ImageReader,
        title: str,
        caption: str,
        y_pos: float,
    ) -> float:
        pdf_canvas.setFillColor(text_light)
        pdf_canvas.setFont("Helvetica-Bold", 11)
        pdf_canvas.drawString(40, y_pos, title)
        y_next = y_pos - 12 - 210
        pdf_canvas.drawImage(
            img,
            40,
            y_next,
            width=515,
            height=210,
            preserveAspectRatio=True,
            anchor="sw",
        )
        pdf_canvas.setFillColor(muted_text)
        pdf_canvas.setFont("Helvetica-Oblique", 9)
        pdf_canvas.drawString(40, y_next - 12, caption)
        return y_next - 26

    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    _, height = A4
    _paint_page_background(pdf)
    _draw_footer(pdf)

    # Cover summary page
    y = height - 70
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, y, f"Prepared by: {report_owner}")
    y -= 20
    pdf.setFillColor(text_light)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, y, "EU ETS Management Report: CO2 + Cost Exposure")
    y -= 22
    pdf.setFillColor(muted_text)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, f"Generated (UTC): {generated_label}")
    y -= 14
    pdf.setFillColor(text_light)
    pdf.drawString(40, y, f"Workbook: {workbook_label}")
    y -= 14
    pdf.drawString(40, y, f"Scope 1 total (tCO2): {scope1_total:,.2f}")
    y -= 14
    pdf.drawString(
        40,
        y,
        f"Selected planning scenario: {selected_scenario_label} @ {selected_price:.2f} EUR/tCO2",
    )
    y -= 14
    pdf.drawString(
        40,
        y,
        f"View granularity: {granularity}; Include Scope2/Steam: {include_scope2_steam}",
    )
    y -= 14
    pdf.drawString(40, y, f"X-axis label step: every {tick_step} point(s)")

    y -= 24
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, y, "Scenario exposure summary")
    y -= 14
    pdf.setFillColor(text_light)
    pdf.setFont("Helvetica", 10)
    for _, row in scenario_df.iterrows():
        pdf.drawString(
            40,
            y,
            f"{row['Scenario']}: EUA {row['EUA_EUR_per_tCO2']:.2f} EUR/tCO2, ETS cost {row['ETS_cost_EUR']:,.0f} EUR",
        )
        y -= 12

    y -= 8
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, y, "Top periods by Scope 1 emissions")
    y -= 14
    pdf.setFillColor(text_light)
    pdf.setFont("Helvetica", 10)
    top = ts_plot.nlargest(6, "Scope1_tCO2_effective")[
        ["Period_plot", "Scope1_tCO2_effective"]
    ]
    for _, row in top.iterrows():
        p = pd.to_datetime(row["Period_plot"]).strftime("%Y-%m")
        pdf.drawString(40, y, f"{p}: {row['Scope1_tCO2_effective']:,.2f} tCO2")
        y -= 12

    # Section 1
    y = _new_page(pdf)
    pdf.setFillColor(text_light)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(40, y, "Section 1: Cost Overview")
    y -= 20
    y = _draw_plot(
        pdf,
        _fig_to_reader(_plot_scenario_bar(scenario_df)),
        "Plot 1: Annualized ETS Cost by Scenario",
        "Interpretation: Compare downside and stress exposure across EUA scenario levels.",
        y,
    )
    y = _draw_plot(
        pdf,
        _fig_to_reader(_plot_costs(ts_plot, tick_step=tick_step)),
        "Plot 2: ETS Cost Over Time by Scenario",
        "Interpretation: Shows period-to-period cost exposure volatility for each scenario.",
        y,
    )

    # Section 2
    y = _new_page(pdf)
    pdf.setFillColor(text_light)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(40, y, "Section 2: Emissions and Intensity")
    y -= 20
    y = _draw_plot(
        pdf,
        _fig_to_reader(
            _plot_emissions(
                ts_plot,
                include_scope2_steam=include_scope2_steam,
                tick_step=tick_step,
            )
        ),
        "Plot 3: Emissions Breakdown Over Time",
        "Interpretation: Tracks Scope 1 contribution and optional Scope 2/steam context.",
        y,
    )
    y = _draw_plot(
        pdf,
        _fig_to_reader(_plot_intensity(ts_plot, tick_step=tick_step)),
        "Plot 4: Carbon Intensity Trends",
        "Interpretation: Lower intensity signals improved emissions performance per output.",
        y,
    )

    # Section 3
    y = _new_page(pdf)
    pdf.setFillColor(text_light)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(40, y, "Section 3: EUA Sensitivity")
    y -= 20
    _draw_plot(
        pdf,
        _fig_to_reader(_plot_sensitivity(sensitivity_df)),
        "Plot 5: EUA Sensitivity Curve",
        "Interpretation: Slope gives annual ETS cost impact per 1 EUR/tCO2 change.",
        y,
    )

    pdf.save()
    return buf.getvalue()


with st.sidebar:
    st.header("Workspace")
    app_mode = st.selectbox(
        "Mode",
        ["Single Site Review", "Portfolio Planner"],
        index=0,
    )
    st.markdown("---")
    st.header("Site Workbook")
    report_user_name = st.text_input(
        "Report user name",
        value="Energy Analyst",
        help="Name shown prominently in the management report.",
    )
    if app_mode == "Single Site Review":
        source_mode = st.radio(
            "Select source", ["Upload workbook", "Use local demo workbook"], index=1
        )
        uploaded = st.file_uploader("Upload .xlsx", type=["xlsx"])
        portfolio_uploads = []
    else:
        source_mode = "Portfolio"
        uploaded = None
        portfolio_uploads = st.file_uploader(
            "Upload portfolio workbooks (.xlsx)",
            type=["xlsx"],
            accept_multiple_files=True,
        )
        use_demo_portfolio = st.checkbox("Include demo workbook as a site", value=True)
        st.subheader("Portfolio Guardrails")
        budget_amber = st.number_input(
            "Amber threshold per site (EUR)",
            min_value=0.0,
            value=4_000_000.0,
            step=100_000.0,
        )
        budget_red = st.number_input(
            "Red threshold per site (EUR)",
            min_value=0.0,
            value=6_000_000.0,
            step=100_000.0,
        )
        portfolio_base_price = st.number_input(
            "Portfolio base EUA (EUR/tCO2)",
            min_value=0.0,
            value=85.0,
            step=1.0,
        )
        portfolio_stress_price = st.number_input(
            "Portfolio stress EUA (EUR/tCO2)",
            min_value=0.0,
            value=110.0,
            step=1.0,
        )
        portfolio_high_price = st.number_input(
            "Portfolio high EUA (EUR/tCO2)",
            min_value=0.0,
            value=140.0,
            step=1.0,
        )
        portfolio_price = st.number_input(
            "Central planning EUA (active curve, EUR/tCO2)",
            min_value=0.0,
            value=95.0,
            step=1.0,
        )
        compare_metric = st.selectbox(
            "Compare site curves by",
            ["Scope1_tCO2_effective", "Selected_ETS_EUR", "Scope1_tCO2_per_tProd"],
            index=1,
        )

source: Path | bytes | None = None
if app_mode == "Single Site Review" and source_mode == "Upload workbook":
    if uploaded is not None:
        source = uploaded.getvalue()
    else:
        st.info("Upload an .xlsx workbook to continue.")
elif app_mode == "Single Site Review":
    demo_path = Path("EU_ETS_Exposure_Calculator_Demo.xlsx")
    if demo_path.exists():
        source = demo_path
    else:
        st.error("Local demo workbook not found: EU_ETS_Exposure_Calculator_Demo.xlsx")

if app_mode == "Single Site Review" and source is not None:
    try:
        workbook_label, calc_df, factors, scenario_df, scope1_total, warnings = (
            _load_from_source(source)
        )
    except WorkbookValidationError as exc:
        st.error(str(exc))
        st.stop()
    except Exception as exc:  # pragma: no cover
        st.exception(exc)
        st.stop()

    if warnings:
        with st.expander("Validation warnings", expanded=True):
            for w in warnings:
                st.warning(w)

    ts_df = _prepare_ets_timeseries(
        calc_df, factors, scenario_df[["Scenario", "EUA_EUR_per_tCO2"]]
    )

    # Controls for readability and ETS-specific exploration.
    with st.sidebar:
        st.header("Review Controls")
        granularity = st.selectbox("Granularity", ["Monthly", "Quarterly"], index=0)
        include_scope2_steam = st.checkbox(
            "Include Scope 2 and Steam in emissions plot", value=True
        )

        min_date = ts_df["Period_dt"].min().date()
        max_date = ts_df["Period_dt"].max().date()
        default_start = (ts_df["Period_dt"].max() - pd.DateOffset(months=17)).date()
        default_start = max(min_date, default_start)
        date_range = st.date_input(
            "Date range",
            value=(default_start, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        scenario_names = scenario_df["Scenario"].astype(str).tolist()
        selected_scenario = st.selectbox(
            "Primary scenario",
            [*scenario_names, "Custom"],
            index=min(1, len(scenario_names) - 1) if scenario_names else 0,
        )
        custom_price = 85.0
        if selected_scenario == "Custom":
            custom_price = st.number_input(
                "Custom EUA price (EUR/tCO2)", min_value=0.0, value=85.0, step=1.0
            )

        st.markdown("---")
        st.subheader("Planning Cases")
        base_price = st.number_input(
            "Base case EUA (EUR/tCO2)",
            min_value=0.0,
            value=_pick_scenario_price(scenario_df, "mid", 85.0),
            step=1.0,
        )
        stress_price = st.number_input(
            "Stress case EUA (EUR/tCO2)",
            min_value=0.0,
            value=_pick_scenario_price(scenario_df, "high", 120.0),
            step=1.0,
        )
        high_price = st.number_input(
            "High-price case EUA (EUR/tCO2)",
            min_value=0.0,
            value=max(_pick_scenario_price(scenario_df, "high", 120.0) + 20, 140.0),
            step=1.0,
        )

        st.markdown("---")
        st.subheader("Plot Settings")
        tick_step = st.slider(
            "X-axis label density (every Nth point)",
            min_value=1,
            max_value=6,
            value=3,
            step=1,
        )
        sensitivity_min = st.number_input(
            "Sensitivity min EUA (EUR/tCO2)",
            min_value=0.0,
            value=30.0,
            step=5.0,
        )
        sensitivity_max = st.number_input(
            "Sensitivity max EUA (EUR/tCO2)",
            min_value=0.0,
            value=180.0,
            step=5.0,
        )
        sensitivity_points = st.slider(
            "Sensitivity grid points",
            min_value=6,
            max_value=60,
            value=24,
            step=1,
        )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    ts_filtered = ts_df[
        (ts_df["Period_dt"].dt.date >= start_date)
        & (ts_df["Period_dt"].dt.date <= end_date)
    ].copy()
    ts_plot = _aggregate_timeseries(ts_filtered, granularity)

    selected_price = float(custom_price)
    if selected_scenario != "Custom":
        selected_price = float(
            scenario_df.loc[
                scenario_df["Scenario"].astype(str) == selected_scenario,
                "EUA_EUR_per_tCO2",
            ].iloc[0]
        )

    scenario_display = scenario_df.copy()
    if selected_scenario == "Custom":
        scenario_display = pd.concat(
            [
                scenario_display,
                pd.DataFrame(
                    {
                        "Scenario": ["Custom"],
                        "EUA_EUR_per_tCO2": [selected_price],
                        "ETS_cost_EUR": [selected_price * scope1_total],
                    }
                ),
            ],
            ignore_index=True,
        )

    selected_period_cost = (
        float(ts_plot["Scope1_tCO2_effective"].sum()) * selected_price
    )
    delta_plus_10 = float(ts_plot["Scope1_tCO2_effective"].sum()) * 10.0
    risk_level, risk_color = _risk_label(selected_price, selected_period_cost)

    st.markdown("<span class='section-pill'>Phase 1</span>", unsafe_allow_html=True)
    st.markdown("### 1) Inputs Check")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Data Source", workbook_label)
    c2.metric(
        "Scope 1 CO2 (tCO2)", f"{float(ts_plot['Scope1_tCO2_effective'].sum()):,.2f}"
    )
    c3.metric(
        "Primary scenario", f"{selected_scenario} ({selected_price:,.0f} EUR/tCO2)"
    )
    c4.metric("Selected Period ETS Cost", f"EUR {selected_period_cost:,.0f}")
    st.markdown(
        f"<div style='border:1px solid {risk_color}; border-radius:10px; padding:8px 12px; "
        f"background:#0A0A0A; color:#EDEDED; width:fit-content;'>Exposure risk: "
        f"<b style='color:{risk_color}'>{risk_level}</b></div>",
        unsafe_allow_html=True,
    )

    completeness = (
        100.0
        * (
            1.0
            - (
                calc_df[["Elec_MWh", "Gas_Nm3"]].isna().any(axis=1).sum()
                / max(len(calc_df), 1)
            )
        )
        if {"Elec_MWh", "Gas_Nm3"}.issubset(calc_df.columns)
        else np.nan
    )
    st.caption(
        f"Data completeness check (core activity fields): {completeness:.1f}%"
        if pd.notna(completeness)
        else "Data completeness check unavailable for this workbook layout."
    )

    st.markdown("<span class='section-pill'>Phase 2</span>", unsafe_allow_html=True)
    st.markdown("### 2) Exposure Summary")
    scenario_frame = _build_scenario_frame(
        scope1_total=float(ts_plot["Scope1_tCO2_effective"].sum()),
        base=float(base_price),
        stress=float(stress_price),
        high=float(high_price),
    )
    st.dataframe(scenario_frame, width="stretch")

    st.subheader("Scenario Exposure Summary")
    st.dataframe(scenario_display, width="stretch")
    fig_summary = _plot_scenario_bar(scenario_display)
    st.pyplot(fig_summary, width="stretch")
    plt.close(fig_summary)

    csv_bytes = scenario_display.to_csv(index=False).encode("utf-8")

    p_min = float(sensitivity_min)
    p_max = float(sensitivity_max)
    if p_max <= p_min:
        p_max = p_min + 1.0
        st.warning("Sensitivity max EUA must be higher than min. Max adjusted by +1.")
    price_grid = np.linspace(p_min, p_max, int(sensitivity_points))
    sensitivity_df = pd.DataFrame(
        {
            "EUA_EUR_per_tCO2": price_grid,
            "Annual_ETS_cost_EUR": price_grid
            * float(ts_plot["Scope1_tCO2_effective"].sum()),
        }
    )

    comparison = _build_period_comparison(ts_filtered, selected_price=selected_price)
    st.markdown("<span class='section-pill'>Phase 3</span>", unsafe_allow_html=True)
    st.markdown("### 3) Drivers and Causes")
    p1, p2, p3, p4 = st.columns(4)
    if comparison:
        p1.metric(
            "Latest period",
            pd.to_datetime(comparison["latest_period"]).strftime("%Y-%m"),
        )
        p2.metric("Latest Scope 1 (tCO2)", f"{comparison['latest_scope1']:,.1f}")
        p3.metric(
            "MoM Scope 1 delta",
            f"{comparison.get('mom_scope1_delta', 0.0):+,.1f}",
        )
        p4.metric(
            "MoM ETS delta (selected case)",
            f"EUR {comparison.get('mom_cost_delta', 0.0):+,.0f}",
        )

        if "ytd_scope1_delta" in comparison and "ytd_cost_delta" in comparison:
            y1, y2 = st.columns(2)
            y1.metric(
                "YTD vs prior YTD Scope 1",
                f"{comparison['ytd_scope1_delta']:+,.1f} tCO2",
            )
            y2.metric(
                "YTD vs prior YTD ETS cost",
                f"EUR {comparison['ytd_cost_delta']:+,.0f}",
            )

    st.info(
        _risk_narrative(
            selected_price=selected_price,
            delta_plus_10=delta_plus_10,
            mom_cost_delta=comparison.get("mom_cost_delta") if comparison else None,
            ytd_cost_delta=comparison.get("ytd_cost_delta") if comparison else None,
        )
    )

    pdf_bytes = _build_pdf_report(
        workbook_label=workbook_label,
        scope1_total=float(ts_plot["Scope1_tCO2_effective"].sum()),
        scenario_df=scenario_display,
        ts_plot=ts_plot,
        selected_scenario_label=selected_scenario,
        selected_price=selected_price,
        granularity=granularity,
        include_scope2_steam=include_scope2_steam,
        sensitivity_df=sensitivity_df,
        tick_step=tick_step,
        report_user_name=report_user_name,
    )

    d1, d2 = st.columns(2)
    d1.download_button(
        label="Download Scenario Summary CSV",
        data=csv_bytes,
        file_name="ets_scenario_summary.csv",
        mime="text/csv",
    )
    d2.download_button(
        label="Download Management Report (PDF)",
        data=pdf_bytes,
        file_name="ets_analysis_report.pdf",
        mime="application/pdf",
    )

    tab_costs, tab_emissions, tab_intensity, tab_sensitivity = st.tabs(
        ["Costs", "Emissions", "Intensity", "Sensitivity"]
    )

    with tab_costs:
        st.markdown("ETS cost exposure trends by scenario")
        fig_cost = _plot_costs(ts_plot, tick_step=tick_step)
        st.pyplot(fig_cost, width="stretch")
        plt.close(fig_cost)

    with tab_emissions:
        st.markdown("CO2 profile (toggle Scope2/Steam context in sidebar)")
        fig_em = _plot_emissions(
            ts_plot, include_scope2_steam=include_scope2_steam, tick_step=tick_step
        )
        st.pyplot(fig_em, width="stretch")
        plt.close(fig_em)

    with tab_intensity:
        st.markdown("Carbon intensity per production output")
        fig_int = _plot_intensity(ts_plot, tick_step=tick_step)
        st.pyplot(fig_int, width="stretch")
        plt.close(fig_int)

    with tab_sensitivity:
        s1, s2 = st.columns([3, 1])
        with s2:
            st.metric(
                "Cost delta for +10 EUR/tCO2",
                f"EUR {delta_plus_10:,.0f}",
            )
            shock = st.slider(
                "Live EUA shock (+/- EUR/tCO2)",
                min_value=-60,
                max_value=60,
                value=0,
                step=5,
            )
            shocked_price = max(0.0, selected_price + float(shock))
            shocked_cost = float(ts_plot["Scope1_tCO2_effective"].sum()) * shocked_price
            st.metric(
                "Shocked ETS cost",
                f"EUR {shocked_cost:,.0f}",
                delta=f"EUR {shocked_cost - selected_period_cost:+,.0f}",
            )
        with s1:
            fig_sens = _plot_sensitivity(sensitivity_df)
            st.pyplot(fig_sens, width="stretch")
            plt.close(fig_sens)

        pulse = min(100, max(0, int((selected_price / max(high_price, 1.0)) * 100)))
        st.progress(pulse, text=f"Exposure pulse vs high-price case: {pulse}%")

    st.markdown("<span class='section-pill'>Phase 4</span>", unsafe_allow_html=True)
    st.markdown("### 4) Actions")
    levers_df = _build_top_levers(ts_filtered)
    watchlist_df = _build_watchlist(ts_filtered, selected_price=selected_price)
    a1, a2 = st.columns(2)
    with a1:
        st.markdown("Top 3 Levers")
        st.dataframe(levers_df, width="stretch")
    with a2:
        st.markdown("Watchlist Periods")
        if watchlist_df.empty:
            st.info("No watchlist flags detected for current range and scenario.")
        else:
            st.dataframe(watchlist_df, width="stretch")

    st.markdown("<span class='section-pill'>Phase 5</span>", unsafe_allow_html=True)
    st.markdown("### 5) Report Export")

    with st.expander("Detailed Exposure Time Series"):
        detail_cols = [
            "Period_plot",
            "Scope1_tCO2_effective",
            "Scope2_tCO2_effective",
            "Steam_tCO2_effective",
            "Total_tCO2_effective",
            "Scope1_tCO2_per_tProd",
            "Total_tCO2_per_tProd",
        ] + [c for c in ts_plot.columns if c.startswith("ETS_") and c.endswith("_EUR")]
        st.dataframe(ts_plot[detail_cols], width="stretch")

    with st.expander("Input Workbook Preview (Calc sheet)"):
        st.dataframe(calc_df, width="stretch")

    with st.expander("Factor Values"):
        st.json(
            {
                "gas_ef_tco2_per_mwh": factors.gas_ef_tco2_per_mwh,
                "other_fuel_ef_tco2_per_mwh": factors.other_fuel_ef_tco2_per_mwh,
                "steam_ef_tco2_per_mwh": factors.steam_ef_tco2_per_mwh,
                "electricity_grid_ef_tco2_per_mwh": factors.electricity_grid_ef_tco2_per_mwh,
                "gas_kwh_per_nm3": factors.gas_kwh_per_nm3,
                "report_generated_utc": datetime.now(timezone.utc).isoformat(),
            }
        )

elif app_mode == "Portfolio Planner":
    site_inputs: list[tuple[str, Path | bytes]] = []
    demo_path = Path("EU_ETS_Exposure_Calculator_Demo.xlsx")
    if use_demo_portfolio and demo_path.exists():
        site_inputs.append(("Demo_Site", demo_path))
    for f in portfolio_uploads:
        site_inputs.append((Path(f.name).stem, f.getvalue()))

    if not site_inputs:
        st.info("Upload one or more workbooks in Portfolio Planner mode.")
    else:
        site_rows: list[dict] = []
        portfolio_ts: list[pd.DataFrame] = []
        warnings_map: dict[str, list[str]] = {}
        errors: list[str] = []

        for site_name, src in site_inputs:
            try:
                _, calc_df_i, factors_i, scen_df_i, scope1_i, warnings_i = (
                    _load_from_source(src)
                )
                ts_i = _prepare_ets_timeseries(
                    calc_df_i, factors_i, scen_df_i[["Scenario", "EUA_EUR_per_tCO2"]]
                )
                ts_i = _aggregate_timeseries(ts_i, "Monthly")
                ts_i["Site"] = site_name
                ts_i["Selected_ETS_EUR"] = ts_i["Scope1_tCO2_effective"] * float(
                    portfolio_price
                )
                portfolio_ts.append(ts_i)

                base_cost = float(scope1_i) * float(portfolio_base_price)
                stress_cost = float(scope1_i) * float(portfolio_stress_price)
                high_cost = float(scope1_i) * float(portfolio_high_price)
                selected_cost = float(scope1_i) * float(portfolio_price)

                if selected_cost >= budget_red:
                    status = "RED"
                elif selected_cost >= budget_amber:
                    status = "AMBER"
                else:
                    status = "GREEN"

                site_rows.append(
                    {
                        "Site": site_name,
                        "Scope1_tCO2": float(scope1_i),
                        "ETS_Base_EUR": base_cost,
                        "ETS_Stress_EUR": stress_cost,
                        "ETS_High_EUR": high_cost,
                        "ETS_Selected_EUR": selected_cost,
                        "Delta_vs_Base_EUR": selected_cost - base_cost,
                        "Guardrail_Status": status,
                    }
                )
                if warnings_i:
                    warnings_map[site_name] = warnings_i
            except Exception as exc:  # pragma: no cover
                errors.append(f"{site_name}: {exc}")

        if errors:
            st.error("Some sites could not be processed:")
            for e in errors:
                st.error(e)

        if not site_rows:
            st.warning("No valid site data available for portfolio analysis.")
        else:
            summary_df = pd.DataFrame(site_rows).sort_values(
                "ETS_Selected_EUR", ascending=False
            )
            portfolio_df = pd.concat(portfolio_ts, ignore_index=True)

            st.markdown(
                "<span class='section-pill'>Portfolio</span>", unsafe_allow_html=True
            )
            st.markdown("### Multi-Site Planning Overview")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Sites processed", f"{len(summary_df)}")
            k2.metric(
                "Portfolio Scope 1 (tCO2)", f"{summary_df['Scope1_tCO2'].sum():,.0f}"
            )
            k3.metric(
                "Portfolio selected ETS cost",
                f"EUR {summary_df['ETS_Selected_EUR'].sum():,.0f}",
            )
            k4.metric(
                "Sites above guardrail",
                f"{int((summary_df['Guardrail_Status'] != 'GREEN').sum())}",
            )

            st.subheader("Site Exposure Table")
            st.dataframe(summary_df, width="stretch")

            scenario_portfolio = pd.DataFrame(
                {
                    "Case": ["Base", "Stress", "High-price"],
                    "EUA_EUR_per_tCO2": [
                        float(portfolio_base_price),
                        float(portfolio_stress_price),
                        float(portfolio_high_price),
                    ],
                }
            )
            total_scope1 = float(summary_df["Scope1_tCO2"].sum())
            scenario_portfolio["Portfolio_ETS_EUR"] = (
                scenario_portfolio["EUA_EUR_per_tCO2"] * total_scope1
            )
            scenario_portfolio["Delta_vs_Base_EUR"] = scenario_portfolio[
                "Portfolio_ETS_EUR"
            ] - float(scenario_portfolio.loc[0, "Portfolio_ETS_EUR"])

            st.subheader("Central Procurement Scenarios")
            st.dataframe(scenario_portfolio, width="stretch")
            fig_port = plt.figure(figsize=(8, 3.2))
            ax_port = fig_port.add_subplot(111)
            ax_port.set_facecolor(PLOT_PANEL)
            fig_port.patch.set_facecolor(PLOT_BG)
            ax_port.bar(
                scenario_portfolio["Case"],
                scenario_portfolio["Portfolio_ETS_EUR"],
                color=[COST_COLOR, "#F5A623", "#FF5F57"],
            )
            _style_axis(ax_port, "Portfolio ETS Cost by Scenario", "EUR", "Case")
            st.pyplot(fig_port, width="stretch")
            plt.close(fig_port)

            st.subheader("Site Comparison Curves")
            metric_col = compare_metric
            comp_fig = plt.figure(figsize=(11, 4))
            comp_ax = comp_fig.add_subplot(111)
            comp_ax.set_facecolor(PLOT_PANEL)
            comp_fig.patch.set_facecolor(PLOT_BG)
            for site, grp in portfolio_df.groupby("Site"):
                grp = grp.sort_values("Period_plot")
                comp_ax.plot(
                    grp["Period_plot"], grp[metric_col], linewidth=1.8, label=site
                )
            _style_axis(comp_ax, f"Site comparison: {metric_col}", metric_col, "Period")
            _set_sparse_ticks(
                comp_ax, portfolio_df["Period_plot"].drop_duplicates().tolist(), 3
            )
            legend = comp_ax.legend(fontsize=8, loc="upper left")
            _style_legend(legend)
            st.pyplot(comp_fig, width="stretch")
            plt.close(comp_fig)

            st.subheader("Monthly Review Log (Editable)")
            latest_period = portfolio_df["Period_plot"].max()
            review_log = summary_df[["Site", "Guardrail_Status"]].copy()
            review_log["Period"] = pd.to_datetime(latest_period).strftime("%Y-%m")
            review_log["Owner"] = "TBD"
            review_log["Action"] = ""
            review_log["Status"] = "Open"
            review_log["DueDate"] = ""
            editable_log = st.data_editor(
                review_log, width="stretch", num_rows="dynamic"
            )

            if warnings_map:
                with st.expander("Site validation warnings"):
                    for site, items in warnings_map.items():
                        st.markdown(f"**{site}**")
                        for w in items:
                            st.warning(w)

            s_csv = summary_df.to_csv(index=False).encode("utf-8")
            l_csv = editable_log.to_csv(index=False).encode("utf-8")
            c1, c2 = st.columns(2)
            c1.download_button(
                "Download Portfolio Summary CSV",
                s_csv,
                "portfolio_summary.csv",
                "text/csv",
            )
            c2.download_button(
                "Download Review Log CSV",
                l_csv,
                "portfolio_review_log.csv",
                "text/csv",
            )
