"""End-to-end workbook fallback and shared dashboard/CLI regressions."""

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import eu_ets_cli
import eu_ets_calc_io as core


@pytest.fixture
def workbook_factory(tmp_path):
    def write(calc_rows, inputs_rows):
        path = tmp_path / "partial.xlsx"
        factors = pd.read_excel(
            "EU_ETS_Exposure_Calculator_Demo.xlsx", sheet_name="Factors", header=None
        )
        with pd.ExcelWriter(path) as writer:
            pd.DataFrame(calc_rows, columns=["Period", "Elec_MWh", "Gas_Nm3"]).to_excel(
                writer, sheet_name="Calc", index=False
            )
            pd.DataFrame(
                inputs_rows,
                columns=["Period", "Electricity (MWh)", "Natural gas (Nm3)"],
            ).to_excel(writer, sheet_name="Inputs", index=False)
            factors.to_excel(writer, sheet_name="Factors", header=False, index=False)
        return path

    return write


@pytest.mark.parametrize(
    "calc_rows", [[], [["2024-01", None, None]], [["2024-01", 5, 1000]]]
)
def test_inputs_recover_empty_partial_and_missing_calc_rows(
    workbook_factory, calc_rows
):
    workbook = workbook_factory(calc_rows, [["2024-01", 5, 1000], ["2024-02", 7, 2000]])
    calc = core.load_calc_table(workbook)
    factors = core.load_factors(workbook)
    assert calc["Period"].tolist() == ["2024-01", "2024-02"]
    assert calc["Gas_Nm3"].tolist() == [1000, 2000]
    assert core.compute_scope1_total_tco2(calc, factors) == pytest.approx(
        3000 * factors.gas_kwh_per_nm3 / 1000 * factors.gas_ef_tco2_per_mwh
    )


def test_cli_reports_missing_gas_without_traceback(
    workbook_factory, monkeypatch, capsys
):
    workbook = workbook_factory([["2024-01", 5, None]], [["2024-01", 5, None]])
    monkeypatch.setattr("sys.argv", ["eu_ets_cli", "--workbook", str(workbook)])
    assert eu_ets_cli.main() == 2
    assert "Scope 1 requires" in capsys.readouterr().err


def test_dashboard_monthly_quarterly_and_cli_share_partial_cache_results():
    # Compile only the pure dashboard functions, without executing Streamlit UI.
    tree = ast.parse(Path("app_streamlit.py").read_text(encoding="utf-8"))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"_prepare_ets_timeseries", "_aggregate_timeseries"}
    ]
    namespace = {"pd": pd, "np": np, **vars(core)}
    exec(
        compile(
            ast.Module(body=functions, type_ignores=[]), "app_streamlit.py", "exec"
        ),
        namespace,
    )
    frame = pd.DataFrame(
        {
            "Period": ["2024-01", "2024-02"],
            "Gas_Nm3": [1000.0, 2000.0],
            "Gas_MWh_in": [5.0, np.nan],
            "OtherFuel_MWh": [2.0, 3.0],
            "Scope1_tCO2": [1.6, np.nan],
            "Elec_MWh": [0.0, 0.0],
            "Steam_MWh": [0.0, 0.0],
            "Prod_t": [10.0, 20.0],
        }
    )
    factors = core.Factors(0.2, 0.3, 0.1, 0.4, 10.0)
    scenarios = pd.DataFrame({"Scenario": ["Mid"], "EUA_EUR_per_tCO2": [85.0]})
    monthly = namespace["_prepare_ets_timeseries"](frame, factors, scenarios)
    quarterly = namespace["_aggregate_timeseries"](monthly, "Quarterly")
    total = core.compute_scope1_total_tco2(frame, factors)
    assert total == pytest.approx(6.5)
    for table in [monthly, quarterly]:
        assert table["Scope1_tCO2_effective"].sum() == pytest.approx(total)
        assert table["ETS_Mid_EUR"].sum() == pytest.approx(total * 85)
