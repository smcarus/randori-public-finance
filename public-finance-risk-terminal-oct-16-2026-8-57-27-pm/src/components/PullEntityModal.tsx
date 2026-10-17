import React, { useState } from 'react';
import { PublicFinanceEntity, GovernmentTier } from '../types/finance';
import {
  X,
  Download,
  Globe2,
  Building2,
  Landmark,
  Sparkles,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Database,
  Search,
  Scale,
  FileText,
  TrendingUp,
  ShieldCheck,
  Building
} from 'lucide-react';

interface PullEntityModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddEntity: (newEntity: PublicFinanceEntity) => void;
}

export const PullEntityModal: React.FC<PullEntityModalProps> = ({
  isOpen,
  onClose,
  onAddEntity,
}) => {
  const [mode, setMode] = useState<'us-muni-live' | 'sovereign-live' | 'custom-muni-sub'>('us-muni-live');

  // US Municipal Live Pull State
  const [muniQuery, setMuniQuery] = useState<string>('nyc');
  const [isPullingMuni, setIsPullingMuni] = useState<boolean>(false);
  const [muniError, setMuniError] = useState<string | null>(null);
  const [muniSuccess, setMuniSuccess] = useState<string | null>(null);

  // Quick Preset US Municipalities
  const quickMunis = [
    { id: 'nyc', name: 'New York City', state: 'NY', rating: 'AA', cusip: '64966Q', category: 'City GO' },
    { id: 'chicago', name: 'City of Chicago', state: 'IL', rating: 'BBB+', cusip: '167735', category: 'City GO' },
    { id: 'la_county', name: 'Los Angeles County', state: 'CA', rating: 'AA+', cusip: '544652', category: 'County GO' },
    { id: 'miami', name: 'City of Miami', state: 'FL', rating: 'Aa2', cusip: '593339', category: 'City GO' },
    { id: 'detroit', name: 'City of Detroit', state: 'MI', rating: 'Baa2', cusip: '250843', category: 'City GO' },
    { id: 'california', name: 'State of California', state: 'CA', rating: 'AA-', cusip: '13063X', category: 'State GO' },
    { id: 'puerto_rico', name: 'Puerto Rico', state: 'PR', rating: 'CCC+', cusip: '74514L', category: 'State GO' },
    { id: 'texas', name: 'State of Texas', state: 'TX', rating: 'AAA', cusip: '882721', category: 'State GO' },
    { id: 'austin', name: 'City of Austin', state: 'TX', rating: 'AA+', cusip: '052441', category: 'City GO' },
    { id: 'bart', name: 'SF Bay Area Transit', state: 'CA', rating: 'AA+', cusip: '072024', category: 'Transit' },
    { id: 'mta_ny', name: 'Metropolitan Transit', state: 'NY', rating: 'A-', cusip: '592595', category: 'Transit' },
    { id: 'philadelphia', name: 'Philadelphia', state: 'PA', rating: 'A', cusip: '717813', category: 'City GO' },
    { id: 'seattle', name: 'City of Seattle', state: 'WA', rating: 'AAA', cusip: '812643', category: 'City GO' },
    { id: 'dc', name: 'District of Columbia', state: 'DC', rating: 'AAA', cusip: '254887', category: 'City GO' },
  ];

  // Sovereign Live Pull State
  const [sovereignQuery, setSovereignQuery] = useState<string>('NGA');
  const [isPulling, setIsPulling] = useState<boolean>(false);
  const [pullError, setPullError] = useState<string | null>(null);
  const [pullSuccess, setPullSuccess] = useState<string | null>(null);

  // Quick Preset Countries
  const quickSovereigns = [
    { code: 'NGA', name: 'Nigeria', flag: '🇳🇬' },
    { code: 'EGY', name: 'Egypt', flag: '🇪🇬' },
    { code: 'GHA', name: 'Ghana', flag: '🇬🇭' },
    { code: 'KEN', name: 'Kenya', flag: '🇰🇪' },
    { code: 'TUR', name: 'Turkey', flag: '🇹🇷' },
    { code: 'ARG', name: 'Argentina', flag: '🇦🇷' },
    { code: 'MEX', name: 'Mexico', flag: '🇲🇽' },
    { code: 'COL', name: 'Colombia', flag: '🇨🇴' },
    { code: 'PAK', name: 'Pakistan', flag: '🇵🇰' },
    { code: 'IDN', name: 'Indonesia', flag: '🇮🇩' },
    { code: 'VNM', name: 'Vietnam', flag: '🇻🇳' },
    { code: 'POL', name: 'Poland', flag: '🇵🇱' },
  ];

  // Custom Entity Form State
  const [customTier, setCustomTier] = useState<GovernmentTier>('municipal');
  const [customName, setCustomName] = useState<string>('City of Miami');
  const [customJurisdiction, setCustomJurisdiction] = useState<string>('Florida, US');
  const [customRating, setCustomRating] = useState<string>('Aa2');
  const [customDebtMillions, setCustomDebtMillions] = useState<number>(3850);
  const [customBudgetBillions, setCustomBudgetBillions] = useState<number>(1.4);
  const [customOwnSourceRatio, setCustomOwnSourceRatio] = useState<number>(72);
  const [customMillRate, setCustomMillRate] = useState<number>(17.8);
  const [customPensionFundedRatio, setCustomPensionFundedRatio] = useState<number>(68);

  if (!isOpen) return null;

  // Handle US Municipality Ingestion (FED, FRED, FRB, MSRB, SEC)
  const handlePullMunicipality = async (query: string) => {
    setIsPullingMuni(true);
    setMuniError(null);
    setMuniSuccess(null);

    const cleanQuery = query.trim();
    if (!cleanQuery) {
      setMuniError('Please enter a US municipality name, city, county, or CUSIP-6.');
      setIsPullingMuni(false);
      return;
    }

    try {
      const resp = await fetch(`/api/entities/import-municipality?query=${encodeURIComponent(cleanQuery)}`);
      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }
      const data = await resp.json();
      if (!data.entity) {
        throw new Error('No entity returned by US Municipal Ingestion service.');
      }

      onAddEntity(data.entity);
      setMuniSuccess(`Successfully ingested ${data.entity.name} with live feeds from FED, FRED, FRB, MSRB, and SEC!`);
      setTimeout(() => {
        onClose();
        setMuniSuccess(null);
      }, 1500);
    } catch (err: any) {
      console.error('Failed to import US municipal entity:', err);
      setMuniError(err.message || 'Failed to pull live US municipal data.');
    } finally {
      setIsPullingMuni(false);
    }
  };

  // Handle Live Sovereign Ingestion (IMF, World Bank, BIS, UN Comtrade)
  const handlePullSovereign = async (countryCode: string) => {
    setIsPulling(true);
    setPullError(null);
    setPullSuccess(null);

    const cleanCode = countryCode.trim().toUpperCase();
    if (!cleanCode) {
      setPullError('Please provide a valid ISO-3 country code or name.');
      setIsPulling(false);
      return;
    }

    try {
      const resp = await fetch(`/api/entities/import-sovereign?country=${cleanCode}`);
      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }
      const data = await resp.json();
      if (!data.entity) {
        throw new Error('No entity payload returned by sovereign ingestion service.');
      }

      onAddEntity(data.entity);
      setPullSuccess(`Successfully ingested ${data.entity.name} with live feeds from IMF, World Bank, BIS, and UN Comtrade!`);
      setTimeout(() => {
        onClose();
        setPullSuccess(null);
      }, 1500);
    } catch (err: any) {
      console.error('Failed to import sovereign entity:', err);
      setPullError(err.message || 'Failed to pull live data for country.');
    } finally {
      setIsPulling(false);
    }
  };

  // Handle Custom Municipal / Subnational Creation
  const handleCreateCustomEntity = (e: React.FormEvent) => {
    e.preventDefault();

    const id = `custom-${customTier}-${Date.now()}`;
    const newEntity: PublicFinanceEntity = {
      id,
      name: customName,
      tier: customTier,
      jurisdiction: customJurisdiction,
      creditRating: customRating,
      ratingOutlook: 'Stable',
      currency: 'USD',
      gdpOrBudgetBillions: customBudgetBillions,
      totalDirectDebtMillions: customDebtMillions,
      weightedAverageMaturityYears: 8.5,
      modifiedDurationYears: 5.4,
      durationGapYears: 1.8,
      marketAccessStressScore: 42,
      taxElasticityCoefficient: 1.15,
      fiscalMultiplierSpending: 1.10,
      fiscalMultiplierTax: -0.75,
      bonds: [
        {
          id: `${id}-bond-1`,
          name: `${customName} Series 2024A Senior GO Bonds`,
          type: 'GO',
          parAmount: Math.round(customDebtMillions * 0.65),
          coupon: 4.50,
          yieldToMaturity: 4.15,
          maturityDate: '2034-08-01',
          callDate: '2029-08-01',
          callPrice: 100,
          rating: customRating,
          isCallable: true,
          spreadOverBenchmarkBps: 65,
          isTaxExempt: true,
        },
        {
          id: `${id}-bond-2`,
          name: `${customName} Revenue Improvement Bonds`,
          type: 'Revenue',
          parAmount: Math.round(customDebtMillions * 0.35),
          coupon: 5.00,
          yieldToMaturity: 4.70,
          maturityDate: '2038-12-01',
          rating: customRating,
          isCallable: false,
          spreadOverBenchmarkBps: 95,
          isTaxExempt: true,
        },
      ],
      vrdos: [
        {
          id: `${id}-vrdo-1`,
          name: `${customName} Multi-Modal VRDO Series 2021`,
          parAmount: Math.round(customDebtMillions * 0.12),
          currentResetRate: 3.45,
          mode: 'Weekly',
          remarketingAgent: 'BofA Securities',
          liquidityProvider: 'JPMorgan Chase Bank, N.A.',
          locExpirationDate: '2026-06-30',
          daysToLocExpiry: 240,
          bankBondRate: 8.0,
        },
      ],
      pppConcessions: [],
      stateOwnedEnterprises: [],
      marketSpreads: [
        { tenor: '1Y', benchmarkYield: 3.05, entityYield: 3.45, spreadBps: 40, cdsSpreadBps: 35, cdsBondBasisBps: -5 },
        { tenor: '3Y', benchmarkYield: 3.15, entityYield: 3.65, spreadBps: 50, cdsSpreadBps: 45, cdsBondBasisBps: -5 },
        { tenor: '5Y', benchmarkYield: 3.30, entityYield: 3.95, spreadBps: 65, cdsSpreadBps: 60, cdsBondBasisBps: -5 },
        { tenor: '10Y', benchmarkYield: 3.65, entityYield: 4.45, spreadBps: 80, cdsSpreadBps: 78, cdsBondBasisBps: -2 },
        { tenor: '20Y', benchmarkYield: 4.10, entityYield: 5.05, spreadBps: 95, cdsSpreadBps: 95, cdsBondBasisBps: 0 },
        { tenor: '30Y', benchmarkYield: 4.30, entityYield: 5.35, spreadBps: 105, cdsSpreadBps: 108, cdsBondBasisBps: +3 },
      ],
      maturityWall: {
        within12M: Math.round(customDebtMillions * 0.12),
        year1to2: Math.round(customDebtMillions * 0.15),
        year2to3: Math.round(customDebtMillions * 0.18),
        year3to5: Math.round(customDebtMillions * 0.25),
        beyond5Y: Math.round(customDebtMillions * 0.30),
      },
    };

    if (customTier === 'municipal') {
      newEntity.municipalMetrics = {
        ownSourceRevenueRatio: customOwnSourceRatio / 100,
        melloRoosOverlappingDebtRatio: 0.048,
        specialAssessmentDistrictsCount: 3,
        totalAssessedValue: Number((customBudgetBillions * 25).toFixed(1)),
        millRate: customMillRate,
        millRateSensitivityRevenueDropPer5PctAV: Number((customBudgetBillions * 25 * 0.05 * (customMillRate / 1000) * 1000).toFixed(1)),
        dscrCoverage: 1.65,
        infrastructureBacklog: Math.round(customDebtMillions * 0.22),
        infrastructureBacklogPctBudget: 0.35,
        liquidityDaysOfCash: 165,
      };
    } else if (customTier === 'subnational') {
      newEntity.subnationalMetrics = {
        netPensionLiability: Math.round(customDebtMillions * 0.45),
        pensionFundedRatio: customPensionFundedRatio,
        pensionDiscountRate: 7.00,
        medicaidExpenditureShare: 26.5,
        medicaidCounterCyclicalSurgeRate: 15.0,
        fmapFederalShare: 58.0,
        transferDependenceRatio: 28.5,
        rainyDayFundReserveMonths: 2.4,
      };
    }

    onAddEntity(newEntity);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
      <div className="bg-slate-900 border border-slate-700/80 rounded-lg max-w-3xl w-full max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-cyan-950 border border-cyan-500/50 flex items-center justify-center text-cyan-400">
              <Download className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <span>Pull New Entity into Terminal</span>
                <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950/70 border border-cyan-800/80 rounded px-1.5 py-0.2">
                  Institutional Ingestion
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Pull US Municipalities with live FED, FRED, FRB, MSRB & SEC feeds or Sovereigns with IMF, WB, BIS & Comtrade feeds.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            aria-label="Close Modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Mode Selector Tabs */}
        <div className="px-6 pt-3 border-b border-slate-800 flex gap-2 bg-slate-950/40">
          <button
            onClick={() => setMode('us-muni-live')}
            className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors ${
              mode === 'us-muni-live'
                ? 'border-emerald-400 text-emerald-300 bg-slate-900'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Landmark className="w-3.5 h-3.5 text-emerald-400" />
            <span>US Municipal Pull (FED • FRED • FRB • MSRB • SEC)</span>
          </button>

          <button
            onClick={() => setMode('sovereign-live')}
            className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors ${
              mode === 'sovereign-live'
                ? 'border-cyan-400 text-cyan-300 bg-slate-900'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Globe2 className="w-3.5 h-3.5 text-cyan-400" />
            <span>Sovereign Pull (IMF • WB • BIS • Comtrade)</span>
          </button>

          <button
            onClick={() => setMode('custom-muni-sub')}
            className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors ${
              mode === 'custom-muni-sub'
                ? 'border-amber-400 text-amber-300 bg-slate-900'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Building2 className="w-3.5 h-3.5 text-amber-400" />
            <span>Custom Modeling</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5">
          {/* ========================================================================= */}
          {/* TAB 1: US MUNICIPAL LIVE PULL (FED, FRED, FRB, MSRB, SEC)                 */}
          {/* ========================================================================= */}
          {mode === 'us-muni-live' && (
            <div className="space-y-5">
              {/* Data Pipeline Banner */}
              <div className="p-3.5 bg-emerald-950/20 border border-emerald-800/40 rounded-lg flex items-start gap-3">
                <Database className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                <div className="text-xs space-y-1">
                  <span className="font-semibold text-emerald-300">
                    Live Multi-Agency US Municipal Ingestion Engine
                  </span>
                  <p className="text-slate-300 leading-relaxed text-[11px]">
                    Pulling any US City, County, State GO, or Authority with synchronized live feeds across:
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-mono text-[10px]">
                    <span className="px-2 py-1 bg-emerald-900/40 border border-emerald-700/60 rounded text-emerald-200 flex items-center gap-1.5">
                      <TrendingUp className="w-3 h-3 text-emerald-400" />
                      <span>FRED (Muni Yields / Ratios)</span>
                    </span>
                    <span className="px-2 py-1 bg-emerald-900/40 border border-emerald-700/60 rounded text-emerald-200 flex items-center gap-1.5">
                      <Building className="w-3 h-3 text-emerald-400" />
                      <span>FED/FRB (Z.1 Flow of Funds)</span>
                    </span>
                    <span className="px-2 py-1 bg-emerald-900/40 border border-emerald-700/60 rounded text-emerald-200 flex items-center gap-1.5">
                      <FileText className="w-3 h-3 text-emerald-400" />
                      <span>MSRB EMMA (CUSIP Trades)</span>
                    </span>
                    <span className="px-2 py-1 bg-emerald-900/40 border border-emerald-700/60 rounded text-emerald-200 flex items-center gap-1.5">
                      <Scale className="w-3 h-3 text-emerald-400" />
                      <span>SEC (Rule 15c2-12 / CIK)</span>
                    </span>
                  </div>
                </div>
              </div>

              {/* Search & Ingestion Input */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                  <span>Search US Municipality by Name, City, State, or CUSIP-6:</span>
                  <span className="text-[11px] text-slate-400 font-normal">e.g., Chicago, NYC, 64966Q, Dallas, BART</span>
                </label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                    <input
                      type="text"
                      value={muniQuery}
                      onChange={(e) => setMuniQuery(e.target.value)}
                      placeholder="Enter municipality name or 6-digit CUSIP..."
                      className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 pl-9 text-xs text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500 font-mono"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handlePullMunicipality(muniQuery);
                      }}
                    />
                  </div>
                  <button
                    onClick={() => handlePullMunicipality(muniQuery)}
                    disabled={isPullingMuni}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-semibold rounded flex items-center gap-2 transition-colors shadow-sm"
                  >
                    {isPullingMuni ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Querying Agencies...</span>
                      </>
                    ) : (
                      <>
                        <Download className="w-3.5 h-3.5" />
                        <span>Ingest US Municipality</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Feedback Notifications */}
              {muniError && (
                <div className="p-3 bg-red-950/40 border border-red-800/80 rounded text-xs text-red-300 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
                  <span>{muniError}</span>
                </div>
              )}
              {muniSuccess && (
                <div className="p-3 bg-emerald-950/50 border border-emerald-700 rounded text-xs text-emerald-300 flex items-center gap-2 animate-in fade-in">
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                  <span>{muniSuccess}</span>
                </div>
              )}

              {/* Quick Select Preset Munis */}
              <div className="space-y-2">
                <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>Institutional Benchmark Municipalities:</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {quickMunis.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => {
                        setMuniQuery(m.id);
                        handlePullMunicipality(m.id);
                      }}
                      disabled={isPullingMuni}
                      className="p-2.5 bg-slate-950 hover:bg-slate-800/80 border border-slate-800 hover:border-emerald-600/70 rounded text-left transition-all group flex flex-col justify-between"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-xs text-slate-200 group-hover:text-emerald-300">
                          {m.name}
                        </span>
                        <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 bg-slate-800 border border-slate-700 rounded text-emerald-300">
                          {m.rating}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono mt-1.5 pt-1 border-t border-slate-800/60">
                        <span>CUSIP: {m.cusip}</span>
                        <span className="text-slate-400">{m.state} • {m.category}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Technical Overview Cards */}
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-3">
                <div className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Multi-Source Accounting Reconciliation & Regulatory Scope</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[11px] text-slate-400 leading-relaxed">
                  <div className="p-2.5 bg-slate-900 border border-slate-800/80 rounded space-y-1">
                    <span className="font-semibold text-emerald-300 block">FRED & Federal Reserve Board</span>
                    <p>
                      Calibrates S&P/Bond Buyer AAA 10Y Muni yields against the US Treasury curve. Calculates municipal-to-Treasury ratios, Flow of Funds Table L.212 total municipal debt ($4.12T), and Section 13(3) Municipal Liquidity Facility (MLF) terms.
                    </p>
                  </div>
                  <div className="p-2.5 bg-slate-900 border border-slate-800/80 rounded space-y-1">
                    <span className="font-semibold text-cyan-300 block">MSRB EMMA & SEC EDGAR</span>
                    <p>
                      Tracks CUSIP-6 issuance, secondary trade pricing, spread over MMD AAA scale, and SEC Rule 15c2-12 compliance. Audits ACFR submission latency (benchmark &lt;180 days) and Form MA registered advisors.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 2: SOVEREIGN LIVE PULL (IMF, WORLD BANK, BIS, UN COMTRADE)            */}
          {/* ========================================================================= */}
          {mode === 'sovereign-live' && (
            <div className="space-y-5">
              {/* Sovereign Pipeline Banner */}
              <div className="p-3.5 bg-cyan-950/30 border border-cyan-800/50 rounded-lg flex items-start gap-3">
                <Database className="w-4 h-4 text-cyan-400 mt-0.5 shrink-0" />
                <div className="text-xs space-y-1">
                  <span className="font-semibold text-cyan-300">
                    Live Sovereign Multi-Agency Ingestion Engine
                  </span>
                  <p className="text-slate-300 leading-relaxed text-[11px]">
                    Ingests verified macro indicators across IMF (General Govt Gross Debt & Fiscal), World Bank (Central Govt Debt & Reserves), BIS (Central Bank Policy Rates), and UN Comtrade (Commodity Concentration).
                  </p>
                </div>
              </div>

              {/* Ingestion Search Input */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                  <span>Enter Sovereign Country ISO-3 Code or Country Name:</span>
                  <span className="text-[11px] text-slate-400 font-normal">e.g., NGA, EGY, ZAF, BRA, CHL, GHA, TUR</span>
                </label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                    <input
                      type="text"
                      value={sovereignQuery}
                      onChange={(e) => setSovereignQuery(e.target.value)}
                      placeholder="e.g. NGA, Egypt, Colombia, TUR..."
                      className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 pl-9 text-xs text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 font-mono uppercase"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handlePullSovereign(sovereignQuery);
                      }}
                    />
                  </div>
                  <button
                    onClick={() => handlePullSovereign(sovereignQuery)}
                    disabled={isPulling}
                    className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-semibold rounded flex items-center gap-2 transition-colors shadow-sm"
                  >
                    {isPulling ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Querying APIs...</span>
                      </>
                    ) : (
                      <>
                        <Download className="w-3.5 h-3.5" />
                        <span>Pull Sovereign Entity</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Feedback Notifications */}
              {pullError && (
                <div className="p-3 bg-red-950/40 border border-red-800/80 rounded text-xs text-red-300 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
                  <span>{pullError}</span>
                </div>
              )}
              {pullSuccess && (
                <div className="p-3 bg-emerald-950/50 border border-emerald-700 rounded text-xs text-emerald-300 flex items-center gap-2 animate-in fade-in">
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                  <span>{pullSuccess}</span>
                </div>
              )}

              {/* Quick Select Sovereigns */}
              <div className="space-y-2">
                <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>Emerging & Frontier Sovereign Presets:</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {quickSovereigns.map((s) => (
                    <button
                      key={s.code}
                      onClick={() => {
                        setSovereignQuery(s.code);
                        handlePullSovereign(s.code);
                      }}
                      disabled={isPulling}
                      className="p-2 bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-cyan-600/70 rounded text-left transition-all group flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-base">{s.flag}</span>
                        <div>
                          <div className="font-semibold text-xs text-slate-200 group-hover:text-cyan-300">
                            {s.name}
                          </div>
                          <div className="text-[10px] font-mono text-slate-400">
                            {s.code}
                          </div>
                        </div>
                      </div>
                      <ArrowRight className="w-3 h-3 text-slate-600 group-hover:text-cyan-400 transition-transform group-hover:translate-x-0.5" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 3: CUSTOM MUNICIPAL OR SUBNATIONAL ENTITY CREATION                     */}
          {/* ========================================================================= */}
          {mode === 'custom-muni-sub' && (
            <form onSubmit={handleCreateCustomEntity} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-300">Government Tier</label>
                  <select
                    value={customTier}
                    onChange={(e) => setCustomTier(e.target.value as GovernmentTier)}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
                  >
                    <option value="municipal">Municipal (City, County, School District)</option>
                    <option value="subnational">Subnational (State, Province, Autonomous Region)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-300">Entity Legal Name</label>
                  <input
                    type="text"
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
                    placeholder="e.g. City of Seattle"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-300">Jurisdiction / State</label>
                  <input
                    type="text"
                    value={customJurisdiction}
                    onChange={(e) => setCustomJurisdiction(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
                    placeholder="e.g. Washington, United States"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-300">Credit Rating (Fitch/Moody's/S&P)</label>
                  <select
                    value={customRating}
                    onChange={(e) => setCustomRating(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
                  >
                    <option value="Aaa">Aaa / AAA (Prime Benchmark)</option>
                    <option value="Aa1">Aa1 / AA+ (High Grade)</option>
                    <option value="Aa2">Aa2 / AA (High Grade)</option>
                    <option value="Aa3">Aa3 / AA- (Upper Medium)</option>
                    <option value="A1">A1 / A+ (Upper Medium)</option>
                    <option value="A2">A2 / A (Upper Medium)</option>
                    <option value="Baa1">Baa1 / BBB+ (Lower Medium)</option>
                    <option value="Baa2">Baa2 / BBB (Lower Medium)</option>
                    <option value="Baa3">Baa3 / BBB- (Threshold Investment Grade)</option>
                    <option value="Ba2">Ba2 / BB (Speculative / High Yield)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-300">Annual Budget ($ Billions)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={customBudgetBillions}
                    onChange={(e) => setCustomBudgetBillions(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500 font-mono"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-300">Total Direct Debt ($ Millions)</label>
                  <input
                    type="number"
                    value={customDebtMillions}
                    onChange={(e) => setCustomDebtMillions(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500 font-mono"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-300">Own-Source Revenue Ratio (%)</label>
                  <input
                    type="number"
                    value={customOwnSourceRatio}
                    onChange={(e) => setCustomOwnSourceRatio(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500 font-mono"
                    min="1"
                    max="100"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-300">
                    {customTier === 'municipal' ? 'Property Mill Rate ($/$1,000)' : 'Pension Funded Ratio (%)'}
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={customTier === 'municipal' ? customMillRate : customPensionFundedRatio}
                    onChange={(e) =>
                      customTier === 'municipal'
                        ? setCustomMillRate(Number(e.target.value))
                        : setCustomPensionFundedRatio(Number(e.target.value))
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500 font-mono"
                  />
                </div>
              </div>

              <div className="pt-3 border-t border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold rounded flex items-center gap-2 transition-colors shadow-sm"
                >
                  <Building2 className="w-3.5 h-3.5" />
                  <span>Instantiate Custom Entity</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
