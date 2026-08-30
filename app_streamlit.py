"""Streamlit app for EU ETS exposure analysis and reporting visuals."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import streamlit as st

from eu_ets_calc_io import (
    WorkbookValidationError,
    compute_emission_rows,
    compute_scope1_total_tco2,
    load_calc_table,
    load_eua_scenarios,
    load_factors,
    validate_loaded_data,
)

SCOPE1_COLOR = "#E4572E"
SCOPE2_COLOR = "#4C78A8"
STEAM_COLOR = "#54A24B"
COST_COLOR = "#2E86AB"
TOTAL_COLOR = "#5B5F97"

st.set_page_config(page_title="EU ETS Exposure Calculator", layout="wide")
st.title("EU ETS Exposure Calculator")
st.caption(
    "Workbook validation, Scope 1 ETS cost sensitivity, and EU ETS-oriented diagnostic plots."
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

    ts = compute_emission_rows(ts, factors)

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
        .resample(pd.offsets.QuarterEnd())
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
    ax.set_title(title, fontsize=12, pad=12)
    ax.set_ylabel(y_label, fontsize=10)
    ax.set_xlabel(x_label, fontsize=10)
    ax.grid(alpha=0.25)
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", labelsize=9)


def _set_sparse_ticks(ax, x_vals, step: int = 3) -> None:
    if len(x_vals) == 0:
        return
    idx = list(range(0, len(x_vals), max(step, 1)))
    ax.set_xticks([x_vals[i] for i in idx])


def _plot_scenario_bar(scenario_df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 3.2))
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
    ax.legend(loc="upper left", fontsize=9)
    return fig


def _plot_costs(ts_plot: pd.DataFrame, tick_step: int = 3):
    fig, ax = plt.subplots(figsize=(11, 3.8))
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
    ax.legend(fontsize=9)
    return fig


def _plot_intensity(ts_plot: pd.DataFrame, tick_step: int = 3):
    fig, ax = plt.subplots(figsize=(11, 3.8))
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
    ax.legend(fontsize=9)
    return fig


def _plot_sensitivity(sens_df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(
        sens_df["EUA_EUR_per_tCO2"],
        sens_df["Annual_ETS_cost_EUR"],
        color=COST_COLOR,
        linewidth=2.2,
    )
    _style_axis(ax, "EUA Sensitivity Curve", "Annual ETS Cost EUR", "EUA EUR/tCO2")
    return fig


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
) -> bytes:
    def _fig_to_reader(fig) -> ImageReader:
        img_buf = BytesIO()
        fig.savefig(img_buf, format="png", dpi=180, bbox_inches="tight")
        plt.close(fig)
        img_buf.seek(0)
        return ImageReader(img_buf)

    def _draw_plot(
        pdf_canvas: canvas.Canvas,
        img: ImageReader,
        title: str,
        caption: str,
        y_pos: float,
    ) -> float:
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
        pdf_canvas.setFont("Helvetica-Oblique", 9)
        pdf_canvas.drawString(40, y_next - 12, caption)
        return y_next - 26

    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    _, height = A4

    # Cover summary page
    y = height - 50
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(40, y, "EU ETS Exposure Analysis Report")
    y -= 22
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        40,
        y,
        f"Generated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
    )
    y -= 14
    pdf.drawString(40, y, f"Workbook: {workbook_label}")
    y -= 14
    pdf.drawString(40, y, f"Scope 1 total (tCO2): {scope1_total:,.2f}")
    y -= 14
    pdf.drawString(
        40,
        y,
        f"Selected scenario: {selected_scenario_label} @ {selected_price:.2f} EUR/tCO2",
    )
    y -= 14
    pdf.drawString(
        40,
        y,
        f"View granularity: {granularity}; Include Scope2/Steam: {include_scope2_steam}",
    )
    y -= 14
    pdf.drawString(40, y, f"X-axis label step: every {tick_step} point(s)")

    y -= 22
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, y, "Scenario summary")
    y -= 14
    pdf.setFont("Helvetica", 10)
    for _, row in scenario_df.iterrows():
        pdf.drawString(
            40,
            y,
            f"{row['Scenario']}: EUA {row['EUA_EUR_per_tCO2']:.2f} EUR/tCO2, ETS cost {row['ETS_cost_EUR']:,.0f} EUR",
        )
        y -= 12

    y -= 8
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, y, "Top periods by Scope 1 emissions")
    y -= 14
    pdf.setFont("Helvetica", 10)
    top = ts_plot.nlargest(6, "Scope1_tCO2_effective")[
        ["Period_plot", "Scope1_tCO2_effective"]
    ]
    for _, row in top.iterrows():
        p = pd.to_datetime(row["Period_plot"]).strftime("%Y-%m")
        pdf.drawString(40, y, f"{p}: {row['Scope1_tCO2_effective']:,.2f} tCO2")
        y -= 12

    # Section 1
    pdf.showPage()
    y = height - 40
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
    pdf.showPage()
    y = height - 40
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
    pdf.showPage()
    y = height - 40
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
    st.header("Workbook")
    source_mode = st.radio(
        "Select source", ["Upload workbook", "Use local demo workbook"], index=1
    )
    uploaded = st.file_uploader("Upload .xlsx", type=["xlsx"])

source: Path | bytes | None = None
if source_mode == "Upload workbook":
    if uploaded is not None:
        source = uploaded.getvalue()
    else:
        st.info("Upload an .xlsx workbook to continue.")
else:
    demo_path = Path("EU_ETS_Exposure_Calculator_Demo.xlsx")
    if demo_path.exists():
        source = demo_path
    else:
        st.error("Local demo workbook not found: EU_ETS_Exposure_Calculator_Demo.xlsx")

if source is not None:
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
        st.header("Analysis Controls")
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Workbook", workbook_label)
    c2.metric(
        "Scope 1 total (tCO2)", f"{float(ts_plot['Scope1_tCO2_effective'].sum()):,.2f}"
    )
    c3.metric(
        "Primary scenario", f"{selected_scenario} ({selected_price:,.0f} EUR/tCO2)"
    )
    c4.metric("Selected period ETS cost", f"EUR {selected_period_cost:,.0f}")

    st.subheader("Annualized ETS Scenario Summary")
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
    )

    d1, d2 = st.columns(2)
    d1.download_button(
        label="Download Scenario Summary CSV",
        data=csv_bytes,
        file_name="ets_scenario_summary.csv",
        mime="text/csv",
    )
    d2.download_button(
        label="Download Analysis PDF",
        data=pdf_bytes,
        file_name="ets_analysis_report.pdf",
        mime="application/pdf",
    )

    tab_costs, tab_emissions, tab_intensity, tab_sensitivity = st.tabs(
        ["Costs", "Emissions", "Intensity", "Sensitivity"]
    )

    with tab_costs:
        st.markdown("ETS cost trends by scenario")
        fig_cost = _plot_costs(ts_plot, tick_step=tick_step)
        st.pyplot(fig_cost, width="stretch")
        plt.close(fig_cost)

    with tab_emissions:
        st.markdown("Scope breakdown (toggle in sidebar for Scope2/Steam visibility)")
        fig_em = _plot_emissions(
            ts_plot, include_scope2_steam=include_scope2_steam, tick_step=tick_step
        )
        st.pyplot(fig_em, width="stretch")
        plt.close(fig_em)

    with tab_intensity:
        st.markdown("Carbon intensity by output")
        fig_int = _plot_intensity(ts_plot, tick_step=tick_step)
        st.pyplot(fig_int, width="stretch")
        plt.close(fig_int)

    with tab_sensitivity:
        s1, s2 = st.columns([3, 1])
        with s2:
            st.metric(
                "Cost delta for +10 EUR/tCO2",
                f"EUR {float(ts_plot['Scope1_tCO2_effective'].sum()) * 10:,.0f}",
            )
        with s1:
            fig_sens = _plot_sensitivity(sensitivity_df)
            st.pyplot(fig_sens, width="stretch")
            plt.close(fig_sens)

    with st.expander("Detailed ETS Time Series"):
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

    with st.expander("Input Preview (Calc sheet)"):
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
