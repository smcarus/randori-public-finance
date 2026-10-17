import React, { useState, useMemo, useEffect } from 'react';
import {
  RandoriCountryScorecard,
  GeopoliticalPeril,
  PriSector,
  AssetLocationRisk,
  HmnRegimeState,
  PriPolicyQuote,
  PublicFinanceEntity,
  LiveSovereignBundle,
} from '../types/finance';
import {
  getCalibratedScorecard,
  bayesianUpdateProbability,
  runGVarMonteCarlo,
  calculatePriPolicyQuote,
  SECTOR_MULTIPLIERS,
  LOCATION_MULTIPLIERS,
} from '../utils/gvarEngine';
import {
  ShieldAlert,
  Flame,
  Award,
  Building,
  Coins,
  Globe2,
  Umbrella,
  Sliders,
  TrendingDown,
  Info,
  CheckCircle2,
  AlertTriangle,
  FileCheck2,
  Layers,
  ArrowRight,
  Maximize2,
  RefreshCw,
  Radio,
  Sparkles,
  Database
} from 'lucide-react';

interface GeopoliticalVaRTabProps {
  activeEntity?: PublicFinanceEntity;
  allEntities?: PublicFinanceEntity[];
  onOpenFormulaModal: () => void;
  onOpenPullModal?: () => void;
}

export const GeopoliticalVaRTab: React.FC<GeopoliticalVaRTabProps> = ({
  activeEntity,
  allEntities = [],
  onOpenFormulaModal,
  onOpenPullModal,
}) => {
  // Determine initial country based on active entity if sovereign
  const initialCountry = useMemo(() => {
    if (activeEntity && activeEntity.tier === 'sovereign') {
      if (activeEntity.id.includes('zaf') || activeEntity.jurisdiction.includes('South Africa')) return 'ZAF';
      if (activeEntity.id.includes('ita') || activeEntity.jurisdiction.includes('Italy')) return 'ITA';
      if (activeEntity.id.includes('nga') || activeEntity.name.includes('Nigeria')) return 'NGA';
      if (activeEntity.id.includes('egy') || activeEntity.name.includes('Egypt')) return 'EGY';
      if (activeEntity.id.includes('arg') || activeEntity.name.includes('Argentina')) return 'ARG';
      if (activeEntity.id.includes('bra') || activeEntity.name.includes('Brazil')) return 'BRA';
      if (activeEntity.id.includes('chl') || activeEntity.name.includes('Chile')) return 'CHL';
      // If code in ID (e.g. sovereign-tur)
      const match = activeEntity.id.match(/sovereign-([a-z]{3})/i);
      if (match) return match[1].toUpperCase();
    }
    return 'BLZ';
  }, [activeEntity]);

  const [selectedCountry, setSelectedCountry] = useState<string>(initialCountry);
  const [isSics, setIsSics] = useState<boolean>(initialCountry === 'BLZ');
  const [regimeState, setRegimeState] = useState<HmnRegimeState>('stressed');
  const [marketImpliedDefaultProb, setMarketImpliedDefaultProb] = useState<number>(0.08);

  // Live Data Ingestion State
  const [liveFeedActive, setLiveFeedActive] = useState<boolean>(true);
  const [liveBundle, setLiveBundle] = useState<LiveSovereignBundle | null>(null);
  const [isLoadingLive, setIsLoadingLive] = useState<boolean>(false);
  const [liveFetchError, setLiveFetchError] = useState<string | null>(null);

  // Custom Country Input
  const [customCountryInput, setCustomCountryInput] = useState<string>('');
  const [showCustomInput, setShowCustomInput] = useState<boolean>(false);

  // PRI Policy Builder Parameters
  const [priPeril, setPriPeril] = useState<GeopoliticalPeril>('expropriation');
  const [policyLimitMillions, setPolicyLimitMillions] = useState<number>(50);
  const [deductibleMillions, setDeductibleMillions] = useState<number>(5);
  const [priSector, setPriSector] = useState<PriSector>('mining_oil_gas');
  const [priLocation, setPriLocation] = useState<AssetLocationRisk>('around_national_average');
  const [portfolioBookExposureMillions, setPortfolioBookExposureMillions] = useState<number>(250);

  // Expanded indicator breakdown drawer state
  const [expandedPillar, setExpandedPillar] = useState<string | null>(null);

  // Fetch Live Data Bundle for Country
  const fetchLiveBundle = async (code: string) => {
    setIsLoadingLive(true);
    setLiveFetchError(null);
    try {
      const resp = await fetch(`/api/live-data/sovereign-bundle?country=${code}`);
      if (resp.ok) {
        const bundle: LiveSovereignBundle = await resp.json();
        setLiveBundle(bundle);
      } else {
        throw new Error(`HTTP ${resp.status}`);
      }
    } catch (err: any) {
      console.warn('Could not fetch live bundle for G-VaR:', err);
      setLiveFetchError('Could not reach live feeds; using calibrated prior benchmarks.');
    } finally {
      setIsLoadingLive(false);
    }
  };

  useEffect(() => {
    if (liveFeedActive) {
      fetchLiveBundle(selectedCountry);
    }
  }, [selectedCountry, liveFeedActive]);

  // 1. Generate 7-Pillar Scorecard (incorporating live feed if active)
  const scorecard = useMemo(() => {
    return getCalibratedScorecard(
      selectedCountry,
      isSics,
      liveFeedActive ? liveBundle : null
    );
  }, [selectedCountry, isSics, liveFeedActive, liveBundle]);

  // 2. Base Hazard Event Probability (Layer 1)
  const baseProb12M = useMemo(() => {
    return selectedCountry === 'BLZ' ? 0.082 :
           selectedCountry === 'CHL' ? 0.024 :
           selectedCountry === 'ZAF' ? 0.075 :
           selectedCountry === 'BRA' ? 0.048 :
           selectedCountry === 'NGA' ? 0.088 :
           selectedCountry === 'EGY' ? 0.092 :
           selectedCountry === 'ARG' ? 0.125 :
           selectedCountry === 'TUR' ? 0.065 :
           selectedCountry === 'ITA' ? 0.028 : 0.045;
  }, [selectedCountry]);

  // 3. Layer 2: Bayesian Updated Probability
  const postBayesianProb = useMemo(() => {
    return bayesianUpdateProbability(
      baseProb12M,
      scorecard.compositeScore,
      45.0,
      regimeState,
      marketImpliedDefaultProb
    );
  }, [baseProb12M, scorecard.compositeScore, regimeState, marketImpliedDefaultProb]);

  // 4. Layer 6: Monte Carlo G-VaR & Expected Shortfall
  const gVarDistribution = useMemo(() => {
    return runGVarMonteCarlo(postBayesianProb, portfolioBookExposureMillions, 10000);
  }, [postBayesianProb, portfolioBookExposureMillions]);

  // 5. PRI Policy Quote
  const priQuote: PriPolicyQuote = useMemo(() => {
    return calculatePriPolicyQuote({
      peril: priPeril,
      policyLimitMillions,
      deductibleMillions,
      tenorYears: 3,
      sector: priSector,
      location: priLocation,
      postBayesianProb,
      scorecardScore: scorecard.compositeScore,
    });
  }, [
    priPeril,
    policyLimitMillions,
    deductibleMillions,
    priSector,
    priLocation,
    postBayesianProb,
    scorecard.compositeScore,
  ]);

  // Sovereign entities currently in terminal
  const terminalSovereigns = useMemo(() => {
    return allEntities.filter((e) => e.tier === 'sovereign');
  }, [allEntities]);

  // SVG Tail Loss Curve Chart
  const chartWidth = 560;
  const chartHeight = 180;
  const padding = { top: 15, right: 25, bottom: 30, left: 45 };
  const innerW = chartWidth - padding.left - padding.right;
  const innerH = chartHeight - padding.top - padding.bottom;

  const exceedancePoints = gVarDistribution.tailLossExceedance;
  const maxLoss = Math.max(...exceedancePoints.map((p) => p.lossPct), 10);

  const xScale = (i: number) => padding.left + (i / (exceedancePoints.length - 1)) * innerW;
  const yScale = (val: number) => padding.top + innerH - (val / maxLoss) * innerH;

  const tailPath = exceedancePoints
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)},${yScale(p.lossPct)}`)
    .join(' ');

  return (
    <div className="space-y-6">
      {/* Top Banner: Randori Country Score & Grade Lockup */}
      <div className="p-4 bg-slate-900 border border-slate-800 rounded flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded bg-cyan-950 border border-cyan-500/50 flex items-center justify-center text-cyan-400 shrink-0">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-100">
                Randori Geopolitical Risk VaR (G-VaR) Methodology
              </h2>
              <span className="text-[11px] font-mono text-cyan-300 bg-cyan-950/70 border border-cyan-800/80 rounded px-1.5 py-0.2">
                12-Month Horizon
              </span>
              {liveFeedActive && (
                <span className="text-[10px] font-mono text-emerald-300 bg-emerald-950/70 border border-emerald-800/80 rounded px-1.5 py-0.2 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span>Live Feeds Linked</span>
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400">
              Proprietary 7-Pillar scorecard, 3-state HMM regimes, and Political Risk Insurance (PRI) underwriting desk.
            </p>
          </div>
        </div>

        {/* Controls: Country selector & Small Island States toggle */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Sovereign Jurisdiction Dropdown */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-500">Jurisdiction:</span>
            <select
              value={selectedCountry}
              onChange={(e) => {
                const code = e.target.value;
                if (code === '__custom__') {
                  setShowCustomInput(true);
                } else {
                  setShowCustomInput(false);
                  setSelectedCountry(code);
                  setIsSics(code === 'BLZ');
                }
              }}
              aria-label="Select Country for Randori G-VaR"
              className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded px-2.5 py-1.5 focus:outline-none focus:border-cyan-500 font-mono"
            >
              <optgroup label="Calibrated Benchmarks">
                <option value="BLZ">Belize (Scorecard Test Case)</option>
                <option value="CHL">Chile (Low-Risk Calibration Anchor)</option>
                <option value="ZAF">South Africa (Emerging Sovereign)</option>
                <option value="BRA">Brazil (Commodity Exporter)</option>
                <option value="ITA">Italy (Eurozone Sovereign)</option>
              </optgroup>
              <optgroup label="Terminal Ingested Sovereigns">
                {terminalSovereigns.map((s) => {
                  const cCode = s.id.replace('sovereign-', '').toUpperCase();
                  return (
                    <option key={s.id} value={cCode}>
                      {s.name} ({cCode})
                    </option>
                  );
                })}
              </optgroup>
              <optgroup label="Other Sovereigns">
                <option value="NGA">Nigeria (NGA)</option>
                <option value="EGY">Egypt (EGY)</option>
                <option value="ARG">Argentina (ARG)</option>
                <option value="TUR">Turkey (TUR)</option>
                <option value="KEN">Kenya (KEN)</option>
                <option value="GHA">Ghana (GHA)</option>
                <option value="__custom__">+ Enter Custom ISO3...</option>
              </optgroup>
            </select>
          </div>

          {/* Custom ISO3 prompt if selected */}
          {showCustomInput && (
            <div className="flex items-center gap-1">
              <input
                type="text"
                placeholder="ISO3"
                value={customCountryInput}
                onChange={(e) => setCustomCountryInput(e.target.value.toUpperCase())}
                className="w-16 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs font-mono text-cyan-300 uppercase"
              />
              <button
                onClick={() => {
                  if (customCountryInput) {
                    setSelectedCountry(customCountryInput);
                    setShowCustomInput(false);
                  }
                }}
                className="px-2 py-1 bg-cyan-400 text-slate-950 text-xs font-semibold rounded"
              >
                Go
              </button>
            </div>
          )}

          {/* SICS Toggle */}
          <button
            onClick={() => setIsSics(!isSics)}
            className={`px-2.5 py-1 text-xs rounded border transition-colors flex items-center gap-1.5 ${
              isSics
                ? 'bg-cyan-950 border-cyan-600/70 text-cyan-300'
                : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
            title="Small Island and Coastal States: Climate pillar rises to 15%, other pillars scaled down"
          >
            <Umbrella className="w-3.5 h-3.5" />
            <span>SICS: {isSics ? '15% Climate' : '5% Standard'}</span>
          </button>

          {/* Live Data Feed Ingestion Toggle */}
          <button
            onClick={() => setLiveFeedActive(!liveFeedActive)}
            className={`px-2.5 py-1 text-xs rounded border transition-colors flex items-center gap-1.5 ${
              liveFeedActive
                ? 'bg-emerald-950/70 border-emerald-600/80 text-emerald-300'
                : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
            title="Toggle Live Ingestion from IMF DataMapper, World Bank IDS, BIS Policy Rates, and UN Comtrade"
          >
            <Radio className={`w-3.5 h-3.5 ${liveFeedActive ? 'animate-pulse text-emerald-400' : ''}`} />
            <span>Live Data: {liveFeedActive ? 'Ingesting Live' : 'Model Prior'}</span>
          </button>

          {/* Pull Entity shortcut button */}
          {onOpenPullModal && (
            <button
              onClick={onOpenPullModal}
              title="Pull new sovereign from live multi-agency APIs"
              className="px-2.5 py-1 text-xs text-slate-300 hover:text-white bg-slate-950 hover:bg-slate-800 border border-slate-700 rounded flex items-center gap-1.5 transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              <span>+ Pull New</span>
            </button>
          )}
        </div>
      </div>

      {/* LIVE DATA INGESTION STATUS STRIP */}
      {liveFeedActive && (
        <div className="p-3 bg-slate-950 border border-slate-800 rounded flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-semibold text-slate-300 flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-cyan-400" />
              <span>Live Empirical Feeds Plugged into G-VaR:</span>
            </span>
            <span className="bg-slate-900 border border-slate-800 rounded px-2 py-0.5 text-slate-300 font-mono text-[11px]">
              IMF Debt: <strong className="text-cyan-300">{liveBundle?.reconciliation?.imfGeneralGovtDebtToGdp ? `${liveBundle.reconciliation.imfGeneralGovtDebtToGdp.toFixed(1)}%` : '76.0%'}</strong>
            </span>
            <span className="bg-slate-900 border border-slate-800 rounded px-2 py-0.5 text-slate-300 font-mono text-[11px]">
              IMF Growth: <strong className="text-cyan-300">{liveBundle?.reconciliation?.realGdpGrowthPct ? `${liveBundle.reconciliation.realGdpGrowthPct.toFixed(2)}%` : '+1.1%'}</strong>
            </span>
            <span className="bg-slate-900 border border-slate-800 rounded px-2 py-0.5 text-slate-300 font-mono text-[11px]">
              WB Reserves: <strong className="text-emerald-300">{liveBundle?.reconciliation?.totalFxReservesBillionsUsd ? `$${liveBundle.reconciliation.totalFxReservesBillionsUsd.toFixed(1)}B` : '$62.4B'}</strong>
            </span>
            <span className="bg-slate-900 border border-slate-800 rounded px-2 py-0.5 text-slate-300 font-mono text-[11px]">
              BIS Policy Rate: <strong className="text-cyan-300">{liveBundle?.reconciliation?.bisPolicyRatePct ? `${liveBundle.reconciliation.bisPolicyRatePct.toFixed(2)}%` : '8.25%'}</strong>
            </span>
            <span className="bg-slate-900 border border-slate-800 rounded px-2 py-0.5 text-slate-300 font-mono text-[11px]">
              UN Trade Conc: <strong className="text-amber-300">{liveBundle?.reconciliation?.commodityConcentrationRatio ? `${liveBundle.reconciliation.commodityConcentrationRatio}%` : '38.5%'}</strong>
            </span>
          </div>

          <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
            {isLoadingLive ? (
              <span className="flex items-center gap-1.5 text-cyan-300">
                <RefreshCw className="w-3 h-3 animate-spin" />
                <span>Syncing live endpoints...</span>
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Pillars recalibrated via live data</span>
              </span>
            )}
          </div>
        </div>
      )}

      {/* CORE SCORECARD SUMMARY CARDS */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {/* Composite Score */}
        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>Randori Country Score</span>
            <span className="text-[11px] text-slate-500">0–100</span>
          </div>
          <div className="text-2xl font-bold font-mono text-cyan-300 tabular-nums">
            {scorecard.compositeScore.toFixed(1)}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            {liveFeedActive ? 'Live empirical weighted composite' : 'Baseline model weighted composite'}
          </div>
        </div>

        {/* Randori Grade */}
        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>Randori Risk Grade</span>
            <Award className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-slate-100 tabular-nums">
            Grade {scorecard.randoriGrade} <span className="text-xs font-normal text-slate-400">/ 10</span>
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            MIN(10, INT(Score / 10) + 1)
          </div>
        </div>

        {/* 12M Event Probability */}
        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>12M Loss Probability</span>
            <span className="text-xs text-rose-400 font-mono">p_post</span>
          </div>
          <div className="text-2xl font-bold font-mono text-rose-400 tabular-nums">
            {(postBayesianProb * 100).toFixed(1)}%
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Layer 2 Bayesian log-odds update
          </div>
        </div>

        {/* HMM Regime State */}
        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>HMM Regime State</span>
            <span className="text-[11px] text-slate-500">Layer 3</span>
          </div>
          <div className="flex items-center gap-1.5 mt-1">
            <span className={`w-2.5 h-2.5 rounded-full ${
              regimeState === 'calm' ? 'bg-emerald-400' :
              regimeState === 'stressed' ? 'bg-amber-400' : 'bg-rose-500'
            }`} />
            <span className="text-base font-bold font-mono uppercase text-slate-200">
              {regimeState}
            </span>
          </div>
          {/* Regime Switcher */}
          <div className="flex items-center gap-1 mt-1 text-[10px] font-mono">
            <button
              onClick={() => setRegimeState('calm')}
              className={`px-1.5 py-0.5 rounded ${regimeState === 'calm' ? 'bg-emerald-950 text-emerald-300' : 'text-slate-500'}`}
            >
              Calm
            </button>
            <button
              onClick={() => setRegimeState('stressed')}
              className={`px-1.5 py-0.5 rounded ${regimeState === 'stressed' ? 'bg-amber-950 text-amber-300' : 'text-slate-500'}`}
            >
              Stressed
            </button>
            <button
              onClick={() => setRegimeState('crisis')}
              className={`px-1.5 py-0.5 rounded ${regimeState === 'crisis' ? 'bg-rose-950 text-rose-300' : 'text-slate-500'}`}
            >
              Crisis
            </button>
          </div>
        </div>

        {/* G-VaR (99%) on Portfolio */}
        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>Portfolio G-VaR (99%)</span>
            <Flame className="w-3.5 h-3.5 text-rose-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-rose-300 tabular-nums">
            ${gVarDistribution.var99UsdMillions}M
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            ES(99%): ${gVarDistribution.expectedShortfall99UsdMillions}M
          </div>
        </div>
      </div>

      {/* SECTION 1: THE 7-PILLAR SCORECARD MATRIX */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              <span>The Randori 7-Pillar Scorecard Architecture</span>
            </h3>
            <p className="text-xs text-slate-400">
              Aggregated via the 70/30 rule: P_k = 0.7 · WeightedAvg + 0.3 · MaxIndicator. Fatal weaknesses cannot be averaged away.
            </p>
          </div>
          <button
            onClick={onOpenFormulaModal}
            className="text-xs text-cyan-400 hover:text-cyan-300 font-mono flex items-center gap-1"
          >
            <Info className="w-3.5 h-3.5" />
            <span>Scorecard Rulebook</span>
          </button>
        </div>

        {/* 7 Pillar Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {Object.entries(scorecard.pillars).map(([key, pillar]) => {
            const isHighRisk = pillar.finalScore >= 65;
            const isModerate = pillar.finalScore >= 45 && pillar.finalScore < 65;
            const liveIndicatorCount = pillar.indicators.filter((i) => i.isLiveFeed).length;

            return (
              <div
                key={key}
                className="p-3.5 bg-slate-900 border border-slate-800 rounded space-y-2 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-semibold text-slate-200 line-clamp-1">{pillar.name}</span>
                    <span className="font-mono text-slate-400 font-medium">
                      {(pillar.activeWeight * 100).toFixed(1)}%
                    </span>
                  </div>

                  <div className="flex items-baseline justify-between mt-1">
                    <span className={`text-xl font-bold font-mono tabular-nums ${
                      isHighRisk ? 'text-rose-400' : isModerate ? 'text-amber-300' : 'text-emerald-400'
                    }`}>
                      {pillar.finalScore.toFixed(1)}
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono">
                      Worst: {pillar.maxIndicatorScore.toFixed(0)}
                    </span>
                  </div>

                  {liveIndicatorCount > 0 && liveFeedActive && (
                    <div className="text-[10px] text-emerald-400 flex items-center gap-1 mt-1 font-mono">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      <span>{liveIndicatorCount} Live {liveIndicatorCount === 1 ? 'Indicator' : 'Indicators'} Ingested</span>
                    </div>
                  )}

                  {pillar.fatalWeakness && (
                    <div className="text-[11px] text-rose-400 bg-rose-950/40 border border-rose-900/60 rounded px-1.5 py-0.5 mt-1.5 line-clamp-1">
                      Fatal: {pillar.fatalWeakness}
                    </div>
                  )}

                  {pillar.triggerAddOns > 0 && (
                    <div className="text-[10px] text-amber-300 mt-1 font-mono">
                      +Trigger Add-on: +{pillar.triggerAddOns} pts
                    </div>
                  )}
                </div>

                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-500">
                  <span className="font-mono text-[11px]">
                    70/30: {pillar.aggregatedScore.toFixed(1)}
                  </span>
                  <button
                    onClick={() => setExpandedPillar(expandedPillar === key ? null : key)}
                    className="text-cyan-400 hover:text-cyan-300 text-[11px] font-sans underline"
                  >
                    {expandedPillar === key ? 'Hide' : 'Inspect'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Expanded Pillar Indicators Table */}
        {expandedPillar && (
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-200">
                Detailed Indicator Scoring: {scorecard.pillars[expandedPillar as keyof typeof scorecard.pillars]?.name}
              </span>
              <button
                onClick={() => setExpandedPillar(null)}
                className="text-xs text-slate-400 hover:text-slate-200"
              >
                Close Drawer
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-900/40 font-medium font-sans">
                    <th className="py-2 px-3">Indicator Name</th>
                    <th className="py-2 px-3 text-right">Pillar Weight</th>
                    <th className="py-2 px-3 text-right">Observed Value</th>
                    <th className="py-2 px-3 text-right">Score (0–100)</th>
                    <th className="py-2 px-3">Data Source / Live Ingestion</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {scorecard.pillars[expandedPillar as keyof typeof scorecard.pillars]?.indicators.map((ind) => (
                    <tr key={ind.id} className="hover:bg-slate-900/50 text-slate-300">
                      <td className="py-2 px-3 font-sans text-slate-200 flex items-center gap-2">
                        <span>{ind.name}</span>
                        {ind.isLiveFeed && (
                          <span className="text-[9px] font-mono uppercase px-1.5 py-0.2 rounded bg-emerald-950/80 border border-emerald-700/80 text-emerald-300">
                            Live Feed
                          </span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums text-slate-400">
                        {(ind.weightInPillar * 100).toFixed(0)}%
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums text-slate-300">
                        <span className={ind.isLiveFeed ? 'text-cyan-300 font-bold' : ''}>
                          {ind.rawObservedValue}
                        </span>
                        {ind.originalBaselineValue !== undefined && ind.originalBaselineValue !== ind.rawObservedValue && (
                          <span className="text-[10px] text-slate-500 block">
                            Prior: {ind.originalBaselineValue}
                          </span>
                        )}
                      </td>
                      <td className={`py-2 px-3 text-right tabular-nums font-bold ${
                        ind.interpolatedScore >= 75 ? 'text-rose-400' :
                        ind.interpolatedScore >= 50 ? 'text-amber-300' : 'text-slate-200'
                      }`}>
                        {ind.interpolatedScore.toFixed(1)}
                      </td>
                      <td className="py-2 px-3 font-sans text-[11px]">
                        {ind.isLiveFeed && ind.liveFeedSource ? (
                          <span className="text-emerald-300 font-mono">
                            {ind.liveFeedSource}
                          </span>
                        ) : (
                          <span className="text-slate-500">{ind.source}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* SECTION 2: LAYER 6 MONTE CARLO LOSS DISTRIBUTION & G-VaR */}
      <div className="p-4 bg-slate-900 border border-slate-800 rounded space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-xs font-bold text-slate-200 flex items-center gap-2">
              <Flame className="w-3.5 h-3.5 text-rose-400" />
              <span>Layer 6: Portfolio G-VaR Loss Distribution (10,000 Monte Carlo Runs)</span>
            </h3>
            <p className="text-xs text-slate-400">
              Evaluates tail risk for a portfolio exposure of ${portfolioBookExposureMillions}M over a 12-month horizon.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400 font-mono">Portfolio Book:</span>
            <input
              type="number"
              value={portfolioBookExposureMillions}
              onChange={(e) => setPortfolioBookExposureMillions(Math.max(1, Number(e.target.value)))}
              className="w-24 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs font-mono text-cyan-300 tabular-nums"
            />
            <span className="text-xs text-slate-400 font-mono">$M</span>
          </div>
        </div>

        {/* Exceedance Curve SVG */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-center">
          <div className="lg:col-span-2 overflow-x-auto">
            <svg
              viewBox={`0 0 ${chartWidth} ${chartHeight}`}
              className="w-full h-auto max-h-[200px] font-mono text-[10px] select-none"
            >
              {/* Grid Lines */}
              {Array.from({ length: 4 }).map((_, i) => {
                const yVal = (i / 3) * maxLoss;
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
                    <text x={padding.left - 6} y={yPos + 3} textAnchor="end" fill="#64748b">
                      {yVal.toFixed(0)}%
                    </text>
                  </g>
                );
              })}

              {/* X Axis */}
              {exceedancePoints.map((p, i) => (
                <text
                  key={i}
                  x={xScale(i)}
                  y={chartHeight - padding.bottom + 16}
                  textAnchor="middle"
                  fill="#94a3b8"
                >
                  {p.percentile}%
                </text>
              ))}

              {/* Exceedance Line */}
              <path d={tailPath} fill="none" stroke="#f43f5e" strokeWidth="2.5" />

              {/* Points */}
              {exceedancePoints.map((p, i) => (
                <circle
                  key={i}
                  cx={xScale(i)}
                  cy={yScale(p.lossPct)}
                  r="3.5"
                  fill="#881337"
                  stroke="#f43f5e"
                  strokeWidth="1.5"
                />
              ))}
            </svg>
          </div>

          {/* Loss Metrics Panel */}
          <div className="p-3.5 bg-slate-950 border border-slate-800 rounded space-y-2 text-xs font-mono">
            <div className="flex justify-between">
              <span className="text-slate-400 font-sans">Expected Loss (EL):</span>
              <span className="text-slate-200 font-semibold tabular-nums">
                ${gVarDistribution.expectedLossUsdMillions}M ({gVarDistribution.expectedLossPct}%)
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400 font-sans">G-VaR (95% Conf):</span>
              <span className="text-amber-300 font-semibold tabular-nums">
                ${gVarDistribution.var95UsdMillions}M ({gVarDistribution.var95Pct}%)
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400 font-sans">G-VaR (99% Tail):</span>
              <span className="text-rose-400 font-bold tabular-nums">
                ${gVarDistribution.var99UsdMillions}M ({gVarDistribution.var99Pct}%)
              </span>
            </div>
            <div className="flex justify-between pt-1 border-t border-slate-800">
              <span className="text-slate-400 font-sans">Expected Shortfall ES(99%):</span>
              <span className="text-rose-300 font-bold tabular-nums">
                ${gVarDistribution.expectedShortfall99UsdMillions}M ({gVarDistribution.expectedShortfall99Pct}%)
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* SECTION 3: POLITICAL RISK INSURANCE (PRI) UNDERWRITING & PRICING DESK */}
      <div className="p-5 bg-slate-900 border border-slate-800 rounded space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
          <div>
            <div className="text-xs font-medium text-cyan-400 uppercase tracking-wider">
              Underwriting & Guarantee Structuring
            </div>
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2 mt-0.5">
              <span>Political Risk Insurance (PRI) Actuarial Pricing Desk</span>
            </h3>
          </div>
          <span className={`px-2.5 py-1 text-xs rounded border flex items-center gap-1.5 font-medium ${
            priQuote.underwritingRecommendation === 'Accept'
              ? 'bg-emerald-950/60 border-emerald-700/60 text-emerald-300'
              : priQuote.underwritingRecommendation === 'Accept with Conditions'
              ? 'bg-amber-950/60 border-amber-700/60 text-amber-300'
              : 'bg-rose-950/60 border-rose-700/60 text-rose-300'
          }`}>
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Recommendation: {priQuote.underwritingRecommendation}</span>
          </span>
        </div>

        {/* Policy Configuration Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 bg-slate-950 p-4 border border-slate-800 rounded">
          {/* Covered Peril */}
          <div className="space-y-1.5">
            <span className="text-xs text-slate-400 block font-medium">Covered Peril:</span>
            <select
              value={priPeril}
              onChange={(e) => setPriPeril(e.target.value as GeopoliticalPeril)}
              aria-label="Covered Peril"
              className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-sans"
            >
              <option value="expropriation">Expropriation & Nationalization (CEND)</option>
              <option value="currency_inconvertibility">Currency Inconvertibility & Transfer</option>
              <option value="political_violence">Political Violence & Sabotage (PV)</option>
              <option value="sovereign_default">Sovereign Default / Debt Restructuring</option>
              <option value="sanctions">Sanctions & Trade Embargo</option>
            </select>
          </div>

          {/* Sector Multiplier */}
          <div className="space-y-1.5">
            <span className="text-xs text-slate-400 block font-medium">Industry Sector (Multiplier):</span>
            <select
              value={priSector}
              onChange={(e) => setPriSector(e.target.value as PriSector)}
              aria-label="Industry Sector"
              className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-sans"
            >
              <option value="mining_oil_gas">Mining, Oil and Gas (1.5x)</option>
              <option value="power_water_telecoms">Power, Water & Telecoms (1.3x)</option>
              <option value="transport_infrastructure">Transport & Port Concessions (1.2x)</option>
              <option value="banking_finance">Banking and Finance (1.0x)</option>
              <option value="manufacturing_services_agri">Manufacturing & Services (0.7x)</option>
            </select>
          </div>

          {/* Asset Location (PV Multiplier) */}
          <div className="space-y-1.5">
            <span className="text-xs text-slate-400 block font-medium">Asset Location (ACLED Density):</span>
            <select
              value={priLocation}
              onChange={(e) => setPriLocation(e.target.value as AssetLocationRisk)}
              disabled={priPeril !== 'political_violence'}
              aria-label="Asset Location"
              className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-sans disabled:opacity-40"
            >
              <option value="no_events_nearby">No events nearby (&lt;50km) (0.7x)</option>
              <option value="around_national_average">Around national average (1.0x)</option>
              <option value="three_times_average">3x national average (1.5x)</option>
              <option value="active_conflict_zone">Active conflict zone (2.0x)</option>
            </select>
          </div>

          {/* Sum Insured / Policy Limit */}
          <div className="space-y-1.5">
            <span className="text-xs text-slate-400 block font-medium">Policy Sum Insured:</span>
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={policyLimitMillions}
                onChange={(e) => setPolicyLimitMillions(Math.max(5, Number(e.target.value)))}
                aria-label="Policy Sum Insured in millions"
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-xs font-mono text-cyan-300 tabular-nums"
              />
              <span className="text-xs text-slate-500 font-mono">$M</span>
            </div>
          </div>
        </div>

        {/* Actuarial Premium Pricing Readout */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-3 bg-slate-950 border border-slate-800 rounded">
            <span className="text-xs text-slate-400 block mb-1">Adjusted Peril Probability</span>
            <span className="font-mono text-xl font-bold text-cyan-300 tabular-nums">
              {priQuote.postBayesianProbability}%
            </span>
            <span className="text-[11px] text-slate-500 block mt-1">
              Sector Multiplier: {priQuote.sectorMultiplier}x
            </span>
          </div>

          <div className="p-3 bg-slate-950 border border-slate-800 rounded">
            <span className="text-xs text-slate-400 block mb-1">Technical Rate-on-Line (ROL)</span>
            <span className="font-mono text-xl font-bold text-amber-300 tabular-nums">
              {priQuote.technicalRateOnLinePct}% p.a.
            </span>
            <span className="text-[11px] text-slate-500 block mt-1">
              Annual premium rate / limit
            </span>
          </div>

          <div className="p-3 bg-slate-950 border border-slate-800 rounded">
            <span className="text-xs text-slate-400 block mb-1">Annual PRI Premium</span>
            <span className="font-mono text-xl font-bold text-emerald-400 tabular-nums">
              ${(priQuote.annualPremiumUsd / 1e6).toFixed(2)}M
            </span>
            <span className="text-[11px] text-slate-500 block mt-1">
              ${priQuote.annualPremiumUsd.toLocaleString()} / year
            </span>
          </div>

          <div className="p-3 bg-slate-950 border border-slate-800 rounded">
            <span className="text-xs text-slate-400 block mb-1">Tail Capital Buffer Charge</span>
            <span className="font-mono text-xl font-bold text-rose-300 tabular-nums">
              ${priQuote.tailRiskCapitalChargeMillions}M
            </span>
            <span className="text-[11px] text-slate-500 block mt-1">
              Allocated G-VaR(99%) solvency cost
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
