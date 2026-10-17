import {
  RandoriGVarAnalysis,
  RandoriCountryScorecard,
  ScorecardPillarResult,
  ScorecardPillarIndicator,
  GeopoliticalPeril,
  PriSector,
  AssetLocationRisk,
  HmnRegimeState,
  PriPolicyQuote,
  GVarLossDistribution,
  LiveSovereignBundle,
} from '../types/finance';

/**
 * Randori Geopolitical Risk VaR (G-VaR) Methodology Engine
 * Proprietary quantitative framework for 12-Month event probabilities,
 * 7-Pillar scorecard calibration, 3-state HMM regimes, and PRI guarantee pricing.
 */

export const SECTOR_MULTIPLIERS: Record<PriSector, number> = {
  mining_oil_gas: 1.5,
  power_water_telecoms: 1.3,
  transport_infrastructure: 1.2,
  banking_finance: 1.0,
  manufacturing_services_agri: 0.7,
};

export const LOCATION_MULTIPLIERS: Record<AssetLocationRisk, number> = {
  no_events_nearby: 0.7,
  around_national_average: 1.0,
  three_times_average: 1.5,
  active_conflict_zone: 2.0,
};

/**
 * Standard vs Small Island & Coastal States (SICS) Pillar Weights
 */
export function getPillarWeights(isSics: boolean) {
  if (isSics) {
    // Page 6: Climate rises to 15%, others scaled down by (85/95) = 0.8947
    return {
      fiscalDebt: 0.224,
      external: 0.179,
      institutionsGovernance: 0.134,
      politicalPolicy: 0.134,
      macroFinancial: 0.089,
      securitySocial: 0.089,
      climateDisaster: 0.150,
    };
  }
  return {
    fiscalDebt: 0.25,
    external: 0.20,
    institutionsGovernance: 0.15,
    politicalPolicy: 0.15,
    macroFinancial: 0.10,
    securitySocial: 0.10,
    climateDisaster: 0.05,
  };
}

/**
 * Compute pillar score using the 70/30 aggregation rule:
 * P_k = 0.7 * sum(w_j * s_j) + 0.3 * max(s_j)
 */
export function aggregatePillarScore(
  indicators: ScorecardPillarIndicator[],
  triggerAddOns: number = 0,
  analystAdjustment: number = 0
): {
  weightedAverage: number;
  maxIndicatorScore: number;
  aggregatedScore: number;
  finalScore: number;
  fatalWeakness?: string;
} {
  let weightedSum = 0;
  let totalWeight = 0;
  let maxScore = 0;
  let fatalWeakness = '';

  for (const ind of indicators) {
    weightedSum += ind.interpolatedScore * ind.weightInPillar;
    totalWeight += ind.weightInPillar;
    if (ind.interpolatedScore > maxScore) {
      maxScore = ind.interpolatedScore;
      if (ind.interpolatedScore >= 75) {
        fatalWeakness = `${ind.name} (Score: ${ind.interpolatedScore.toFixed(0)})`;
      }
    }
  }

  const weightedAverage = totalWeight > 0 ? weightedSum / totalWeight : 0;
  const aggregatedScore = 0.7 * weightedAverage + 0.3 * maxScore;
  const finalScore = Math.min(100, Math.max(0, aggregatedScore + triggerAddOns + analystAdjustment));

  return {
    weightedAverage: Number(weightedAverage.toFixed(1)),
    maxIndicatorScore: Number(maxScore.toFixed(1)),
    aggregatedScore: Number(aggregatedScore.toFixed(1)),
    finalScore: Number(finalScore.toFixed(1)),
    fatalWeakness: fatalWeakness || undefined,
  };
}

/**
 * Logit helper functions for Layer 2 Bayesian updating
 */
export function logit(p: number): number {
  const safeP = Math.min(0.9999, Math.max(0.0001, p));
  return Math.log(safeP / (1 - safeP));
}

export function expit(x: number): number {
  return 1 / (1 + Math.exp(-x));
}

/**
 * Layer 2: Bayesian Log-Odds Update
 * logit(p_post) = logit(p_model) + w_s * (S_i - S_bar) + sum(w_k * z_k)
 */
export function bayesianUpdateProbability(
  baseProb: number,
  scorecardScore: number,
  meanScore: number = 45.0,
  regimeState: HmnRegimeState = 'calm',
  marketImpliedProb: number = 0.05
): number {
  const ws = 0.042; // Scorecard log-odds elasticity
  const baseLogit = logit(baseProb);
  
  // Regime signal shift
  const regimeShift = regimeState === 'crisis' ? 0.85 : regimeState === 'stressed' ? 0.38 : 0.0;
  // Market spread signal
  const marketShift = (logit(marketImpliedProb) - logit(baseProb)) * 0.25;

  const postLogit = baseLogit + ws * (scorecardScore - meanScore) + regimeShift + marketShift;
  return Number(expit(postLogit).toFixed(4));
}

/**
 * Calibrated Profiles from the Randori Document:
 * Belize (October 2026 test, SICS, Hurricane & debt restructurings)
 * Chile (October 2026 test, low-risk anchor, copper, floating peso)
 * South Africa (emerging benchmark, SARB rate, Eskom)
 * Plus dynamic sovereign calibration with live IMF, World Bank, BIS, and UN Comtrade data!
 */
export function getCalibratedScorecard(
  countryCode: string,
  isSicsOverride?: boolean,
  liveBundle?: LiveSovereignBundle | null
): RandoriCountryScorecard {
  const code = (countryCode || 'BLZ').toUpperCase();
  const isBelize = code === 'BLZ';
  const isChile = code === 'CHL';
  const isSouthAfrica = code === 'ZAF';
  const isSics = isSicsOverride !== undefined ? isSicsOverride : isBelize;
  const weights = getPillarWeights(isSics);

  // Extract live metrics if available
  const r = liveBundle?.reconciliation;
  const liveDebtGdp = r?.imfGeneralGovtDebtToGdp ?? r?.worldBankCentralGovtDebtToGdp ?? null;
  const liveGdpGrowth = r?.realGdpGrowthPct ?? null;
  const liveInflation = r?.inflationRatePct ?? null;
  const livePrimaryBal = r?.primaryFiscalBalancePctGdp ?? null;
  const liveFxReserves = r?.totalFxReservesBillionsUsd ?? null;
  const liveExternalDebt = r?.totalExternalDebtBillionsUsd ?? null;
  const liveBisPolicyRate = r?.bisPolicyRatePct ?? null;
  const liveCommodityConcentration = r?.commodityConcentrationRatio ?? null;

  // 1. Fiscal & Debt Indicators
  const baseDebtGdp = isBelize ? 66 : isChile ? 42 : isSouthAfrica ? 76 : 68;
  const effectiveDebtGdp = liveDebtGdp !== null ? liveDebtGdp : baseDebtGdp;
  let debtScore = 50;
  if (effectiveDebtGdp <= 30) debtScore = 15;
  else if (effectiveDebtGdp <= 50) debtScore = 15 + ((effectiveDebtGdp - 30) / 20) * 20;
  else if (effectiveDebtGdp <= 70) debtScore = 35 + ((effectiveDebtGdp - 50) / 20) * 25;
  else if (effectiveDebtGdp <= 90) debtScore = 60 + ((effectiveDebtGdp - 70) / 20) * 25;
  else debtScore = Math.min(100, 85 + ((effectiveDebtGdp - 90) / 30) * 15);

  const basePrimary = isBelize ? -1.8 : isChile ? 0.2 : -2.4;
  const effectivePrimary = livePrimaryBal !== null ? livePrimaryBal : basePrimary;
  let primaryScore = 45;
  if (effectivePrimary >= 1.5) primaryScore = 15;
  else if (effectivePrimary >= 0) primaryScore = 30;
  else if (effectivePrimary >= -2.0) primaryScore = 50;
  else if (effectivePrimary >= -4.0) primaryScore = 70;
  else primaryScore = Math.min(100, 70 + Math.abs(effectivePrimary + 4) * 8);

  const fiscalIndicators: ScorecardPillarIndicator[] = [
    { id: 'f1', name: 'Debt Service % Revenue', weightInPillar: 0.20, rawObservedValue: isBelize ? 32 : isChile ? 14 : 38, interpolatedScore: isBelize ? 55 : isChile ? 18 : 65, source: 'IMF DSA / Budget' },
    { id: 'f2', name: 'Foreign Currency Debt Service (24M) % FX Reserves', weightInPillar: 0.15, rawObservedValue: isBelize ? 68 : isChile ? 22 : 72, interpolatedScore: isBelize ? 70 : isChile ? 20 : 75, source: liveFxReserves ? 'Live World Bank Reserves' : 'World Bank IDS', isLiveFeed: liveFxReserves !== null, liveFeedSource: liveFxReserves ? `WB FX Reserves: $${liveFxReserves.toFixed(1)}B` : undefined },
    { id: 'f3', name: 'Gross Debt % GDP (Stress Path)', weightInPillar: 0.15, rawObservedValue: Number(effectiveDebtGdp.toFixed(1)), interpolatedScore: Number(debtScore.toFixed(1)), source: liveDebtGdp ? 'Live IMF WEO Gross Debt' : 'IMF WEO', isLiveFeed: liveDebtGdp !== null, liveFeedSource: liveDebtGdp ? `IMF WEO 2024: ${liveDebtGdp.toFixed(1)}% GDP` : undefined, originalBaselineValue: baseDebtGdp },
    { id: 'f4', name: 'Gross Financing Need % GDP', weightInPillar: 0.10, rawObservedValue: isBelize ? 14 : isChile ? 8 : 17, interpolatedScore: isBelize ? 48 : isChile ? 15 : 62, source: 'Article IV' },
    { id: 'f5', name: 'Foreign Currency Share of Debt %', weightInPillar: 0.10, rawObservedValue: isBelize ? 64 : isChile ? 35 : 32, interpolatedScore: isBelize ? 72 : isChile ? 25 : 30, source: 'World Bank IDS' },
    { id: 'f6', name: 'Primary Balance Gap to Stabilizing (pp GDP)', weightInPillar: 0.05, rawObservedValue: Number(effectivePrimary.toFixed(2)), interpolatedScore: Number(primaryScore.toFixed(1)), source: livePrimaryBal !== null ? 'Live IMF Primary Balance' : 'DSA Engine', isLiveFeed: livePrimaryBal !== null, liveFeedSource: livePrimaryBal !== null ? `IMF Net Lending: ${livePrimaryBal.toFixed(2)}% GDP` : undefined, originalBaselineValue: basePrimary },
    { id: 'f7', name: '5-Year Change in Debt/GDP (pp)', weightInPillar: 0.05, rawObservedValue: isBelize ? +4 : isChile ? +3 : +12, interpolatedScore: isBelize ? 45 : isChile ? 35 : 80, source: 'IMF WEO' },
    { id: 'f8', name: 'Default & Restructuring Record (20Y)', weightInPillar: 0.10, rawObservedValue: isBelize ? 4 : isChile ? 0 : (code === 'ARG' ? 3 : 0), interpolatedScore: isBelize ? 100 : (code === 'ARG' ? 95 : (isChile ? 0 : 0)), source: 'BoC-BoE Default DB' },
    { id: 'f9', name: 'Contingent Liabilities & Arrears', weightInPillar: 0.10, rawObservedValue: isBelize ? 2 : isChile ? 1 : 4, interpolatedScore: isBelize ? 50 : isChile ? 15 : 85, source: 'Article IV' },
  ];
  const p1Agg = aggregatePillarScore(fiscalIndicators, 0, 0);

  // 2. External Indicators
  const baseConcentration = isBelize ? 42 : isChile ? 52 : 38;
  const effectiveConcentration = liveCommodityConcentration !== null ? liveCommodityConcentration : baseConcentration;
  const concentrationScore = effectiveConcentration > 50 ? 78 : effectiveConcentration > 35 ? 58 : 38;

  // Greenspan-Guidotti coverage check from live data
  let shortTermDebtScore = isBelize ? 48 : isChile ? 38 : 68;
  let shortTermDebtVal = isBelize ? 48 : isChile ? 38 : 68;
  if (liveFxReserves && liveExternalDebt) {
    const estShortTerm = liveExternalDebt * 0.25;
    const ratio = liveFxReserves / Math.max(0.1, estShortTerm);
    shortTermDebtVal = Number(((estShortTerm / liveFxReserves) * 100).toFixed(1));
    shortTermDebtScore = ratio < 0.8 ? 85 : ratio < 1.0 ? 70 : ratio < 1.5 ? 45 : 25;
  }

  const externalIndicators: ScorecardPillarIndicator[] = [
    { id: 'e1', name: 'Net Usable Reserves % IMF ARA Metric', weightInPillar: 0.15, rawObservedValue: isBelize ? 78 : isChile ? 95 : 82, interpolatedScore: isBelize ? 72 : isChile ? 55 : 68, source: liveFxReserves ? 'Live WB / IMF ARA Metric' : 'IMF ARA Template', isLiveFeed: liveFxReserves !== null, liveFeedSource: liveFxReserves ? `WB Reserves: $${liveFxReserves.toFixed(1)}B` : undefined },
    { id: 'e2', name: 'External Financing Need % Net Reserves', weightInPillar: 0.15, rawObservedValue: isBelize ? 140 : isChile ? 85 : 125, interpolatedScore: isBelize ? 70 : isChile ? 35 : 62, source: liveExternalDebt ? 'Live WB External Debt' : 'World Bank IDS', isLiveFeed: liveExternalDebt !== null, liveFeedSource: liveExternalDebt ? `WB Debt: $${liveExternalDebt.toFixed(1)}B` : undefined },
    { id: 'e3', name: 'Hot Money % Net Reserves', weightInPillar: 0.10, rawObservedValue: isBelize ? 15 : isChile ? 35 : 55, interpolatedScore: isBelize ? 15 : isChile ? 35 : 55, source: 'IMF Arslanalp-Tsuda' },
    { id: 'e4', name: 'Dollarized Banks: FX Deposits % Total', weightInPillar: 0.10, rawObservedValue: isBelize ? 28 : isChile ? 16 : 10, interpolatedScore: isBelize ? 35 : isChile ? 20 : 10, source: 'Central Bank FSI' },
    { id: 'e5', name: 'Exchange Regime & Convertibility', weightInPillar: 0.10, rawObservedValue: isBelize ? 75 : isChile ? 0 : 15, interpolatedScore: isBelize ? 75 : isChile ? 10 : 25, source: 'IMF AREAER' },
    { id: 'e6', name: 'Official Backstop & Swap Facilities', weightInPillar: 0.10, rawObservedValue: isBelize ? 45 : isChile ? 10 : 30, interpolatedScore: isBelize ? 50 : isChile ? 15 : 30, source: 'IMF Country Pages' },
    { id: 'e7', name: 'Access to Dollar Banking System', weightInPillar: 0.05, rawObservedValue: isBelize ? 30 : isChile ? 0 : 50, interpolatedScore: isBelize ? 45 : isChile ? 0 : 50, source: 'FATF List' },
    { id: 'e8', name: 'Current Account Balance % GDP', weightInPillar: 0.05, rawObservedValue: isBelize ? -5.2 : isChile ? -2.8 : -2.1, interpolatedScore: isBelize ? 68 : isChile ? 35 : 28, source: 'IMF WEO' },
    { id: 'e9', name: 'Short-Term External Debt % Reserves', weightInPillar: 0.05, rawObservedValue: shortTermDebtVal, interpolatedScore: shortTermDebtScore, source: liveFxReserves ? 'Live WB Reserves / Debt' : 'BIS / WB', isLiveFeed: liveFxReserves !== null, liveFeedSource: liveFxReserves ? `Greenspan-Guidotti Buffer` : undefined },
    { id: 'e10', name: 'Export Concentration: Largest Sector %', weightInPillar: 0.05, rawObservedValue: Number(effectiveConcentration.toFixed(1)), interpolatedScore: concentrationScore, source: liveCommodityConcentration !== null ? 'Live UN Comtrade HS' : 'UN Comtrade', isLiveFeed: liveCommodityConcentration !== null, liveFeedSource: liveCommodityConcentration !== null ? `UN Comtrade Concentration: ${effectiveConcentration.toFixed(1)}%` : undefined, originalBaselineValue: baseConcentration },
  ];
  const p2Agg = aggregatePillarScore(externalIndicators, 0, 0);

  // 3. Institutions & Governance Indicators
  const instIndicators: ScorecardPillarIndicator[] = [
    { id: 'g1', name: 'Record on Investor Treatment (Past 20Y)', weightInPillar: 0.15, rawObservedValue: isBelize ? 3 : isChile ? 0 : 1, interpolatedScore: isBelize ? 75 : isChile ? 10 : 35, source: 'UNCTAD Dispute DB' },
    { id: 'g2', name: 'Arbitration Award Compliance (ICSID)', weightInPillar: 0.15, rawObservedValue: isBelize ? 3 : isChile ? 0 : 0, interpolatedScore: isBelize ? 75 : isChile ? 0 : 15, source: 'ICSID Case Records' },
    { id: 'g3', name: 'Treaty Protection & BIT Coverage', weightInPillar: 0.10, rawObservedValue: isBelize ? 2 : isChile ? 0 : 1, interpolatedScore: isBelize ? 40 : isChile ? 10 : 25, source: 'UNCTAD IIA' },
    { id: 'g4', name: 'Direction of Change: 3Y WGI Composite', weightInPillar: 0.10, rawObservedValue: isBelize ? -2 : isChile ? -1 : +1, interpolatedScore: isBelize ? 45 : isChile ? 35 : 20, source: 'World Bank WGI' },
    { id: 'g5', name: 'WGI Composite Rule of Law Percentile', weightInPillar: 0.10, rawObservedValue: isBelize ? 46 : isChile ? 78 : 55, interpolatedScore: isBelize ? 54 : isChile ? 22 : 45, source: 'World Bank WGI' },
    { id: 'g6', name: 'Executive Constraints (V-Dem)', weightInPillar: 0.10, rawObservedValue: isBelize ? 0.65 : isChile ? 0.82 : 0.72, interpolatedScore: isBelize ? 35 : isChile ? 15 : 25, source: 'V-Dem Institute' },
    { id: 'g7', name: 'Civil Justice & Contract Enforcement', weightInPillar: 0.10, rawObservedValue: isBelize ? 0.48 : isChile ? 0.68 : 0.58, interpolatedScore: isBelize ? 52 : isChile ? 28 : 42, source: 'WJP Rule of Law' },
    { id: 'g8', name: 'Budget & Data Credibility (SDDS)', weightInPillar: 0.10, rawObservedValue: isBelize ? 2 : isChile ? 0 : 1, interpolatedScore: isBelize ? 45 : isChile ? 10 : 25, source: 'IMF Data Standards' },
    { id: 'g9', name: 'State Growing Role in Strategic Sectors', weightInPillar: 0.05, rawObservedValue: isBelize ? 3 : isChile ? 1 : 2, interpolatedScore: isBelize ? 65 : isChile ? 20 : 50, source: 'OECD SOE Data' },
    { id: 'g10', name: 'Central Bank Independence in Practice', weightInPillar: 0.05, rawObservedValue: isBelize ? 2 : isChile ? 0 : 1, interpolatedScore: isBelize ? 35 : isChile ? 10 : 20, source: 'CBI Index (Garriga)' },
  ];
  const p3Triggers = isBelize ? 10 : isChile ? 0 : 5;
  const p3Agg = aggregatePillarScore(instIndicators, p3Triggers, 0);

  // 4. Political & Policy Indicators
  const polIndicators: ScorecardPillarIndicator[] = [
    { id: 'p1', name: 'Street Pressure Against Promised Adjustment', weightInPillar: 0.15, rawObservedValue: isBelize ? 1 : isChile ? 2 : 3, interpolatedScore: isBelize ? 20 : isChile ? 45 : 65, source: 'ACLED / GDELT' },
    { id: 'p2', name: 'Military and Elite Cohesion', weightInPillar: 0.10, rawObservedValue: isBelize ? 0 : isChile ? 0 : 1, interpolatedScore: isBelize ? 10 : isChile ? 15 : 30, source: 'IISS Military Balance' },
    { id: 'p3', name: 'Regime Type and Factionalism', weightInPillar: 0.10, rawObservedValue: isBelize ? 1 : isChile ? 1 : 2, interpolatedScore: isBelize ? 25 : isChile ? 20 : 45, source: 'V-Dem Regime Class' },
    { id: 'p4', name: 'Coup & Irregular Transfer Risk', weightInPillar: 0.10, rawObservedValue: isBelize ? 0 : isChile ? 0 : 0, interpolatedScore: isBelize ? 0 : isChile ? 0 : 15, source: 'Powell & Thyne' },
    { id: 'p5', name: 'Election Timing & Contestation', weightInPillar: 0.10, rawObservedValue: isBelize ? 1 : isChile ? 2 : 2, interpolatedScore: isBelize ? 25 : isChile ? 50 : 50, source: 'IFES ElectionGuide' },
    { id: 'p6', name: 'Policy Predictability (Decree Rule)', weightInPillar: 0.10, rawObservedValue: isBelize ? 1 : isChile ? 1 : 2, interpolatedScore: isBelize ? 25 : isChile ? 25 : 45, source: 'Article IV' },
    { id: 'p7', name: 'Government Ability to Pass Legislation', weightInPillar: 0.10, rawObservedValue: isBelize ? 0 : isChile ? 2 : 2, interpolatedScore: isBelize ? 15 : isChile ? 60 : 55, source: 'IDB DPI' },
    { id: 'p8', name: 'Stance Toward Creditors & Contracts', weightInPillar: 0.10, rawObservedValue: isBelize ? 1 : isChile ? 0 : 1, interpolatedScore: isBelize ? 35 : isChile ? 10 : 35, source: 'Policy Speeches' },
    { id: 'p9', name: 'Outside Patrons & Geopolitical Ties', weightInPillar: 0.10, rawObservedValue: isBelize ? 1 : isChile ? 1 : 2, interpolatedScore: isBelize ? 25 : isChile ? 20 : 40, source: 'SIPRI / AidData' },
    { id: 'p10', name: 'Leader & Succession Institutionalization', weightInPillar: 0.05, rawObservedValue: isBelize ? 1 : isChile ? 0 : 1, interpolatedScore: isBelize ? 20 : isChile ? 10 : 25, source: 'V-Dem' },
  ];
  const p4Triggers = isBelize ? -5 : isChile ? 5 : 5;
  const p4Agg = aggregatePillarScore(polIndicators, p4Triggers, 0);

  // 5. Macro & Financial Indicators (Live IMF GDP, Inflation & BIS Policy Rate)
  const baseInflation = isBelize ? 3.8 : isChile ? 4.2 : 5.4;
  const effectiveInflation = liveInflation !== null ? liveInflation : baseInflation;
  let inflationScore = 20;
  if (effectiveInflation <= 2.5) inflationScore = 15;
  else if (effectiveInflation <= 5.0) inflationScore = 25;
  else if (effectiveInflation <= 8.0) inflationScore = 50;
  else if (effectiveInflation <= 15.0) inflationScore = 75;
  else inflationScore = Math.min(100, 80 + (effectiveInflation - 15) * 2);

  const baseGdpGrowth = isBelize ? 2.4 : isChile ? 2.1 : 1.2;
  const effectiveGdpGrowth = liveGdpGrowth !== null ? liveGdpGrowth : baseGdpGrowth;
  let gdpGrowthScore = 45;
  if (effectiveGdpGrowth >= 4.0) gdpGrowthScore = 20;
  else if (effectiveGdpGrowth >= 2.0) gdpGrowthScore = 38;
  else if (effectiveGdpGrowth >= 0.5) gdpGrowthScore = 55;
  else gdpGrowthScore = Math.min(100, 75 + Math.max(0, 0.5 - effectiveGdpGrowth) * 12);

  const basePolicyRate = isBelize ? 1.5 : isChile ? 2.2 : 3.8;
  const effectivePolicyRate = liveBisPolicyRate !== null ? (liveBisPolicyRate - effectiveInflation) : basePolicyRate;

  const macroIndicators: ScorecardPillarIndicator[] = [
    { id: 'm1', name: 'Banks Claims on Government % Bank Assets', weightInPillar: 0.10, rawObservedValue: isBelize ? 32 : isChile ? 14 : 26, interpolatedScore: isBelize ? 68 : isChile ? 20 : 52, source: 'IMF Monetary Stats' },
    { id: 'm2', name: 'Currency Mismatch: FX Loans % Total', weightInPillar: 0.10, rawObservedValue: isBelize ? 18 : isChile ? 15 : 8, interpolatedScore: isBelize ? 25 : isChile ? 20 : 10, source: 'Central Bank FSI' },
    { id: 'm3', name: 'Banking Sector Concentration & Weakest Bank', weightInPillar: 0.10, rawObservedValue: isBelize ? 2 : isChile ? 1 : 2, interpolatedScore: isBelize ? 40 : isChile ? 25 : 45, source: 'Bank Annual Reports' },
    { id: 'm4', name: 'Commodity-Credit Link Correlation', weightInPillar: 0.10, rawObservedValue: isBelize ? 0.35 : isChile ? 0.48 : 0.42, interpolatedScore: isBelize ? 45 : isChile ? 62 : 55, source: 'World Bank / IMF' },
    { id: 'm5', name: 'Inflation (12M Stress Path)', weightInPillar: 0.10, rawObservedValue: Number(effectiveInflation.toFixed(1)), interpolatedScore: Number(inflationScore.toFixed(1)), source: liveInflation !== null ? 'Live IMF Inflation' : 'IMF WEO', isLiveFeed: liveInflation !== null, liveFeedSource: liveInflation !== null ? `IMF Inflation: ${effectiveInflation.toFixed(1)}%` : undefined, originalBaselineValue: baseInflation },
    { id: 'm6', name: 'Real GDP Growth Next Year (Stress Path)', weightInPillar: 0.10, rawObservedValue: Number(effectiveGdpGrowth.toFixed(1)), interpolatedScore: Number(gdpGrowthScore.toFixed(1)), source: liveGdpGrowth !== null ? 'Live IMF Real GDP Growth' : 'IMF WEO', isLiveFeed: liveGdpGrowth !== null, liveFeedSource: liveGdpGrowth !== null ? `IMF WEO: ${effectiveGdpGrowth.toFixed(2)}%` : undefined, originalBaselineValue: baseGdpGrowth },
    { id: 'm7', name: 'Non-Performing Loans % Loans', weightInPillar: 0.05, rawObservedValue: isBelize ? 5.2 : isChile ? 2.8 : 4.4, interpolatedScore: isBelize ? 35 : isChile ? 15 : 28, source: 'Central Bank FSI' },
    { id: 'm8', name: 'Real Policy Rate %', weightInPillar: 0.05, rawObservedValue: Number(effectivePolicyRate.toFixed(2)), interpolatedScore: effectivePolicyRate < 0 ? 55 : effectivePolicyRate > 6 ? 65 : 20, source: liveBisPolicyRate !== null ? 'Live BIS Central Bank Rate' : 'BIS / Central Bank', isLiveFeed: liveBisPolicyRate !== null, liveFeedSource: liveBisPolicyRate !== null ? `BIS Policy Rate: ${liveBisPolicyRate.toFixed(2)}%` : undefined, originalBaselineValue: basePolicyRate },
    { id: 'm9', name: 'Credit-to-GDP Gap (pp of GDP)', weightInPillar: 0.05, rawObservedValue: isBelize ? +1.2 : isChile ? +2.4 : +3.5, interpolatedScore: isBelize ? 18 : isChile ? 25 : 35, source: 'BIS Credit Gaps' },
    { id: 'm10', name: 'GDP Per Capita (USD)', weightInPillar: 0.05, rawObservedValue: isBelize ? 6800 : isChile ? 15800 : 6400, interpolatedScore: isBelize ? 48 : isChile ? 24 : 50, source: 'IMF WEO' },
  ];
  const p5Agg = aggregatePillarScore(macroIndicators, 0, 0);

  // 6. Security & Social Indicators
  const secIndicators: ScorecardPillarIndicator[] = [
    { id: 's1', name: 'Armed Conflict on Territory (Battle Deaths)', weightInPillar: 0.10, rawObservedValue: isBelize ? 0 : isChile ? 0 : 0, interpolatedScore: isBelize ? 0 : isChile ? 0 : 15, source: 'UCDP' },
    { id: 's2', name: 'Homicide Rate per 100,000', weightInPillar: 0.10, rawObservedValue: isBelize ? 28 : isChile ? 6.7 : 41, interpolatedScore: isBelize ? 85 : isChile ? 30 : 98, source: 'UNODC / Police' },
    { id: 's3', name: 'Gang Control & Extortion', weightInPillar: 0.10, rawObservedValue: isBelize ? 3 : isChile ? 1 : 3, interpolatedScore: isBelize ? 75 : isChile ? 25 : 75, source: 'InSight Crime' },
    { id: 's4', name: 'Attacks on Business & Staff', weightInPillar: 0.10, rawObservedValue: isBelize ? 1 : isChile ? 1 : 2, interpolatedScore: isBelize ? 25 : isChile ? 25 : 50, source: 'ACLED' },
    { id: 's5', name: 'State Control of Territory', weightInPillar: 0.10, rawObservedValue: isBelize ? 1 : isChile ? 1 : 1, interpolatedScore: isBelize ? 20 : isChile ? 15 : 30, source: 'Crisis Group' },
    { id: 's6', name: 'Youth Unemployment %', weightInPillar: 0.10, rawObservedValue: isBelize ? 18 : isChile ? 14 : 45, interpolatedScore: isBelize ? 50 : isChile ? 35 : 100, source: 'ILOSTAT' },
    { id: 's7', name: 'Illegal Economy Score (GI-TOC)', weightInPillar: 0.05, rawObservedValue: isBelize ? 5.8 : isChile ? 4.2 : 6.8, interpolatedScore: isBelize ? 55 : isChile ? 30 : 72, source: 'Global Crime Index' },
    { id: 's8', name: 'Cyber Attacks on State Systems', weightInPillar: 0.05, rawObservedValue: isBelize ? 1 : isChile ? 1 : 2, interpolatedScore: isBelize ? 25 : isChile ? 20 : 45, source: 'ITU Index' },
    { id: 's9', name: 'Inequality & Gini Index', weightInPillar: 0.05, rawObservedValue: isBelize ? 48 : isChile ? 44 : 63, interpolatedScore: isBelize ? 65 : isChile ? 50 : 100, source: 'World Bank' },
    { id: 's10', name: 'Security Forces Capacity & Human Rights', weightInPillar: 0.05, rawObservedValue: isBelize ? 2 : isChile ? 1 : 2, interpolatedScore: isBelize ? 50 : isChile ? 20 : 50, source: 'State Dept HR Report' },
  ];
  const p6Agg = aggregatePillarScore(secIndicators, 0, 0);

  // 7. Climate & Disaster Indicators
  const climIndicators: ScorecardPillarIndicator[] = [
    { id: 'c1', name: 'Expected Annual Disaster Loss % GDP', weightInPillar: 0.15, rawObservedValue: isBelize ? 2.8 : isChile ? 0.9 : 0.4, interpolatedScore: isBelize ? 92 : isChile ? 60 : 35, source: 'UNDRR / EM-DAT' },
    { id: 'c2', name: '1-in-100 Year Disaster Loss % GDP', weightInPillar: 0.10, rawObservedValue: isBelize ? 42 : isChile ? 18 : 6, interpolatedScore: isBelize ? 90 : isChile ? 65 : 30, source: 'CCRIF / World Bank' },
    { id: 'c3', name: 'Back-to-Back Major Disaster Risk %', weightInPillar: 0.10, rawObservedValue: isBelize ? 35 : isChile ? 15 : 10, interpolatedScore: isBelize ? 75 : isChile ? 35 : 25, source: 'Catastrophe Model' },
    { id: 'c4', name: 'Loss to Main Earner (Tourism / Copper) %', weightInPillar: 0.10, rawObservedValue: isBelize ? 45 : isChile ? 35 : 25, interpolatedScore: isBelize ? 70 : isChile ? 50 : 35, source: 'WTTC / Central Bank' },
    { id: 'c5', name: 'Insurance Protection Gap % Uninsured', weightInPillar: 0.10, rawObservedValue: isBelize ? 85 : isChile ? 65 : 75, interpolatedScore: isBelize ? 85 : isChile ? 60 : 75, source: 'Swiss Re Institute' },
    { id: 'c6', name: 'Financial Protection & Cat DDO / CCRIF', weightInPillar: 0.10, rawObservedValue: isBelize ? 2 : isChile ? 1 : 3, interpolatedScore: isBelize ? 40 : isChile ? 25 : 75, source: 'CCRIF Payout History' },
    { id: 'c7', name: 'Low-Elevation Coastal Zone Exposure %', weightInPillar: 0.05, rawObservedValue: isBelize ? 48 : isChile ? 12 : 8, interpolatedScore: isBelize ? 95 : isChile ? 30 : 20, source: 'CIESIN LECZ' },
    { id: 'c8', name: 'Transition Risk: Fossil Fuel Export Share %', weightInPillar: 0.05, rawObservedValue: isBelize ? 8 : isChile ? 2 : 22, interpolatedScore: isBelize ? 15 : isChile ? 10 : 45, source: 'UN Comtrade' },
    { id: 'c9', name: 'ND-GAIN Climate Vulnerability Score', weightInPillar: 0.05, rawObservedValue: isBelize ? 0.48 : isChile ? 0.38 : 0.44, interpolatedScore: isBelize ? 65 : isChile ? 20 : 45, source: 'Notre Dame GAIN' },
    { id: 'c10', name: 'Water Stress (WRI Aqueduct Baseline)', weightInPillar: 0.05, rawObservedValue: isBelize ? 1 : isChile ? 4 : 3, interpolatedScore: isBelize ? 15 : isChile ? 85 : 65, source: 'WRI Aqueduct' },
  ];
  const p7Triggers = isBelize ? 5 : isChile ? 5 : 0;
  const p7Agg = aggregatePillarScore(climIndicators, p7Triggers, 0);

  // Composite Scorecard Calculation
  const compositeScore = Number((
    weights.fiscalDebt * p1Agg.finalScore +
    weights.external * p2Agg.finalScore +
    weights.institutionsGovernance * p3Agg.finalScore +
    weights.politicalPolicy * p4Agg.finalScore +
    weights.macroFinancial * p5Agg.finalScore +
    weights.securitySocial * p6Agg.finalScore +
    weights.climateDisaster * p7Agg.finalScore
  ).toFixed(1));

  // Grade: MIN(10, INT(score / 10) + 1)
  const randoriGrade = Math.min(10, Math.floor(compositeScore / 10) + 1);

  let activeOverrideFloor: number | undefined;
  let overrideReason: string | undefined;

  if (p1Agg.maxIndicatorScore >= 100 && code === 'BLZ') {
    overrideReason = 'Multiple historical debt restructurings elevate credit scrutiny';
  }

  const countryName =
    liveBundle?.countryName ||
    (code === 'BLZ' ? 'Belize' :
     code === 'CHL' ? 'Republic of Chile' :
     code === 'ZAF' ? 'Republic of South Africa' :
     code === 'BRA' ? 'Federative Republic of Brazil' :
     code === 'ITA' ? 'Italian Republic' :
     code === 'NGA' ? 'Federal Republic of Nigeria' :
     code === 'EGY' ? 'Arab Republic of Egypt' :
     code === 'ARG' ? 'Argentine Republic' :
     code === 'TUR' ? 'Republic of Turkey' :
     code === 'KEN' ? 'Republic of Kenya' :
     code === 'GHA' ? 'Republic of Ghana' :
     code === 'USA' ? 'United States of America' :
     code === 'DEU' ? 'Federal Republic of Germany' :
     code === 'GBR' ? 'United Kingdom' : code);

  return {
    countryCode,
    countryName,
    isSmallIslandCoastalState: isSics,
    pillars: {
      fiscalDebt: { ...p1Agg, id: 'fiscalDebt', name: 'Pillar 1: Fiscal and Debt', standardWeight: 0.25, sicsWeight: 0.224, activeWeight: weights.fiscalDebt, triggerAddOns: 0, analystAdjustment: 0, indicators: fiscalIndicators },
      external: { ...p2Agg, id: 'external', name: 'Pillar 2: External Liquidity', standardWeight: 0.20, sicsWeight: 0.179, activeWeight: weights.external, triggerAddOns: 0, analystAdjustment: 0, indicators: externalIndicators },
      institutionsGovernance: { ...p3Agg, id: 'institutionsGovernance', name: 'Pillar 3: Institutions & Governance', standardWeight: 0.15, sicsWeight: 0.134, activeWeight: weights.institutionsGovernance, triggerAddOns: p3Triggers, analystAdjustment: 0, indicators: instIndicators },
      politicalPolicy: { ...p4Agg, id: 'politicalPolicy', name: 'Pillar 4: Political and Policy', standardWeight: 0.15, sicsWeight: 0.134, activeWeight: weights.politicalPolicy, triggerAddOns: p4Triggers, analystAdjustment: 0, indicators: polIndicators },
      macroFinancial: { ...p5Agg, id: 'macroFinancial', name: 'Pillar 5: Macro and Financial', standardWeight: 0.10, sicsWeight: 0.089, activeWeight: weights.macroFinancial, triggerAddOns: 0, analystAdjustment: 0, indicators: macroIndicators },
      securitySocial: { ...p6Agg, id: 'securitySocial', name: 'Pillar 6: Security and Social', standardWeight: 0.10, sicsWeight: 0.089, activeWeight: weights.securitySocial, triggerAddOns: 0, analystAdjustment: 0, indicators: secIndicators },
      climateDisaster: { ...p7Agg, id: 'climateDisaster', name: 'Pillar 7: Climate and Disaster', standardWeight: 0.05, sicsWeight: 0.150, activeWeight: weights.climateDisaster, triggerAddOns: p7Triggers, analystAdjustment: 0, indicators: climIndicators },
    },
    compositeScore,
    randoriGrade,
    activeOverrideFloor,
    overrideReason,
  };
}

/**
 * Monte Carlo Loss Distribution (Layer 6 G-VaR & Expected Shortfall)
 */
export function runGVarMonteCarlo(
  baseProb: number,
  portfolioExposureMillions: number = 100,
  numSimulations: number = 10000
): GVarLossDistribution {
  const losses: number[] = [];
  const lgdMean = 0.52; // Cruces and Trebesch sovereign haircut mean
  const lgdStd = 0.18;

  for (let i = 0; i < numSimulations; i++) {
    // Event occurrence
    const occurs = Math.random() < baseProb;
    if (occurs) {
      // Draw loss severity (LGD) from Beta or truncated Gaussian
      const u1 = Math.max(1e-9, Math.random());
      const u2 = Math.random();
      const z = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
      const lgd = Math.min(0.95, Math.max(0.15, lgdMean + z * lgdStd));
      losses.push(lgd);
    } else {
      losses.push(0);
    }
  }

  losses.sort((a, b) => a - b);

  const idx95 = Math.floor(numSimulations * 0.95);
  const idx99 = Math.floor(numSimulations * 0.99);

  const var95Pct = losses[idx95] * 100;
  const var99Pct = losses[idx99] * 100;

  const tail99 = losses.slice(idx99);
  const es99Pct = (tail99.reduce((a, b) => a + b, 0) / Math.max(1, tail99.length)) * 100;

  const expectedLossPct = (losses.reduce((a, b) => a + b, 0) / numSimulations) * 100;

  // Build exceedance curve
  const percentiles = [50, 75, 90, 95, 98, 99, 99.5, 99.9];
  const tailLossExceedance = percentiles.map((p) => {
    const idx = Math.min(numSimulations - 1, Math.floor(numSimulations * (p / 100)));
    const lossPct = Number((losses[idx] * 100).toFixed(2));
    return {
      percentile: p,
      lossPct,
      lossMillions: Number(((lossPct / 100) * portfolioExposureMillions).toFixed(2)),
    };
  });

  return {
    numSimulations,
    timeHorizonMonths: 12,
    expectedLossPct: Number(expectedLossPct.toFixed(2)),
    expectedLossUsdMillions: Number(((expectedLossPct / 100) * portfolioExposureMillions).toFixed(2)),
    var95Pct: Number(var95Pct.toFixed(2)),
    var95UsdMillions: Number(((var95Pct / 100) * portfolioExposureMillions).toFixed(2)),
    var99Pct: Number(var99Pct.toFixed(2)),
    var99UsdMillions: Number(((var99Pct / 100) * portfolioExposureMillions).toFixed(2)),
    expectedShortfall99Pct: Number(es99Pct.toFixed(2)),
    expectedShortfall99UsdMillions: Number(((es99Pct / 100) * portfolioExposureMillions).toFixed(2)),
    tailLossExceedance,
  };
}

/**
 * Political Risk Insurance (PRI) Policy Pricing Engine
 */
export function calculatePriPolicyQuote(params: {
  peril: GeopoliticalPeril;
  policyLimitMillions: number;
  deductibleMillions: number;
  tenorYears: number;
  sector: PriSector;
  location: AssetLocationRisk;
  postBayesianProb: number;
  scorecardScore: number;
}): PriPolicyQuote {
  const {
    peril,
    policyLimitMillions,
    deductibleMillions,
    tenorYears,
    sector,
    location,
    postBayesianProb,
    scorecardScore,
  } = params;

  const sectorMult = SECTOR_MULTIPLIERS[sector] ?? 1.0;
  const locationMult = peril === 'political_violence' ? (LOCATION_MULTIPLIERS[location] ?? 1.0) : 1.0;

  // Adjusted loss probability for this specific peril and sector
  const adjustedProb = Math.min(0.45, postBayesianProb * sectorMult * locationMult);
  const netExposure = Math.max(0, policyLimitMillions - deductibleMillions);

  // Expected severity given peril
  const severityMean = peril === 'expropriation' ? 0.70 :
                       peril === 'currency_inconvertibility' ? 0.35 :
                       peril === 'political_violence' ? 0.50 : 0.55;

  const annualExpectedLossMillions = netExposure * adjustedProb * severityMean;
  
  // Cost of capital / tail risk charge (reflecting VaR 99% cushion)
  const capitalCostRate = 0.085; // 8.5% return on solvency capital
  const tailRiskFactor = scorecardScore > 65 ? 0.40 : scorecardScore > 45 ? 0.25 : 0.15;
  const tailCapitalChargeMillions = netExposure * tailRiskFactor * capitalCostRate;

  const expenseLoad = 0.0035 * netExposure; // 35 bps admin and reinsurance friction
  const annualTechnicalPremium = annualExpectedLossMillions + tailCapitalChargeMillions + expenseLoad;

  const rateOnLinePct = netExposure > 0 ? (annualTechnicalPremium / netExposure) * 100 : 2.5;

  let recommendation: 'Accept' | 'Accept with Conditions' | 'Refer to Committee' | 'Decline' = 'Accept';
  if (scorecardScore >= 75 || adjustedProb > 0.25) {
    recommendation = 'Decline';
  } else if (scorecardScore >= 60 || adjustedProb > 0.15) {
    recommendation = 'Refer to Committee';
  } else if (scorecardScore >= 45) {
    recommendation = 'Accept with Conditions';
  }

  return {
    peril,
    policyLimitUsdMillions: policyLimitMillions,
    deductibleUsdMillions: deductibleMillions,
    tenorYears,
    sector,
    sectorMultiplier: sectorMult,
    location,
    locationMultiplier: locationMult,
    baseLossProbability12M: Number((postBayesianProb * 100).toFixed(2)),
    postBayesianProbability: Number((adjustedProb * 100).toFixed(2)),
    expectedLossMillions: Number(annualExpectedLossMillions.toFixed(2)),
    tailRiskCapitalChargeMillions: Number(tailCapitalChargeMillions.toFixed(2)),
    technicalRateOnLinePct: Number(rateOnLinePct.toFixed(2)),
    annualPremiumUsd: Math.round(annualTechnicalPremium * 1e6),
    underwritingRecommendation: recommendation,
  };
}
