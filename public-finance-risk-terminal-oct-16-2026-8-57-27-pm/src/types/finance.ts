/**
 * Institutional Public Finance Risk & Debt Architecture Types
 */

export type GovernmentTier = 'municipal' | 'subnational' | 'sovereign';

export interface BondTranche {
  id: string;
  name: string;
  type: 'GO' | 'Revenue' | 'MoralObligation' | 'TIF' | 'SovereignExternal' | 'SovereignLocal';
  parAmount: number; // in $ millions or local currency millions
  coupon: number; // percentage, e.g. 4.75%
  yieldToMaturity: number; // percentage, e.g. 4.20%
  maturityDate: string; // YYYY-MM-DD
  callDate?: string; // YYYY-MM-DD if callable
  callPrice?: number; // e.g. 100.0 or 102.0
  rating: string; // e.g. 'Aa2', 'BBB-', 'AA+'
  isCallable: boolean;
  spreadOverBenchmarkBps: number; // bps over MMD / UST / Bund
  isTaxExempt?: boolean;
}

export interface VrdoTranche {
  id: string;
  name: string;
  parAmount: number; // $ millions
  currentResetRate: number; // weekly reset %
  liquidityProvider: string; // Bank name
  locExpirationDate: string; // Letter of Credit expiration
  remarketingAgent: string;
  daysToLocExpiry: number;
  bankBondRate: number; // Penalty term-out rate if tendered and un-remarketed
  mode: 'Weekly' | 'Daily' | 'CommercialPaper';
}

export interface PppConcession {
  id: string;
  projectName: string;
  sector: 'Toll Highway' | 'Transit Rail' | 'Water Treatment' | 'Airport Terminal' | 'Healthcare Facility';
  capitalExpenditure: number; // millions
  concessionExpiryYear: number;
  concessionaireName: string;
  paymentStructure: 'Availability Payment' | 'Shadow Toll' | 'Direct User Fee';
  mrgTriggerFloor: number; // Annual revenue/traffic floor ($ millions)
  currentProjectedRevenue: number; // Projected annual revenue ($ millions)
  contingentLiabilityExposure: number; // Maximum government shortfall payout ($ millions)
  status: 'Nominal' | 'Triggered' | 'At Risk';
}

export interface StateOwnedEnterprise {
  id: string;
  name: string;
  sector: 'Electric Power' | 'Public Transit' | 'Port Authority' | 'Water Utility';
  totalDebt: number; // millions
  debtServiceCoverageRatio: number;
  explicitGovernmentGuarantee: boolean;
  bailoutProbability: number; // 0 to 1
  expectedShortfall95: number; // Expected Shortfall ES_95% in millions
}

export interface PensionOpebData {
  planName: string;
  totalPensionLiability: number; // $ millions (TPL)
  actuarialValueOfAssets: number; // $ millions (AVA)
  netPensionLiability: number; // $ millions (NPL)
  fundedRatio: number; // % (AVA / TPL)
  assumedDiscountRate: number; // e.g. 7.00%
  // Sensitivity: NPL at discount rate +/- 100 bps
  nplAtPlus100Bps: number;
  nplAtMinus100Bps: number;
  actuariallyDeterminedContribution: number; // ADC / ADEC ($ millions)
  actualContribution: number;
  opebFundedRatio: number; // Other Post-Employment Benefits %
  opebNetLiability: number;
  activeEmployees: number;
  beneficiaries: number;
}

export interface MunicipalMetrics {
  ownSourceRevenueRatio: number; // Local Taxes / Total Revenue (e.g. 68%)
  melloRoosOverlappingDebtRatio: number; // Overlapping special district debt as % of assessed value
  specialAssessmentDistrictsCount: number;
  totalAssessedValue: number; // $ billions
  millRate: number; // Tax rate per $1,000 assessed value (e.g. 18.5)
  millRateSensitivityRevenueDropPer5PctAV: number; // $ millions drop per 5% AV contraction
  dscrCoverage: number; // Debt Service Coverage Ratio (e.g. 1.45x)
  infrastructureBacklog: number; // Deferred capital maintenance in $ millions
  infrastructureBacklogPctBudget: number; // % of annual budget
  liquidityDaysOfCash: number; // Unrestricted cash / (operating expense / 365)
}

export interface SubnationalMetrics {
  netPensionLiability: number; // $ millions
  pensionFundedRatio: number; // %
  pensionDiscountRate: number; // %
  medicaidExpenditureShare: number; // % of state budget
  medicaidCounterCyclicalSurgeRate: number; // Expected surge in recession %
  fmapFederalShare: number; // Federal Medical Assistance Percentage
  transferDependenceRatio: number; // Federal grants / Total state revenues (e.g. 32%)
  rainyDayFundReserveMonths: number; // Months of operating expenses in reserve
}

export interface SovereignMetrics {
  externalDebtToFxReserves: number; // External debt / Foreign Exchange Reserves ratio (e.g. 1.35x)
  greenspanGuidottiRatio: number; // FX Reserves / Short-term debt maturing in 1 year (>= 1.0 safe)
  fxReservesTotalUsdBillions: number;
  shortTermExternalDebtUsdBillions: number;
  seigniorageCapacityPctGdp: number; // Max sustainable monetization without hyperinflation
  centralBankMonetizationLimitPctGdp: number;
  primaryBalancePctGdp: number; // Fiscal balance excluding interest
  overallFiscalBalancePctGdp: number;
  publicDebtToGdp: number; // %
  externalDebtSharePct: number; // % of public debt in foreign currency
  currentAccountBalancePctGdp: number;
}

export interface MarketSpreadData {
  tenor: string; // '1Y' | '3Y' | '5Y' | '10Y' | '20Y' | '30Y'
  benchmarkYield: number; // AAA MMD or US Treasury %
  entityYield: number; // Entity yield %
  spreadBps: number; // Spread in basis points
  cdsSpreadBps: number; // Synthetic CDS spread in basis points
  cdsBondBasisBps: number; // CDS spread - Z-spread
}

export interface PublicFinanceEntity {
  id: string;
  name: string;
  tier: GovernmentTier;
  jurisdiction: string;
  creditRating: string;
  ratingOutlook: 'Stable' | 'Negative' | 'Positive' | 'Watch';
  currency: string;
  gdpOrBudgetBillions: number;
  totalDirectDebtMillions: number;
  weightedAverageMaturityYears: number; // WAM
  modifiedDurationYears: number;
  durationGapYears: number;
  marketAccessStressScore: number; // 0 to 100
  taxElasticityCoefficient: number; // E = (% dTax) / (% dGDP)
  fiscalMultiplierSpending: number; // e.g. 1.15
  fiscalMultiplierTax: number; // e.g. -0.85
  
  // Specific Tier data
  municipalMetrics?: MunicipalMetrics;
  subnationalMetrics?: SubnationalMetrics;
  sovereignMetrics?: SovereignMetrics;

  pensionOpeb?: PensionOpebData;
  bonds: BondTranche[];
  vrdos: VrdoTranche[];
  pppConcessions: PppConcession[];
  stateOwnedEnterprises: StateOwnedEnterprise[];
  marketSpreads: MarketSpreadData[];

  // Maturity distribution in millions ($)
  maturityWall: {
    within12M: number;
    year1to2: number;
    year2to3: number;
    year3to5: number;
    beyond5Y: number;
  };
}

export interface StressScenario {
  id: string;
  name: string;
  description: string;
  interestRateDeltaBps: number;
  gdpGrowthShockPct: number;
  inflationShockPct: number;
  propertyValueDeclinePct: number;
  pensionAssetShockPct: number;
  pppTrafficDeclinePct: number;
  soeDistressProbabilityMultiplier: number;
  externalCurrencyDevaluationPct: number;
}

export interface DsaTrajectoryPoint {
  year: number;
  baseline: number;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  debtStabilizingPrimaryBalance: number;
}

export interface RefundingAnalysisResult {
  candidateBond: BondTranche;
  currentYield: number;
  refundingYield: number;
  grossSavings: number;
  presentValueSavings: number;
  npvSavingsPercent: number; // (PV savings / refunded par) * 100
  meetsThreshold: boolean; // >= 3.0%
  negativeArbitrageLoss: number;
  efficiencyRatio: number;
  refundingType: 'Current Refunding' | 'Taxable Advance Refunding' | 'Crossover';
}


export interface LiveFeedMetric {
  indicator: string;
  series: Record<string, number>;
  latestYear: string | null;
  latestValue: number | null;
}

export interface LiveImfFeed {
  source: string;
  database: string;
  country: string;
  status: 'online' | 'degraded' | 'offline';
  fetchedAt: string;
  cached?: boolean;
  metrics: {
    debtToGdp?: LiveFeedMetric;
    gdpGrowth?: LiveFeedMetric;
    inflation?: LiveFeedMetric;
    netLending?: LiveFeedMetric;
    currentAccount?: LiveFeedMetric;
  };
}

export interface LiveWorldBankFeed {
  source: string;
  database: string;
  country: string;
  status: 'online' | 'degraded' | 'offline';
  fetchedAt: string;
  cached?: boolean;
  greenspanGuidottiEstimate?: number | null;
  metrics: {
    centralGovtDebt?: LiveFeedMetric;
    externalDebtUsd?: LiveFeedMetric;
    fxReservesUsd?: LiveFeedMetric;
    gdpUsd?: LiveFeedMetric;
    realInterestRate?: LiveFeedMetric;
    externalDebtGni?: LiveFeedMetric;
  };
}

export interface LiveBisFeed {
  source: string;
  database: string;
  country: string;
  status: 'online' | 'degraded' | 'offline';
  fetchedAt: string;
  cached?: boolean;
  policyRate: number | null;
  latestPeriod: string | null;
  timeSeries: Record<string, number>;
  description: string;
}

export interface LiveUnComtradeFeed {
  source: string;
  database: string;
  reporterCode: string;
  country: string;
  status: 'online' | 'degraded' | 'offline';
  fetchedAt: string;
  cached?: boolean;
  topCommodities: Array<{
    commodityCode: string;
    description: string;
    valueUsd: number;
  }>;
  commodityConcentrationRatio: number;
  termsOfTradeVulnerability: string;
}

export interface LiveReconciliationMetrics {
  imfGeneralGovtDebtToGdp: number | null;
  worldBankCentralGovtDebtToGdp: number | null;
  differenceNote: string;
  realGdpGrowthPct: number | null;
  inflationRatePct: number | null;
  primaryFiscalBalancePctGdp: number | null;
  totalFxReservesBillionsUsd: number | null;
  totalExternalDebtBillionsUsd: number | null;
  bisPolicyRatePct: number | null;
  commodityConcentrationRatio: number | null;
  termsOfTradeVulnerability: string;
}

export interface LiveSovereignBundle {
  country: string;
  countryName: string;
  timestamp: string;
  reconciliation: LiveReconciliationMetrics;
  feeds: {
    imf: LiveImfFeed | null;
    worldBank: LiveWorldBankFeed | null;
    bis: LiveBisFeed | null;
    unComtrade: LiveUnComtradeFeed | null;
  };
}

export interface LiveFredFeed {
  source: string;
  database: string;
  status: 'online' | 'degraded' | 'offline';
  fetchedAt: string;
  cached?: boolean;
  muniBondYieldAaa10Y: number; // e.g. 3.45%
  muniBondYield20BondGo: number; // e.g. 3.82%
  usTreasuryYield10Y: number; // e.g. 4.25%
  muniToTreasuryRatioPct: number; // e.g. 81.2%
  stateLocalTaxReceiptsBillions: number; // e.g. $2,280B
  stateLocalEmploymentThousands: number; // e.g. 20,240K
  regionalCpiYoY: number; // e.g. 3.2%
  series: Record<string, { id: string; name: string; latestValue: number; unit: string; date: string }>;
}

export interface LiveFrbFeed {
  source: string;
  database: string;
  status: 'online' | 'degraded' | 'offline';
  fetchedAt: string;
  cached?: boolean;
  effr: number; // Effective Federal Funds Rate %
  sofr: number; // Secured Overnight Financing Rate %
  z1StateLocalDebtOutstandingBillions: number; // Flow of Funds Table L.212
  z1HouseholdMuniHoldingSharePct: number; // % held directly by households & mutual funds
  bankCreditToMuniSectorBillions: number; // Commercial bank loans/leases to state/local govts
  municipalLiquidityFacilityEligibility: boolean;
  mlfSpreadBps: number; // Fed MLF spread over OIS
  description: string;
}

export interface LiveMsrbFeed {
  source: string;
  database: string;
  status: 'online' | 'degraded' | 'offline';
  fetchedAt: string;
  cached?: boolean;
  cusip6: string;
  issuerName: string;
  activeCusipsCount: number;
  averageDailyTradeVolumeMillions: number;
  recentTradesCount: number;
  mmdCurveSpreadBps: number;
  continuingDisclosuresStatus: 'Current' | 'Notice Filed' | 'Delayed';
  latestContinuingDisclosureDate: string;
  materialEventsList: Array<{ date: string; type: string; description: string; rule15c212Category: string }>;
  topBondIssues: Array<{
    cusip: string;
    series: string;
    coupon: number;
    yieldToMaturity: number;
    maturityDate: string;
    parMillions: number;
    rating: string;
    isTaxExempt: boolean;
    useOfProceeds: string;
  }>;
}

export interface LiveSecFeed {
  source: string;
  database: string;
  status: 'online' | 'degraded' | 'offline';
  fetchedAt: string;
  cached?: boolean;
  edgarCik: string;
  rule15c212Compliance: 'Compliant' | 'Substantial Compliance' | 'Notice of Non-Compliance';
  auditedAcfrSubmissionLatencyDays: number; // Benchmark: <180 days after fiscal year end
  timelinessStatus: 'Timely (<180d)' | 'Acceptable (180-210d)' | 'Late (>210d)' | 'Severely Delinquent (>365d)';
  formMaRegisteredAdvisorsCount: number;
  secEnforcementActionsFlag: boolean;
  activeAuditor: string;
  auditOpinionType: 'Unmodified (Clean)' | 'Qualified' | 'Adverse' | 'Disclaimer';
  lastAuditFiscalYear: number;
  notes: string;
}

export interface LiveUsMuniBundle {
  muniId: string;
  muniName: string;
  state: string;
  cusip6: string;
  tier: 'municipal' | 'subnational';
  timestamp: string;
  reconciliation: {
    muniToTreasuryRatio: number;
    creditSpreadOverMmdBps: number;
    acfrFilingLatencyDays: number;
    pensionFundedRatioPct: number;
    ownSourceRevenueSharePct: number;
    taxBaseGrowthPct: number;
    liquidityDaysOfCash: number;
  };
  feeds: {
    fred: LiveFredFeed;
    frb: LiveFrbFeed;
    msrb: LiveMsrbFeed;
    sec: LiveSecFeed;
  };
}

export interface UsMuniPreset {
  id: string;
  name: string;
  state: string;
  tier: 'municipal' | 'subnational';
  cusip6: string;
  cik: string;
  defaultRating: string;
  budgetBillions: number;
  debtMillions: number;
  category: 'City GO' | 'County GO' | 'State GO' | 'Water/Sewer Revenue' | 'Transportation Authority' | 'Special District';
}
// PROPRIETARY RANDORI GEOPOLITICAL RISK VaR (G-VaR) & PRI TYPES
// ==============================================================================

export type GeopoliticalPeril =
  | 'sovereign_default'
  | 'subnational_default'
  | 'expropriation'
  | 'currency_inconvertibility'
  | 'political_violence'
  | 'sanctions';

export type PriSector =
  | 'mining_oil_gas'
  | 'power_water_telecoms'
  | 'transport_infrastructure'
  | 'banking_finance'
  | 'manufacturing_services_agri';

export type AssetLocationRisk =
  | 'no_events_nearby'
  | 'around_national_average'
  | 'three_times_average'
  | 'active_conflict_zone';

export type HmnRegimeState = 'calm' | 'stressed' | 'crisis';

export interface ScorecardPillarIndicator {
  id: string;
  name: string;
  weightInPillar: number; // e.g. 0.20
  rawObservedValue: number;
  interpolatedScore: number; // 0 to 100
  source: string;
  isFatalCandidate?: boolean;
  isLiveFeed?: boolean;
  liveFeedSource?: string;
  originalBaselineValue?: number;
}

export interface ScorecardPillarResult {
  id: string;
  name: string;
  standardWeight: number; // e.g. 0.25
  sicsWeight: number; // e.g. 0.224 for Small Island & Coastal States
  activeWeight: number;
  weightedAverage: number;
  maxIndicatorScore: number;
  aggregatedScore: number; // 0.7 * weightedAverage + 0.3 * maxIndicatorScore
  triggerAddOns: number;
  analystAdjustment: number;
  finalScore: number; // min(100, max(0, aggregatedScore + triggers + adjustment))
  fatalWeakness?: string;
  indicators: ScorecardPillarIndicator[];
}

export interface RandoriCountryScorecard {
  countryCode: string;
  countryName: string;
  isSmallIslandCoastalState: boolean;
  pillars: {
    fiscalDebt: ScorecardPillarResult;
    external: ScorecardPillarResult;
    institutionsGovernance: ScorecardPillarResult;
    politicalPolicy: ScorecardPillarResult;
    macroFinancial: ScorecardPillarResult;
    securitySocial: ScorecardPillarResult;
    climateDisaster: ScorecardPillarResult;
  };
  compositeScore: number; // 0 to 100
  randoriGrade: number; // 1 to 10 (MIN(10, INT(score / 10) + 1))
  activeOverrideFloor?: number;
  overrideReason?: string;
}

export interface GVarLossDistribution {
  numSimulations: number;
  timeHorizonMonths: number; // 12 months
  expectedLossPct: number;
  expectedLossUsdMillions: number;
  var95Pct: number;
  var95UsdMillions: number;
  var99Pct: number;
  var99UsdMillions: number;
  expectedShortfall99Pct: number;
  expectedShortfall99UsdMillions: number;
  tailLossExceedance: Array<{ percentile: number; lossPct: number; lossMillions: number }>;
}

export interface PriPolicyQuote {
  peril: GeopoliticalPeril;
  policyLimitUsdMillions: number;
  deductibleUsdMillions: number;
  tenorYears: number;
  sector: PriSector;
  sectorMultiplier: number;
  location: AssetLocationRisk;
  locationMultiplier: number;
  baseLossProbability12M: number;
  postBayesianProbability: number;
  expectedLossMillions: number;
  tailRiskCapitalChargeMillions: number;
  technicalRateOnLinePct: number; // Annual Rate on Line (ROL)
  annualPremiumUsd: number;
  underwritingRecommendation: 'Accept' | 'Accept with Conditions' | 'Refer to Committee' | 'Decline';
}

export interface RandoriGVarAnalysis {
  countryScorecard: RandoriCountryScorecard;
  baseProbabilityHazard12M: number;
  bayesianUpdatedProbability12M: number;
  regimeState: HmnRegimeState;
  regimeJumpProbability: number;
  lossDistribution: GVarLossDistribution;
  perilProbabilities: Record<GeopoliticalPeril, number>;
  activePriQuote: PriPolicyQuote;
}
