import React from 'react';
import { X, BookOpen, Sigma, Calculator, HelpCircle } from 'lucide-react';

interface FormulaGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const FormulaGuideModal: React.FC<FormulaGuideModalProps> = ({
  isOpen,
  onClose,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700/80 rounded w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded bg-cyan-950/60 border border-cyan-500/50 flex items-center justify-center text-cyan-400">
              <Sigma className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100">
                Institutional Financial Equations & Analytical Specifications
              </h2>
              <p className="text-xs text-slate-400">
                Mathematical foundations of DSA, CDS Basis, Tax Elasticity, and Refunding
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 text-slate-400 hover:text-slate-100 rounded hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-300 leading-relaxed">
          {/* Equation 1: IMF/World Bank DSA */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-cyan-300">
              1. IMF / World Bank Debt Dynamics Equation
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-cyan-200 text-sm overflow-x-auto text-center">
              Δd_t = [ (r_t - g_t) / (1 + g_t) ] · d_(t-1) - p_t
            </div>
            <ul className="list-disc list-inside space-y-1 text-slate-400 font-mono text-[11px]">
              <li><strong className="text-slate-200 font-sans">d_t</strong>: Public Debt-to-GDP ratio (or Debt-to-Operating Revenue ratio) at period t</li>
              <li><strong className="text-slate-200 font-sans">r_t</strong>: Real effective interest rate on public debt</li>
              <li><strong className="text-slate-200 font-sans">g_t</strong>: Real economic growth rate of the jurisdiction</li>
              <li><strong className="text-slate-200 font-sans">p_t</strong>: Primary fiscal balance as % of GDP (Surplus &gt; 0, Deficit &lt; 0)</li>
              <li><strong className="text-slate-200 font-sans">(r - g)/(1 + g)</strong>: The "Snowball Effect". If r &gt; g, debt expands automatically unless offset by primary surpluses.</li>
            </ul>
          </div>

          {/* Equation 2: Debt-Stabilizing Primary Balance */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-cyan-300">
              2. Debt-Stabilizing Primary Balance (p*)
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-cyan-200 text-sm overflow-x-auto text-center">
              p* = [ (r - g) / (1 + g) ] · d
            </div>
            <p className="text-slate-400">
              Defines the exact non-interest budgetary balance needed to freeze the debt-to-GDP ratio at its current level. If the government’s actual primary balance is below p*, the debt trajectory diverges unsustainably.
            </p>
          </div>

          {/* Equation 3: Tax Elasticity Coefficient */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-cyan-300">
              3. Tax Elasticity Coefficient (E) & SVAR Response
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-cyan-200 text-sm overflow-x-auto text-center">
              E = ( % Δ Tax Revenue ) / ( % Δ Regional GDP )
            </div>
            <p className="text-slate-400">
              Measures the automatic responsiveness of revenues to economic cycles. Subnationals and municipalities with progressive income tax structures or capital gains reliance typically display E between 1.30 and 1.90, suffering catastrophic revenue plunges during mild recessions.
            </p>
          </div>

          {/* Equation 4: CDS-Bond Basis */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-cyan-300">
              4. Credit Default Swap (CDS) - Cash Bond Basis
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-cyan-200 text-sm overflow-x-auto text-center">
              Basis = CDS Spread - Z-Spread (Cash Bond Spread)
            </div>
            <p className="text-slate-400">
              The theoretical difference between synthetic default protection and cash physical bond spreads:
            </p>
            <ul className="list-disc list-inside space-y-1 text-slate-400 text-[11px]">
              <li><strong className="text-rose-300 font-mono">Negative Basis (&lt; 0):</strong> Physical bond yield spread exceeds CDS spread. Signals market illiquidity, balance sheet cost for bondholders, or funding distress.</li>
              <li><strong className="text-emerald-300 font-mono">Positive Basis (&gt; 0):</strong> CDS spread exceeds physical bond spread. Signals speculative short hedging, shortage of cash paper, or impending credit downgrade.</li>
            </ul>
          </div>

          {/* Equation 5: NPV Refunding Hurdle */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-cyan-300">
              5. Net Present Value (NPV) Bond Refunding Savings
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-cyan-200 text-sm overflow-x-auto text-center">
              NPV % = [ PV(Old Debt Service) - PV(New Debt Service) - Issuance Costs ] / Refunded Par
            </div>
            <p className="text-slate-400">
              Industry standard policy requires a minimum threshold of <strong className="text-emerald-400">3.00% NPV savings</strong> to justify executing a refunding, factoring in legal, rating agency, and underwriting frictions.
            </p>
          </div>

          {/* Equation 6: Defeasance Escrow Linear Program */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-cyan-300">
              6. Defeasance Escrow Linear Program (SciPy Optimization)
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-cyan-200 text-sm overflow-x-auto text-center">
              min  c^T · x    subject to    A_eq · x = b_eq,   x ≥ 0
            </div>
            <p className="text-slate-400">
              Minimizes the initial capital outlay required to purchase a portfolio of SLGS (State and Local Government Series) or Treasury STRIPS such that principal and interest receipts exactly match each future coupon payment and call redemption obligation without negative arbitrage violations.
            </p>
          </div>

          {/* Equation 7: Randori 7-Pillar Aggregation Rule */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-cyan-300">
              7. Randori Scorecard Pillar Aggregation (70/30 Fatal Weakness Rule)
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-cyan-200 text-sm overflow-x-auto text-center">
              P_k = 0.7 · ∑ (w_j · s_j) + 0.3 · max_j (s_j)
            </div>
            <p className="text-slate-400">
              Scores each pillar as 70% of the weighted average plus 30% of the highest single indicator score. One fatal vulnerability (e.g. an impending bond wall that liquid foreign reserves cannot cover) is explicitly captured rather than averaged away.
            </p>
          </div>

          {/* Equation 8: Randori Bayesian Log-Odds Update */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-cyan-300">
              8. Randori Bayesian Log-Odds Update (Layer 2)
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-cyan-200 text-sm overflow-x-auto text-center">
              logit(p_post) = logit(p_model) + w_s · (S_i - S̄) + ∑ w_k · z_(k,t)
            </div>
            <p className="text-slate-400">
              Combines the baseline discrete-time hazard model with the Randori 7-Pillar Scorecard (S_i) and live market signals z_k (spread-implied default probability, GDELT text stress index, and HMM regime state).
            </p>
          </div>

          {/* Equation 9: Expected Shortfall & PRI Actuarial Rate on Line */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-cyan-300">
              9. Political Risk Insurance (PRI) G-VaR Expected Shortfall & Rate on Line
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-cyan-200 text-sm overflow-x-auto text-center">
              ES_99% = E[ L | L ≥ VaR_99% ]  ·  Technical ROL = (Expected Loss + Tail Capital Cost) / Limit
            </div>
            <p className="text-slate-400">
              Prices political risk insurance (expropriation, currency inconvertibility, political violence, arbitration award default) using Monte Carlo simulated tail loss distributions adjusted by sector multipliers (mining 1.5x, telecoms 1.3x) and ACLED event location multipliers (0.7x to 2.0x).
            </p>
          </div>

          {/* Equation 10: Multi-Agency Live Data Ingestion & Accounting Reconciliation */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-cyan-300">
              10. Sovereign Multi-Agency Live Ingestion & Accounting Scope Reconciliation
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-cyan-200 text-sm overflow-x-auto text-center">
              Greenspan-Guidotti Buffer = FX Reserves / Short-Term External Debt (Target ≥ 1.0x)
            </div>
            <p className="text-slate-400">
              Dynamic REST pipelines automatically ingest live data from:
            </p>
            <ul className="list-disc list-inside space-y-1 text-slate-400 text-[11px]">
              <li><strong className="text-slate-200 font-sans">IMF WEO DataMapper:</strong> General Government Gross Debt (including subnational tiers and social security), Real GDP Growth, Inflation, and Primary Balance.</li>
              <li><strong className="text-slate-200 font-sans">World Bank WDI & IDS:</strong> Central Government direct debt liabilities, Total External Debt stocks, and Foreign Exchange Reserves.</li>
              <li><strong className="text-slate-200 font-sans">BIS SDMX:</strong> Central Bank Policy Rates and total credit conditions.</li>
              <li><strong className="text-slate-200 font-sans">UN Comtrade:</strong> Harmonized System (HS) merchandise trade exports, commodity concentration ratios, and terms-of-trade vulnerability.</li>
            </ul>
          </div>

          {/* Section 11: US Municipal Ingestion & Regulatory Framework */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-emerald-400">
              11. US Municipal Multi-Agency Ingestion (FED • FRED • FRB • MSRB • SEC)
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-emerald-200 text-sm overflow-x-auto text-center">
              Muni/Treasury Ratio = (AAA 10Y Muni Yield / 10Y US Treasury Yield) × 100
            </div>
            <p className="text-slate-400">
              Synchronized municipal ingestion calibrates local credit risk and market liquidity across 5 statutory authorities:
            </p>
            <ul className="list-disc list-inside space-y-1 text-slate-400 text-[11px]">
              <li><strong className="text-slate-200 font-sans">FRED (St. Louis Fed):</strong> S&P/Bond Buyer AAA 10Y Muni Yield, 20-Bond GO Index, 10Y Constant Maturity Treasury, and State/Local Tax Receipts (SAAR).</li>
              <li><strong className="text-slate-200 font-sans">Federal Reserve Board (FRB Z.1):</strong> Flow of Funds Table L.212 total municipal debt ($4.12T), household retail ownership share (68.4%), and Municipal Liquidity Facility (MLF) Section 13(3) haircut pricing.</li>
              <li><strong className="text-slate-200 font-sans">MSRB EMMA:</strong> 6-digit CUSIP registry, secondary market trade reporting, Municipal Market Data (MMD) benchmark curve spreads, and Rule 15c2-12 continuing disclosure postings.</li>
              <li><strong className="text-slate-200 font-sans">SEC EDGAR & OMS:</strong> Exchange Act Rule 15c2-12 audit timeliness (ACFR submission latency in days vs &lt;180-day benchmark), independent auditor opinion, and Form MA municipal advisor registrations.</li>
            </ul>
          </div>

          {/* Section 12: 5-Axis Fiscal Radar & Peer Normalization Engine */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-cyan-300">
              12. Cross-Sectional Peer Benchmark Radar & 5 Key Fiscal Metrics Normalization
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-cyan-200 text-xs overflow-x-auto text-center space-y-1">
              <div>Composite Fiscal Index = ∑ (w_i · MetricScore_i) where MetricScore_i ∈ [0, 100]</div>
              <div className="text-[11px] text-slate-400">Δ_peer = MetricScore_entity - μ_peer_group</div>
            </div>
            <p className="text-slate-400">
              Standardizes disparate multi-tier balance-sheet dimensions onto a normalized institutional radar polygon (pentagon) across five critical fiscal health vectors:
            </p>
            <ul className="list-disc list-inside space-y-1 text-slate-400 text-[11px]">
              <li><strong className="text-slate-200 font-sans">Debt Solvency & Leverage:</strong> Direct Debt / Annual Budget (or GDP scale). Normalization: <code className="text-cyan-300 font-mono">105 - (DebtRatio% × 0.70)</code> (lower leverage yields higher solvency score).</li>
              <li><strong className="text-slate-200 font-sans">Cash Reserves & Liquidity:</strong> Unrestricted days of cash, rainy day reserve months, or Greenspan-Guidotti FX reserve coverage days. Normalization: <code className="text-cyan-300 font-mono">15 + (Days / 180) × 80</code>.</li>
              <li><strong className="text-slate-200 font-sans">Debt Service Coverage (DSCR):</strong> Net operating revenues available for debt service covenants or primary fiscal balance headroom. Normalization: <code className="text-cyan-300 font-mono">((DSCR - 0.8) / 1.3) × 80 + 15</code>.</li>
              <li><strong className="text-slate-200 font-sans">Pension & OPEB Balance Sheet Health:</strong> Actuarial funded ratio under GASB 67/68 discount rate standards. Normalization: <code className="text-cyan-300 font-mono">(FundedRatio% / 100) × 88 + 8</code>.</li>
              <li><strong className="text-slate-200 font-sans">Market Access & Rollover Resilience:</strong> Rollover vulnerability and refinancing security. Normalization: <code className="text-cyan-300 font-mono">100 - MarketAccessStressScore</code>.</li>
            </ul>
          </div>

          {/* Section 13: Geographic Location & Neighboring Entities Contagion Map */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-2">
            <div className="text-xs font-bold text-cyan-300">
              13. Geographic Location & Neighboring Entities Contagion Map
            </div>
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded font-mono text-cyan-200 text-xs overflow-x-auto text-center space-y-1">
              <div>Contagion Severity = f(TaxOverlap, StatutoryIntergovernmentalShare, GeographicProximity)</div>
              <div className="text-[11px] text-slate-400">Projected (x, y) = MercatorScale · (Δλ · cos(φ_0), -Δφ) + Offset</div>
            </div>
            <p className="text-slate-400">
              Dynamic multi-tier geospatial model tracking spatial correlation, overlapping property tax assessments, regional commuter corridors, and fiscal spillover channels between the selected entity and adjacent jurisdictions:
            </p>
            <ul className="list-disc list-inside space-y-1 text-slate-400 text-[11px]">
              <li><strong className="text-slate-200 font-sans">Overlapping Tax Jurisdictions:</strong> Co-dependent assessments (e.g., City of Chicago and Cook County co-funding health/pensions on an identical AV base).</li>
              <li><strong className="text-slate-200 font-sans">Intergovernmental Statutory Channels:</strong> State Local Government Distributive Fund formula transfers, pension intercepts, and transit authority funding.</li>
              <li><strong className="text-slate-200 font-sans">Cross-Border Spillover Risk:</strong> Inter-entity trade corridors, shared utilities/water compacts, and bilateral supply chain linkages.</li>
              <li><strong className="text-slate-200 font-sans">Multi-Mode Color Topography:</strong> Color-coded nodes and bezier contagion vectors categorized by Credit Rating (AAA to B/CCC), Fiscal Stress Score (0–100), Government Tier (Municipal, Subnational, Sovereign), or Spillover Contagion Severity.</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold text-slate-950 bg-cyan-400 hover:bg-cyan-300 rounded transition-colors"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
};
