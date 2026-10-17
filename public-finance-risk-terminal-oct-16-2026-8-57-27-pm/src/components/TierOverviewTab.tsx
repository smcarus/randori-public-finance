import React, { useState } from 'react';
import { PublicFinanceEntity, StressScenario } from '../types/finance';
import { calculateMacroStressImpact } from '../utils/macroStressEngine';
import { PeerRadarComparison } from './PeerRadarComparison';
import { EntityGeoMap } from './EntityGeoMap';
import {
  TrendingDown,
  AlertTriangle,
  Building,
  Landmark,
  Coins,
  ShieldCheck,
  Activity,
  Layers,
  ArrowUpRight,
  Info
} from 'lucide-react';

interface TierOverviewTabProps {
  entity: PublicFinanceEntity;
  allEntities?: PublicFinanceEntity[];
  onSelectEntity?: (entity: PublicFinanceEntity) => void;
  activeScenario: StressScenario;
  onOpenStressModal: () => void;
  onOpenFormulaModal: () => void;
}

export const TierOverviewTab: React.FC<TierOverviewTabProps> = ({
  entity,
  allEntities,
  onSelectEntity,
  activeScenario,
  onOpenStressModal,
  onOpenFormulaModal,
}) => {
  const stressImpact = calculateMacroStressImpact(entity, activeScenario);

  // Interactive slider for Mill Rate / Assessed Value sensitivity calculator (Municipal)
  const [interactiveAvChangePct, setInteractiveAvChangePct] = useState<number>(-5);

  // Interactive slider for Discount Rate sensitivity (Subnational / Pension)
  const [selectedDiscountRateShift, setSelectedDiscountRateShift] = useState<number>(0);

  return (
    <div className="space-y-6">
      {/* Top Metric Strip - High Density Institutional KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>Direct Debt Total</span>
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div className="text-lg font-bold font-mono tabular-nums text-slate-100">
            ${entity.totalDirectDebtMillions >= 1000
              ? `${(entity.totalDirectDebtMillions / 1000).toFixed(2)}B`
              : `${entity.totalDirectDebtMillions.toLocaleString()}M`}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            {entity.tier === 'sovereign' ? 'External & Local Book' : 'Tax-Supported & Revenue'}
          </div>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>Budget / GDP Scale</span>
            <Landmark className="w-3.5 h-3.5 text-slate-500" />
          </div>
          <div className="text-lg font-bold font-mono tabular-nums text-slate-100">
            ${entity.gdpOrBudgetBillions.toFixed(1)}B
          </div>
          <div className="text-xs text-slate-500 mt-1">
            {entity.tier === 'sovereign' ? 'Nominal Annual GDP' : 'Annual Operating Budget'}
          </div>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>Weighted Avg Maturity</span>
            <span className="text-xs text-slate-500">WAM</span>
          </div>
          <div className="text-lg font-bold font-mono tabular-nums text-slate-100">
            {entity.weightedAverageMaturityYears.toFixed(1)} yrs
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Mod. Duration: {entity.modifiedDurationYears.toFixed(1)} yrs
          </div>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>Duration Gap</span>
            <Layers className="w-3.5 h-3.5 text-slate-500" />
          </div>
          <div className="text-lg font-bold font-mono tabular-nums text-slate-100">
            {entity.durationGapYears > 0 ? `+${entity.durationGapYears.toFixed(1)}` : entity.durationGapYears.toFixed(1)} yrs
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Asset vs Liability Mismatch
          </div>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>Market Access Stress</span>
            <AlertTriangle className={`w-3.5 h-3.5 ${
              entity.marketAccessStressScore > 60 ? 'text-rose-400' :
              entity.marketAccessStressScore > 40 ? 'text-amber-400' : 'text-emerald-400'
            }`} />
          </div>
          <div className="text-lg font-bold font-mono tabular-nums text-slate-100">
            {entity.marketAccessStressScore}/100
          </div>
          <div className="text-xs text-slate-500 mt-1">
            {entity.marketAccessStressScore > 60 ? 'Elevated Rollover Risk' :
             entity.marketAccessStressScore > 40 ? 'Moderate Vigilance' : 'Robust Market Access'}
          </div>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>Tax Elasticity (E)</span>
            <button onClick={onOpenFormulaModal} title="View Formula" className="text-cyan-400 hover:text-cyan-300">
              <Info className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="text-lg font-bold font-mono tabular-nums text-cyan-300">
            {entity.taxElasticityCoefficient.toFixed(2)}x
          </div>
          <div className="text-xs text-slate-500 mt-1">
            dTax % / dGDP % Sensitivity
          </div>
        </div>
      </div>

      {/* Active Macro Stress Banner if shocked */}
      {activeScenario.id !== 'baseline' && (
        <div className="p-4 bg-amber-950/20 border border-amber-800/60 rounded flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-semibold text-amber-200">
                Active Stress Shock: {activeScenario.name}
              </div>
              <div className="text-xs text-slate-300 mt-0.5">
                {activeScenario.description}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-6 text-xs font-mono shrink-0">
            <div>
              <span className="text-slate-400">Total Fiscal Shock:</span>{' '}
              <span className="text-amber-400 font-semibold tabular-nums">
                -${stressImpact.totalFiscalShockMillions.toLocaleString()}M
              </span>
            </div>
            <div>
              <span className="text-slate-400">Shocked DSCR:</span>{' '}
              <span className={`font-semibold tabular-nums ${stressImpact.shockedDscr < 1.15 ? 'text-rose-400' : 'text-amber-300'}`}>
                {stressImpact.shockedDscr.toFixed(2)}x
              </span>
            </div>
            <button
              onClick={onOpenStressModal}
              className="text-xs px-2.5 py-1 bg-amber-900/40 hover:bg-amber-900/60 text-amber-200 border border-amber-700/50 rounded transition-colors"
            >
              Modify Stress
            </button>
          </div>
        </div>
      )}

      {/* 5-Axis Peer Benchmark Radar & Comparative Scorecard */}
      <PeerRadarComparison
        entity={entity}
        allEntities={allEntities}
        onOpenFormulaModal={onOpenFormulaModal}
      />

      {/* Color-Coded Geographic Location & Neighboring Entities Map */}
      <EntityGeoMap
        entity={entity}
        allEntities={allEntities}
        onSelectEntity={onSelectEntity}
        onOpenFormulaModal={onOpenFormulaModal}
      />

      {/* TIER-SPECIFIC DEEP RISK MODULE */}
      {entity.tier === 'municipal' && entity.municipalMetrics && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <Building className="w-4 h-4 text-cyan-400" />
              <span>Municipal Structural Risk & Mill Rate Sensitivity Engine</span>
            </h2>
            <div className="text-xs text-slate-500">
              Mello-Roos Overlapping Assessment · Assessed Valuation Volatility · DSCR
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Metric Card 1: Own Source Revenue */}
            <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
              <div className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>Own-Source Revenue Ratio</span>
                <span className="font-mono text-cyan-400 font-bold tabular-nums">
                  {(entity.municipalMetrics.ownSourceRevenueRatio * 100).toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
                <div
                  className="bg-cyan-500 h-2 rounded-full"
                  style={{ width: `${entity.municipalMetrics.ownSourceRevenueRatio * 100}%` }}
                />
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">
                Represents local tax autonomy (property, local sales, utility franchise fees) vs dependence on state/federal revenue sharing. Higher ratio confers fiscal sovereignty but raises exposure to local assessed value shifts.
              </div>
              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-500 font-mono">
                <span>Unrestricted Liquidity Days</span>
                <span className={`font-semibold tabular-nums ${entity.municipalMetrics.liquidityDaysOfCash < 60 ? 'text-amber-400' : 'text-slate-200'}`}>
                  {entity.municipalMetrics.liquidityDaysOfCash} Days
                </span>
              </div>
            </div>

            {/* Metric Card 2: Mello-Roos & Overlapping Debt */}
            <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
              <div className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>Mello-Roos & Overlapping Debt</span>
                <span className="font-mono text-amber-400 font-bold tabular-nums">
                  {(entity.municipalMetrics.melloRoosOverlappingDebtRatio * 100).toFixed(2)}% of AV
                </span>
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">
                Tracks overlapping Community Facilities Districts (CFDs), special assessment tax liens, school district bonds, and regional authority obligations sitting on the identical property tax base.
              </div>
              <div className="space-y-1.5 pt-2 border-t border-slate-800/80 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>Special Assessment Districts:</span>
                  <span className="font-mono text-slate-200 tabular-nums font-medium">
                    {entity.municipalMetrics.specialAssessmentDistrictsCount} Districts
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Total Assessed Valuation (AV):</span>
                  <span className="font-mono text-slate-200 tabular-nums font-medium">
                    ${entity.municipalMetrics.totalAssessedValue.toFixed(1)}B
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Current Mill Rate:</span>
                  <span className="font-mono text-slate-200 tabular-nums font-medium">
                    {entity.municipalMetrics.millRate} mills ($/{1000} AV)
                  </span>
                </div>
              </div>
            </div>

            {/* Metric Card 3: Debt Service Coverage & Infrastructure Backlog */}
            <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
              <div className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>Debt Service Coverage (DSCR)</span>
                <span className={`font-mono font-bold tabular-nums ${
                  entity.municipalMetrics.dscrCoverage < 1.25 ? 'text-rose-400' :
                  entity.municipalMetrics.dscrCoverage < 1.40 ? 'text-amber-400' : 'text-emerald-400'
                }`}>
                  {entity.municipalMetrics.dscrCoverage.toFixed(2)}x
                </span>
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">
                Operating revenues minus operating expenses divided by annual debt service. Institutional covenant red flag triggers below 1.20x.
              </div>
              <div className="space-y-1.5 pt-2 border-t border-slate-800/80 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>Infrastructure Maintenance Backlog:</span>
                  <span className="font-mono text-rose-300 tabular-nums font-medium">
                    ${entity.municipalMetrics.infrastructureBacklog.toLocaleString()}M
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Backlog as % of Annual Budget:</span>
                  <span className="font-mono text-amber-300 tabular-nums font-medium">
                    {(entity.municipalMetrics.infrastructureBacklogPctBudget * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Interactive Mill Rate Sensitivity Sandbox */}
          <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-xs font-bold text-slate-200">
                  Interactive Assessed Value (AV) Contraction & Mill Rate Stress Sandbox
                </h3>
                <p className="text-xs text-slate-400">
                  Model how commercial or residential property value contractions impact annual tax collections under statutory mill levy caps.
                </p>
              </div>
              <div className="font-mono text-xs text-cyan-300 tabular-nums font-semibold">
                AV Shock: {interactiveAvChangePct > 0 ? `+${interactiveAvChangePct}%` : `${interactiveAvChangePct}%`}
              </div>
            </div>

            <div className="flex items-center gap-4">
              <span className="text-xs text-slate-500 font-mono">-25%</span>
              <input
                type="range"
                min="-25"
                max="10"
                step="1"
                value={interactiveAvChangePct}
                onChange={(e) => setInteractiveAvChangePct(Number(e.target.value))}
                aria-label="Assessed Value Change Percentage"
                className="w-full accent-cyan-400 h-1.5 bg-slate-950 rounded cursor-pointer"
              />
              <span className="text-xs text-slate-500 font-mono">+10%</span>
            </div>

            {/* Calculated Sensitivity Results */}
            {(() => {
              const avMultiplier = 1 + (interactiveAvChangePct / 100);
              const shockedAV = entity.municipalMetrics.totalAssessedValue * avMultiplier;
              const revenueShiftMillions = (interactiveAvChangePct / -5) * entity.municipalMetrics.millRateSensitivityRevenueDropPer5PctAV;
              const requiredMillRateToNeutralize = (entity.municipalMetrics.millRate / avMultiplier).toFixed(2);

              return (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                  <div className="p-2.5 bg-slate-950 border border-slate-800 rounded">
                    <span className="text-xs text-slate-500 block">Shocked Assessed Value</span>
                    <span className="font-mono text-sm font-semibold text-slate-200 tabular-nums">
                      ${shockedAV.toFixed(1)}B
                    </span>
                  </div>
                  <div className="p-2.5 bg-slate-950 border border-slate-800 rounded">
                    <span className="text-xs text-slate-500 block">Direct Tax Revenue Impact</span>
                    <span className={`font-mono text-sm font-semibold tabular-nums ${
                      revenueShiftMillions > 0 ? 'text-rose-400' : 'text-emerald-400'
                    }`}>
                      {revenueShiftMillions > 0 ? `-$${revenueShiftMillions.toFixed(1)}M` : `+$${Math.abs(revenueShiftMillions).toFixed(1)}M`}
                    </span>
                  </div>
                  <div className="p-2.5 bg-slate-950 border border-slate-800 rounded">
                    <span className="text-xs text-slate-500 block">Compensating Mill Rate Needed</span>
                    <span className="font-mono text-sm font-semibold text-amber-300 tabular-nums">
                      {requiredMillRateToNeutralize} mills
                    </span>
                    <span className="text-xs text-slate-500 block text-[11px] mt-0.5">
                      Statutory cap limit risk if &gt; 25 mills
                    </span>
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* SUBNATIONAL SPECIFIC DEEP RISK MODULE */}
      {entity.tier === 'subnational' && entity.subnationalMetrics && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <Landmark className="w-4 h-4 text-cyan-400" />
              <span>Subnational / State Risk Engine: Pension Liability, Medicaid Drag & Transfers</span>
            </h2>
            <div className="text-xs text-slate-500">
              GASB 67/68 Actuarial Sensitivity · Counter-Cyclical Medicaid Drag · Federal Grant Volatility
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Metric Card 1: Net Pension Liability */}
            <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
              <div className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>Net Pension Liability (NPL)</span>
                <span className="font-mono text-rose-400 font-bold tabular-nums">
                  ${(entity.subnationalMetrics.netPensionLiability / 1000).toFixed(1)}B
                </span>
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">
                Total Pension Liability (TPL) minus Actuarial Value of Assets (AVA). The single largest structural drag on state credit ratings, demanding escalating General Fund allocations.
              </div>
              <div className="space-y-1.5 pt-2 border-t border-slate-800/80 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>Aggregate Funded Ratio:</span>
                  <span className={`font-mono font-semibold tabular-nums ${
                    entity.subnationalMetrics.pensionFundedRatio < 50 ? 'text-rose-400' :
                    entity.subnationalMetrics.pensionFundedRatio < 70 ? 'text-amber-400' : 'text-emerald-400'
                  }`}>
                    {entity.subnationalMetrics.pensionFundedRatio.toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Assumed Discount Rate:</span>
                  <span className="font-mono text-slate-200 tabular-nums font-medium">
                    {entity.subnationalMetrics.pensionDiscountRate.toFixed(2)}%
                  </span>
                </div>
              </div>
            </div>

            {/* Metric Card 2: Medicaid Drag */}
            <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
              <div className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>Medicaid Expenditure Share</span>
                <span className="font-mono text-amber-400 font-bold tabular-nums">
                  {(entity.subnationalMetrics.medicaidExpenditureShare * 100).toFixed(1)}%
                </span>
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">
                Share of State General Funds consumed by Medicaid. Operates as an asymmetric automatic drag: enrollment surges during recessions exactly when tax revenues collapse.
              </div>
              <div className="space-y-1.5 pt-2 border-t border-slate-800/80 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>Counter-Cyclical Surge Risk:</span>
                  <span className="font-mono text-rose-300 tabular-nums font-medium">
                    +{(entity.subnationalMetrics.medicaidCounterCyclicalSurgeRate * 100).toFixed(0)}% in downturn
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Federal Match Rate (FMAP):</span>
                  <span className="font-mono text-cyan-300 tabular-nums font-medium">
                    {(entity.subnationalMetrics.fmapFederalShare * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>

            {/* Metric Card 3: Transfer Dependence & Reserves */}
            <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
              <div className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>Federal Grant Dependence</span>
                <span className="font-mono text-cyan-400 font-bold tabular-nums">
                  {(entity.subnationalMetrics.transferDependenceRatio * 100).toFixed(1)}%
                </span>
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">
                Portion of state revenues derived from federal intergovernmental transfers. Exposure to federal austerity, reconciliation clawbacks, or block grant restructuring.
              </div>
              <div className="space-y-1.5 pt-2 border-t border-slate-800/80 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>Rainy Day Fund Reserves:</span>
                  <span className={`font-mono font-medium tabular-nums ${
                    entity.subnationalMetrics.rainyDayFundReserveMonths < 1.0 ? 'text-amber-400' : 'text-emerald-400'
                  }`}>
                    {entity.subnationalMetrics.rainyDayFundReserveMonths.toFixed(1)} Months of expenses
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>OPEB Net Liability:</span>
                  <span className="font-mono text-slate-200 tabular-nums font-medium">
                    ${entity.pensionOpeb ? `${(entity.pensionOpeb.opebNetLiability / 1000).toFixed(1)}B` : 'N/A'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Interactive Discount Rate Sensitivity Curve for Pensions */}
          {entity.pensionOpeb && (
            <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <h3 className="text-xs font-bold text-slate-200">
                    Actuarial Discount Rate Sensitivity Curve (GASB 67/68)
                  </h3>
                  <p className="text-xs text-slate-400">
                    A 100 bps reduction in assumed investment return inflates Net Pension Liability exponentially.
                  </p>
                </div>
                <div className="flex items-center gap-1.5 p-1 bg-slate-950 border border-slate-800 rounded text-xs font-mono">
                  <button
                    onClick={() => setSelectedDiscountRateShift(-100)}
                    className={`px-2 py-1 rounded transition-colors ${selectedDiscountRateShift === -100 ? 'bg-rose-950 text-rose-300 border border-rose-800' : 'text-slate-400 hover:text-slate-200'}`}
                  >
                    -100 bps ({entity.pensionOpeb.assumedDiscountRate - 1.0}%)
                  </button>
                  <button
                    onClick={() => setSelectedDiscountRateShift(0)}
                    className={`px-2 py-1 rounded transition-colors ${selectedDiscountRateShift === 0 ? 'bg-slate-800 text-cyan-300' : 'text-slate-400 hover:text-slate-200'}`}
                  >
                    Baseline ({entity.pensionOpeb.assumedDiscountRate}%)
                  </button>
                  <button
                    onClick={() => setSelectedDiscountRateShift(100)}
                    className={`px-2 py-1 rounded transition-colors ${selectedDiscountRateShift === 100 ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'text-slate-400 hover:text-slate-200'}`}
                  >
                    +100 bps ({entity.pensionOpeb.assumedDiscountRate + 1.0}%)
                  </button>
                </div>
              </div>

              {/* Display Sensitivity Values */}
              {(() => {
                const activeNpl = selectedDiscountRateShift === -100
                  ? entity.pensionOpeb.nplAtMinus100Bps
                  : selectedDiscountRateShift === 100
                  ? entity.pensionOpeb.nplAtPlus100Bps
                  : entity.pensionOpeb.netPensionLiability;

                const deltaNpl = activeNpl - entity.pensionOpeb.netPensionLiability;

                return (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
                    <div className="p-3 bg-slate-950 border border-slate-800 rounded">
                      <span className="text-xs text-slate-500 block">Total Pension Liability (TPL)</span>
                      <span className="font-mono text-sm font-semibold text-slate-200 tabular-nums">
                        ${(entity.pensionOpeb.totalPensionLiability / 1000).toFixed(1)}B
                      </span>
                    </div>
                    <div className="p-3 bg-slate-950 border border-slate-800 rounded">
                      <span className="text-xs text-slate-500 block">Resulting Net Pension Liability (NPL)</span>
                      <span className="font-mono text-sm font-semibold text-rose-300 tabular-nums">
                        ${(activeNpl / 1000).toFixed(1)}B
                      </span>
                    </div>
                    <div className="p-3 bg-slate-950 border border-slate-800 rounded">
                      <span className="text-xs text-slate-500 block">NPL Shift vs Baseline</span>
                      <span className={`font-mono text-sm font-semibold tabular-nums ${
                        deltaNpl > 0 ? 'text-rose-400' : deltaNpl < 0 ? 'text-emerald-400' : 'text-slate-400'
                      }`}>
                        {deltaNpl > 0 ? `+$${(deltaNpl / 1000).toFixed(1)}B (+${((deltaNpl / entity.pensionOpeb.netPensionLiability) * 100).toFixed(0)}%)` :
                         deltaNpl < 0 ? `-$${(Math.abs(deltaNpl) / 1000).toFixed(1)}B` : 'Current Baseline'}
                      </span>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}
        </div>
      )}

      {/* SOVEREIGN SPECIFIC DEEP RISK MODULE */}
      {entity.tier === 'sovereign' && entity.sovereignMetrics && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <Coins className="w-4 h-4 text-cyan-400" />
              <span>Sovereign Macro-Monetary & External Liquidity Engine</span>
            </h2>
            <div className="text-xs text-slate-500">
              Greenspan-Guidotti Threshold · Seigniorage Limits · Primary Balance Dynamics
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Metric Card 1: External Debt to FX Reserves */}
            <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
              <div className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>External Debt-to-FX Reserves</span>
                <span className={`font-mono font-bold tabular-nums ${
                  entity.sovereignMetrics.externalDebtToFxReserves > 2.5 ? 'text-rose-400' :
                  entity.sovereignMetrics.externalDebtToFxReserves > 1.8 ? 'text-amber-400' : 'text-emerald-400'
                }`}>
                  {entity.sovereignMetrics.externalDebtToFxReserves.toFixed(2)}x
                </span>
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">
                Ratio of total external liabilities to liquid Central Bank foreign exchange reserves. Measures vulnerability to sudden stops in capital flows and balance of payment crises.
              </div>
              <div className="space-y-1.5 pt-2 border-t border-slate-800/80 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>Greenspan-Guidotti Ratio:</span>
                  <span className={`font-mono font-semibold tabular-nums ${
                    entity.sovereignMetrics.greenspanGuidottiRatio < 1.0 ? 'text-rose-400' : 'text-emerald-400'
                  }`}>
                    {entity.sovereignMetrics.greenspanGuidottiRatio.toFixed(2)}x (Threshold: $\ge$ 1.0x)
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>FX Reserves Total:</span>
                  <span className="font-mono text-slate-200 tabular-nums font-medium">
                    ${entity.sovereignMetrics.fxReservesTotalUsdBillions.toFixed(1)}B
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Short-Term External Debt:</span>
                  <span className="font-mono text-slate-200 tabular-nums font-medium">
                    ${entity.sovereignMetrics.shortTermExternalDebtUsdBillions.toFixed(1)}B
                  </span>
                </div>
              </div>
            </div>

            {/* Metric Card 2: Seigniorage & Monetization Capacity */}
            <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
              <div className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>Seigniorage Monetization Limit</span>
                <span className="font-mono text-cyan-400 font-bold tabular-nums">
                  {entity.sovereignMetrics.seigniorageCapacityPctGdp.toFixed(2)}% of GDP
                </span>
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">
                Maximum sustainable central bank fiscal financing before triggering unanchored inflation expectations or currency depreciation spirals.
              </div>
              <div className="space-y-1.5 pt-2 border-t border-slate-800/80 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>Direct CB Monetization Headroom:</span>
                  <span className="font-mono text-slate-200 tabular-nums font-medium">
                    {entity.sovereignMetrics.centralBankMonetizationLimitPctGdp > 0
                      ? `${entity.sovereignMetrics.centralBankMonetizationLimitPctGdp.toFixed(2)}% GDP`
                      : 'Prohibited (EU Art 123)'}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Current Account Balance:</span>
                  <span className={`font-mono font-medium tabular-nums ${
                    entity.sovereignMetrics.currentAccountBalancePctGdp < 0 ? 'text-amber-400' : 'text-emerald-400'
                  }`}>
                    {entity.sovereignMetrics.currentAccountBalancePctGdp > 0 ? `+${entity.sovereignMetrics.currentAccountBalancePctGdp.toFixed(1)}%` : `${entity.sovereignMetrics.currentAccountBalancePctGdp.toFixed(1)}%`} of GDP
                  </span>
                </div>
              </div>
            </div>

            {/* Metric Card 3: Primary Balance vs Overall Deficit */}
            <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
              <div className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>Primary Fiscal Balance</span>
                <span className={`font-mono font-bold tabular-nums ${
                  entity.sovereignMetrics.primaryBalancePctGdp >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}>
                  {entity.sovereignMetrics.primaryBalancePctGdp > 0 ? `+${entity.sovereignMetrics.primaryBalancePctGdp.toFixed(2)}%` : `${entity.sovereignMetrics.primaryBalancePctGdp.toFixed(2)}%`} of GDP
                </span>
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">
                Fiscal balance excluding debt interest payments. Negative primary balances directly fuel sovereign debt expansion regardless of interest rate conditions.
              </div>
              <div className="space-y-1.5 pt-2 border-t border-slate-800/80 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>Overall Fiscal Deficit:</span>
                  <span className="font-mono text-rose-300 tabular-nums font-medium">
                    {entity.sovereignMetrics.overallFiscalBalancePctGdp.toFixed(2)}% of GDP
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Public Debt / GDP:</span>
                  <span className="font-mono text-amber-300 tabular-nums font-medium">
                    {entity.sovereignMetrics.publicDebtToGdp.toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>External Hard Currency Share:</span>
                  <span className="font-mono text-cyan-300 tabular-nums font-medium">
                    {entity.sovereignMetrics.externalDebtSharePct.toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
