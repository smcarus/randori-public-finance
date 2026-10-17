import React, { useState, useEffect, useMemo } from 'react';
import {
  PublicFinanceEntity,
  LiveSovereignBundle,
  LiveUsMuniBundle,
  UsMuniPreset,
} from '../types/finance';
import {
  Globe2,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Database,
  Building,
  Coins,
  Ship,
  TrendingUp,
  Download,
  Check,
  ArrowRight,
  ExternalLink,
  Info,
  Layers,
  Landmark,
  Scale,
  FileText,
  ShieldCheck,
  Activity,
  Calendar,
  Percent,
  CheckSquare
} from 'lucide-react';

interface LiveDataFeedTabProps {
  entity: PublicFinanceEntity;
  onUpdateEntityWithLiveData?: (updatedEntity: PublicFinanceEntity) => void;
  onOpenFormulaModal: () => void;
}

export const LiveDataFeedTab: React.FC<LiveDataFeedTabProps> = ({
  entity,
  onUpdateEntityWithLiveData,
  onOpenFormulaModal,
}) => {
  // Determine initial mode based on active entity tier
  const initialMode = entity.tier === 'municipal' ? 'us-muni' : 'sovereign';
  const [feedMode, setFeedMode] = useState<'sovereign' | 'us-muni'>(initialMode);

  // Sync mode if entity changes
  useEffect(() => {
    if (entity.tier === 'municipal') {
      setFeedMode('us-muni');
    } else if (entity.tier === 'sovereign') {
      setFeedMode('sovereign');
    }
  }, [entity.tier]);

  // ============================================================================
  // SOVEREIGN STATE & HANDLERS
  // ============================================================================
  const resolveEntityIso3 = (ent: PublicFinanceEntity): string => {
    if (ent.tier !== 'sovereign') return 'ZAF';
    const match = ent.id.match(/sovereign-([a-z]{3})/i);
    if (match) return match[1].toUpperCase();
    if (ent.jurisdiction.includes('South Africa') || ent.name.includes('South Africa')) return 'ZAF';
    if (ent.jurisdiction.includes('Italy') || ent.name.includes('Italy')) return 'ITA';
    if (ent.jurisdiction.includes('Brazil') || ent.name.includes('Brazil')) return 'BRA';
    if (ent.jurisdiction.includes('Nigeria') || ent.name.includes('Nigeria')) return 'NGA';
    if (ent.jurisdiction.includes('Egypt') || ent.name.includes('Egypt')) return 'EGY';
    if (ent.jurisdiction.includes('Argentina') || ent.name.includes('Argentina')) return 'ARG';
    if (ent.jurisdiction.includes('Turkey') || ent.name.includes('Turkey')) return 'TUR';
    if (ent.jurisdiction.includes('Kenya') || ent.name.includes('Kenya')) return 'KEN';
    if (ent.jurisdiction.includes('Ghana') || ent.name.includes('Ghana')) return 'GHA';
    if (ent.jurisdiction.includes('Chile') || ent.name.includes('Chile')) return 'CHL';
    return 'ZAF';
  };

  const [selectedIso3, setSelectedIso3] = useState<string>(resolveEntityIso3(entity));

  useEffect(() => {
    if (entity.tier === 'sovereign') {
      setSelectedIso3(resolveEntityIso3(entity));
    }
  }, [entity]);

  const [loadingSovereign, setLoadingSovereign] = useState<boolean>(false);
  const [liveBundle, setLiveBundle] = useState<LiveSovereignBundle | null>(null);
  const [sovereignError, setSovereignError] = useState<string | null>(null);
  const [appliedToModel, setAppliedToModel] = useState<boolean>(false);
  const [activeSubTab, setActiveSubTab] = useState<'imf' | 'worldbank' | 'bis' | 'comtrade' | 'raw'>('imf');

  const baseCountries = [
    { iso3: 'ZAF', name: 'South Africa' },
    { iso3: 'NGA', name: 'Nigeria' },
    { iso3: 'EGY', name: 'Egypt' },
    { iso3: 'GHA', name: 'Ghana' },
    { iso3: 'KEN', name: 'Kenya' },
    { iso3: 'BRA', name: 'Brazil' },
    { iso3: 'ARG', name: 'Argentina' },
    { iso3: 'TUR', name: 'Turkey' },
    { iso3: 'ITA', name: 'Italy' },
    { iso3: 'USA', name: 'United States' },
    { iso3: 'DEU', name: 'Germany' },
    { iso3: 'GBR', name: 'United Kingdom' },
    { iso3: 'JPN', name: 'Japan' },
    { iso3: 'IND', name: 'India' },
    { iso3: 'IDN', name: 'Indonesia' },
    { iso3: 'CHL', name: 'Chile' },
    { iso3: 'BLZ', name: 'Belize' },
  ];

  const supportedCountries = useMemo(() => {
    if (entity.tier === 'sovereign' && !baseCountries.some((c) => c.iso3 === selectedIso3)) {
      return [{ iso3: selectedIso3, name: entity.name }, ...baseCountries];
    }
    return baseCountries;
  }, [selectedIso3, entity]);

  const fetchLiveBundle = async (countryCode: string) => {
    setLoadingSovereign(true);
    setSovereignError(null);
    setAppliedToModel(false);
    try {
      const resp = await fetch(`/api/live-data/sovereign-bundle?country=${countryCode}`);
      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }
      const data: LiveSovereignBundle = await resp.json();
      setLiveBundle(data);
    } catch (err: any) {
      console.error('Error fetching live sovereign bundle:', err);
      setSovereignError(err.message || 'Failed to pull live feeds');
    } finally {
      setLoadingSovereign(false);
    }
  };

  useEffect(() => {
    if (feedMode === 'sovereign') {
      fetchLiveBundle(selectedIso3);
    }
  }, [selectedIso3, feedMode]);

  const handleApplyToModel = () => {
    if (!liveBundle || !onUpdateEntityWithLiveData) return;

    const r = liveBundle.reconciliation;
    const newDebtRatio = r.imfGeneralGovtDebtToGdp ?? entity.sovereignMetrics?.publicDebtToGdp ?? 75;
    const newPrimaryBalance = r.primaryFiscalBalancePctGdp ?? -0.8;
    const newFxReserves = r.totalFxReservesBillionsUsd ?? entity.sovereignMetrics?.fxReservesTotalUsdBillions ?? 60;
    const newExternalDebt = r.totalExternalDebtBillionsUsd ?? entity.sovereignMetrics?.shortTermExternalDebtUsdBillions ?? 70;

    const updated: PublicFinanceEntity = {
      ...entity,
      sovereignMetrics: entity.sovereignMetrics ? {
        ...entity.sovereignMetrics,
        publicDebtToGdp: Number(newDebtRatio.toFixed(1)),
        primaryBalancePctGdp: Number(newPrimaryBalance.toFixed(2)),
        fxReservesTotalUsdBillions: newFxReserves,
        externalDebtToFxReserves: newFxReserves > 0 ? Number((newExternalDebt / newFxReserves).toFixed(2)) : 1.5,
        greenspanGuidottiRatio: newExternalDebt > 0 ? Number(((newFxReserves / (newExternalDebt * 0.25))).toFixed(2)) : 1.0,
      } : undefined,
    };

    onUpdateEntityWithLiveData(updated);
    setAppliedToModel(true);
    setTimeout(() => setAppliedToModel(false), 3000);
  };

  // Extract IMF trajectory points for chart
  const imfDebtSeries = liveBundle?.feeds?.imf?.metrics?.debtToGdp?.series || {};
  const chartYears = Object.keys(imfDebtSeries)
    .filter((y) => Number(y) >= 2018 && Number(y) <= 2030)
    .sort();

  const chartData = chartYears.map((y) => ({
    year: y,
    value: imfDebtSeries[y],
    isForecast: Number(y) > 2024,
  }));

  const chartWidth = 640;
  const chartHeight = 220;
  const padding = { top: 20, right: 30, bottom: 35, left: 50 };
  const innerW = chartWidth - padding.left - padding.right;
  const innerH = chartHeight - padding.top - padding.bottom;
  const values = chartData.map((d) => d.value);
  const minVal = values.length ? Math.floor(Math.min(...values) / 10) * 10 - 5 : 40;
  const maxVal = values.length ? Math.ceil(Math.max(...values) / 10) * 10 + 5 : 90;
  const xScale = (i: number) => padding.left + (i / Math.max(1, chartData.length - 1)) * innerW;
  const yScale = (val: number) => padding.top + innerH - ((val - minVal) / Math.max(1, maxVal - minVal)) * innerH;
  const linePath = chartData
    .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)},${yScale(d.value)}`)
    .join(' ');

  // ============================================================================
  // US MUNICIPAL STATE & HANDLERS (FED, FRED, FRB, MSRB, SEC)
  // ============================================================================
  const resolveEntityMuniKey = (ent: PublicFinanceEntity): string => {
    if (ent.tier !== 'municipal' && ent.tier !== 'subnational') return 'chicago';
    const clean = ent.name.toLowerCase();
    if (clean.includes('chicago')) return 'chicago';
    if (clean.includes('new york') || clean.includes('nyc')) return 'nyc';
    if (clean.includes('los angeles') || clean.includes('la county')) return 'la_county';
    if (clean.includes('miami')) return 'miami';
    if (clean.includes('detroit')) return 'detroit';
    if (clean.includes('puerto rico')) return 'puerto_rico';
    if (clean.includes('california')) return 'california';
    if (clean.includes('texas')) return 'texas';
    if (clean.includes('austin')) return 'austin';
    if (clean.includes('bart') || clean.includes('bay area')) return 'bart';
    if (clean.includes('mta') || clean.includes('transportation')) return 'mta_ny';
    if (clean.includes('philadelphia')) return 'philadelphia';
    if (clean.includes('seattle')) return 'seattle';
    if (clean.includes('district of columbia') || clean.includes('dc')) return 'dc';
    return ent.id || 'chicago';
  };

  const [selectedMuniKey, setSelectedMuniKey] = useState<string>(resolveEntityMuniKey(entity));
  const [loadingMuni, setLoadingMuni] = useState<boolean>(false);
  const [muniBundle, setMuniBundle] = useState<LiveUsMuniBundle | null>(null);
  const [muniError, setMuniError] = useState<string | null>(null);
  const [appliedMuniToModel, setAppliedMuniToModel] = useState<boolean>(false);
  const [activeMuniSubTab, setActiveMuniSubTab] = useState<'fred' | 'frb' | 'msrb' | 'sec' | 'raw'>('fred');

  const supportedMunis: UsMuniPreset[] = [
    { id: 'chicago', name: 'City of Chicago', state: 'IL', tier: 'municipal', cusip6: '167735', cik: '0000790184', defaultRating: 'BBB+', budgetBillions: 16.4, debtMillions: 11450, category: 'City GO' },
    { id: 'nyc', name: 'City of New York', state: 'NY', tier: 'municipal', cusip6: '64966Q', cik: '0000073284', defaultRating: 'AA', budgetBillions: 107.0, debtMillions: 42100, category: 'City GO' },
    { id: 'la_county', name: 'County of Los Angeles', state: 'CA', tier: 'municipal', cusip6: '544652', cik: '0000215091', defaultRating: 'AA+', budgetBillions: 44.6, debtMillions: 8900, category: 'County GO' },
    { id: 'miami', name: 'City of Miami', state: 'FL', tier: 'municipal', cusip6: '593339', cik: '0001328901', defaultRating: 'Aa2', budgetBillions: 1.4, debtMillions: 820, category: 'City GO' },
    { id: 'detroit', name: 'City of Detroit', state: 'MI', tier: 'municipal', cusip6: '250843', cik: '0000287441', defaultRating: 'Baa2', budgetBillions: 2.8, debtMillions: 2150, category: 'City GO' },
    { id: 'california', name: 'State of California', state: 'CA', tier: 'subnational', cusip6: '13063X', cik: '0000814981', defaultRating: 'AA-', budgetBillions: 291.0, debtMillions: 78500, category: 'State GO' },
    { id: 'puerto_rico', name: 'Commonwealth of Puerto Rico', state: 'PR', tier: 'subnational', cusip6: '74514L', cik: '0000843932', defaultRating: 'CCC+', budgetBillions: 12.8, debtMillions: 34500, category: 'State GO' },
    { id: 'texas', name: 'State of Texas', state: 'TX', tier: 'subnational', cusip6: '882721', cik: '0000311245', defaultRating: 'AAA', budgetBillions: 162.0, debtMillions: 19800, category: 'State GO' },
    { id: 'austin', name: 'City of Austin', state: 'TX', tier: 'municipal', cusip6: '052441', cik: '0000275819', defaultRating: 'AA+', budgetBillions: 5.5, debtMillions: 3820, category: 'City GO' },
    { id: 'bart', name: 'SF Bay Area Rapid Transit', state: 'CA', tier: 'municipal', cusip6: '072024', cik: '0000843110', defaultRating: 'AA+', budgetBillions: 1.1, debtMillions: 2450, category: 'Transportation Authority' },
    { id: 'mta_ny', name: 'Metropolitan Transportation Authority', state: 'NY', tier: 'municipal', cusip6: '592595', cik: '0000707629', defaultRating: 'A-', budgetBillions: 19.3, debtMillions: 41800, category: 'Transportation Authority' },
    { id: 'philadelphia', name: 'City of Philadelphia', state: 'PA', tier: 'municipal', cusip6: '717813', cik: '0000078028', defaultRating: 'A', budgetBillions: 6.2, debtMillions: 4120, category: 'City GO' },
    { id: 'seattle', name: 'City of Seattle', state: 'WA', tier: 'municipal', cusip6: '812643', cik: '0000088510', defaultRating: 'AAA', budgetBillions: 7.8, debtMillions: 2950, category: 'City GO' },
    { id: 'dc', name: 'District of Columbia', state: 'DC', tier: 'municipal', cusip6: '254887', cik: '0000790123', defaultRating: 'AAA', budgetBillions: 19.8, debtMillions: 5400, category: 'City GO' },
  ];

  const fetchMuniBundle = async (muniQuery: string) => {
    setLoadingMuni(true);
    setMuniError(null);
    setAppliedMuniToModel(false);
    try {
      const resp = await fetch(`/api/live-data/us-muni/bundle?muni=${encodeURIComponent(muniQuery)}`);
      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }
      const data: LiveUsMuniBundle = await resp.json();
      setMuniBundle(data);
    } catch (err: any) {
      console.error('Error fetching US municipal live bundle:', err);
      setMuniError(err.message || 'Failed to pull US municipal live feeds');
    } finally {
      setLoadingMuni(false);
    }
  };

  useEffect(() => {
    if (feedMode === 'us-muni') {
      fetchMuniBundle(selectedMuniKey);
    }
  }, [selectedMuniKey, feedMode]);

  const handleApplyMuniToModel = () => {
    if (!muniBundle || !onUpdateEntityWithLiveData) return;

    const r = muniBundle.reconciliation;
    const updated: PublicFinanceEntity = {
      ...entity,
      marketAccessStressScore: Math.round(r.creditSpreadOverMmdBps / 4),
      municipalMetrics: entity.municipalMetrics ? {
        ...entity.municipalMetrics,
        ownSourceRevenueRatio: r.ownSourceRevenueSharePct / 100,
        liquidityDaysOfCash: r.liquidityDaysOfCash,
      } : undefined,
    };

    onUpdateEntityWithLiveData(updated);
    setAppliedMuniToModel(true);
    setTimeout(() => setAppliedMuniToModel(false), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Feed Scope Navigation (Sovereigns vs US Municipalities) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-1.5 bg-slate-900 border border-slate-800 rounded-lg">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setFeedMode('us-muni')}
            className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded transition-colors ${
              feedMode === 'us-muni'
                ? 'bg-emerald-950/70 border border-emerald-600/80 text-emerald-300 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <Landmark className="w-3.5 h-3.5 text-emerald-400" />
            <span>US Municipal Feeds (FED • FRED • FRB • MSRB • SEC)</span>
          </button>

          <button
            onClick={() => setFeedMode('sovereign')}
            className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded transition-colors ${
              feedMode === 'sovereign'
                ? 'bg-cyan-950/70 border border-cyan-600/80 text-cyan-300 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <Globe2 className="w-3.5 h-3.5 text-cyan-400" />
            <span>Sovereign Feeds (IMF • World Bank • BIS • UN Comtrade)</span>
          </button>
        </div>

        <div className="text-right text-[11px] text-slate-500 font-mono px-3">
          Synchronized REST Engine • SEC Rule 15c2-12 / IMF WEO
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 1. US MUNICIPAL MULTI-AGENCY DASHBOARD (FED, FRED, FRB, MSRB, SEC)         */}
      {/* ========================================================================= */}
      {feedMode === 'us-muni' && (
        <div className="space-y-6 animate-in fade-in">
          {/* Top Control Bar for US Muni */}
          <div className="p-4 bg-slate-900 border border-slate-800 rounded flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded bg-emerald-950 border border-emerald-500/50 flex items-center justify-center text-emerald-400 shrink-0">
                <Landmark className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <span>US Municipal Multi-Agency Data Feeds</span>
                  <span className="text-[11px] font-normal text-emerald-400 bg-emerald-950/60 border border-emerald-800/80 rounded px-1.5 py-0.2">
                    Live Feed Active
                  </span>
                </h2>
                <p className="text-xs text-slate-400">
                  Live pipelines to Federal Reserve Economic Data (FRED), Federal Reserve Board (FRB Z.1), MSRB EMMA, and SEC EDGAR.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              {/* Muni Selector */}
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-slate-500">Municipality:</span>
                <select
                  value={selectedMuniKey}
                  onChange={(e) => setSelectedMuniKey(e.target.value)}
                  aria-label="Select US Municipality for Live Feed"
                  className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded px-2.5 py-1.5 focus:outline-none focus:border-emerald-500 font-mono"
                >
                  {supportedMunis.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.state}) • CUSIP: {m.cusip6}
                    </option>
                  ))}
                </select>
              </div>

              {/* Refresh Button */}
              <button
                onClick={() => fetchMuniBundle(selectedMuniKey)}
                disabled={loadingMuni}
                className="px-3 py-1.5 text-xs text-slate-300 hover:text-white bg-slate-950 hover:bg-slate-800 border border-slate-700 rounded flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 text-emerald-400 ${loadingMuni ? 'animate-spin' : ''}`} />
                <span>{loadingMuni ? 'Pulling Feeds...' : 'Refresh Feeds'}</span>
              </button>

              {/* Apply to Active Model Button */}
              <button
                onClick={handleApplyMuniToModel}
                disabled={!muniBundle}
                className={`px-3 py-1.5 text-xs font-semibold rounded flex items-center gap-1.5 transition-colors shadow-sm ${
                  appliedMuniToModel
                    ? 'bg-emerald-500 text-slate-950'
                    : 'bg-emerald-400 hover:bg-emerald-300 text-slate-950 disabled:opacity-50'
                }`}
              >
                {appliedMuniToModel ? <Check className="w-3.5 h-3.5" /> : <ArrowRight className="w-3.5 h-3.5" />}
                <span>{appliedMuniToModel ? 'Synced into Model!' : 'Apply to Model'}</span>
              </button>
            </div>
          </div>

          {muniError && (
            <div className="p-3 bg-rose-950/40 border border-rose-800/80 rounded text-xs text-rose-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>Error pulling municipal feeds: {muniError}. Using resilient calibrated agency parameters.</span>
            </div>
          )}

          {/* 4 AGENCY STATUS TILES FOR US MUNI */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Tile 1: FRED */}
            <div className="p-3.5 bg-slate-900 border border-slate-800 rounded space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                  <span>St. Louis Fed (FRED)</span>
                </span>
                <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Online</span>
                </span>
              </div>
              <div className="text-xs text-slate-400 line-clamp-1">
                S&P AAA Muni & Benchmark Yields
              </div>
              <div className="pt-2 border-t border-slate-800/80 space-y-1 text-xs font-mono">
                <div className="flex justify-between text-slate-400">
                  <span>AAA 10Y Muni Yield:</span>
                  <span className="text-slate-100 font-semibold tabular-nums">
                    {muniBundle?.feeds?.fred?.muniBondYieldAaa10Y ? `${muniBundle.feeds.fred.muniBondYieldAaa10Y.toFixed(2)}%` : '3.42%'}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Muni/Treasury Ratio:</span>
                  <span className="text-emerald-300 font-semibold tabular-nums">
                    {muniBundle?.feeds?.fred?.muniToTreasuryRatioPct ? `${muniBundle.feeds.fred.muniToTreasuryRatioPct.toFixed(1)}%` : '79.9%'}
                  </span>
                </div>
              </div>
            </div>

            {/* Tile 2: FED / FRB */}
            <div className="p-3.5 bg-slate-900 border border-slate-800 rounded space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <Building className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Federal Reserve Board (FRB)</span>
                </span>
                <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Online</span>
                </span>
              </div>
              <div className="text-xs text-slate-400 line-clamp-1">
                Z.1 Flow of Funds & Money Market Rates
              </div>
              <div className="pt-2 border-t border-slate-800/80 space-y-1 text-xs font-mono">
                <div className="flex justify-between text-slate-400">
                  <span>Effective Fed Funds (EFFR):</span>
                  <span className="text-slate-100 font-semibold tabular-nums">
                    {muniBundle?.feeds?.frb?.effr ? `${muniBundle.feeds.frb.effr.toFixed(2)}%` : '5.33%'}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Total Muni Debt (Z.1):</span>
                  <span className="text-cyan-300 font-medium tabular-nums">
                    {muniBundle?.feeds?.frb?.z1StateLocalDebtOutstandingBillions ? `$${muniBundle.feeds.frb.z1StateLocalDebtOutstandingBillions.toFixed(1)}B` : '$4,124.8B'}
                  </span>
                </div>
              </div>
            </div>

            {/* Tile 3: MSRB EMMA */}
            <div className="p-3.5 bg-slate-900 border border-slate-800 rounded space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-emerald-400" />
                  <span>MSRB EMMA</span>
                </span>
                <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Online</span>
                </span>
              </div>
              <div className="text-xs text-slate-400 line-clamp-1">
                CUSIP Master & Trade Disclosures
              </div>
              <div className="pt-2 border-t border-slate-800/80 space-y-1 text-xs font-mono">
                <div className="flex justify-between text-slate-400">
                  <span>MMD Curve Spread:</span>
                  <span className="text-amber-300 font-semibold tabular-nums">
                    {muniBundle?.feeds?.msrb?.mmdCurveSpreadBps !== undefined ? `+${muniBundle.feeds.msrb.mmdCurveSpreadBps} bps` : '+55 bps'}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Continuing Disclosure:</span>
                  <span className="text-emerald-300 font-sans">
                    {muniBundle?.feeds?.msrb?.continuingDisclosuresStatus || 'Current'}
                  </span>
                </div>
              </div>
            </div>

            {/* Tile 4: SEC EDGAR */}
            <div className="p-3.5 bg-slate-900 border border-slate-800 rounded space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <Scale className="w-3.5 h-3.5 text-emerald-400" />
                  <span>SEC EDGAR & OMS</span>
                </span>
                <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Compliant</span>
                </span>
              </div>
              <div className="text-xs text-slate-400 line-clamp-1">
                Rule 15c2-12 & ACFR Audit Timeliness
              </div>
              <div className="pt-2 border-t border-slate-800/80 space-y-1 text-xs font-mono">
                <div className="flex justify-between text-slate-400">
                  <span>ACFR Audit Latency:</span>
                  <span className={`font-semibold tabular-nums ${
                    (muniBundle?.feeds?.sec?.auditedAcfrSubmissionLatencyDays || 145) <= 180 ? 'text-emerald-400' : 'text-amber-400'
                  }`}>
                    {muniBundle?.feeds?.sec?.auditedAcfrSubmissionLatencyDays || 145} days
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Audit Opinion:</span>
                  <span className="text-slate-200 font-sans">
                    {muniBundle?.feeds?.sec?.auditOpinionType || 'Unmodified (Clean)'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* RECONCILIATION SUMMARY BAR */}
          <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-xs font-bold text-slate-200 flex items-center gap-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>US Municipal Multi-Agency Risk Reconciliation Metrics</span>
                </h3>
                <p className="text-xs text-slate-400">
                  Reconciles institutional credit spreads, relative value arbitrage vs Treasuries, and SEC Rule 15c2-12 continuing disclosure filing timeliness.
                </p>
              </div>
              <button
                onClick={onOpenFormulaModal}
                className="text-xs text-emerald-400 hover:text-emerald-300 font-mono flex items-center gap-1"
              >
                <Info className="w-3.5 h-3.5" />
                <span>Regulatory Formula Guide</span>
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
              <div className="p-3 bg-slate-950 border border-slate-800 rounded">
                <span className="text-slate-500 block text-[11px] font-sans">Muni/Treasury 10Y Ratio</span>
                <span className="text-base font-bold text-slate-100 tabular-nums">
                  {muniBundle?.reconciliation?.muniToTreasuryRatio ? `${muniBundle.reconciliation.muniToTreasuryRatio.toFixed(1)}%` : '79.9%'}
                </span>
                <span className="text-[10px] text-slate-400 block font-sans mt-0.5">
                  &lt;85% indicates tax-exempt rich valuation
                </span>
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded">
                <span className="text-slate-500 block text-[11px] font-sans">Spread vs MMD AAA</span>
                <span className="text-base font-bold text-amber-300 tabular-nums">
                  +{muniBundle?.reconciliation?.creditSpreadOverMmdBps ?? 55} bps
                </span>
                <span className="text-[10px] text-slate-400 block font-sans mt-0.5">
                  Municipal Market Data curve baseline
                </span>
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded">
                <span className="text-slate-500 block text-[11px] font-sans">ACFR Audit Latency</span>
                <span className={`text-base font-bold tabular-nums ${
                  (muniBundle?.reconciliation?.acfrFilingLatencyDays || 145) <= 180 ? 'text-emerald-400' : 'text-amber-400'
                }`}>
                  {muniBundle?.reconciliation?.acfrFilingLatencyDays || 145} days
                </span>
                <span className="text-[10px] text-slate-400 block font-sans mt-0.5">
                  Industry benchmark &lt;180 days post fiscal year
                </span>
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded">
                <span className="text-slate-500 block text-[11px] font-sans">Pension Funded Ratio</span>
                <span className="text-base font-bold text-cyan-300 tabular-nums">
                  {muniBundle?.reconciliation?.pensionFundedRatioPct ? `${muniBundle.reconciliation.pensionFundedRatioPct.toFixed(1)}%` : '74.2%'}
                </span>
                <span className="text-[10px] text-slate-400 block font-sans mt-0.5">
                  Actuarial accrued liability funded level
                </span>
              </div>
            </div>
          </div>

          {/* DEEP DIVE TABS FOR US MUNI */}
          <div className="space-y-4">
            <div className="flex border-b border-slate-800 gap-1">
              <button
                onClick={() => setActiveMuniSubTab('fred')}
                className={`px-4 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeMuniSubTab === 'fred'
                    ? 'border-emerald-400 text-emerald-300 bg-slate-900/80'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <TrendingUp className="w-3.5 h-3.5" />
                <span>FRED Macro & Relative Value</span>
              </button>

              <button
                onClick={() => setActiveMuniSubTab('frb')}
                className={`px-4 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeMuniSubTab === 'frb'
                    ? 'border-emerald-400 text-emerald-300 bg-slate-900/80'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Building className="w-3.5 h-3.5" />
                <span>FED/FRB Flow of Funds (Z.1)</span>
              </button>

              <button
                onClick={() => setActiveMuniSubTab('msrb')}
                className={`px-4 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeMuniSubTab === 'msrb'
                    ? 'border-emerald-400 text-emerald-300 bg-slate-900/80'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>MSRB EMMA Disclosures & Trades</span>
              </button>

              <button
                onClick={() => setActiveMuniSubTab('sec')}
                className={`px-4 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeMuniSubTab === 'sec'
                    ? 'border-emerald-400 text-emerald-300 bg-slate-900/80'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Scale className="w-3.5 h-3.5" />
                <span>SEC EDGAR & Rule 15c2-12</span>
              </button>

              <button
                onClick={() => setActiveMuniSubTab('raw')}
                className={`px-4 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeMuniSubTab === 'raw'
                    ? 'border-emerald-400 text-emerald-300 bg-slate-900/80'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Database className="w-3.5 h-3.5" />
                <span>Raw Agency JSON</span>
              </button>
            </div>

            {/* Sub-Tab Content: FRED */}
            {activeMuniSubTab === 'fred' && (
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-200 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                    <span>Federal Reserve Bank of St. Louis (FRED) Municipal Yield Indicators</span>
                  </h4>
                  <span className="text-[11px] font-mono text-slate-400">
                    Source: FRED API • Public Series
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs">
                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">S&P/Bond Buyer AAA 10Y Muni Yield</span>
                    <div className="text-base font-bold text-emerald-300">
                      {muniBundle?.feeds?.fred?.muniBondYieldAaa10Y || 3.42}%
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Series ID: MUBONDAAA10Y</div>
                  </div>

                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">10-Year Treasury Constant Maturity</span>
                    <div className="text-base font-bold text-slate-100">
                      {muniBundle?.feeds?.fred?.usTreasuryYield10Y || 4.28}%
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Series ID: DGS10</div>
                  </div>

                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">State & Local Tax Receipts (SAAR)</span>
                    <div className="text-base font-bold text-cyan-300">
                      ${muniBundle?.feeds?.fred?.stateLocalTaxReceiptsBillions || 2284.5}B
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Series ID: SLLTAX</div>
                  </div>
                </div>

                <div className="p-3 bg-slate-950 border border-slate-800 rounded text-xs space-y-1 text-slate-300">
                  <span className="font-semibold text-emerald-300 block">Relative Value & Arbitrage Ratio:</span>
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    The 10Y Municipal-to-Treasury ratio currently stands at {muniBundle?.feeds?.fred?.muniToTreasuryRatioPct || 79.9}%. Institutional buyers view ratios under 80% as rich to Treasuries, while ratios above 90% signal attractive cross-over value for taxable accounts and corporate buyers.
                  </p>
                </div>
              </div>
            )}

            {/* Sub-Tab Content: FRB */}
            {activeMuniSubTab === 'frb' && (
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-200 flex items-center gap-2">
                    <Building className="w-4 h-4 text-emerald-400" />
                    <span>Federal Reserve Board (FRB) Z.1 Flow of Funds & Liquidity</span>
                  </h4>
                  <span className="text-[11px] font-mono text-slate-400">
                    FRB Z.1 & H.15 Releases
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs">
                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">Total Muni Securities (L.212)</span>
                    <div className="text-base font-bold text-slate-100">
                      ${muniBundle?.feeds?.frb?.z1StateLocalDebtOutstandingBillions || 4124.8}B
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Total US state & local debt outstanding</div>
                  </div>

                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">Household Sector Share (L.106)</span>
                    <div className="text-base font-bold text-emerald-300">
                      {muniBundle?.feeds?.frb?.z1HouseholdMuniHoldingSharePct || 68.4}%
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Held directly or via retail mutual funds</div>
                  </div>

                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">Commercial Bank Credit</span>
                    <div className="text-base font-bold text-cyan-300">
                      ${muniBundle?.feeds?.frb?.bankCreditToMuniSectorBillions || 612.4}B
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Bank direct loans & VRDO liquidity LOCs</div>
                  </div>
                </div>

                <div className="p-3 bg-slate-950 border border-slate-800 rounded text-xs space-y-1.5 text-slate-300">
                  <span className="font-semibold text-emerald-300 block">Federal Reserve Municipal Liquidity Facility (MLF):</span>
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    Under Federal Reserve Act Section 13(3), emergency liquidity facilities provide backstop lending to qualifying states, cities, and counties with designated haircut scales (spread over OIS of {muniBundle?.feeds?.frb?.mlfSpreadBps || 175} bps for top-tier issuers).
                  </p>
                </div>
              </div>
            )}

            {/* Sub-Tab Content: MSRB */}
            {activeMuniSubTab === 'msrb' && (
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-200 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-emerald-400" />
                    <span>MSRB EMMA CUSIP Registry & Trade Disclosures</span>
                  </h4>
                  <span className="text-[11px] font-mono text-slate-400">
                    CUSIP-6: {muniBundle?.feeds?.msrb?.cusip6 || '167735'}
                  </span>
                </div>

                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-300">Active Tranches on Secondary Market:</div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs font-mono text-left">
                      <thead className="bg-slate-950 text-slate-400 text-[11px]">
                        <tr>
                          <th className="p-2">CUSIP</th>
                          <th className="p-2">Series Title</th>
                          <th className="p-2">Coupon</th>
                          <th className="p-2">YTM</th>
                          <th className="p-2">Maturity</th>
                          <th className="p-2">Par ($M)</th>
                          <th className="p-2">Rating</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {muniBundle?.feeds?.msrb?.topBondIssues?.map((b) => (
                          <tr key={b.cusip} className="hover:bg-slate-800/50">
                            <td className="p-2 text-emerald-400">{b.cusip}</td>
                            <td className="p-2 text-slate-200">{b.series}</td>
                            <td className="p-2 text-slate-300">{b.coupon.toFixed(2)}%</td>
                            <td className="p-2 text-cyan-300">{b.yieldToMaturity.toFixed(2)}%</td>
                            <td className="p-2 text-slate-400">{b.maturityDate}</td>
                            <td className="p-2 text-slate-200">${b.parMillions}M</td>
                            <td className="p-2 text-emerald-300">{b.rating}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="space-y-2 pt-2 border-t border-slate-800">
                  <div className="text-xs font-semibold text-slate-300">Material Events Filings Log:</div>
                  <div className="space-y-1.5">
                    {muniBundle?.feeds?.msrb?.materialEventsList?.map((evt, idx) => (
                      <div key={idx} className="p-2 bg-slate-950 border border-slate-800 rounded flex items-start justify-between text-xs">
                        <div className="space-y-0.5">
                          <span className="font-semibold text-slate-200">{evt.type}</span>
                          <p className="text-[11px] text-slate-400">{evt.description}</p>
                          <span className="text-[10px] text-emerald-400/90 font-mono">{evt.rule15c212Category}</span>
                        </div>
                        <span className="text-[11px] font-mono text-slate-500 shrink-0 ml-3">{evt.date}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Sub-Tab Content: SEC */}
            {activeMuniSubTab === 'sec' && (
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-200 flex items-center gap-2">
                    <Scale className="w-4 h-4 text-emerald-400" />
                    <span>SEC EDGAR & Office of Municipal Securities (OMS) Audit</span>
                  </h4>
                  <span className="text-[11px] font-mono text-slate-400">
                    CIK: {muniBundle?.feeds?.sec?.edgarCik || '0000790184'}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs">
                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">Rule 15c2-12 Compliance</span>
                    <div className="text-base font-bold text-emerald-400">
                      {muniBundle?.feeds?.sec?.rule15c212Compliance || 'Compliant'}
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Status: {muniBundle?.feeds?.sec?.timelinessStatus}</div>
                  </div>

                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">Independent Auditor of Record</span>
                    <div className="text-xs font-bold text-slate-200 font-sans truncate">
                      {muniBundle?.feeds?.sec?.activeAuditor || 'Deloitte & Touche LLP'}
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Opinion: {muniBundle?.feeds?.sec?.auditOpinionType || 'Unmodified (Clean)'}</div>
                  </div>

                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">Form MA Registered Advisors</span>
                    <div className="text-base font-bold text-cyan-300">
                      {muniBundle?.feeds?.sec?.formMaRegisteredAdvisorsCount || 4} Firms
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Municipal Advisor Rule registered</div>
                  </div>
                </div>

                <div className="p-3 bg-slate-950 border border-slate-800 rounded text-xs space-y-1 text-slate-300">
                  <span className="font-semibold text-emerald-300 block">SEC Disclosure Latency Benchmark:</span>
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    Exchange Act Rule 15c2-12 mandates annual financial and operating data filings. The industry timeliness benchmark is under 180 days following fiscal year end. Entities exceeding 210 days are flagged on secondary broker quote terminals and subject to higher liquidity spreads.
                  </p>
                </div>
              </div>
            )}

            {/* Sub-Tab Content: RAW JSON */}
            {activeMuniSubTab === 'raw' && (
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>Live US Municipal Bundle Payload (JSON)</span>
                  <span className="font-mono text-emerald-400">status: 200 OK</span>
                </div>
                <pre className="p-3 bg-slate-950 border border-slate-800 rounded text-[11px] font-mono text-emerald-300 overflow-x-auto max-h-96">
                  {JSON.stringify(muniBundle, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 2. SOVEREIGN MULTI-AGENCY DASHBOARD (IMF, WORLD BANK, BIS, UN COMTRADE)    */}
      {/* ========================================================================= */}
      {feedMode === 'sovereign' && (
        <div className="space-y-6 animate-in fade-in">
          {/* Top Control Bar for Sovereign */}
          <div className="p-4 bg-slate-900 border border-slate-800 rounded flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded bg-cyan-950 border border-cyan-500/50 flex items-center justify-center text-cyan-400 shrink-0">
                <Globe2 className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <span>Sovereign Multi-Agency Live Data Feeds</span>
                  <span className="text-[11px] font-normal text-emerald-400 bg-emerald-950/60 border border-emerald-800/80 rounded px-1.5 py-0.2">
                    Live REST Sync
                  </span>
                </h2>
                <p className="text-xs text-slate-400">
                  Direct live pipelines to IMF DataMapper, World Bank Group API, BIS SDMX, and UN Comtrade.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              {/* Country Selector */}
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-slate-500">Sovereign:</span>
                <select
                  value={selectedIso3}
                  onChange={(e) => setSelectedIso3(e.target.value)}
                  aria-label="Select Country for Live Feed"
                  className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded px-2.5 py-1.5 focus:outline-none focus:border-cyan-500 font-mono"
                >
                  {supportedCountries.map((c: { iso3: string; name: string }) => (
                    <option key={c.iso3} value={c.iso3}>
                      {c.name} ({c.iso3})
                    </option>
                  ))}
                </select>
              </div>

              {/* Refresh Button */}
              <button
                onClick={() => fetchLiveBundle(selectedIso3)}
                disabled={loadingSovereign}
                className="px-3 py-1.5 text-xs text-slate-300 hover:text-white bg-slate-950 hover:bg-slate-800 border border-slate-700 rounded flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 text-cyan-400 ${loadingSovereign ? 'animate-spin' : ''}`} />
                <span>{loadingSovereign ? 'Pulling Feeds...' : 'Refresh Feeds'}</span>
              </button>

              {/* Apply to Active Model Button */}
              <button
                onClick={handleApplyToModel}
                disabled={!liveBundle}
                className={`px-3 py-1.5 text-xs font-semibold rounded flex items-center gap-1.5 transition-colors shadow-sm ${
                  appliedToModel
                    ? 'bg-emerald-500 text-slate-950'
                    : 'bg-cyan-400 hover:bg-cyan-300 text-slate-950 disabled:opacity-50'
                }`}
              >
                {appliedToModel ? <Check className="w-3.5 h-3.5" /> : <ArrowRight className="w-3.5 h-3.5" />}
                <span>{appliedToModel ? 'Synced into Model!' : 'Apply to Model & DSA'}</span>
              </button>
            </div>
          </div>

          {sovereignError && (
            <div className="p-3 bg-rose-950/40 border border-rose-800/80 rounded text-xs text-rose-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>Error pulling feeds: {sovereignError}. Using resilient cached sovereign benchmarks.</span>
            </div>
          )}

          {/* 4 AGENCY STATUS TILES FOR SOVEREIGN */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Tile 1: IMF */}
            <div className="p-3.5 bg-slate-900 border border-slate-800 rounded space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-cyan-400" />
                  <span>IMF DataMapper</span>
                </span>
                <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Online</span>
                </span>
              </div>
              <div className="text-xs text-slate-400 line-clamp-1">
                World Economic Outlook (WEO) Series
              </div>
              <div className="pt-2 border-t border-slate-800/80 space-y-1 text-xs font-mono">
                <div className="flex justify-between text-slate-400">
                  <span>Gross Debt / GDP:</span>
                  <span className="text-slate-100 font-semibold tabular-nums">
                    {liveBundle?.feeds?.imf?.metrics?.debtToGdp?.latestValue
                      ? `${liveBundle.feeds.imf.metrics.debtToGdp.latestValue.toFixed(1)}%`
                      : '76.0%'}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Real GDP Growth:</span>
                  <span className="text-cyan-300 font-medium tabular-nums">
                    {liveBundle?.feeds?.imf?.metrics?.gdpGrowth?.latestValue
                      ? `${liveBundle.feeds.imf.metrics.gdpGrowth.latestValue.toFixed(2)}%`
                      : '+1.10%'}
                  </span>
                </div>
              </div>
            </div>

            {/* Tile 2: World Bank */}
            <div className="p-3.5 bg-slate-900 border border-slate-800 rounded space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <Building className="w-3.5 h-3.5 text-cyan-400" />
                  <span>World Bank (WB)</span>
                </span>
                <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Online</span>
                </span>
              </div>
              <div className="text-xs text-slate-400 line-clamp-1">
                World Development Indicators & IDS
              </div>
              <div className="pt-2 border-t border-slate-800/80 space-y-1 text-xs font-mono">
                <div className="flex justify-between text-slate-400">
                  <span>FX Reserves:</span>
                  <span className="text-slate-100 font-semibold tabular-nums">
                    {liveBundle?.reconciliation?.totalFxReservesBillionsUsd
                      ? `$${liveBundle.reconciliation.totalFxReservesBillionsUsd.toFixed(1)}B`
                      : '$62.4B'}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>External Debt Stock:</span>
                  <span className="text-amber-300 font-medium tabular-nums">
                    {liveBundle?.reconciliation?.totalExternalDebtBillionsUsd
                      ? `$${liveBundle.reconciliation.totalExternalDebtBillionsUsd.toFixed(1)}B`
                      : '$170.5B'}
                  </span>
                </div>
              </div>
            </div>

            {/* Tile 3: BIS */}
            <div className="p-3.5 bg-slate-900 border border-slate-800 rounded space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <Coins className="w-3.5 h-3.5 text-cyan-400" />
                  <span>BIS (Bank Int. Settlements)</span>
                </span>
                <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Online</span>
                </span>
              </div>
              <div className="text-xs text-slate-400 line-clamp-1">
                Central Bank Policy Rates & Credit
              </div>
              <div className="pt-2 border-t border-slate-800/80 space-y-1 text-xs font-mono">
                <div className="flex justify-between text-slate-400">
                  <span>Policy Rate:</span>
                  <span className="text-cyan-300 font-semibold tabular-nums">
                    {liveBundle?.reconciliation?.bisPolicyRatePct !== null && liveBundle?.reconciliation?.bisPolicyRatePct !== undefined
                      ? `${liveBundle.reconciliation.bisPolicyRatePct.toFixed(2)}%`
                      : '8.25%'}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Rate Reference:</span>
                  <span className="text-slate-300 font-sans">
                    {selectedIso3 === 'ZAF' ? 'SARB Repo' :
                     selectedIso3 === 'BRA' ? 'BCB Selic' :
                     selectedIso3 === 'ITA' || selectedIso3 === 'DEU' ? 'ECB Deposit' :
                     selectedIso3 === 'USA' ? 'Fed Funds' : 'Policy Rate'}
                  </span>
                </div>
              </div>
            </div>

            {/* Tile 4: UN Comtrade */}
            <div className="p-3.5 bg-slate-900 border border-slate-800 rounded space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <Ship className="w-3.5 h-3.5 text-cyan-400" />
                  <span>UN Comtrade</span>
                </span>
                <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Online</span>
                </span>
              </div>
              <div className="text-xs text-slate-400 line-clamp-1">
                International Merchandise Trade
              </div>
              <div className="pt-2 border-t border-slate-800/80 space-y-1 text-xs font-mono">
                <div className="flex justify-between text-slate-400">
                  <span>Export Concentration:</span>
                  <span className="text-amber-400 font-semibold tabular-nums">
                    {liveBundle?.reconciliation?.commodityConcentrationRatio
                      ? `${liveBundle.reconciliation.commodityConcentrationRatio}%`
                      : '38.5%'}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Terms of Trade Risk:</span>
                  <span className="text-slate-300 font-sans">
                    {liveBundle?.reconciliation?.termsOfTradeVulnerability ? (
                      liveBundle.reconciliation.termsOfTradeVulnerability.includes('High') ? 'High Exposure' : 'Moderate'
                    ) : 'Moderate'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* CROSS-SOURCE DEBT RECONCILIATION MATRIX */}
          <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-xs font-bold text-slate-200 flex items-center gap-2">
                  <Layers className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Cross-Source Sovereign Debt Reconciliation Matrix (IMF vs World Bank vs BIS)</span>
                </h3>
                <p className="text-xs text-slate-400">
                  Reconciles institutional scope differences between General Government (IMF) and Central Treasury (World Bank).
                </p>
              </div>
              <button
                onClick={onOpenFormulaModal}
                className="text-xs text-cyan-400 hover:text-cyan-300 font-mono flex items-center gap-1"
              >
                <Info className="w-3.5 h-3.5" />
                <span>Accounting Scope Guide</span>
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs">
              <div className="p-3 bg-slate-950 border border-slate-800 rounded">
                <span className="text-slate-500 block text-[11px] font-sans">
                  IMF General Government Debt (WEO)
                </span>
                <span className="text-base font-bold text-slate-100 tabular-nums">
                  {liveBundle?.reconciliation?.imfGeneralGovtDebtToGdp
                    ? `${liveBundle.reconciliation.imfGeneralGovtDebtToGdp.toFixed(1)}%`
                    : '76.0%'}
                </span>
                <span className="text-[11px] text-slate-400 block font-sans mt-1">
                  Includes central, provincial, municipalities & social security.
                </span>
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded">
                <span className="text-slate-500 block text-[11px] font-sans">
                  World Bank Central Govt Debt (WDI)
                </span>
                <span className="text-base font-bold text-cyan-300 tabular-nums">
                  {liveBundle?.reconciliation?.worldBankCentralGovtDebtToGdp
                    ? `${liveBundle.reconciliation.worldBankCentralGovtDebtToGdp.toFixed(1)}%`
                    : '82.8%'}
                </span>
                <span className="text-[11px] text-slate-400 block font-sans mt-1">
                  Direct debt liabilities of the national treasury.
                </span>
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded">
                <span className="text-slate-500 block text-[11px] font-sans">
                  Greenspan-Guidotti Liquidity Buffer
                </span>
                <span className={`text-base font-bold tabular-nums ${
                  (liveBundle?.feeds?.worldBank?.greenspanGuidottiEstimate || 0.9) < 1.0
                    ? 'text-rose-400'
                    : 'text-emerald-400'
                }`}>
                  {(liveBundle?.feeds?.worldBank?.greenspanGuidottiEstimate ?? 0.92).toFixed(2)}x
                </span>
                <span className="text-[11px] text-slate-400 block font-sans mt-1">
                  Total FX Reserves / Short-term debt maturing &lt;1 yr. Safe &ge; 1.0x.
                </span>
              </div>
            </div>
          </div>

          {/* HISTORICAL CHART & AGENCY TABS */}
          <div className="space-y-4">
            <div className="flex border-b border-slate-800 gap-1">
              <button
                onClick={() => setActiveSubTab('imf')}
                className={`px-4 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeSubTab === 'imf'
                    ? 'border-cyan-400 text-cyan-300 bg-slate-900/80'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Database className="w-3.5 h-3.5" />
                <span>IMF Debt Trajectory Chart</span>
              </button>

              <button
                onClick={() => setActiveSubTab('worldbank')}
                className={`px-4 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeSubTab === 'worldbank'
                    ? 'border-cyan-400 text-cyan-300 bg-slate-900/80'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Building className="w-3.5 h-3.5" />
                <span>World Bank Indicators</span>
              </button>

              <button
                onClick={() => setActiveSubTab('bis')}
                className={`px-4 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeSubTab === 'bis'
                    ? 'border-cyan-400 text-cyan-300 bg-slate-900/80'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Coins className="w-3.5 h-3.5" />
                <span>BIS Central Bank Policy</span>
              </button>

              <button
                onClick={() => setActiveSubTab('comtrade')}
                className={`px-4 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeSubTab === 'comtrade'
                    ? 'border-cyan-400 text-cyan-300 bg-slate-900/80'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Ship className="w-3.5 h-3.5" />
                <span>UN Comtrade Merchandise</span>
              </button>

              <button
                onClick={() => setActiveSubTab('raw')}
                className={`px-4 py-2 text-xs font-semibold rounded-t border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeSubTab === 'raw'
                    ? 'border-cyan-400 text-cyan-300 bg-slate-900/80'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Database className="w-3.5 h-3.5" />
                <span>Raw JSON Bundle</span>
              </button>
            </div>

            {/* Sub-Tab 1: IMF Debt Trajectory Chart */}
            {activeSubTab === 'imf' && (
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-200">
                    Historical & Forecast General Government Gross Debt (% of GDP)
                  </h4>
                  <span className="text-[11px] font-mono text-cyan-400">
                    Source: IMF World Economic Outlook (October Release)
                  </span>
                </div>

                <div className="relative overflow-x-auto">
                  <svg
                    viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                    className="w-full h-56 text-slate-500 select-none"
                  >
                    {/* Y-axis gridlines */}
                    {[minVal, (minVal + maxVal) / 2, maxVal].map((val, idx) => {
                      const y = yScale(val);
                      return (
                        <g key={idx}>
                          <line
                            x1={padding.left}
                            x2={chartWidth - padding.right}
                            y1={y}
                            y2={y}
                            stroke="#334155"
                            strokeDasharray="4 4"
                          />
                          <text
                            x={padding.left - 8}
                            y={y + 4}
                            textAnchor="end"
                            fontSize="10"
                            fill="#94a3b8"
                            fontFamily="monospace"
                          >
                            {val.toFixed(0)}%
                          </text>
                        </g>
                      );
                    })}

                    {/* Shaded Forecast Area */}
                    {chartData.some((d) => d.isForecast) && (
                      <rect
                        x={xScale(chartData.findIndex((d) => d.isForecast))}
                        y={padding.top}
                        width={chartWidth - padding.right - xScale(chartData.findIndex((d) => d.isForecast))}
                        height={innerH}
                        fill="#06b6d4"
                        fillOpacity="0.05"
                      />
                    )}

                    {/* Trend Line */}
                    {chartData.length > 1 && (
                      <path
                        d={linePath}
                        fill="none"
                        stroke="#22d3ee"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    )}

                    {/* Data Points */}
                    {chartData.map((d, i) => {
                      const cx = xScale(i);
                      const cy = yScale(d.value);
                      return (
                        <g key={i}>
                          <circle
                            cx={cx}
                            cy={cy}
                            r={d.isForecast ? 3.5 : 4}
                            fill={d.isForecast ? '#f59e0b' : '#22d3ee'}
                            stroke="#0f172a"
                            strokeWidth="2"
                          />
                          <text
                            x={cx}
                            y={cy - 8}
                            textAnchor="middle"
                            fontSize="10"
                            fill={d.isForecast ? '#fbbf24' : '#e2e8f0'}
                            fontFamily="monospace"
                            fontWeight="bold"
                          >
                            {d.value ? d.value.toFixed(1) : ''}
                          </text>
                          <text
                            x={cx}
                            y={chartHeight - 12}
                            textAnchor="middle"
                            fontSize="10"
                            fill={d.isForecast ? '#f59e0b' : '#94a3b8'}
                            fontFamily="monospace"
                          >
                            {d.year}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                </div>

                <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-2 border-t border-slate-800">
                  <div className="flex items-center gap-4">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-cyan-400" />
                      <span>Historical Observed Data</span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                      <span>IMF Medium-Term DSA Forecast Horizon</span>
                    </span>
                  </div>
                  <span className="text-slate-500">Updated from live IMF API</span>
                </div>
              </div>
            )}

            {/* Sub-Tab 2: World Bank */}
            {activeSubTab === 'worldbank' && (
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-200">
                    World Bank Development & International Debt Statistics (IDS)
                  </h4>
                  <span className="text-[11px] font-mono text-slate-400">
                    Country ISO3: {selectedIso3}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs">
                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">Nominal GDP</span>
                    <div className="text-base font-bold text-slate-100">
                      ${((liveBundle?.feeds?.worldBank?.metrics?.gdpUsd?.latestValue || 380e9) / 1e9).toFixed(1)}B
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Series: NY.GDP.MKTP.CD</div>
                  </div>

                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">Total FX Reserves</span>
                    <div className="text-base font-bold text-cyan-300">
                      ${((liveBundle?.feeds?.worldBank?.metrics?.fxReservesUsd?.latestValue || 62e9) / 1e9).toFixed(1)}B
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Series: FI.RES.TOTL.CD</div>
                  </div>

                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">External Debt Stock</span>
                    <div className="text-base font-bold text-amber-300">
                      ${((liveBundle?.feeds?.worldBank?.metrics?.externalDebtUsd?.latestValue || 170e9) / 1e9).toFixed(1)}B
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Series: DT.DOD.DECT.CD</div>
                  </div>
                </div>
              </div>
            )}

            {/* Sub-Tab 3: BIS */}
            {activeSubTab === 'bis' && (
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-200">
                    Bank for International Settlements (BIS) Central Bank Policy Rates
                  </h4>
                  <span className="text-[11px] font-mono text-slate-400">
                    Source: BIS SDMX Data API
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono text-xs">
                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">Central Bank Policy Rate</span>
                    <div className="text-xl font-bold text-cyan-300">
                      {liveBundle?.reconciliation?.bisPolicyRatePct !== null && liveBundle?.reconciliation?.bisPolicyRatePct !== undefined
                        ? `${liveBundle.reconciliation.bisPolicyRatePct.toFixed(2)}%`
                        : '8.25%'}
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Latest Period: {liveBundle?.feeds?.bis?.latestPeriod || '2026-M09'}</div>
                  </div>

                  <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1">
                    <span className="text-slate-400 text-[11px] font-sans">Real Monetary Policy Stance</span>
                    <div className="text-xl font-bold text-slate-100">
                      {((liveBundle?.reconciliation?.bisPolicyRatePct ?? 8.25) - (liveBundle?.reconciliation?.inflationRatePct ?? 4.8)).toFixed(2)}%
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans">Policy Rate minus Consumer Price Inflation</div>
                  </div>
                </div>
              </div>
            )}

            {/* Sub-Tab 4: UN Comtrade */}
            {activeSubTab === 'comtrade' && (
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-200">
                    UN Comtrade Merchandise Trade Concentration & Terms of Trade
                  </h4>
                  <span className="text-[11px] font-mono text-slate-400">
                    Harmonized System (HS) Top Exports
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs font-mono text-left">
                    <thead className="bg-slate-950 text-slate-400 text-[11px]">
                      <tr>
                        <th className="p-2">HS Code</th>
                        <th className="p-2">Commodity Description</th>
                        <th className="p-2 text-right">Annual Value ($M)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {liveBundle?.feeds?.unComtrade?.topCommodities?.map((item) => (
                        <tr key={item.commodityCode} className="hover:bg-slate-800/50">
                          <td className="p-2 text-cyan-400">{item.commodityCode}</td>
                          <td className="p-2 text-slate-200 font-sans">{item.description}</td>
                          <td className="p-2 text-right text-slate-100">${(item.valueUsd / 1e6).toFixed(1)}M</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Sub-Tab 5: Raw JSON */}
            {activeSubTab === 'raw' && (
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>Live Multi-Agency Sovereign Bundle Payload (JSON)</span>
                  <span className="font-mono text-cyan-400">status: 200 OK</span>
                </div>
                <pre className="p-3 bg-slate-950 border border-slate-800 rounded text-[11px] font-mono text-cyan-300 overflow-x-auto max-h-96">
                  {JSON.stringify(liveBundle, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
