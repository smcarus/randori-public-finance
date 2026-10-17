import React, { useState } from 'react';
import { PublicFinanceEntity, StressScenario } from '../types/finance';
import { generateDemographicDecayTrajectory } from '../utils/macroStressEngine';
import {
  FileText,
  AlertTriangle,
  Users,
  ShieldAlert,
  Building2,
  TrendingDown,
  Info,
  DollarSign
} from 'lucide-react';

interface ContingentLiabilitiesTabProps {
  entity: PublicFinanceEntity;
  activeScenario: StressScenario;
  onOpenFormulaModal: () => void;
}

export const ContingentLiabilitiesTab: React.FC<ContingentLiabilitiesTabProps> = ({
  entity,
  activeScenario,
  onOpenFormulaModal,
}) => {
  // Interactive traffic shock slider for PPP MRG testing
  const [trafficShockPct, setTrafficShockPct] = useState<number>(activeScenario.pppTrafficDeclinePct || 15);

  // Demographic decay trajectory
  const demographicTrajectory = generateDemographicDecayTrajectory(entity);

  // Compute shocked PPP concessions
  const pppEvaluated = entity.pppConcessions.map((ppp) => {
    const trafficMultiplier = 1 - (trafficShockPct / 100);
    const shockedRevenue = ppp.currentProjectedRevenue * trafficMultiplier;
    const isTriggered = shockedRevenue < ppp.mrgTriggerFloor;
    const shortfall = isTriggered ? ppp.mrgTriggerFloor - shockedRevenue : 0;
    const fiscalPayout = Math.min(ppp.contingentLiabilityExposure, shortfall);

    return {
      ...ppp,
      shockedRevenue: Number(shockedRevenue.toFixed(1)),
      shortfall: Number(shortfall.toFixed(1)),
      fiscalPayout: Number(fiscalPayout.toFixed(1)),
      isTriggered,
    };
  });

  const totalPppExposure = entity.pppConcessions.reduce((acc, p) => acc + p.contingentLiabilityExposure, 0);
  const totalTriggeredPayout = pppEvaluated.reduce((acc, p) => acc + p.fiscalPayout, 0);

  // Total SOE Expected Shortfall
  const totalSoeDebt = entity.stateOwnedEnterprises.reduce((acc, soe) => acc + soe.totalDebt, 0);
  const totalSoeExpectedShortfall = entity.stateOwnedEnterprises.reduce((acc, soe) => acc + soe.expectedShortfall95, 0);

  return (
    <div className="space-y-8">
      {/* SECTION 1: PPP INFRASTRUCTURE FINANCIAL ASSESSMENT MODELS (IFRAM) */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <FileText className="w-4 h-4 text-cyan-400" />
              <span>Public-Private Partnerships (PPP) & IFRAM Contingent Engine</span>
            </h2>
            <p className="text-xs text-slate-400">
              Minimum Revenue Guarantee (MRG) Triggers · Availability Payment Structures · Fiscal Pass-Through Exposures
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400 font-mono">
              Total PPP Exposure: <span className="text-cyan-300 font-semibold">${totalPppExposure}M</span>
            </span>
            <span className="text-xs text-rose-400 font-mono">
              Triggered Payout: <span className="font-bold">${totalTriggeredPayout.toFixed(1)}M</span>
            </span>
          </div>
        </div>

        {/* Interactive PPP Traffic / Usage Shock Slider */}
        <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
          <div className="flex justify-between items-center text-xs">
            <span className="text-slate-300 font-medium">
              Concession Traffic & Toll Volume Shock Simulation:
            </span>
            <span className="font-mono text-rose-300 font-bold tabular-nums">
              -{trafficShockPct}% Volume Reduction
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="50"
            step="1"
            value={trafficShockPct}
            onChange={(e) => setTrafficShockPct(Number(e.target.value))}
            aria-label="Concession Traffic Shock Percentage"
            className="w-full accent-cyan-400 h-1.5 bg-slate-950 rounded cursor-pointer"
          />
          <div className="flex justify-between text-[11px] text-slate-500 font-mono">
            <span>0% (Nominal Baseline)</span>
            <span>-25% (Recessionary Volume Dip)</span>
            <span>-50% (Pandemic / Lockout Stress)</span>
          </div>
        </div>

        {/* PPP Concessions Table */}
        <div className="bg-slate-900 border border-slate-800 rounded overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/60 font-medium">
                <th className="py-2.5 px-3">Infrastructure Project</th>
                <th className="py-2.5 px-3">Sector</th>
                <th className="py-2.5 px-3 text-right">Capex ($M)</th>
                <th className="py-2.5 px-3">Payment Model</th>
                <th className="py-2.5 px-3 text-right">MRG Floor ($M)</th>
                <th className="py-2.5 px-3 text-right">Shocked Rev ($M)</th>
                <th className="py-2.5 px-3 text-right">Contingent Exposure</th>
                <th className="py-2.5 px-3 text-right">Fiscal Payout Due</th>
                <th className="py-2.5 px-3 text-center">Trigger Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {pppEvaluated.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-4 text-center text-slate-500 font-sans">
                    No active PPP concessions registered for this entity.
                  </td>
                </tr>
              ) : (
                pppEvaluated.map((ppp) => (
                  <tr key={ppp.id} className="hover:bg-slate-800/30 text-slate-300">
                    <td className="py-2.5 px-3 font-sans font-medium text-slate-200">
                      <div>{ppp.projectName}</div>
                      <div className="text-[11px] text-slate-500">Operator: {ppp.concessionaireName} (Exp: {ppp.concessionExpiryYear})</div>
                    </td>
                    <td className="py-2.5 px-3 font-sans text-slate-400">
                      {ppp.sector}
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-slate-200">
                      ${ppp.capitalExpenditure.toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 font-sans text-slate-400">
                      {ppp.paymentStructure}
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-slate-200">
                      ${ppp.mrgTriggerFloor.toFixed(1)}
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-slate-400">
                      ${ppp.shockedRevenue.toFixed(1)}
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-slate-300">
                      ${ppp.contingentLiabilityExposure.toFixed(1)}M
                    </td>
                    <td className={`py-2.5 px-3 text-right tabular-nums font-bold ${
                      ppp.fiscalPayout > 0 ? 'text-rose-400' : 'text-emerald-400'
                    }`}>
                      ${ppp.fiscalPayout.toFixed(1)}M
                    </td>
                    <td className="py-2.5 px-3 text-center font-sans">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                        ppp.isTriggered
                          ? 'bg-rose-950/80 text-rose-300 border border-rose-800/60'
                          : 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/60'
                      }`}>
                        {ppp.isTriggered ? 'MRG Triggered' : 'Nominal'}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* SECTION 2: STATE-OWNED ENTERPRISE (SOE) BAILOUT RISK ENGINE */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <Building2 className="w-4 h-4 text-cyan-400" />
              <span>State-Owned Enterprise (SOE) Contingent Bailout Engine</span>
            </h2>
            <p className="text-xs text-slate-400">
              Utilities & Transit Authorities · Debt Covenant Breaches · Expected Shortfall (ES 95%)
            </p>
          </div>
          <div className="text-xs text-slate-500 font-mono">
            Total SOE Debt: ${totalSoeDebt.toLocaleString()}M · Total ES (95%): ${totalSoeExpectedShortfall.toLocaleString()}M
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {entity.stateOwnedEnterprises.map((soe) => (
            <div
              key={soe.id}
              className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs font-bold text-slate-200">{soe.name}</div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    Sector: {soe.sector} · Guarantee: <span className="text-slate-200 font-medium">{soe.explicitGovernmentGuarantee ? 'Explicit Sovereign Pledge' : 'Implicit Moral Pledge'}</span>
                  </div>
                </div>
                <span className="font-mono text-cyan-300 text-sm font-bold tabular-nums">
                  ${soe.totalDebt.toLocaleString()}M Debt
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800/80 text-xs font-mono">
                <div>
                  <span className="text-slate-500 block text-[11px]">DSCR Coverage</span>
                  <span className={`font-semibold tabular-nums ${soe.debtServiceCoverageRatio < 1.10 ? 'text-rose-400' : 'text-slate-200'}`}>
                    {soe.debtServiceCoverageRatio.toFixed(2)}x
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[11px]">Bailout Prob.</span>
                  <span className={`font-semibold tabular-nums ${soe.bailoutProbability > 0.5 ? 'text-rose-400' : 'text-amber-400'}`}>
                    {(soe.bailoutProbability * 100).toFixed(0)}%
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[11px]">Expected Shortfall</span>
                  <span className="text-rose-400 font-semibold tabular-nums">
                    ${soe.expectedShortfall95}M
                  </span>
                </div>
              </div>

              <div className="text-xs text-slate-400 leading-relaxed pt-1">
                {soe.debtServiceCoverageRatio < 1.0 ? (
                  <span className="text-rose-300">
                    Operating cash flow fails to cover debt service. High likelihood of emergency government capital injection or debt assumption within 12–24 months.
                  </span>
                ) : (
                  <span>
                    Self-sustaining operational cash flows currently cover senior debt service, but vulnerable to tariff freezes or major capital expenditure overruns.
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* SECTION 3: DEMOGRAPHIC & ACTUARIAL DECAY FUNCTIONS (20-YEAR HORIZON) */}
      <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-xs font-bold text-slate-200 flex items-center gap-2">
              <Users className="w-3.5 h-3.5 text-cyan-400" />
              <span>Demographic & Actuarial Decay Functions (20-Year Horizon)</span>
            </h3>
            <p className="text-xs text-slate-400">
              Models long-term income and sales tax base erosion driven by rising dependency ratios against escalating pension & healthcare draws.
            </p>
          </div>
          <button
            onClick={onOpenFormulaModal}
            className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-mono"
          >
            <Info className="w-3 h-3" />
            <span>Decay Equations</span>
          </button>
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 bg-slate-900/40 font-medium">
                <th className="py-2.5 px-3">Projection Year</th>
                <th className="py-2.5 px-3 text-right">Dependency Ratio (Retirees / 100 Workers)</th>
                <th className="py-2.5 px-3 text-right">Tax Base Capacity Index</th>
                <th className="py-2.5 px-3 text-right">Pension Draw Index</th>
                <th className="py-2.5 px-3 text-right">Annual Structural Deficit Gap ($M)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 font-mono">
              {demographicTrajectory.map((pt, idx) => (
                <tr key={idx} className="hover:bg-slate-900/50 text-slate-300">
                  <td className="py-2.5 px-3 font-semibold text-slate-200">{pt.year}</td>
                  <td className="py-2.5 px-3 text-right tabular-nums text-amber-300">
                    {pt.dependencyRatio.toFixed(1)}%
                  </td>
                  <td className="py-2.5 px-3 text-right tabular-nums text-slate-300">
                    {pt.taxBaseIndex.toFixed(1)} <span className="text-[11px] text-slate-500">(Base 100)</span>
                  </td>
                  <td className="py-2.5 px-3 text-right tabular-nums text-rose-300">
                    {pt.pensionDrawIndex.toFixed(1)} <span className="text-[11px] text-slate-500">(Base 100)</span>
                  </td>
                  <td className="py-2.5 px-3 text-right tabular-nums font-bold text-rose-400">
                    -${pt.structuralDeficitGapMillions.toLocaleString()}M
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
