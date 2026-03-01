import { BadRequestException, Injectable } from '@nestjs/common';
import * as XLSX from 'xlsx';
import {
  ActionRow,
  AnalyzeOptions,
  AnalyzeResponse,
  AssumptionRow,
  MarketScenarioRow,
  OpportunityRow,
  PeriodSeriesRow,
  PortfolioResponse,
  PortfolioSiteRow,
  QualityRow,
  ReconciliationRow,
  ScenarioRow,
  VarianceDecompositionRow,
} from './ets.types';

type RowArray = Array<string | number | null | undefined>;

@Injectable()
export class EtsService {
  private toNumber(val: unknown): number {
    if (typeof val === 'number' && Number.isFinite(val)) return val;
    if (typeof val === 'string') {
      const cleaned = val.replaceAll(',', '').trim();
      if (cleaned === '') return NaN;
      const n = Number(cleaned);
      return Number.isFinite(n) ? n : NaN;
    }
    if (val && typeof val === 'object') {
      const maybe = (val as { v?: unknown }).v;
      if (maybe !== undefined) return this.toNumber(maybe);
    }
    return NaN;
  }

  analyzeWorkbook(sourceName: string, buffer: Buffer, options: AnalyzeOptions): AnalyzeResponse {
    const calcRows = this.readSheetRows(buffer, 'Calc');
    const factorRows = this.readSheetRows(buffer, 'Factors');
    const inputRows = this.readSheetRows(buffer, 'Inputs');

    const calcTable = this.loadCalcTable(calcRows);
    const inputsTable = this.loadInputsTable(inputRows);
    const factorPack = this.loadFactors(factorRows);
    const factors = factorPack.values;
    const scenarios = this.loadScenarios(factorRows);

    const scope1Total = this.computeScope1Total(calcTable, factors, inputsTable);
    const scenarioTable = scenarios.map((s) => ({
      scenario: s.scenario,
      euaEurPerTco2: s.euaEurPerTco2,
      etsCostEur: scope1Total * s.euaEurPerTco2,
    }));

    const selected = this.selectScenarioPrice(scenarios, options);
    const selectedCost = scope1Total * selected.price;
    const scenarioPrices = this.resolveScenarioPriceTriplet(scenarios);
    const periodSeries = this.buildPeriodSeries(
      calcTable,
      inputsTable,
      factors,
      scenarioPrices,
      selected.price,
      scope1Total,
      options.scope3FactorTco2PerT ?? factors.scope3FactorTco2PerT ?? 0,
    );
    const scope2Total = periodSeries.reduce((acc, row) => acc + row.scope2Tco2, 0);
    const scope3Total = periodSeries.reduce((acc, row) => acc + row.scope3Tco2, 0);
    const scope12Total = periodSeries.reduce((acc, row) => acc + row.scope12Tco2, 0);
    const scope123Total = periodSeries.reduce((acc, row) => acc + row.scope123Tco2, 0);

    const planningCases = this.buildPlanningCases(scope1Total, scenarios, options);
    const varianceDecomposition = this.buildVarianceDecomposition(periodSeries, factors);
    const qualityChecks = this.buildQualityChecks(periodSeries);
    const marketScenarios = this.buildMarketScenarios(periodSeries, selectedCost);
    const actionsRegister = this.buildActionsRegister(periodSeries, qualityChecks, selectedCost);
    const reconciliationChecks = this.buildReconciliationChecks(periodSeries);
    const opportunityShortlist = this.buildOpportunityShortlist(varianceDecomposition, qualityChecks);
    const freeAllocation = options.freeAllocationTco2 ?? 0;
    const netEuaRequirement = Math.max(0, scope1Total - freeAllocation);
    const measureReductionPct = Math.max(0, options.measureReductionPct ?? 0.08);
    const measureAnnualizedCost = Math.max(0, options.measureAnnualizedCostEur ?? 500_000);
    const avoidedT = scope1Total * measureReductionPct;
    const breakEvenEuaEurPerTco2 = avoidedT > 0 ? measureAnnualizedCost / avoidedT : 0;
    const powerBase = marketScenarios.find((m) => m.scenario === 'Power Base')?.totalCostEur ?? 0;
    const power20 = marketScenarios.find((m) => m.scenario === 'Power +20%')?.totalCostEur ?? 0;

    return {
      sourceName,
      periods: periodSeries.length,
      scope1TotalTco2: scope1Total,
      scope2TotalTco2: scope2Total,
      scope3TotalTco2: scope3Total,
      scope12TotalTco2: scope12Total,
      scope123TotalTco2: scope123Total,
      selectedScenario: selected.label,
      selectedEuaPrice: selected.price,
      selectedEtsCostEur: selectedCost,
      netEuaRequirementTco2: netEuaRequirement,
      deltaPer10Eur: scope1Total * 10,
      scenarioTable,
      planningCases,
      periodSeries,
      varianceDecomposition,
      qualityChecks,
      assumptions: factorPack.assumptions,
      marketScenarios,
      actionsRegister,
      reconciliationChecks,
      opportunityShortlist,
      electricityPlus20PctImpactEur: power20 - powerBase,
      breakEvenEuaEurPerTco2,
      warnings: [],
    };
  }

  buildPdfReportFromWorkbook(
    sourceName: string,
    buffer: Buffer,
    options: AnalyzeOptions,
    reportOwner?: string,
  ): Buffer {
    const analysis = this.analyzeWorkbook(sourceName, buffer, options);
    const owner = (reportOwner ?? 'Analyst').trim() || 'Analyst';
    const generated = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    return this.renderDarkPdfReport(analysis, owner, generated);
  }

  analyzePortfolio(
    files: { name: string; buffer: Buffer }[],
    options: AnalyzeOptions,
    guardrails: { amberThresholdEur: number; redThresholdEur: number },
  ): PortfolioResponse {
    const siteTable: PortfolioSiteRow[] = [];
    const errors: string[] = [];

    for (const file of files) {
      try {
        const res = this.analyzeWorkbook(file.name, file.buffer, options);
        const base = this.getPlanningCasePrice(res.planningCases, 'Base');
        const stress = this.getPlanningCasePrice(res.planningCases, 'Stress');
        const high = this.getPlanningCasePrice(res.planningCases, 'High-price');

        const etsBase = res.scope1TotalTco2 * base;
        const etsStress = res.scope1TotalTco2 * stress;
        const etsHigh = res.scope1TotalTco2 * high;
        const etsSelected = res.selectedEtsCostEur;

        let status: 'GREEN' | 'AMBER' | 'RED' = 'GREEN';
        if (etsSelected >= guardrails.redThresholdEur) {
          status = 'RED';
        } else if (etsSelected >= guardrails.amberThresholdEur) {
          status = 'AMBER';
        }

        siteTable.push({
          site: file.name,
          scope1Tco2: res.scope1TotalTco2,
          scope2Tco2: res.scope2TotalTco2,
          scope3Tco2: res.scope3TotalTco2,
          scope123Tco2: res.scope123TotalTco2,
          etsBaseEur: etsBase,
          etsStressEur: etsStress,
          etsHighEur: etsHigh,
          etsSelectedEur: etsSelected,
          deltaVsBaseEur: etsSelected - etsBase,
          status,
        });
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        errors.push(`${file.name}: ${msg}`);
      }
    }

    const totalScope1 = siteTable.reduce((acc, r) => acc + r.scope1Tco2, 0);
    const totalScope2 = siteTable.reduce((acc, r) => acc + r.scope2Tco2, 0);
    const totalScope3 = siteTable.reduce((acc, r) => acc + r.scope3Tco2, 0);
    const totalScope123 = siteTable.reduce((acc, r) => acc + r.scope123Tco2, 0);
    const totalSelected = siteTable.reduce((acc, r) => acc + r.etsSelectedEur, 0);

    return {
      sitesProcessed: siteTable.length,
      totalScope1Tco2: totalScope1,
      totalScope2Tco2: totalScope2,
      totalScope3Tco2: totalScope3,
      totalScope123Tco2: totalScope123,
      totalSelectedEtsEur: totalSelected,
      centralEuaPrice:
        options.customEuaPrice ?? this.pickDefaultScenarioPrice(options.selectedScenario),
      siteTable,
      errors,
    };
  }

  private readSheetRows(buffer: Buffer, sheetName: string): RowArray[] {
    const wb = XLSX.read(buffer, { type: 'buffer' });
    const sheet = wb.Sheets[sheetName];
    if (!sheet) {
      throw new BadRequestException(`Sheet '${sheetName}' not found in workbook.`);
    }
    return XLSX.utils.sheet_to_json(sheet, {
      header: 1,
      raw: true,
      defval: null,
    }) as RowArray[];
  }

  private normalize(val: unknown): string {
    return String(val ?? '')
      .trim()
      .toLowerCase()
      .replaceAll('€', 'eur')
      .replaceAll('₂', '2')
      .replaceAll('³', '3')
      .replace(/\s+/g, ' ');
  }

  private findHeaderRow(rows: RowArray[], expected: string[]): number {
    for (let i = 0; i < Math.min(40, rows.length); i++) {
      const set = new Set((rows[i] ?? []).map((v) => this.normalize(v)).filter(Boolean));
      const ok = expected.every((e) => set.has(e));
      if (ok) {
        return i;
      }
    }
    throw new BadRequestException(`Header row not found for expected columns: ${expected.join(', ')}`);
  }

  private loadCalcTable(rows: RowArray[]) {
    const headerIdx = this.findHeaderRow(rows, ['period', 'elec_mwh', 'gas_nm3']);
    const headers = (rows[headerIdx] ?? []).map((h) => String(h ?? '').trim());
    const dataRows = rows.slice(headerIdx + 1).filter((r) => r?.[0] !== null && r?.[0] !== undefined && String(r?.[0]).trim() !== '');

    return dataRows.map((r) => {
      const obj: Record<string, unknown> = {};
      headers.forEach((h, idx) => {
        obj[h] = r[idx];
      });
      return obj;
    });
  }

  private loadInputsTable(rows: RowArray[]) {
    let headerIdx = -1;
    for (let i = 0; i < Math.min(rows.length, 40); i++) {
      const norm = (rows[i] ?? []).map((v) => this.normalize(v));
      const hasPeriod = norm.some((c) => c === 'period');
      const hasElec = norm.some((c) => c.includes('electricity') && c.includes('mwh'));
      const hasGas = norm.some((c) => c.includes('natural gas'));
      if (hasPeriod && hasElec && hasGas) {
        headerIdx = i;
        break;
      }
    }
    if (headerIdx < 0) {
      return [] as Array<Record<string, unknown>>;
    }

    const header = rows[headerIdx] ?? [];
    const idx = {
      period: -1,
      elecMwh: -1,
      gasNm3: -1,
      gasMwh: -1,
      otherFuelMwh: -1,
      steamMwh: -1,
      productionT: -1,
      elecPrice: -1,
    };

    header.forEach((h, i) => {
      const n = this.normalize(h);
      if (n === 'period') idx.period = i;
      else if (n.includes('electricity') && n.includes('price')) idx.elecPrice = i;
      else if (n.includes('electricity') && n.includes('mwh') && !n.includes('price'))
        idx.elecMwh = i;
      else if (
        n.includes('natural gas') &&
        !n.includes('mwh') &&
        !n.includes('optional')
      )
        idx.gasNm3 = i;
      else if (n.includes('natural gas') && (n.includes('nm') || n.includes('nm3')))
        idx.gasNm3 = i;
      else if (n.includes('natural gas') && n.includes('mwh')) idx.gasMwh = i;
      else if (n.includes('other fuel') && n.includes('mwh')) idx.otherFuelMwh = i;
      else if (n.includes('steam') && n.includes('mwh')) idx.steamMwh = i;
      else if (n.includes('production') && n.includes('t')) idx.productionT = i;
      else if ((n.includes('price') && n.includes('eur') && n.includes('mwh')))
        idx.elecPrice = i;
    });

    // Fallback: if we found natural gas MWh but not Nm3, assume any remaining natural gas
    // column is the Nm3 activity input.
    if (idx.gasNm3 < 0) {
      header.forEach((h, i) => {
        const n = this.normalize(h);
        if (n.includes('natural gas') && i !== idx.gasMwh) {
          idx.gasNm3 = i;
        }
      });
    }

    return rows
      .slice(headerIdx + 1)
      .filter((r) => idx.period >= 0 && r[idx.period] !== null && r[idx.period] !== undefined && String(r[idx.period]).trim() !== '')
      .map((r) => ({
        Period: idx.period >= 0 ? r[idx.period] : null,
        Elec_MWh: idx.elecMwh >= 0 ? r[idx.elecMwh] : null,
        Gas_Nm3: idx.gasNm3 >= 0 ? r[idx.gasNm3] : null,
        Gas_MWh_in: idx.gasMwh >= 0 ? r[idx.gasMwh] : null,
        OtherFuel_MWh: idx.otherFuelMwh >= 0 ? r[idx.otherFuelMwh] : null,
        Steam_MWh: idx.steamMwh >= 0 ? r[idx.steamMwh] : null,
        Prod_t: idx.productionT >= 0 ? r[idx.productionT] : null,
        ElecPrice_EurPerMWh: idx.elecPrice >= 0 ? r[idx.elecPrice] : null,
      }));
  }

  private loadFactors(rows: RowArray[]): {
    values: {
      gasEf: number;
      otherEf: number;
      steamEf: number;
      elecEf: number;
      gasConv: number;
      scope3FactorTco2PerT?: number;
    };
    assumptions: AssumptionRow[];
  } {
    const wanted: Record<string, string> = {
      'natural gas ef (tco2/mwh)': 'gasEf',
      'other fuel ef (tco2/mwh)': 'otherEf',
      'steam ef (tco2/mwh)': 'steamEf',
      'electricity grid ef (tco2/mwh)': 'elecEf',
      'gas conversion (kwh per nm3)': 'gasConv',
    };

    const mapped: Record<string, number> = {};
    for (const row of rows) {
      const key = this.normalize(row[0]);
      const val = this.toNumber(row[1]);
      if (wanted[key] && Number.isFinite(val)) {
        mapped[wanted[key]] = val;
      }
      if (
        Number.isFinite(val) &&
        ((key.includes('scope 3') && key.includes('tco2/t')) ||
          (key.includes('scope 3') && key.includes('tco2 per t')))
      ) {
        mapped['scope3FactorTco2PerT'] = val;
      }
    }

    const missing = ['gasEf', 'otherEf', 'steamEf', 'elecEf', 'gasConv'].filter((k) => mapped[k] === undefined);
    if (missing.length > 0) {
      throw new BadRequestException(`Missing required factors: ${missing.join(', ')}`);
    }

    const values = mapped as {
      gasEf: number;
      otherEf: number;
      steamEf: number;
      elecEf: number;
      gasConv: number;
      scope3FactorTco2PerT?: number;
    };

    const assumptionRows: AssumptionRow[] = rows
      .map((row) => {
        const key = this.normalize(row[0]);
        const name = String(row[0] ?? '').trim();
        const value = this.toNumber(row[1]);
        const unit = String(row[2] ?? '').trim();
        const note = String(row[3] ?? '').trim();
        const isScope3Proxy =
          (key.includes('scope 3') && key.includes('tco2/t')) ||
          (key.includes('scope 3') && key.includes('tco2 per t'));
        if ((!wanted[key] && !isScope3Proxy) || !Number.isFinite(value)) return null;
        return {
          name,
          value,
          unit: unit || '-',
          source: 'Workbook Factors sheet',
          validityDate: new Date().toISOString().slice(0, 10),
          note: note || 'Managed in workbook assumptions.',
        } as AssumptionRow;
      })
      .filter((v): v is AssumptionRow => v !== null);

    return { values, assumptions: assumptionRows };
  }

  private loadScenarios(rows: RowArray[]): { scenario: string; euaEurPerTco2: number }[] {
    const headerIdx = this.findHeaderRow(rows, ['scenario', 'eua price (eur/tco2)']);
    const out: { scenario: string; euaEurPerTco2: number }[] = [];

    for (const row of rows.slice(headerIdx + 1)) {
      const scenario = String(row[0] ?? '').trim();
      const price = this.toNumber(row[1]);
      if (scenario && Number.isFinite(price) && price > 0) {
        out.push({ scenario, euaEurPerTco2: price });
      }
    }

    if (out.length === 0) {
      throw new BadRequestException('No valid EUA scenarios found in Factors sheet.');
    }
    return out;
  }

  private computeScope1Total(
    calcTable: Record<string, unknown>[],
    factors: { gasEf: number; otherEf: number; gasConv: number },
    inputsTable: Record<string, unknown>[],
  ): number {
    const loaded = calcTable
      .map((r) => this.toNumber(r['Scope1_tCO2']))
      .filter((v) => Number.isFinite(v));
    if (loaded.length > 0 && loaded.reduce((a, b) => a + b, 0) > 0) {
      return loaded.reduce((a, b) => a + b, 0);
    }

    const calcComputed = calcTable.reduce((acc, row) => {
      let gasMwh = this.toNumber(row['Gas_MWh_in']);
      if (!Number.isFinite(gasMwh)) gasMwh = this.toNumber(row['Gas_MWh_calc']);
      if (!Number.isFinite(gasMwh)) {
        const gasNm3 = this.toNumber(row['Gas_Nm3']);
        gasMwh = Number.isFinite(gasNm3) ? (gasNm3 * factors.gasConv) / 1000 : 0;
      }
      const otherFuel = this.toNumber(row['OtherFuel_MWh']);
      const other = Number.isFinite(otherFuel) ? otherFuel : 0;
      return acc + gasMwh * factors.gasEf + other * factors.otherEf;
    }, 0);
    if (calcComputed > 0) {
      return calcComputed;
    }

    return inputsTable.reduce((acc, row) => {
      let gasMwh = this.toNumber(row['Gas_MWh_in']);
      if (!Number.isFinite(gasMwh)) {
        const gasNm3 = this.toNumber(row['Gas_Nm3']);
        gasMwh = Number.isFinite(gasNm3) ? (gasNm3 * factors.gasConv) / 1000 : 0;
      }
      const otherFuel = this.toNumber(row['OtherFuel_MWh']);
      const other = Number.isFinite(otherFuel) ? otherFuel : 0;
      return acc + gasMwh * factors.gasEf + other * factors.otherEf;
    }, 0);
  }

  private buildPeriodSeries(
    calcTable: Record<string, unknown>[],
    inputsTable: Record<string, unknown>[],
    factors: { gasEf: number; otherEf: number; steamEf: number; elecEf: number; gasConv: number },
    scenarioPrices: { low: number; mid: number; high: number },
    selectedPrice: number,
    scope1Total: number,
    scope3FactorTco2PerT: number,
  ): PeriodSeriesRow[] {
    const rowCount = Math.max(calcTable.length, inputsTable.length);
    const out: PeriodSeriesRow[] = [];

    for (let i = 0; i < rowCount; i++) {
      const calc = calcTable[i] ?? {};
      const input = inputsTable[i] ?? {};

      const periodRaw = this.pickFirst(calc, input, ['Period', 'period']);
      const period = String(periodRaw ?? `P${i + 1}`).trim() || `P${i + 1}`;

      const elecMwh = this.pickNumber(calc, input, ['Elec_MWh', 'elec_mwh']);
      const gasNm3 = this.pickNumber(calc, input, ['Gas_Nm3', 'gas_nm3']);
      const gasMwhInput = this.pickNumber(calc, input, ['Gas_MWh_in', 'gas_mwh_in']);
      const gasMwhCalc = this.pickNumber(calc, input, ['Gas_MWh_calc', 'gas_mwh_calc']);
      const gasMwh = Number.isFinite(gasMwhInput)
        ? gasMwhInput
        : Number.isFinite(gasMwhCalc)
          ? gasMwhCalc
          : Number.isFinite(gasNm3)
            ? (gasNm3 * factors.gasConv) / 1000
            : 0;

      const otherFuelMwh = this.pickNumber(calc, input, ['OtherFuel_MWh', 'otherfuel_mwh']);
      const steamMwh = this.pickNumber(calc, input, ['Steam_MWh', 'steam_mwh']);
      const prodT = this.pickNumber(calc, input, ['Prod_t', 'prod_t']);
      const electricityPrice = this.pickNumber(calc, input, [
        'ElecPrice_EurPerMWh',
        'elecprice_eurpermwh',
      ]);

      const rowScope1 = this.pickNumber(calc, input, [
        'Scope1_tCO2',
        'scope1_tco2',
        'Scope1 (tCO2)',
      ]);
      const scope1Tco2 = Number.isFinite(rowScope1)
        ? rowScope1
        : gasMwh * factors.gasEf + this.safe(otherFuelMwh) * factors.otherEf;
      const scope2Tco2 = this.safe(elecMwh) * factors.elecEf + this.safe(steamMwh) * factors.steamEf;
      const scope3Tco2 = this.safe(prodT) * this.safe(scope3FactorTco2PerT);
      const scope12Tco2 = scope1Tco2 + scope2Tco2;
      const scope123Tco2 = scope12Tco2 + scope3Tco2;
      const energyTotalMwh = gasMwh + this.safe(otherFuelMwh) + this.safe(steamMwh) + this.safe(elecMwh);
      const energyIntensityMwhPerT =
        Number.isFinite(prodT) && prodT > 0 ? energyTotalMwh / prodT : 0;
      const scope1IntensityTPerT = Number.isFinite(prodT) && prodT > 0 ? scope1Tco2 / prodT : 0;
      const intensityKgPerT =
        Number.isFinite(prodT) && prodT > 0 ? (scope123Tco2 * 1000) / prodT : 0;
      const electricityCostEur = this.safe(elecMwh) * this.safe(electricityPrice);

      out.push({
        period,
        elecMwh: this.safe(elecMwh),
        gasNm3: this.safe(gasNm3),
        gasMwh: this.safe(gasMwh),
        otherFuelMwh: this.safe(otherFuelMwh),
        steamMwh: this.safe(steamMwh),
        prodT: this.safe(prodT),
        scope1Tco2: this.safe(scope1Tco2),
        scope2Tco2: this.safe(scope2Tco2),
        scope3Tco2: this.safe(scope3Tco2),
        scope12Tco2: this.safe(scope12Tco2),
        scope123Tco2: this.safe(scope123Tco2),
        energyTotalMwh: this.safe(energyTotalMwh),
        energyIntensityMwhPerT: this.safe(energyIntensityMwhPerT),
        scope1IntensityTPerT: this.safe(scope1IntensityTPerT),
        intensityKgPerT: this.safe(intensityKgPerT),
        etsCostLowEur: this.safe(scope1Tco2) * scenarioPrices.low,
        etsCostMidEur: this.safe(scope1Tco2) * scenarioPrices.mid,
        etsCostHighEur: this.safe(scope1Tco2) * scenarioPrices.high,
        etsCostSelectedEur: this.safe(scope1Tco2) * selectedPrice,
        electricityPriceEurPerMwh: this.safe(electricityPrice),
        electricityCostEur: this.safe(electricityCostEur),
      });
    }

    const rawScope1Sum = out.reduce((acc, row) => acc + row.scope1Tco2, 0);
    if (scope1Total > 0 && rawScope1Sum <= 0.001) {
      const activitySum = out.reduce((acc, row) => acc + row.gasMwh + row.otherFuelMwh, 0);
      if (activitySum > 0) {
        for (const row of out) {
          const w = (row.gasMwh + row.otherFuelMwh) / activitySum;
          row.scope1Tco2 = scope1Total * w;
          row.scope12Tco2 = row.scope1Tco2 + row.scope2Tco2;
          row.scope123Tco2 = row.scope12Tco2 + row.scope3Tco2;
          row.scope1IntensityTPerT = row.prodT > 0 ? row.scope1Tco2 / row.prodT : 0;
          row.intensityKgPerT = row.prodT > 0 ? (row.scope123Tco2 * 1000) / row.prodT : 0;
          row.etsCostLowEur = row.scope1Tco2 * scenarioPrices.low;
          row.etsCostMidEur = row.scope1Tco2 * scenarioPrices.mid;
          row.etsCostHighEur = row.scope1Tco2 * scenarioPrices.high;
          row.etsCostSelectedEur = row.scope1Tco2 * selectedPrice;
        }
      } else {
        const avg = scope1Total / Math.max(out.length, 1);
        for (const row of out) {
          row.scope1Tco2 = avg;
          row.scope12Tco2 = row.scope1Tco2 + row.scope2Tco2;
          row.scope123Tco2 = row.scope12Tco2 + row.scope3Tco2;
          row.scope1IntensityTPerT = row.prodT > 0 ? row.scope1Tco2 / row.prodT : 0;
          row.intensityKgPerT = row.prodT > 0 ? (row.scope123Tco2 * 1000) / row.prodT : 0;
          row.etsCostLowEur = row.scope1Tco2 * scenarioPrices.low;
          row.etsCostMidEur = row.scope1Tco2 * scenarioPrices.mid;
          row.etsCostHighEur = row.scope1Tco2 * scenarioPrices.high;
          row.etsCostSelectedEur = row.scope1Tco2 * selectedPrice;
        }
      }
    }

    return out;
  }

  private buildVarianceDecomposition(
    periodSeries: PeriodSeriesRow[],
    factors: { gasEf: number; otherEf: number },
  ): VarianceDecompositionRow[] {
    const out: VarianceDecompositionRow[] = [];
    for (let i = 1; i < periodSeries.length; i++) {
      const prev = periodSeries[i - 1];
      const curr = periodSeries[i];
      const p0 = prev.prodT;
      const p1 = curr.prodT;
      const ei0 = p0 > 0 ? (prev.gasMwh + prev.otherFuelMwh) / p0 : 0;
      const ei1 = p1 > 0 ? (curr.gasMwh + curr.otherFuelMwh) / p1 : 0;
      const mix0Den = prev.gasMwh + prev.otherFuelMwh;
      const mix1Den = curr.gasMwh + curr.otherFuelMwh;
      const share0 = mix0Den > 0 ? prev.gasMwh / mix0Den : 0;
      const share1 = mix1Den > 0 ? curr.gasMwh / mix1Den : 0;
      const ci0 = share0 * factors.gasEf + (1 - share0) * factors.otherEf;

      const productionEffect = (p1 - p0) * ei0 * ci0;
      const energyIntensityEffect = p1 * (ei1 - ei0) * ci0;
      const fuelMixEffect = p1 * ei1 * (share1 - share0) * (factors.gasEf - factors.otherEf);
      const delta = curr.scope1Tco2 - prev.scope1Tco2;
      const factorAssumptionEffect = delta - productionEffect - energyIntensityEffect - fuelMixEffect;

      out.push({
        period: curr.period,
        deltaCo2T: delta,
        productionEffectT: productionEffect,
        energyIntensityEffectT: energyIntensityEffect,
        fuelMixEffectT: fuelMixEffect,
        factorAssumptionEffectT: factorAssumptionEffect,
      });
    }
    return out;
  }

  private buildQualityChecks(periodSeries: PeriodSeriesRow[]): QualityRow[] {
    const avgScope1 =
      periodSeries.length > 0
        ? periodSeries.reduce((acc, r) => acc + r.scope1Tco2, 0) / periodSeries.length
        : 0;
    return periodSeries.map((row) => {
      const flags: string[] = [];
      if (row.elecMwh <= 0) flags.push('METER_ELEC_ZERO_OR_NEG');
      if (row.gasNm3 <= 0 && row.gasMwh <= 0) flags.push('METER_GAS_ZERO_OR_NEG');
      if (row.prodT <= 0) flags.push('MISSING_OR_ZERO_PRODUCTION');
      if (row.electricityPriceEurPerMwh <= 0) flags.push('MISSING_ELECTRICITY_PRICE');
      if (avgScope1 > 0 && row.scope1Tco2 > 1.35 * avgScope1) flags.push('SCOPE1_STEP_CHANGE');
      if (row.energyIntensityMwhPerT > 0.45) flags.push('ENERGY_INTENSITY_HIGH');

      const grade: 'A' | 'B' | 'C' =
        flags.length === 0 ? 'A' : flags.length <= 2 ? 'B' : 'C';
      return { period: row.period, grade, flags };
    });
  }

  private buildMarketScenarios(
    periodSeries: PeriodSeriesRow[],
    selectedEtsCostEur: number,
  ): MarketScenarioRow[] {
    const baseElecCost = periodSeries.reduce((acc, r) => acc + r.electricityCostEur, 0);
    const settings = [
      { label: 'Power Base', m: 1.0 },
      { label: 'Power +20%', m: 1.2 },
      { label: 'Power +40%', m: 1.4 },
    ];
    return settings.map((s) => {
      const electricityCostEur = baseElecCost * s.m;
      return {
        scenario: s.label,
        electricityPriceMultiplier: s.m,
        electricityCostEur,
        etsCostEur: selectedEtsCostEur,
        totalCostEur: electricityCostEur + selectedEtsCostEur,
      };
    });
  }

  private buildActionsRegister(
    periodSeries: PeriodSeriesRow[],
    qualityChecks: QualityRow[],
    selectedEtsCostEur: number,
  ): ActionRow[] {
    const horizonYears = 1;
    const scope1Total = periodSeries.reduce((acc, r) => acc + r.scope1Tco2, 0);
    const meanEi =
      periodSeries.length > 0
        ? periodSeries.reduce((acc, r) => acc + r.energyIntensityMwhPerT, 0) / periodSeries.length
        : 0;
    const avgEua = scope1Total > 0 ? selectedEtsCostEur / scope1Total : 85;
    const poorQualityMonths = qualityChecks.filter((q) => q.grade === 'C').length;
    const latest = periodSeries[periodSeries.length - 1]?.period ?? '2026-12';

    const actions: ActionRow[] = [
      {
        action: 'Boiler combustion optimization campaign',
        owner: 'Energy Engineer',
        dueDate: `${latest}-28`,
        expectedSavingsMwh: 1800,
        co2ImpactT: 1800 * 0.202,
        eurImpact: 1800 * 0.202 * avgEua,
        capexEur: 120000,
        paybackYears: 120000 / Math.max(1, 1800 * 0.202 * avgEua),
        actualSavingsMwh: 1300,
      },
      {
        action: 'Steam system leak + trap program',
        owner: 'Utilities Lead',
        dueDate: `${latest}-25`,
        expectedSavingsMwh: 1400,
        co2ImpactT: 1400 * 0.1,
        eurImpact: 1400 * 0.1 * avgEua,
        capexEur: 80000,
        paybackYears: 80000 / Math.max(1, 1400 * 0.1 * avgEua),
        actualSavingsMwh: 900,
      },
      {
        action: 'Electricity peak shaving + scheduling',
        owner: 'Production Manager',
        dueDate: `${latest}-20`,
        expectedSavingsMwh: Math.max(500, meanEi * 1200),
        co2ImpactT: Math.max(500, meanEi * 1200) * 0.12,
        eurImpact: Math.max(500, meanEi * 1200) * 0.12 * avgEua,
        capexEur: 150000,
        paybackYears: 150000 / Math.max(1, Math.max(500, meanEi * 1200) * 0.12 * avgEua),
        actualSavingsMwh: Math.max(300, meanEi * 900),
      },
      {
        action: 'Metering & data QA remediation',
        owner: 'Controls Engineer',
        dueDate: `${latest}-15`,
        expectedSavingsMwh: poorQualityMonths > 0 ? 600 : 250,
        co2ImpactT: (poorQualityMonths > 0 ? 600 : 250) * 0.15,
        eurImpact: (poorQualityMonths > 0 ? 600 : 250) * 0.15 * avgEua,
        capexEur: 45000,
        paybackYears: 45000 / Math.max(1, (poorQualityMonths > 0 ? 600 : 250) * 0.15 * avgEua),
        actualSavingsMwh: poorQualityMonths > 0 ? 300 : 180,
      },
    ];

    return actions.map((a) => ({
      ...a,
      paybackYears: Number.isFinite(a.paybackYears) ? a.paybackYears / horizonYears : 0,
    }));
  }

  private buildReconciliationChecks(periodSeries: PeriodSeriesRow[]): ReconciliationRow[] {
    return periodSeries.map((row) => {
      const expected = row.gasMwh * 0.202 + row.otherFuelMwh * 0.27;
      const reported = row.scope1Tco2;
      const deviationPct =
        expected > 0 ? ((reported - expected) / expected) * 100 : reported > 0 ? 100 : 0;
      const absDev = Math.abs(deviationPct);
      const flag =
        absDev <= 5
          ? 'OK'
          : absDev <= 12
            ? 'CHECK_FACTOR_OR_UNITS'
            : 'REVIEW_METER_OR_BOUNDARY';
      return {
        period: row.period,
        expectedScope1FromEnergyT: expected,
        reportedScope1T: reported,
        deviationPct,
        flag,
      };
    });
  }

  private buildOpportunityShortlist(
    variance: VarianceDecompositionRow[],
    qualityChecks: QualityRow[],
  ): OpportunityRow[] {
    if (variance.length === 0) {
      return [];
    }
    const latest = variance[variance.length - 1];
    const latestQuality = qualityChecks.find((q) => q.period === latest.period);
    const candidates: OpportunityRow[] = [
      {
        driver: 'Production effect',
        impactTco2: latest.productionEffectT,
        direction: latest.productionEffectT >= 0 ? 'INCREASE' : 'DECREASE',
        note: 'Volume change impact on combustion emissions.',
      },
      {
        driver: 'Energy intensity effect',
        impactTco2: latest.energyIntensityEffectT,
        direction: latest.energyIntensityEffectT >= 0 ? 'INCREASE' : 'DECREASE',
        note: 'MWh per tonne performance vs prior month.',
      },
      {
        driver: 'Fuel mix effect',
        impactTco2: latest.fuelMixEffectT,
        direction: latest.fuelMixEffectT >= 0 ? 'INCREASE' : 'DECREASE',
        note: 'Shift between gas and other fuel contribution.',
      },
      {
        driver: 'Factor / assumption effect',
        impactTco2: latest.factorAssumptionEffectT,
        direction: latest.factorAssumptionEffectT >= 0 ? 'INCREASE' : 'DECREASE',
        note: 'Residual component including factor/boundary changes.',
      },
      {
        driver: 'Data quality risk',
        impactTco2: latestQuality && latestQuality.grade === 'C' ? Math.abs(latest.deltaCo2T) : 0,
        direction:
          latestQuality && latestQuality.grade === 'C' && latest.deltaCo2T >= 0
            ? 'INCREASE'
            : 'DECREASE',
        note:
          latestQuality && latestQuality.flags.length > 0
            ? `Flags: ${latestQuality.flags.join(', ')}`
            : 'No material quality flags.',
      },
    ];

    return candidates
      .sort((a, b) => Math.abs(b.impactTco2) - Math.abs(a.impactTco2))
      .slice(0, 5);
  }

  private resolveScenarioPriceTriplet(
    scenarios: { scenario: string; euaEurPerTco2: number }[],
  ): { low: number; mid: number; high: number } {
    return {
      low: this.resolveScenario(scenarios, 'low', 50),
      mid: this.resolveScenario(scenarios, 'mid', 85),
      high: this.resolveScenario(scenarios, 'high', 120),
    };
  }

  private pickFirst(
    primary: Record<string, unknown>,
    fallback: Record<string, unknown>,
    keys: string[],
  ): unknown {
    for (const key of keys) {
      const p = this.getFromRow(primary, key);
      if (p !== null && p !== undefined && String(p).trim() !== '') {
        return p;
      }
      const f = this.getFromRow(fallback, key);
      if (f !== null && f !== undefined && String(f).trim() !== '') {
        return f;
      }
    }
    return null;
  }

  private pickNumber(
    primary: Record<string, unknown>,
    fallback: Record<string, unknown>,
    keys: string[],
  ): number {
    for (const key of keys) {
      const a = this.toNumber(this.getFromRow(primary, key));
      if (Number.isFinite(a)) return a;
      const b = this.toNumber(this.getFromRow(fallback, key));
      if (Number.isFinite(b)) return b;
    }
    return NaN;
  }

  private getFromRow(row: Record<string, unknown>, targetKey: string): unknown {
    if (targetKey in row) return row[targetKey];
    const targetNorm = this.normalize(targetKey);
    for (const [k, v] of Object.entries(row)) {
      if (this.normalize(k) === targetNorm) return v;
    }
    return undefined;
  }

  private safe(v: number): number {
    return Number.isFinite(v) ? v : 0;
  }

  private selectScenarioPrice(
    scenarios: { scenario: string; euaEurPerTco2: number }[],
    options: AnalyzeOptions,
  ): { label: string; price: number } {
    if (options.customEuaPrice !== undefined && Number.isFinite(options.customEuaPrice)) {
      return { label: 'Custom', price: options.customEuaPrice };
    }

    if (options.selectedScenario) {
      const match = scenarios.find(
        (s) => s.scenario.toLowerCase() === options.selectedScenario?.toLowerCase(),
      );
      if (match) return { label: match.scenario, price: match.euaEurPerTco2 };
    }

    const mid = scenarios.find((s) => s.scenario.toLowerCase().includes('mid'));
    if (mid) return { label: mid.scenario, price: mid.euaEurPerTco2 };
    return { label: scenarios[0].scenario, price: scenarios[0].euaEurPerTco2 };
  }

  private buildPlanningCases(
    scope1Total: number,
    scenarios: { scenario: string; euaEurPerTco2: number }[],
    options: AnalyzeOptions,
  ): ScenarioRow[] {
    const base = options.basePrice ?? this.resolveScenario(scenarios, 'mid', 85);
    const stress = options.stressPrice ?? this.resolveScenario(scenarios, 'high', 120);
    const high = options.highPrice ?? Math.max(stress + 20, 140);

    return [
      { scenario: 'Base', euaEurPerTco2: base, etsCostEur: scope1Total * base },
      { scenario: 'Stress', euaEurPerTco2: stress, etsCostEur: scope1Total * stress },
      { scenario: 'High-price', euaEurPerTco2: high, etsCostEur: scope1Total * high },
    ];
  }

  private resolveScenario(
    scenarios: { scenario: string; euaEurPerTco2: number }[],
    key: string,
    fallback: number,
  ): number {
    const found = scenarios.find((s) => s.scenario.toLowerCase().includes(key));
    return found ? found.euaEurPerTco2 : fallback;
  }

  private getPlanningCasePrice(cases: ScenarioRow[], caseName: string): number {
    const found = cases.find((c) => c.scenario === caseName);
    return found ? found.euaEurPerTco2 : 0;
  }

  private pickDefaultScenarioPrice(selectedScenario?: string): number {
    if (!selectedScenario) return 95;
    const s = selectedScenario.toLowerCase();
    if (s.includes('low')) return 60;
    if (s.includes('high')) return 120;
    return 95;
  }

  private renderSimplePdf(lines: string[]): Buffer {
    const escapePdfText = (txt: string): string =>
      txt.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)');

    let y = 810;
    const contentOps: string[] = [];
    for (const line of lines) {
      if (line === '') {
        y -= 10;
        continue;
      }
      if (y < 40) break;
      const size = line === 'EU ETS Management Report (Planning)' ? 16 : 10;
      contentOps.push(`BT /F1 ${size} Tf 40 ${y} Td (${escapePdfText(line)}) Tj ET`);
      y -= size + 5;
    }

    const content = contentOps.join('\n') + '\n';

    const obj1 = '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n';
    const obj2 = '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n';
    const obj3 =
      '3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n';
    const obj4 = '4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n';
    const obj5 = `5 0 obj\n<< /Length ${Buffer.byteLength(content, 'utf8')} >>\nstream\n${content}endstream\nendobj\n`;

    const parts = ['%PDF-1.4\n', obj1, obj2, obj3, obj4, obj5];
    const offsets: number[] = [0];
    let cursor = Buffer.byteLength(parts[0], 'utf8');
    for (let i = 1; i < parts.length; i++) {
      offsets.push(cursor);
      cursor += Buffer.byteLength(parts[i], 'utf8');
    }

    return this.buildPdfDocument(content);
  }

  private renderDarkPdfReport(
    analysis: AnalyzeResponse,
    owner: string,
    generatedLabel: string,
  ): Buffer {
    const esc = (txt: string): string =>
      txt
        .replace(/\\/g, '\\\\')
        .replace(/\(/g, '\\(')
        .replace(/\)/g, '\\)');
    const n2 = (n: number): string => n.toFixed(2);
    const n0 = (n: number): string => n.toFixed(0);
    const ops: string[] = [];

    const text = (
      x: number,
      y: number,
      size: number,
      value: string,
      color: [number, number, number],
    ) => {
      ops.push(`${color[0]} ${color[1]} ${color[2]} rg BT /F1 ${size} Tf ${x} ${y} Td (${esc(value)}) Tj ET`);
    };
    const fillRect = (
      x: number,
      y: number,
      w: number,
      h: number,
      color: [number, number, number],
    ) => {
      ops.push(`${color[0]} ${color[1]} ${color[2]} rg ${x} ${y} ${w} ${h} re f`);
    };
    const strokeRect = (
      x: number,
      y: number,
      w: number,
      h: number,
      color: [number, number, number],
      lineW = 1,
    ) => {
      ops.push(`${color[0]} ${color[1]} ${color[2]} RG ${lineW} w ${x} ${y} ${w} ${h} re S`);
    };
    const line = (
      x1: number,
      y1: number,
      x2: number,
      y2: number,
      color: [number, number, number],
      lineW = 1,
    ) => {
      ops.push(`${color[0]} ${color[1]} ${color[2]} RG ${lineW} w ${x1} ${y1} m ${x2} ${y2} l S`);
    };

    const bg: [number, number, number] = [0.03, 0.03, 0.04];
    const panel: [number, number, number] = [0.07, 0.07, 0.09];
    const accent: [number, number, number] = [0.0, 0.9, 0.67];
    const textMain: [number, number, number] = [0.93, 0.95, 0.97];
    const muted: [number, number, number] = [0.62, 0.68, 0.72];
    const cyan: [number, number, number] = [0.2, 0.9, 1.0];
    const purple: [number, number, number] = [0.71, 0.22, 0.95];
    const amber: [number, number, number] = [0.96, 0.66, 0.14];

    fillRect(0, 0, 595, 842, bg);
    fillRect(18, 18, 559, 806, panel);
    line(24, 788, 571, 788, accent, 2);

    text(30, 805, 17, 'EU ETS Management Report (Dark Theme)', textMain);
    text(30, 790, 9, `Prepared by: ${owner}`, accent);
    text(30, 776, 9, `Generated: ${generatedLabel}`, muted);
    text(350, 776, 9, `Workbook: ${analysis.sourceName}`, muted);

    const cards = [
      { label: 'Scope 1 (tCO2)', value: n2(analysis.scope1TotalTco2) },
      { label: 'Net EUA (planning)', value: n2(analysis.netEuaRequirementTco2) },
      { label: 'Selected ETS (EUR)', value: n0(analysis.selectedEtsCostEur) },
      { label: '+20% power impact (EUR)', value: n0(analysis.electricityPlus20PctImpactEur) },
    ];
    const cw = 130;
    for (let i = 0; i < cards.length; i++) {
      const x = 30 + i * (cw + 8);
      fillRect(x, 704, cw, 58, [0.05, 0.05, 0.07]);
      strokeRect(x, 704, cw, 58, [0.12, 0.18, 0.2], 1);
      text(x + 8, 744, 8, cards[i].label, muted);
      text(x + 8, 720, 12, cards[i].value, textMain);
    }

    fillRect(30, 468, 260, 214, [0.045, 0.045, 0.06]);
    strokeRect(30, 468, 260, 214, [0.15, 0.2, 0.24], 1);
    text(38, 668, 10, 'Scenario ETS Cost (EUR)', textMain);
    line(50, 490, 270, 490, [0.25, 0.3, 0.35], 1);
    line(50, 490, 50, 640, [0.25, 0.3, 0.35], 1);
    const sc = analysis.scenarioTable.slice(0, 3);
    const maxCost = Math.max(1, ...sc.map((s) => s.etsCostEur));
    sc.forEach((s, i) => {
      const bw = 45;
      const x = 70 + i * 70;
      const h = (s.etsCostEur / maxCost) * 135;
      fillRect(x, 490, bw, h, accent);
      text(x + 5, 476, 8, s.scenario, muted);
    });

    fillRect(305, 468, 260, 214, [0.045, 0.045, 0.06]);
    strokeRect(305, 468, 260, 214, [0.15, 0.2, 0.24], 1);
    text(313, 668, 10, 'Monthly ETS Trend (Selected)', textMain);
    line(325, 490, 545, 490, [0.25, 0.3, 0.35], 1);
    line(325, 490, 325, 640, [0.25, 0.3, 0.35], 1);
    const ts = analysis.periodSeries;
    const yMax = Math.max(1, ...ts.map((r) => r.etsCostSelectedEur));
    for (let i = 1; i < ts.length; i++) {
      const x1 = 325 + ((i - 1) / Math.max(1, ts.length - 1)) * 220;
      const x2 = 325 + (i / Math.max(1, ts.length - 1)) * 220;
      const y1 = 490 + (ts[i - 1].etsCostSelectedEur / yMax) * 140;
      const y2 = 490 + (ts[i].etsCostSelectedEur / yMax) * 140;
      line(x1, y1, x2, y2, cyan, 1.4);
    }

    fillRect(30, 204, 535, 248, [0.045, 0.045, 0.06]);
    strokeRect(30, 204, 535, 248, [0.15, 0.2, 0.24], 1);
    text(38, 436, 10, 'Diagnostics Table', textMain);
    line(38, 420, 557, 420, [0.2, 0.24, 0.28], 1);
    text(42, 408, 8, 'Metric', muted);
    text(320, 408, 8, 'Value', muted);
    const latestVar = analysis.varianceDecomposition.slice(-1)[0];
    const topOpp = analysis.opportunityShortlist[0];
    const rows: Array<[string, string, [number, number, number]]> = [
      ['Scope 2 total (tCO2)', n2(analysis.scope2TotalTco2), textMain],
      ['Scope 3 proxy total (tCO2)', n2(analysis.scope3TotalTco2), textMain],
      ['Break-even EUA (EUR/tCO2)', n2(analysis.breakEvenEuaEurPerTco2), amber],
      [
        'Latest variance delta (tCO2)',
        latestVar ? n2(latestVar.deltaCo2T) : 'n/a',
        latestVar && latestVar.deltaCo2T >= 0 ? [1, 0.42, 0.35] : accent,
      ],
      [
        'Top opportunity driver',
        topOpp ? `${topOpp.driver} (${n2(topOpp.impactTco2)})` : 'n/a',
        purple,
      ],
      [
        'Boundary statement',
        'ETS cost based on Scope 1; Scope 2/3 for context.',
        muted,
      ],
    ];
    rows.forEach((r, i) => {
      const y = 390 - i * 28;
      line(38, y - 8, 557, y - 8, [0.12, 0.16, 0.2], 0.8);
      text(42, y, 9, r[0], textMain);
      text(320, y, 9, r[1], r[2]);
    });

    text(30, 32, 8, 'Monthly close pack: management summary + investigate list + actions register.', muted);
    const content = ops.join('\n') + '\n';
    return this.buildPdfDocument(content);
  }

  private buildPdfDocument(content: string): Buffer {
    const obj1 = '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n';
    const obj2 = '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n';
    const obj3 =
      '3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n';
    const obj4 = '4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n';
    const obj5 = `5 0 obj\n<< /Length ${Buffer.byteLength(content, 'utf8')} >>\nstream\n${content}endstream\nendobj\n`;
    const parts = ['%PDF-1.4\n', obj1, obj2, obj3, obj4, obj5];
    const offsets: number[] = [0];
    let cursor = Buffer.byteLength(parts[0], 'utf8');
    for (let i = 1; i < parts.length; i++) {
      offsets.push(cursor);
      cursor += Buffer.byteLength(parts[i], 'utf8');
    }

    let pdf = parts.join('');
    const xrefStart = Buffer.byteLength(pdf, 'utf8');
    const xrefRows = [
      '0000000000 65535 f ',
      ...offsets.slice(1).map((n) => `${n.toString().padStart(10, '0')} 00000 n `),
    ];
    pdf += `xref\n0 ${xrefRows.length}\n${xrefRows.join('\n')}\n`;
    pdf += `trailer\n<< /Size ${xrefRows.length} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF\n`;
    return Buffer.from(pdf, 'utf8');
  }
}
