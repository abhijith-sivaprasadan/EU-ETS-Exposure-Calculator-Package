export interface AnalyzeOptions {
  selectedScenario?: string;
  customEuaPrice?: number;
  basePrice?: number;
  stressPrice?: number;
  highPrice?: number;
  scope3FactorTco2PerT?: number;
  freeAllocationTco2?: number;
  measureReductionPct?: number;
  measureAnnualizedCostEur?: number;
}

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
  grade: 'A' | 'B' | 'C';
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
  direction: 'INCREASE' | 'DECREASE';
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
  status: 'GREEN' | 'AMBER' | 'RED';
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
