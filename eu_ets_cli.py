"""CLI entrypoint for validating workbook inputs and computing ETS sensitivity."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from eu_ets_calc_io import (
    compute_scope1_total_tco2,
    load_calc_table,
    load_eua_scenarios,
    load_factors,
    validate_loaded_data,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EU ETS workbook validator and scenario calculator"
    )
    parser.add_argument(
        "--workbook",
        default="EU_ETS_Exposure_Calculator_Demo.xlsx",
        help="Path to input workbook (.xlsx)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional path to write scenario costs as CSV",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workbook = Path(args.workbook)

    if not workbook.exists():
        print(f"ERROR: Workbook not found: {workbook}", file=sys.stderr)
        return 1

    try:
        calc = load_calc_table(workbook)
        factors = load_factors(workbook)
        scenarios = load_eua_scenarios(workbook)
        warnings = validate_loaded_data(calc, factors, scenarios)
        scope1_total = compute_scope1_total_tco2(calc, factors)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    scenarios = scenarios.copy()
    scenarios["ETS_cost_EUR"] = scenarios["EUA_EUR_per_tCO2"] * scope1_total

    print(f"Workbook: {workbook}")
    print(f"Scope 1 total (tCO2): {scope1_total:,.2f}")
    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f"- {item}")

    print("Scenario costs (EUR):")
    print(scenarios.to_string(index=False))

    if args.output:
        out_path = Path(args.output)
        scenarios.to_csv(out_path, index=False)
        print(f"Wrote scenario costs CSV: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
