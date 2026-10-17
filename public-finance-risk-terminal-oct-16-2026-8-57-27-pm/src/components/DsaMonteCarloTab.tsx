import React, { useState, useMemo } from 'react';
import { PublicFinanceEntity, StressScenario } from '../types/finance';
import { runDsaMonteCarlo } from '../utils/dsaCalculations';
import {
  TrendingUp,
  Activity,
  Sliders,
  HelpCircle,
  RefreshCw,
  AlertTriangle,
  Info
} from 'lucide-react';

interface DsaMonteCarloTabProps {
  entity: PublicFinanceEntity;
  activeScenario: StressScenario;
  onOpenFormulaModal: () => void;
}

export const DsaMonteCarloTab: React.FC<DsaMonteCarloTabProps> = ({
  entity,
  activeScenario,
  onOpenFormulaModal,
}) => {
  // Interactive real-time overrides for interest rate, growth, and primary balance
  const [realInterestRate, setRealInterestRate] = useState<number>(3.2);
  const [realGrowthRate, setRealGrowthRate] = useState<number>(2.0);
  const [primaryBalance, setPrimaryBalance] = useState<number>(-0.5);
  const [simSeed, setSimSeed] = useState<number>(1);

  // Compute simulation
  const dsaResult = useMemo(() => {
    // Merge overrides with active scenario
    const mergedScenario: StressScenario = {
      ...activeScenario,
      interestRateDeltaBps: Math.round((realInterestRate - 3.0) * 100),
      gdpGrowthShockPct: realGrowthRate - 2.0,
    };

    return runDsaMonteCarlo({
      entity,
      scenario: mergedScenario,
      projectionYears: 10,
      numSimulations: 1000,
    });
  }, [entity, activeScenario, realInterestRate, realGrowthRate, primaryBalance, simSeed]);

  // SVG Fan Chart Dimensions
  const chartWidth = 720;
  const chartHeight = 320;
  const padding = { top: 20, right: 30, bottom: 40, left: 55 };
  const innerWidth = chartWidth - padding.left - padding.right;
  const innerHeight = chartHeight - padding.top - padding.bottom;

  // Max and Min values for Y-axis
  const allValues = dsaResult.trajectory.flatMap((p) => [p.p10, p.p90, p.baseline]);
  const minY = Math.max(0, Math.floor(Math.min(...allValues) / 10) * 10 - 10);
  const maxY = Math.ceil(Math.max(...allValues, 100) / 10) * 10 + 10;

  const xScale = (index: number) => padding.left + (index / (dsaResult.trajectory.length - 1)) * innerWidth;
  const yScale = (val: number) => padding.top + innerHeight - ((val - minY) / (maxY - minY)) * innerHeight;

  // Build SVG polygon area paths
  // Area 10-90
  const area10to90 = useMemo(() => {
    const topPath = dsaResult.trajectory.map((p, i) => `${xScale(i)},${yScale(p.p90)}`).join(' L ');
    const bottomPath = [...dsaResult.trajectory].reverse().map((p, i) => {
      const idx = dsaResult.trajectory.length - 1 - i;
      return `${xScale(idx)},${yScale(p.p10)}`;
    }).join(' L ');
    return `M ${topPath} L ${bottomPath} Z`;
  }, [dsaResult, minY, maxY]);

  // Area 25-75
  const area25to75 = useMemo(() => {
    const topPath = dsaResult.trajectory.map((p, i) => `${xScale(i)},${yScale(p.p75)}`).join(' L ');
    const bottomPath = [...dsaResult.trajectory].reverse().map((p, i) => {
      const idx = dsaResult.trajectory.length - 1 - i;
      return `${xScale(idx)},${yScale(p.p25)}`;
    }).join(' L ');
    return `M ${topPath} L ${bottomPath} Z`;
  }, [dsaResult, minY, maxY]);

  // Line paths
  const medianLine = useMemo(() => {
    return dsaResult.trajectory.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)},${yScale(p.p50)}`).join(' ');
  }, [dsaResult, minY, maxY]);

  const baselineLine = useMemo(() => {
    return dsaResult.trajectory.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)},${yScale(p.baseline)}`).join(' ');
  }, [dsaResult, minY, maxY]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-cyan-400" />
            <span>IMF / World Bank Debt Sustainability Analysis (DSA) Fan Chart</span>
          </h2>
          <p className="text-xs text-slate-400">
            Stochastic Monte Carlo simulation (1,000 paths) under correlated growth, interest rate, and primary balance shocks.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSimSeed((prev) => prev + 1)}
            className="px-2.5 py-1 text-xs text-slate-300 hover:text-white bg-slate-900 border border-slate-700 rounded flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className="w-3 h-3 text-cyan-400" />
            <span>Re-run Monte Carlo</span>
          </button>
          <button
            onClick={onOpenFormulaModal}
            className="px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200 border border-slate-800 rounded flex items-center gap-1 transition-colors"
          >
            <HelpCircle className="w-3 h-3 text-cyan-400" />
            <span>DSA Equation</span>
          </button>
        </div>
      </div>

      {/* Primary KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <span className="text-xs text-slate-400 block mb-1">Debt Dynamics Classification</span>
          <span className={`font-mono text-sm font-bold block ${
            dsaResult.riskTrajectoryClassification.includes('Sustainable') ? 'text-emerald-400' :
            dsaResult.riskTrajectoryClassification.includes('Borderline') ? 'text-amber-400' : 'text-rose-400'
          }`}>
            {dsaResult.riskTrajectoryClassification}
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">
            Terminal Median: {dsaResult.terminalMedianDebtRatio.toFixed(1)}%
          </span>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <span className="text-xs text-slate-400 block mb-1">Debt-Stabilizing Primary Balance</span>
          <span className="font-mono text-lg font-bold text-cyan-300 tabular-nums">
            {dsaResult.debtStabilizingPrimaryBalance > 0 ? `+${dsaResult.debtStabilizingPrimaryBalance.toFixed(2)}%` : `${dsaResult.debtStabilizingPrimaryBalance.toFixed(2)}%`}
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">
            Required p* to freeze debt ratio
          </span>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <span className="text-xs text-slate-400 block mb-1">Effective Snowball Factor</span>
          <span className={`font-mono text-lg font-bold tabular-nums ${
            dsaResult.effectiveSnowballEffect > 0 ? 'text-rose-400' : 'text-emerald-400'
          }`}>
            {(dsaResult.effectiveSnowballEffect * 100).toFixed(2)}%
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">
            Formula: (r - g) / (1 + g)
          </span>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <span className="text-xs text-slate-400 block mb-1">Pr(Debt &gt; 90% in 10Y)</span>
          <span className={`font-mono text-lg font-bold tabular-nums ${
            dsaResult.probabilityOfExceeding90Pct > 50 ? 'text-rose-400' :
            dsaResult.probabilityOfExceeding90Pct > 20 ? 'text-amber-400' : 'text-emerald-400'
          }`}>
            {dsaResult.probabilityOfExceeding90Pct.toFixed(1)}%
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">
            Excess threshold breaches
          </span>
        </div>
      </div>

      {/* Main Fan Chart Visualization */}
      <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="text-xs font-semibold text-slate-200">
            10-Year Debt-to-GDP Trajectory Distribution (% of GDP / Operating Revenue)
          </div>
          {/* Legend */}
          <div className="flex items-center gap-4 text-xs font-mono text-slate-400 flex-wrap">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 bg-cyan-950/80 border border-cyan-700/50 rounded-xs" />
              <span>10th–90th Pct</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 bg-cyan-800/40 border border-cyan-500/60 rounded-xs" />
              <span>25th–75th Pct</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-0.5 bg-cyan-300" />
              <span className="text-cyan-300">50th (Median)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-0.5 bg-slate-400 border-dashed" />
              <span className="text-slate-300">Baseline</span>
            </div>
          </div>
        </div>

        {/* Responsive SVG Container */}
        <div className="w-full overflow-x-auto">
          <svg
            viewBox={`0 0 ${chartWidth} ${chartHeight}`}
            className="w-full h-auto max-h-[360px] font-mono text-[11px] select-none"
          >
            {/* Grid Lines */}
            {Array.from({ length: 6 }).map((_, i) => {
              const yVal = minY + (i / 5) * (maxY - minY);
              const yPos = yScale(yVal);
              return (
                <g key={i}>
                  <line
                    x1={padding.left}
                    y1={yPos}
                    x2={chartWidth - padding.right}
                    y2={yPos}
                    stroke="#1e293b"
                    strokeDasharray="3 3"
                  />
                  <text
                    x={padding.left - 8}
                    y={yPos + 4}
                    textAnchor="end"
                    fill="#64748b"
                    className="tabular-nums"
                  >
                    {yVal.toFixed(0)}%
                  </text>
                </g>
              );
            })}

            {/* X-axis labels */}
            {dsaResult.trajectory.map((p, i) => {
              const xPos = xScale(i);
              return (
                <g key={i}>
                  <line
                    x1={xPos}
                    y1={chartHeight - padding.bottom}
                    x2={xPos}
                    y2={chartHeight - padding.bottom + 5}
                    stroke="#334155"
                  />
                  <text
                    x={xPos}
                    y={chartHeight - padding.bottom + 18}
                    textAnchor="middle"
                    fill="#94a3b8"
                    className="tabular-nums"
                  >
                    {p.year}
                  </text>
                </g>
              );
            })}

            {/* Threshold Line at 90% */}
            {maxY >= 90 && minY <= 90 && (
              <g>
                <line
                  x1={padding.left}
                  y1={yScale(90)}
                  x2={chartWidth - padding.right}
                  y2={yScale(90)}
                  stroke="#ef4444"
                  strokeWidth="1.2"
                  strokeDasharray="4 4"
                />
                <text
                  x={chartWidth - padding.right - 4}
                  y={yScale(90) - 5}
                  textAnchor="end"
                  fill="#f87171"
                  className="font-bold text-[10px]"
                >
                  90% Sustainability Threshold
                </text>
              </g>
            )}

            {/* 10th-90th Percentile Shaded Polygon */}
            <path d={area10to90} fill="rgba(6, 182, 212, 0.12)" />

            {/* 25th-75th Percentile Shaded Polygon */}
            <path d={area25to75} fill="rgba(6, 182, 212, 0.25)" />

            {/* Baseline Trajectory Line */}
            <path
              d={baselineLine}
              fill="none"
              stroke="#94a3b8"
              strokeWidth="1.75"
              strokeDasharray="4 4"
            />

            {/* 50th Percentile (Median) Line */}
            <path
              d={medianLine}
              fill="none"
              stroke="#22d3ee"
              strokeWidth="2.5"
            />

            {/* Data Points on Median Line */}
            {dsaResult.trajectory.map((p, i) => (
              <circle
                key={i}
                cx={xScale(i)}
                cy={yScale(p.p50)}
                r="3.5"
                fill="#0e7490"
                stroke="#22d3ee"
                strokeWidth="1.5"
              />
            ))}
          </svg>
        </div>
      </div>

      {/* Interactive Parameter Control Sliders */}
      <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-4">
        <h3 className="text-xs font-bold text-slate-200 flex items-center gap-2">
          <Sliders className="w-3.5 h-3.5 text-cyan-400" />
          <span>Macroeconomic Driver Controls (Real-Time DSA Perturbation)</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-1">
          {/* Real Interest Rate (r) */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">Effective Real Rate (r):</span>
              <span className="font-mono text-cyan-300 font-semibold tabular-nums">
                {realInterestRate.toFixed(2)}%
              </span>
            </div>
            <input
              type="range"
              min="0.5"
              max="7.0"
              step="0.1"
              value={realInterestRate}
              onChange={(e) => setRealInterestRate(Number(e.target.value))}
              aria-label="Effective Real Interest Rate"
              className="w-full accent-cyan-400 h-1.5 bg-slate-950 rounded cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-500 font-mono">
              <span>0.5% (Accommodative)</span>
              <span>7.0% (Tight)</span>
            </div>
          </div>

          {/* Real GDP Growth Rate (g) */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">Real Economic Growth (g):</span>
              <span className="font-mono text-emerald-300 font-semibold tabular-nums">
                {realGrowthRate.toFixed(2)}%
              </span>
            </div>
            <input
              type="range"
              min="-3.0"
              max="5.0"
              step="0.1"
              value={realGrowthRate}
              onChange={(e) => setRealGrowthRate(Number(e.target.value))}
              aria-label="Real Economic Growth Rate"
              className="w-full accent-cyan-400 h-1.5 bg-slate-950 rounded cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-500 font-mono">
              <span>-3.0% (Recession)</span>
              <span>+5.0% (Boom)</span>
            </div>
          </div>

          {/* Primary Fiscal Balance (p) */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">Primary Fiscal Balance (p):</span>
              <span className={`font-mono font-semibold tabular-nums ${
                primaryBalance >= 0 ? 'text-emerald-300' : 'text-rose-300'
              }`}>
                {primaryBalance > 0 ? `+${primaryBalance.toFixed(2)}%` : `${primaryBalance.toFixed(2)}%`}
              </span>
            </div>
            <input
              type="range"
              min="-4.0"
              max="3.0"
              step="0.1"
              value={primaryBalance}
              onChange={(e) => setPrimaryBalance(Number(e.target.value))}
              aria-label="Primary Fiscal Balance"
              className="w-full accent-cyan-400 h-1.5 bg-slate-950 rounded cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-500 font-mono">
              <span>-4.0% (Deficit)</span>
              <span>+3.0% (Surplus)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
