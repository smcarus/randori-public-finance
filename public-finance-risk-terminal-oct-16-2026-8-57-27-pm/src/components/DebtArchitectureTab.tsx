import React, { useState } from 'react';
import { BondTranche, PublicFinanceEntity, RefundingAnalysisResult } from '../types/finance';
import { evaluateBondRefunding, generateDefeasanceEscrowSchedule } from '../utils/refundingOptimizer';
import {
  ShieldAlert,
  Calendar,
  Percent,
  CheckCircle2,
  XCircle,
  AlertCircle,
  HelpCircle,
  ArrowRight,
  Layers,
  Banknote
} from 'lucide-react';

interface DebtArchitectureTabProps {
  entity: PublicFinanceEntity;
  onOpenFormulaModal: () => void;
}

export const DebtArchitectureTab: React.FC<DebtArchitectureTabProps> = ({
  entity,
  onOpenFormulaModal,
}) => {
  // Candidate bond selected for refunding analysis
  const initialCallable = entity.bonds.find((b) => b.isCallable) || entity.bonds[0];
  const [selectedBondId, setSelectedBondId] = useState<string>(initialCallable?.id ?? '');
  const [marketRefundingYieldPct, setMarketRefundingYieldPct] = useState<number>(3.65);
  const [issuanceCostsPct, setIssuanceCostsPct] = useState<number>(0.85);

  const selectedBond = entity.bonds.find((b) => b.id === selectedBondId) || entity.bonds[0];
  
  const refundingResult: RefundingAnalysisResult | null = selectedBond
    ? evaluateBondRefunding(selectedBond, marketRefundingYieldPct, issuanceCostsPct)
    : null;

  // Escrow cash flows
  const escrowSchedule = selectedBond
    ? generateDefeasanceEscrowSchedule(selectedBond.parAmount, selectedBond.coupon, 3)
    : [];

  return (
    <div className="space-y-8">
      {/* SECTION 1: BOND ARCHITECTURE & CATEGORIZATION */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              <span>Debt Architecture Tracker & Categorization</span>
            </h2>
            <p className="text-xs text-slate-400">
              General Obligation (GO) · Dedicated Revenue · Moral Obligation · Tax Increment Financing (TIF)
            </p>
          </div>
          <div className="text-xs text-slate-500 font-mono">
            {entity.bonds.length} Active Tranches · Total Par: ${entity.bonds.reduce((acc, b) => acc + b.parAmount, 0).toLocaleString()}M
          </div>
        </div>

        {/* Bond Tranche Data Grid */}
        <div className="bg-slate-900 border border-slate-800 rounded overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/60 font-medium">
                <th className="py-2.5 px-3">Issue Name</th>
                <th className="py-2.5 px-3">Pledge Type</th>
                <th className="py-2.5 px-3 text-right">Par ($M)</th>
                <th className="py-2.5 px-3 text-right">Coupon</th>
                <th className="py-2.5 px-3 text-right">YTM</th>
                <th className="py-2.5 px-3">Maturity Date</th>
                <th className="py-2.5 px-3">Call Date</th>
                <th className="py-2.5 px-3 text-right">Spread (bps)</th>
                <th className="py-2.5 px-3">Rating</th>
                <th className="py-2.5 px-3 text-center">Refunding Candidacy</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {entity.bonds.map((bond) => {
                const isSelected = bond.id === selectedBondId;
                return (
                  <tr
                    key={bond.id}
                    onClick={() => setSelectedBondId(bond.id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected ? 'bg-cyan-950/30 text-cyan-200' : 'hover:bg-slate-800/40 text-slate-300'
                    }`}
                  >
                    <td className="py-2.5 px-3 font-sans font-medium text-slate-200 flex items-center gap-2">
                      <div className={`w-1.5 h-1.5 rounded-full ${isSelected ? 'bg-cyan-400' : 'bg-slate-600'}`} />
                      <span>{bond.name}</span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`px-1.5 py-0.5 rounded text-[11px] font-sans ${
                        bond.type === 'GO' ? 'bg-blue-950/80 text-blue-300 border border-blue-800/60' :
                        bond.type === 'Revenue' ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/60' :
                        bond.type === 'MoralObligation' ? 'bg-amber-950/80 text-amber-300 border border-amber-800/60' :
                        bond.type === 'TIF' ? 'bg-purple-950/80 text-purple-300 border border-purple-800/60' :
                        'bg-slate-800 text-slate-300'
                      }`}>
                        {bond.type === 'GO' ? 'General Obligation' :
                         bond.type === 'Revenue' ? 'Dedicated Revenue' :
                         bond.type === 'MoralObligation' ? 'Moral Obligation' :
                         bond.type === 'TIF' ? 'TIF Allocation' : bond.type}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums font-semibold text-slate-100">
                      ${bond.parAmount.toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-slate-200">
                      {bond.coupon.toFixed(2)}%
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-slate-400">
                      {bond.yieldToMaturity.toFixed(2)}%
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 font-sans">
                      {bond.maturityDate}
                    </td>
                    <td className="py-2.5 px-3 font-sans">
                      {bond.callDate ? (
                        <span className="text-cyan-300 flex items-center gap-1">
                          <Calendar className="w-3 h-3 text-cyan-400" />
                          <span>{bond.callDate}</span>
                        </span>
                      ) : (
                        <span className="text-slate-500">Non-Callable</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-slate-300">
                      +{bond.spreadOverBenchmarkBps}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="font-semibold text-slate-200">{bond.rating}</span>
                    </td>
                    <td className="py-2.5 px-3 text-center font-sans">
                      {bond.isCallable ? (
                        <span className="text-cyan-400 font-medium text-[11px] underline">
                          Analyze NPV
                        </span>
                      ) : (
                        <span className="text-slate-600 text-[11px]">N/A</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* SECTION 2: VARIABLE-RATE DEMAND OBLIGATIONS (VRDOs) MONITOR */}
      {entity.vrdos.length > 0 && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-amber-400" />
                <span>Variable-Rate Demand Obligations (VRDOs) & Remarketing Risk</span>
              </h2>
              <p className="text-xs text-slate-400">
                Letter of Credit (LOC) Bank Expiration Timelines · Remarketing Agent Failure · Penalty Bank Bond Rates
              </p>
            </div>
            <div className="text-xs text-amber-400 font-mono font-medium">
              Mandatory Tender Trigger if LOC &lt; 90 Days
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {entity.vrdos.map((vrdo) => {
              const isUrgent = vrdo.daysToLocExpiry < 200;
              return (
                <div
                  key={vrdo.id}
                  className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-xs font-bold text-slate-200">{vrdo.name}</div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        Liquidity Bank: <span className="text-slate-200 font-medium">{vrdo.liquidityProvider}</span>
                      </div>
                    </div>
                    <span className="font-mono text-cyan-300 text-sm font-bold tabular-nums">
                      ${vrdo.parAmount}M Par
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-800/80 text-xs font-mono">
                    <div>
                      <span className="text-slate-500 block text-[11px]">Weekly Reset</span>
                      <span className="text-slate-200 font-semibold tabular-nums">{vrdo.currentResetRate.toFixed(2)}%</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">LOC Expiration</span>
                      <span className={`tabular-nums font-semibold ${isUrgent ? 'text-amber-400' : 'text-slate-300'}`}>
                        {vrdo.locExpirationDate}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Days to Expiry</span>
                      <span className={`tabular-nums font-semibold ${isUrgent ? 'text-amber-400' : 'text-slate-200'}`}>
                        {vrdo.daysToLocExpiry} Days
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Penalty Bank Rate</span>
                      <span className="text-rose-400 font-semibold tabular-nums">{vrdo.bankBondRate.toFixed(2)}%</span>
                    </div>
                  </div>

                  <div className="text-xs text-slate-400 pt-1 leading-relaxed">
                    Remarketing Agent: <span className="text-slate-300 font-medium">{vrdo.remarketingAgent}</span>. If remarketing fails on tender date, bank draws on LOC, converting into a bank bond with mandatory 3-year accelerated term-out at {vrdo.bankBondRate.toFixed(2)}%.
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* SECTION 3: BOND REFUNDING & LIABILITY MANAGEMENT ENGINE */}
      {selectedBond && refundingResult && (
        <div className="p-5 bg-slate-900 border border-slate-800 rounded space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-4 border-b border-slate-800">
            <div>
              <div className="text-xs font-medium text-cyan-400 uppercase tracking-wider">
                Liability Management & Refinancing Module
              </div>
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2 mt-0.5">
                <span>NPV Refunding Savings Analysis: {selectedBond.name}</span>
              </h3>
            </div>
            <div className="flex items-center gap-3">
              <span className={`px-2.5 py-1 text-xs rounded border flex items-center gap-1.5 font-medium ${
                refundingResult.meetsThreshold
                  ? 'bg-emerald-950/60 border-emerald-700/60 text-emerald-300'
                  : 'bg-rose-950/60 border-rose-700/60 text-rose-300'
              }`}>
                {refundingResult.meetsThreshold ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <XCircle className="w-3.5 h-3.5 text-rose-400" />
                )}
                <span>
                  {refundingResult.meetsThreshold
                    ? 'Exceeds 3.0% Minimum NPV Benchmark'
                    : 'Below 3.0% Minimum NPV Hurdle Rate'}
                </span>
              </span>
              <button
                onClick={onOpenFormulaModal}
                title="View Refunding Mathematics"
                className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1"
              >
                <HelpCircle className="w-3.5 h-3.5" />
                <span>Formula</span>
              </button>
            </div>
          </div>

          {/* Interactive Yield & Cost Sliders */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-slate-950 p-4 border border-slate-800/80 rounded">
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Target Market Refunding Yield:</span>
                <span className="font-mono text-cyan-300 font-bold tabular-nums">
                  {marketRefundingYieldPct.toFixed(2)}%
                </span>
              </div>
              <input
                type="range"
                min="2.00"
                max="6.00"
                step="0.05"
                value={marketRefundingYieldPct}
                onChange={(e) => setMarketRefundingYieldPct(Number(e.target.value))}
                aria-label="Target Market Refunding Yield Percentage"
                className="w-full accent-cyan-400 h-1.5 bg-slate-800 rounded cursor-pointer"
              />
              <div className="flex justify-between text-[11px] text-slate-500 font-mono">
                <span>2.00%</span>
                <span>Current Coupon: {selectedBond.coupon.toFixed(2)}%</span>
                <span>6.00%</span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Cost of Issuance & Underwriting Spread:</span>
                <span className="font-mono text-slate-200 font-bold tabular-nums">
                  {issuanceCostsPct.toFixed(2)}% of Par
                </span>
              </div>
              <input
                type="range"
                min="0.30"
                max="2.00"
                step="0.05"
                value={issuanceCostsPct}
                onChange={(e) => setIssuanceCostsPct(Number(e.target.value))}
                aria-label="Cost of Issuance Percentage"
                className="w-full accent-cyan-400 h-1.5 bg-slate-800 rounded cursor-pointer"
              />
              <div className="flex justify-between text-[11px] text-slate-500 font-mono">
                <span>0.30% (Low friction)</span>
                <span>1.00% (Standard)</span>
                <span>2.00% (Complex)</span>
              </div>
            </div>
          </div>

          {/* Refunding Financial Results Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-3 bg-slate-950 border border-slate-800 rounded">
              <span className="text-xs text-slate-400 block mb-1">Net Present Value Savings</span>
              <span className="font-mono text-xl font-bold text-emerald-400 tabular-nums">
                ${refundingResult.presentValueSavings.toLocaleString()}M
              </span>
              <span className="text-[11px] text-slate-500 block mt-1">
                Discounted at {refundingResult.refundingYield}%
              </span>
            </div>

            <div className="p-3 bg-slate-950 border border-slate-800 rounded">
              <span className="text-xs text-slate-400 block mb-1">NPV Savings % of Par</span>
              <span className={`font-mono text-xl font-bold tabular-nums ${
                refundingResult.npvSavingsPercent >= 3.0 ? 'text-emerald-400' : 'text-amber-400'
              }`}>
                {refundingResult.npvSavingsPercent.toFixed(2)}%
              </span>
              <span className="text-[11px] text-slate-500 block mt-1">
                Target Hurdle: $\ge$ 3.00%
              </span>
            </div>

            <div className="p-3 bg-slate-950 border border-slate-800 rounded">
              <span className="text-xs text-slate-400 block mb-1">Refunding Structure</span>
              <span className="font-mono text-sm font-semibold text-cyan-300 block">
                {refundingResult.refundingType}
              </span>
              <span className="text-[11px] text-slate-500 block mt-1">
                Call: {selectedBond.callDate ?? 'None'}
              </span>
            </div>

            <div className="p-3 bg-slate-950 border border-slate-800 rounded">
              <span className="text-xs text-slate-400 block mb-1">Negative Arbitrage Drag</span>
              <span className="font-mono text-xl font-bold text-amber-400 tabular-nums">
                ${refundingResult.negativeArbitrageLoss.toFixed(2)}M
              </span>
              <span className="text-[11px] text-slate-500 block mt-1">
                Efficiency: {refundingResult.efficiencyRatio}%
              </span>
            </div>
          </div>

          {/* SECTION 4: DEFEASANCE ESCROW OPTIMIZER MATRIX */}
          <div className="space-y-3 pt-2">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
              <h4 className="text-xs font-bold text-slate-200 flex items-center gap-2">
                <Banknote className="w-3.5 h-3.5 text-cyan-400" />
                <span>Defeasance Escrow Linear Programming Cash Flow Match (SLGS vs Treasuries)</span>
              </h4>
              <span className="text-xs text-slate-500 font-mono">
                Exact Liability Matching (0.00 Net Variance)
              </span>
            </div>

            <div className="bg-slate-950 border border-slate-800 rounded overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-900/40 font-medium">
                    <th className="py-2 px-3">Period Date</th>
                    <th className="py-2 px-3 text-right">Refunded Debt Service Due</th>
                    <th className="py-2 px-3 text-right">Escrow Maturity Receipt</th>
                    <th className="py-2 px-3 text-right">Net Cash Variance</th>
                    <th className="py-2 px-3">Escrow Instrument Allocated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40 font-mono">
                  {escrowSchedule.map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-900/40 text-slate-300">
                      <td className="py-2 px-3 text-slate-400">{item.periodDate}</td>
                      <td className="py-2 px-3 text-right tabular-nums text-slate-200">
                        ${item.refundedDebtService.toLocaleString()}M
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums text-emerald-400">
                        ${item.escrowMaturityReceipt.toLocaleString()}M
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums text-cyan-300">
                        ${item.netVariance.toFixed(2)}
                      </td>
                      <td className="py-2 px-3 font-sans">
                        <span className="px-2 py-0.5 rounded text-[11px] bg-slate-900 border border-slate-800 text-slate-300">
                          {item.treasurySecurityType}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="text-[11px] text-slate-500 italic">
              Structured to satisfy IRC Section 148 arbitrage yield restriction requirements. Open-market Treasury STRIPS or special non-marketable State and Local Government Series (SLGS) securities match every future debt service date to irrevocably defease the pledge.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
