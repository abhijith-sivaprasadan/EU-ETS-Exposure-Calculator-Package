"use client";

import { useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  analyzePortfolio,
  analyzeSingle,
  AnalyzeResponse,
  downloadSinglePdf,
  PortfolioResponse,
} from "../lib/api";

type Mode = "single" | "portfolio";

type Tab = "summary" | "cost" | "intensity" | "planning" | "close" | "actions";

const sectionVariants = {
  hidden: { opacity: 0, y: 14, filter: "blur(4px)" },
  show: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.55 } },
};

function fmtNum(v: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(v);
}

function fmtCur(v: number): string {
  return `EUR ${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(v)}`;
}

export default function Page() {
  const singleInputRef = useRef<HTMLInputElement | null>(null);
  const portfolioInputRef = useRef<HTMLInputElement | null>(null);
  const [mode, setMode] = useState<Mode>("single");
  const [tab, setTab] = useState<Tab>("summary");
  const [singleFile, setSingleFile] = useState<File | null>(null);
  const [portfolioFiles, setPortfolioFiles] = useState<File[]>([]);
  const [selectedScenario, setSelectedScenario] = useState("Mid");
  const [customEua, setCustomEua] = useState<number>(95);
  const [basePrice, setBasePrice] = useState<number>(85);
  const [stressPrice, setStressPrice] = useState<number>(110);
  const [highPrice, setHighPrice] = useState<number>(140);
  const [scope3Factor, setScope3Factor] = useState<number>(0);
  const [reportOwner, setReportOwner] = useState<string>("Energy Engineer");
  const [freeAllocation, setFreeAllocation] = useState<number>(0);
  const [measureReductionPct, setMeasureReductionPct] = useState<number>(0.08);
  const [measureAnnualizedCost, setMeasureAnnualizedCost] = useState<number>(500000);
  const [amber, setAmber] = useState<number>(4_000_000);
  const [red, setRed] = useState<number>(6_000_000);
  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [err, setErr] = useState<string>("");
  const [single, setSingle] = useState<AnalyzeResponse | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);

  const risk = useMemo(() => {
    if (!single) return null;
    if (single.selectedEtsCostEur >= red) return { label: "HIGH", color: "#FF5F57" };
    if (single.selectedEtsCostEur >= amber) return { label: "MEDIUM", color: "#F5A623" };
    return { label: "LOW", color: "#2ECC71" };
  }, [single, amber, red]);

  async function runSingle() {
    const file = singleFile ?? singleInputRef.current?.files?.[0] ?? null;
    if (!file) {
      setErr("Upload a workbook first.");
      return;
    }
    setErr("");
    setLoading(true);
    try {
      const res = await analyzeSingle({
        file,
        selectedScenario,
        customEuaPrice: selectedScenario === "Custom" ? customEua : undefined,
        basePrice,
        stressPrice,
        highPrice,
        scope3FactorTco2PerT: scope3Factor,
        freeAllocationTco2: freeAllocation,
        measureReductionPct,
        measureAnnualizedCostEur: measureAnnualizedCost,
      });
      setSingle(res);
      setPortfolio(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function runPortfolio() {
    const files =
      portfolioFiles.length > 0
        ? portfolioFiles
        : Array.from(portfolioInputRef.current?.files ?? []);
    if (files.length === 0) {
      setErr("Upload one or more workbooks.");
      return;
    }
    setErr("");
    setLoading(true);
    try {
      const res = await analyzePortfolio({
        files,
        selectedScenario,
        customEuaPrice: selectedScenario === "Custom" ? customEua : undefined,
        basePrice,
        stressPrice,
        highPrice,
        scope3FactorTco2PerT: scope3Factor,
        freeAllocationTco2: freeAllocation,
        measureReductionPct,
        measureAnnualizedCostEur: measureAnnualizedCost,
        amberThresholdEur: amber,
        redThresholdEur: red,
      });
      setPortfolio(res);
      setSingle(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function downloadPdfReport() {
    const file = singleFile ?? singleInputRef.current?.files?.[0] ?? null;
    if (!file) {
      setErr("Upload a workbook first.");
      return;
    }
    setErr("");
    setPdfLoading(true);
    try {
      const blob = await downloadSinglePdf({
        file,
        reportOwner,
        selectedScenario,
        customEuaPrice: selectedScenario === "Custom" ? customEua : undefined,
        basePrice,
        stressPrice,
        highPrice,
        scope3FactorTco2PerT: scope3Factor,
        freeAllocationTco2: freeAllocation,
        measureReductionPct,
        measureAnnualizedCostEur: measureAnnualizedCost,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "ets_management_report.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setPdfLoading(false);
    }
  }

  return (
    <main>
      <motion.div className="grid" initial="hidden" animate="show" variants={sectionVariants}>
        <div>
          <h1 className="h1">EU ETS Portfolio Studio</h1>
          <p className="muted">Next.js + Framer Motion frontend connected to NestJS ETS analysis APIs.</p>
        </div>

        <div className="panel grid cols-5">
          <div>
            <label>Mode</label>
            <select value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
              <option value="single">Single Site</option>
              <option value="portfolio">Portfolio</option>
            </select>
          </div>
          <div>
            <label>Primary Scenario</label>
            <select value={selectedScenario} onChange={(e) => setSelectedScenario(e.target.value)}>
              <option>Low</option>
              <option>Mid</option>
              <option>High</option>
              <option>Custom</option>
            </select>
          </div>
          <div>
            <label>Custom EUA (EUR/tCO2)</label>
            <input type="number" value={customEua} onChange={(e) => setCustomEua(Number(e.target.value))} />
          </div>
          <div>
            <label>Run</label>
            <button onClick={mode === "single" ? runSingle : runPortfolio} disabled={loading}>
              {loading ? "Running..." : "Analyze"}
            </button>
          </div>
          {mode === "single" && (
            <div>
              <label>Report</label>
              <button onClick={downloadPdfReport} disabled={pdfLoading}>
                {pdfLoading ? "Generating..." : "Download PDF"}
              </button>
            </div>
          )}
        </div>

        <div className="panel grid cols-4">
          <div>
            <label>Base EUA</label>
            <input type="number" value={basePrice} onChange={(e) => setBasePrice(Number(e.target.value))} />
          </div>
          <div>
            <label>Stress EUA</label>
            <input type="number" value={stressPrice} onChange={(e) => setStressPrice(Number(e.target.value))} />
          </div>
          <div>
            <label>High EUA</label>
            <input type="number" value={highPrice} onChange={(e) => setHighPrice(Number(e.target.value))} />
          </div>
          <div>
            <label>Guardrails (Amber / Red)</label>
            <div className="grid cols-2">
              <input type="number" value={amber} onChange={(e) => setAmber(Number(e.target.value))} />
              <input type="number" value={red} onChange={(e) => setRed(Number(e.target.value))} />
            </div>
          </div>
          <div>
            <label>Scope 3 Factor (tCO2 / t)</label>
            <input
              type="number"
              step="0.01"
              value={scope3Factor}
              onChange={(e) => setScope3Factor(Number(e.target.value))}
            />
          </div>
        </div>

        <div className="panel grid cols-3">
          <div>
            <label>Report Owner (PDF)</label>
            <input
              type="text"
              value={reportOwner}
              onChange={(e) => setReportOwner(e.target.value)}
              placeholder="Your name"
            />
          </div>
        </div>

        <div className="panel grid cols-3">
          <div>
            <label>Free Allocation (tCO2)</label>
            <input
              type="number"
              value={freeAllocation}
              onChange={(e) => setFreeAllocation(Number(e.target.value))}
            />
          </div>
          <div>
            <label>Measure Reduction (%)</label>
            <input
              type="number"
              step="0.01"
              value={measureReductionPct}
              onChange={(e) => setMeasureReductionPct(Number(e.target.value))}
            />
          </div>
          <div>
            <label>Measure Annualized Cost (EUR)</label>
            <input
              type="number"
              value={measureAnnualizedCost}
              onChange={(e) => setMeasureAnnualizedCost(Number(e.target.value))}
            />
          </div>
        </div>

        {mode === "single" ? (
          <div className="panel">
            <label>Single workbook</label>
            <input
              ref={singleInputRef}
              type="file"
              accept=".xlsx"
              onChange={(e) => setSingleFile(e.target.files?.[0] ?? null)}
            />
          </div>
        ) : (
          <div className="panel">
            <label>Portfolio workbooks</label>
            <input
              ref={portfolioInputRef}
              type="file"
              accept=".xlsx"
              multiple
              onChange={(e) => setPortfolioFiles(Array.from(e.target.files ?? []))}
            />
          </div>
        )}

        {err && <div className="err">{err}</div>}

        {single && (
          <motion.section className="grid" initial="hidden" animate="show" variants={sectionVariants}>
            <div className="grid cols-7">
              <div className="metric">
                <div className="label">Source</div>
                <div className="value">{single.sourceName}</div>
              </div>
              <div className="metric">
                <div className="label">Scope 1 CO2</div>
                <div className="value">{fmtNum(single.scope1TotalTco2)} tCO2</div>
              </div>
              <div className="metric">
                <div className="label">Scope 2 CO2</div>
                <div className="value">{fmtNum(single.scope2TotalTco2)} tCO2</div>
              </div>
              <div className="metric">
                <div className="label">Scope 3 CO2</div>
                <div className="value">{fmtNum(single.scope3TotalTco2)} tCO2</div>
              </div>
              <div className="metric">
                <div className="label">Selected ETS Cost (Scope 1)</div>
                <div className="value">{fmtCur(single.selectedEtsCostEur)}</div>
              </div>
              <div className="metric">
                <div className="label">Net EUA Requirement</div>
                <div className="value">{fmtNum(single.netEuaRequirementTco2)} tCO2</div>
              </div>
              <div className="metric">
                <div className="label">Risk</div>
                <div className="value" style={{ color: risk?.color ?? "#EDEDED" }}>
                  {risk?.label ?? "-"}
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="tabs">
                {(["summary", "cost", "intensity", "planning", "close", "actions"] as Tab[]).map((t) => (
                  <button key={t} className={`tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
                    {t.toUpperCase()}
                  </button>
                ))}
              </div>

              {tab === "summary" && (
                <div className="grid cols-2">
                  <div style={{ height: 320 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={single.periodSeries}>
                        <CartesianGrid stroke="#2a2a2a" />
                        <XAxis dataKey="period" stroke="#E6EDF3" interval="preserveStartEnd" />
                        <YAxis stroke="#E6EDF3" />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="scope1Tco2" stroke="#00E6A8" strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="scope2Tco2" stroke="#2AF5FF" strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="scope3Tco2" stroke="#B537F2" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div style={{ height: 320 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={single.scenarioTable}>
                        <CartesianGrid stroke="#2a2a2a" />
                        <XAxis dataKey="scenario" stroke="#E6EDF3" />
                        <YAxis stroke="#E6EDF3" />
                        <Tooltip />
                        <Bar dataKey="etsCostEur" fill="#00E6A8" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {tab === "cost" && (
                <div style={{ height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={single.periodSeries}>
                      <CartesianGrid stroke="#2a2a2a" />
                      <XAxis dataKey="period" stroke="#E6EDF3" interval="preserveStartEnd" />
                      <YAxis stroke="#E6EDF3" />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="etsCostSelectedEur"
                        name="Selected"
                        stroke="#2AF5FF"
                        strokeWidth={2.4}
                        dot={false}
                      />
                      <Line type="monotone" dataKey="etsCostLowEur" name="Low" stroke="#00E6A8" dot={false} />
                      <Line type="monotone" dataKey="etsCostMidEur" name="Mid" stroke="#F5A623" dot={false} />
                      <Line type="monotone" dataKey="etsCostHighEur" name="High" stroke="#FF5F57" dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {tab === "intensity" && (
                <div style={{ height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={single.periodSeries}>
                      <CartesianGrid stroke="#2a2a2a" />
                      <XAxis dataKey="period" stroke="#E6EDF3" interval="preserveStartEnd" />
                      <YAxis stroke="#E6EDF3" />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="intensityKgPerT"
                        name="kgCO2/t"
                        stroke="#B537F2"
                        strokeWidth={2.4}
                        dot={false}
                      />
                      <Line type="monotone" dataKey="prodT" name="Production (t)" stroke="#00E6A8" dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {tab === "planning" && (
                <div style={{ height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={single.planningCases}>
                      <CartesianGrid stroke="#2a2a2a" />
                      <XAxis dataKey="scenario" stroke="#E6EDF3" />
                      <YAxis stroke="#E6EDF3" />
                      <Tooltip />
                      <Bar dataKey="etsCostEur" fill="#B537F2" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {tab === "close" && (
                <div className="grid">
                  <div style={{ height: 280 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={single.periodSeries}>
                        <CartesianGrid stroke="#2a2a2a" />
                        <XAxis dataKey="period" stroke="#E6EDF3" interval="preserveStartEnd" />
                        <YAxis stroke="#E6EDF3" />
                        <Tooltip />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="energyIntensityMwhPerT"
                          name="Energy Intensity (MWh/t)"
                          stroke="#2AF5FF"
                          dot={false}
                        />
                        <Line
                          type="monotone"
                          dataKey="scope1IntensityTPerT"
                          name="CO2 Intensity Scope1 (t/t)"
                          stroke="#F5A623"
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="panel">
                    <div className="label">Variance Decomposition (Scope 1 CO2)</div>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Period</th>
                          <th>Delta tCO2</th>
                          <th>Production</th>
                          <th>Energy Intensity</th>
                          <th>Fuel Mix</th>
                          <th>Factor/Assumption</th>
                        </tr>
                      </thead>
                      <tbody>
                        {single.varianceDecomposition.slice(-6).map((r) => (
                          <tr key={r.period}>
                            <td>{r.period}</td>
                            <td>{fmtNum(r.deltaCo2T)}</td>
                            <td>{fmtNum(r.productionEffectT)}</td>
                            <td>{fmtNum(r.energyIntensityEffectT)}</td>
                            <td>{fmtNum(r.fuelMixEffectT)}</td>
                            <td>{fmtNum(r.factorAssumptionEffectT)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="panel">
                    <div className="label">Data Quality Grade</div>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Period</th>
                          <th>Grade</th>
                          <th>Flags</th>
                        </tr>
                      </thead>
                      <tbody>
                        {single.qualityChecks.slice(-6).map((q) => (
                          <tr key={q.period}>
                            <td>{q.period}</td>
                            <td>{q.grade}</td>
                            <td>{q.flags.join(", ") || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="panel">
                    <div className="label">Energy-CO2 Reconciliation Check</div>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Period</th>
                          <th>Expected tCO2</th>
                          <th>Reported tCO2</th>
                          <th>Deviation %</th>
                          <th>Flag</th>
                        </tr>
                      </thead>
                      <tbody>
                        {single.reconciliationChecks.slice(-6).map((r) => (
                          <tr key={r.period}>
                            <td>{r.period}</td>
                            <td>{fmtNum(r.expectedScope1FromEnergyT)}</td>
                            <td>{fmtNum(r.reportedScope1T)}</td>
                            <td>{fmtNum(r.deviationPct)}</td>
                            <td>{r.flag}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {tab === "actions" && (
                <div className="grid">
                  <div className="panel">
                    <div className="label">
                      Action Register (expected vs actual) | Break-even EUA: {fmtNum(single.breakEvenEuaEurPerTco2)} EUR/tCO2
                    </div>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Action</th>
                          <th>Owner</th>
                          <th>Due</th>
                          <th>Exp. MWh</th>
                          <th>Act. MWh</th>
                          <th>CO2 Impact (t)</th>
                          <th>EUR Impact</th>
                          <th>CAPEX</th>
                          <th>Payback (y)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {single.actionsRegister.map((a) => (
                          <tr key={a.action}>
                            <td>{a.action}</td>
                            <td>{a.owner}</td>
                            <td>{a.dueDate}</td>
                            <td>{fmtNum(a.expectedSavingsMwh)}</td>
                            <td>{fmtNum(a.actualSavingsMwh)}</td>
                            <td>{fmtNum(a.co2ImpactT)}</td>
                            <td>{fmtCur(a.eurImpact)}</td>
                            <td>{fmtCur(a.capexEur)}</td>
                            <td>{fmtNum(a.paybackYears)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="grid cols-2">
                    <div className="panel">
                      <div className="label">
                        Electricity Market Sensitivity | +20% impact: {fmtCur(single.electricityPlus20PctImpactEur)}
                      </div>
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Scenario</th>
                            <th>Elec Cost</th>
                            <th>ETS Cost</th>
                            <th>Total Cost</th>
                          </tr>
                        </thead>
                        <tbody>
                          {single.marketScenarios.map((m) => (
                            <tr key={m.scenario}>
                              <td>{m.scenario}</td>
                              <td>{fmtCur(m.electricityCostEur)}</td>
                              <td>{fmtCur(m.etsCostEur)}</td>
                              <td>{fmtCur(m.totalCostEur)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="panel">
                      <div className="label">Assumptions Register</div>
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Parameter</th>
                            <th>Value</th>
                            <th>Unit</th>
                            <th>Source</th>
                          </tr>
                        </thead>
                        <tbody>
                          {single.assumptions.map((a) => (
                            <tr key={a.name}>
                              <td>{a.name}</td>
                              <td>{fmtNum(a.value)}</td>
                              <td>{a.unit}</td>
                              <td>{a.source}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div className="panel">
                    <div className="label">Opportunity Shortlist (Top 5 drivers)</div>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Driver</th>
                          <th>Impact (tCO2)</th>
                          <th>Direction</th>
                          <th>Note</th>
                        </tr>
                      </thead>
                      <tbody>
                        {single.opportunityShortlist.map((o) => (
                          <tr key={o.driver}>
                            <td>{o.driver}</td>
                            <td>{fmtNum(o.impactTco2)}</td>
                            <td>{o.direction}</td>
                            <td>{o.note}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </motion.section>
        )}

        {portfolio && (
          <motion.section className="grid" initial="hidden" animate="show" variants={sectionVariants}>
            <div className="grid cols-6">
              <div className="metric"><div className="label">Sites</div><div className="value">{portfolio.sitesProcessed}</div></div>
              <div className="metric"><div className="label">Portfolio Scope 1</div><div className="value">{fmtNum(portfolio.totalScope1Tco2)} tCO2</div></div>
              <div className="metric"><div className="label">Portfolio Scope 2</div><div className="value">{fmtNum(portfolio.totalScope2Tco2)} tCO2</div></div>
              <div className="metric"><div className="label">Portfolio Scope 3</div><div className="value">{fmtNum(portfolio.totalScope3Tco2)} tCO2</div></div>
              <div className="metric"><div className="label">Portfolio ETS Cost (Scope 1)</div><div className="value">{fmtCur(portfolio.totalSelectedEtsEur)}</div></div>
              <div className="metric"><div className="label">Central EUA</div><div className="value">{fmtNum(portfolio.centralEuaPrice)} EUR/tCO2</div></div>
            </div>

            <div className="panel">
              <table className="table">
                <thead>
                  <tr>
                    <th>Site</th>
                    <th>Scope 1 (tCO2)</th>
                    <th>Scope 2 (tCO2)</th>
                    <th>Scope 3 (tCO2)</th>
                    <th>Selected ETS (EUR)</th>
                    <th>Delta vs Base</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {portfolio.siteTable.map((row) => (
                    <tr key={row.site}>
                      <td>{row.site}</td>
                      <td>{fmtNum(row.scope1Tco2)}</td>
                      <td>{fmtNum(row.scope2Tco2)}</td>
                      <td>{fmtNum(row.scope3Tco2)}</td>
                      <td>{fmtCur(row.etsSelectedEur)}</td>
                      <td>{fmtCur(row.deltaVsBaseEur)}</td>
                      <td>
                        <span className="badge">{row.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="panel" style={{ height: 340 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={portfolio.siteTable}>
                  <CartesianGrid stroke="#2a2a2a" />
                  <XAxis dataKey="site" stroke="#E6EDF3" />
                  <YAxis stroke="#E6EDF3" />
                  <Tooltip />
                  <Bar dataKey="etsSelectedEur" fill="#00E6A8" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.section>
        )}
      </motion.div>
    </main>
  );
}
