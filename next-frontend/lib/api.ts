export interface ScenarioRow {
  scenario: string;
  euaEurPerTco2: number;
  etsCostEur: number;
}

export interface PeriodSeriesRow {
  period: string;
  elecMwh: number;
  gasNm3: number;
  gasMwh: number;
  otherFuelMwh: number;
  steamMwh: number;
  prodT: number;
  scope1Tco2: number;
  scope2Tco2: number;
  scope3Tco2: number;
  scope12Tco2: number;
  scope123Tco2: number;
  energyTotalMwh: number;
  energyIntensityMwhPerT: number;
  scope1IntensityTPerT: number;
  intensityKgPerT: number;
  etsCostLowEur: number;
  etsCostMidEur: number;
  etsCostHighEur: number;
  etsCostSelectedEur: number;
  electricityPriceEurPerMwh: number;
  electricityCostEur: number;
}

export interface VarianceDecompositionRow {
  period: string;
  deltaCo2T: number;
  productionEffectT: number;
  energyIntensityEffectT: number;
  fuelMixEffectT: number;
  factorAssumptionEffectT: number;
}

export interface QualityRow {
  period: string;
  grade: "A" | "B" | "C";
  flags: string[];
}

export interface AssumptionRow {
  name: string;
  value: number;
  unit: string;
  source: string;
  validityDate: string;
  note: string;
}

export interface MarketScenarioRow {
  scenario: string;
  electricityPriceMultiplier: number;
  electricityCostEur: number;
  etsCostEur: number;
  totalCostEur: number;
}

export interface ActionRow {
  action: string;
  owner: string;
  dueDate: string;
  expectedSavingsMwh: number;
  co2ImpactT: number;
  eurImpact: number;
  capexEur: number;
  paybackYears: number;
  actualSavingsMwh: number;
}

export interface ReconciliationRow {
  period: string;
  expectedScope1FromEnergyT: number;
  reportedScope1T: number;
  deviationPct: number;
  flag: string;
}

export interface OpportunityRow {
  driver: string;
  impactTco2: number;
  direction: "INCREASE" | "DECREASE";
  note: string;
}

export interface AnalyzeResponse {
  sourceName: string;
  periods: number;
  scope1TotalTco2: number;
  scope2TotalTco2: number;
  scope3TotalTco2: number;
  scope12TotalTco2: number;
  scope123TotalTco2: number;
  selectedScenario: string;
  selectedEuaPrice: number;
  selectedEtsCostEur: number;
  netEuaRequirementTco2: number;
  deltaPer10Eur: number;
  scenarioTable: ScenarioRow[];
  planningCases: ScenarioRow[];
  periodSeries: PeriodSeriesRow[];
  varianceDecomposition: VarianceDecompositionRow[];
  qualityChecks: QualityRow[];
  assumptions: AssumptionRow[];
  marketScenarios: MarketScenarioRow[];
  actionsRegister: ActionRow[];
  reconciliationChecks: ReconciliationRow[];
  opportunityShortlist: OpportunityRow[];
  electricityPlus20PctImpactEur: number;
  breakEvenEuaEurPerTco2: number;
  warnings: string[];
}

export interface PortfolioSiteRow {
  site: string;
  scope1Tco2: number;
  scope2Tco2: number;
  scope3Tco2: number;
  scope123Tco2: number;
  etsBaseEur: number;
  etsStressEur: number;
  etsHighEur: number;
  etsSelectedEur: number;
  deltaVsBaseEur: number;
  status: "GREEN" | "AMBER" | "RED";
}

export interface PortfolioResponse {
  sitesProcessed: number;
  totalScope1Tco2: number;
  totalScope2Tco2: number;
  totalScope3Tco2: number;
  totalScope123Tco2: number;
  totalSelectedEtsEur: number;
  centralEuaPrice: number;
  siteTable: PortfolioSiteRow[];
  errors: string[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:4000/api";

export async function analyzeSingle(payload: {
  file: File;
  selectedScenario?: string;
  customEuaPrice?: number;
  basePrice?: number;
  stressPrice?: number;
  highPrice?: number;
  scope3FactorTco2PerT?: number;
  freeAllocationTco2?: number;
  measureReductionPct?: number;
  measureAnnualizedCostEur?: number;
}): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("workbook", payload.file);
  if (payload.selectedScenario) form.append("selectedScenario", payload.selectedScenario);
  if (payload.customEuaPrice !== undefined) form.append("customEuaPrice", String(payload.customEuaPrice));
  if (payload.basePrice !== undefined) form.append("basePrice", String(payload.basePrice));
  if (payload.stressPrice !== undefined) form.append("stressPrice", String(payload.stressPrice));
  if (payload.highPrice !== undefined) form.append("highPrice", String(payload.highPrice));
  if (payload.scope3FactorTco2PerT !== undefined)
    form.append("scope3FactorTco2PerT", String(payload.scope3FactorTco2PerT));
  if (payload.freeAllocationTco2 !== undefined)
    form.append("freeAllocationTco2", String(payload.freeAllocationTco2));
  if (payload.measureReductionPct !== undefined)
    form.append("measureReductionPct", String(payload.measureReductionPct));
  if (payload.measureAnnualizedCostEur !== undefined)
    form.append("measureAnnualizedCostEur", String(payload.measureAnnualizedCostEur));

  const res = await fetch(`${API_BASE}/ets/analyze`, { method: "POST", body: form });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || "Single-site analysis failed");
  }
  return (await res.json()) as AnalyzeResponse;
}

export async function analyzePortfolio(payload: {
  files: File[];
  selectedScenario?: string;
  customEuaPrice?: number;
  basePrice?: number;
  stressPrice?: number;
  highPrice?: number;
  scope3FactorTco2PerT?: number;
  freeAllocationTco2?: number;
  measureReductionPct?: number;
  measureAnnualizedCostEur?: number;
  amberThresholdEur?: number;
  redThresholdEur?: number;
}): Promise<PortfolioResponse> {
  const form = new FormData();
  payload.files.forEach((f) => form.append("workbooks", f));
  if (payload.selectedScenario) form.append("selectedScenario", payload.selectedScenario);
  if (payload.customEuaPrice !== undefined) form.append("customEuaPrice", String(payload.customEuaPrice));
  if (payload.basePrice !== undefined) form.append("basePrice", String(payload.basePrice));
  if (payload.stressPrice !== undefined) form.append("stressPrice", String(payload.stressPrice));
  if (payload.highPrice !== undefined) form.append("highPrice", String(payload.highPrice));
  if (payload.scope3FactorTco2PerT !== undefined)
    form.append("scope3FactorTco2PerT", String(payload.scope3FactorTco2PerT));
  if (payload.freeAllocationTco2 !== undefined)
    form.append("freeAllocationTco2", String(payload.freeAllocationTco2));
  if (payload.measureReductionPct !== undefined)
    form.append("measureReductionPct", String(payload.measureReductionPct));
  if (payload.measureAnnualizedCostEur !== undefined)
    form.append("measureAnnualizedCostEur", String(payload.measureAnnualizedCostEur));
  if (payload.amberThresholdEur !== undefined) form.append("amberThresholdEur", String(payload.amberThresholdEur));
  if (payload.redThresholdEur !== undefined) form.append("redThresholdEur", String(payload.redThresholdEur));

  const res = await fetch(`${API_BASE}/ets/portfolio`, { method: "POST", body: form });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || "Portfolio analysis failed");
  }
  return (await res.json()) as PortfolioResponse;
}

export async function downloadSinglePdf(payload: {
  file: File;
  reportOwner?: string;
  selectedScenario?: string;
  customEuaPrice?: number;
  basePrice?: number;
  stressPrice?: number;
  highPrice?: number;
  scope3FactorTco2PerT?: number;
  freeAllocationTco2?: number;
  measureReductionPct?: number;
  measureAnnualizedCostEur?: number;
}): Promise<Blob> {
  const form = new FormData();
  form.append("workbook", payload.file);
  if (payload.reportOwner) form.append("reportOwner", payload.reportOwner);
  if (payload.selectedScenario) form.append("selectedScenario", payload.selectedScenario);
  if (payload.customEuaPrice !== undefined) form.append("customEuaPrice", String(payload.customEuaPrice));
  if (payload.basePrice !== undefined) form.append("basePrice", String(payload.basePrice));
  if (payload.stressPrice !== undefined) form.append("stressPrice", String(payload.stressPrice));
  if (payload.highPrice !== undefined) form.append("highPrice", String(payload.highPrice));
  if (payload.scope3FactorTco2PerT !== undefined)
    form.append("scope3FactorTco2PerT", String(payload.scope3FactorTco2PerT));
  if (payload.freeAllocationTco2 !== undefined)
    form.append("freeAllocationTco2", String(payload.freeAllocationTco2));
  if (payload.measureReductionPct !== undefined)
    form.append("measureReductionPct", String(payload.measureReductionPct));
  if (payload.measureAnnualizedCostEur !== undefined)
    form.append("measureAnnualizedCostEur", String(payload.measureAnnualizedCostEur));

  const res = await fetch(`${API_BASE}/ets/report`, { method: "POST", body: form });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || "PDF report generation failed");
  }
  return await res.blob();
}
