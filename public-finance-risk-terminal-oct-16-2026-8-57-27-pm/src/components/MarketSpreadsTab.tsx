import React from 'react';
import { PublicFinanceEntity } from '../types/finance';
import {
  TrendingUp,
  BarChart3,
  Layers,
  AlertTriangle,
  Info,
  CalendarClock,
  ArrowRight
} from 'lucide-react';

interface MarketSpreadsTabProps {
  entity: PublicFinanceEntity;
  onOpenFormulaModal: () => void;
}

export const MarketSpreadsTab: React.FC<MarketSpreadsTabProps> = ({
  entity,
  onOpenFormulaModal,
}) => {
  const benchmarkName =
    entity.tier === 'municipal' ? 'AAA Municipal Market Data (MMD)' :
    entity.currency === 'EUR' ? 'German Bund Curve' :
    'US Treasury Benchmark';

  // Maturity Wall distribution
  const wallItems = [
    { label: '< 12 Months', amount: entity.maturityWall.within12M, color: 'bg-rose-500' },
    { label: '12 – 24 Months', amount: entity.maturityWall.year1to2, color: 'bg-amber-500' },
    { label: '24 – 36 Months', amount: entity.maturityWall.year2to3, color: 'bg-yellow-500' },
    { label: '36 – 60 Months', amount: entity.maturityWall.year3to5, color: 'bg-cyan-500' },
    { label: 'Beyond 60 Months', amount: entity.maturityWall.beyond5Y, color: 'bg-slate-600' },
  ];

  const maxWallAmount = Math.max(...wallItems.map((w) => w.amount), 1);
  const totalMaturingIn3Years = entity.maturityWall.within12M + entity.maturityWall.year1to2 + entity.maturityWall.year2to3;
  const threeYearRolloverRatio = entity.totalDirectDebtMillions > 0
    ? (totalMaturingIn3Years / entity.totalDirectDebtMillions) * 100
    : 0;

  return (
    <div className="space-y-8">
      {/* SECTION 1: BENCHMARK YIELD CURVES & CDS-BOND BASIS */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-cyan-400" />
              <span>Credit & Spread Analytics: Yield Curve & CDS-Bond Basis</span>
            </h2>
            <p className="text-xs text-slate-400">
              Benchmark Spread ({benchmarkName}) vs Synthetic Credit Default Swap (CDS) Divergence
            </p>
          </div>
          <button
            onClick={onOpenFormulaModal}
            className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-mono"
          >
            <Info className="w-3.5 h-3.5" />
            <span>CDS Basis Mechanics</span>
          </button>
        </div>

        {/* Spreads Grid */}
        <div className="bg-slate-900 border border-slate-800 rounded overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/60 font-medium">
                <th className="py-2.5 px-3">Tenor</th>
                <th className="py-2.5 px-3 text-right">Benchmark Yield ({benchmarkName})</th>
                <th className="py-2.5 px-3 text-right">{entity.name} Yield</th>
                <th className="py-2.5 px-3 text-right">Cash Spread (Z-spread)</th>
                <th className="py-2.5 px-3 text-right">Synthetic CDS Spread</th>
                <th className="py-2.5 px-3 text-right">CDS-Bond Basis</th>
                <th className="py-2.5 px-3">Market Interpretation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {entity.marketSpreads.map((s) => {
                const isNegativeBasis = s.cdsBondBasisBps < 0;
                return (
                  <tr key={s.tenor} className="hover:bg-slate-800/40 text-slate-300">
                    <td className="py-2.5 px-3 font-semibold text-slate-200">{s.tenor}</td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-slate-400">
                      {s.benchmarkYield.toFixed(2)}%
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-slate-200 font-semibold">
                      {s.entityYield.toFixed(2)}%
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-cyan-300">
                      +{s.spreadBps} bps
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-amber-300">
                      {s.cdsSpreadBps} bps
                    </td>
                    <td className={`py-2.5 px-3 text-right tabular-nums font-bold ${
                      isNegativeBasis ? 'text-rose-400' : 'text-emerald-400'
                    }`}>
                      {s.cdsBondBasisBps > 0 ? `+${s.cdsBondBasisBps}` : s.cdsBondBasisBps} bps
                    </td>
                    <td className="py-2.5 px-3 font-sans text-xs">
                      {isNegativeBasis ? (
                        <span className="text-rose-300 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3 text-rose-400 shrink-0" />
                          <span>Negative Basis: Physical cash illiquidity / repo friction</span>
                        </span>
                      ) : (
                        <span className="text-slate-400">
                          Positive Basis: Synthetic CDS hedging demand / downgrade alert
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* SECTION 2: CHRONOLOGICAL REFINANCING & MATURITY WALL */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <CalendarClock className="w-4 h-4 text-cyan-400" />
              <span>Refinancing & Rollover Risk Matrix: Chronological Maturity Wall</span>
            </h2>
            <p className="text-xs text-slate-400">
              Evaluates market-access risks across upcoming 12, 24, 36, and 60-month redemption windows.
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="text-slate-400">
              3-Year Rollover Share: <span className="text-amber-300 font-bold">{threeYearRolloverRatio.toFixed(1)}%</span>
            </span>
          </div>
        </div>

        {/* Visual Maturity Wall Stack */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {wallItems.map((item, idx) => {
              const heightPct = (item.amount / maxWallAmount) * 100;
              return (
                <div key={idx} className="space-y-2 flex flex-col justify-end">
                  <div className="text-center font-mono">
                    <span className="text-sm font-bold text-slate-100 tabular-nums">
                      ${item.amount.toLocaleString()}M
                    </span>
                    <span className="text-[11px] text-slate-500 block">
                      {entity.totalDirectDebtMillions > 0
                        ? `${((item.amount / entity.totalDirectDebtMillions) * 100).toFixed(1)}%`
                        : ''}
                    </span>
                  </div>

                  <div className="h-32 w-full bg-slate-950 rounded border border-slate-800 flex items-end p-1">
                    <div
                      className={`w-full rounded-xs transition-all duration-300 ${item.color}`}
                      style={{ height: `${Math.max(6, heightPct)}%` }}
                    />
                  </div>

                  <div className="text-center text-xs font-medium text-slate-300">
                    {item.label}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Rollover & Liquidity Diagnostics */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3 border-t border-slate-800/80">
            <div className="p-3 bg-slate-950 border border-slate-800 rounded">
              <span className="text-xs text-slate-500 block">12-Month Refinancing Burden</span>
              <span className="font-mono text-sm font-bold text-rose-300 tabular-nums">
                ${entity.maturityWall.within12M.toLocaleString()}M
              </span>
              <span className="text-[11px] text-slate-500 block mt-0.5">
                Immediate market rollover exposure
              </span>
            </div>

            <div className="p-3 bg-slate-950 border border-slate-800 rounded">
              <span className="text-xs text-slate-500 block">Total 3-Year Maturity Wall</span>
              <span className="font-mono text-sm font-bold text-amber-300 tabular-nums">
                ${totalMaturingIn3Years.toLocaleString()}M
              </span>
              <span className="text-[11px] text-slate-500 block mt-0.5">
                Cumulates through year 3
              </span>
            </div>

            <div className="p-3 bg-slate-950 border border-slate-800 rounded">
              <span className="text-xs text-slate-500 block">Market Access Stress Score</span>
              <span className={`font-mono text-sm font-bold tabular-nums ${
                entity.marketAccessStressScore > 60 ? 'text-rose-400' :
                entity.marketAccessStressScore > 40 ? 'text-amber-400' : 'text-emerald-400'
              }`}>
                {entity.marketAccessStressScore}/100
              </span>
              <span className="text-[11px] text-slate-500 block mt-0.5">
                Liquidity buffer vs maturity density
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
