import { PublicFinanceEntity, StressScenario } from '../types/finance';

/**
 * Macroeconomic Modeling, Structural VAR (SVAR) Elasticities,
 * Contingent Liabilities (PPP IFRAM & SOE Bailout), and Demographic Decay
 */

export interface MacroStressImpact {
  projectedRevenueDropMillions: number;
  projectedRevenueDropPercent: number;
  projectedMedicaidSurgeMillions: number;
  pppTotalTriggeredPayoutMillions: number;
  soeExpectedBailoutCallMillions: number;
  totalFiscalShockMillions: number;
  shockedDscr: number;
  shockedLiquidityDays: number;
  effectiveTaxElasticity: number;
}

export interface DemographicDecayPoint {
  year: number;
  dependencyRatio: number; // % (Retirees / Working Population)
  taxBaseIndex: number; // 100 base
  pensionDrawIndex: number; // 100 base
  structuralDeficitGapMillions: number;
}

/**
 * Calculate macro stress impacts across the active entity
 */
export function calculateMacroStressImpact(
  entity: PublicFinanceEntity,
  scenario: StressScenario
): MacroStressImpact {
  const budgetMillions = entity.gdpOrBudgetBillions * 1000;
  
  // 1. Tax Revenue Drop via Tax Elasticity: E = (% dTax) / (% dGDP)
  // Revenue Drop % = E * GDP Shock %
  const gdpShockPct = Math.abs(scenario.gdpGrowthShockPct);
  const effectiveElasticity = entity.taxElasticityCoefficient;
  const taxDropPct = gdpShockPct * effectiveElasticity;
  
  // If property value decline applies (for munis)
  let propertyTaxLoss = 0;
  if (entity.tier === 'municipal' && entity.municipalMetrics) {
    const avDropPct = Math.abs(scenario.propertyValueDeclinePct);
    // Sensitivity per 5% drop
    propertyTaxLoss = (avDropPct / 5) * entity.municipalMetrics.millRateSensitivityRevenueDropPer5PctAV;
  }

  const baseTaxRevenue = budgetMillions * (entity.municipalMetrics?.ownSourceRevenueRatio ?? 0.65);
  const incomeSalesTaxLoss = baseTaxRevenue * (taxDropPct / 100);
  const projectedRevenueDropMillions = incomeSalesTaxLoss + propertyTaxLoss;
  const projectedRevenueDropPercent = budgetMillions > 0 ? (projectedRevenueDropMillions / budgetMillions) * 100 : 0;

  // 2. Medicaid / Social Safety Net Counter-Cyclical Drag (Subnationals)
  let projectedMedicaidSurgeMillions = 0;
  if (entity.tier === 'subnational' && entity.subnationalMetrics) {
    const baseMedicaidBudget = budgetMillions * entity.subnationalMetrics.medicaidExpenditureShare;
    // Surge is amplified during recession
    const surgeFraction = entity.subnationalMetrics.medicaidCounterCyclicalSurgeRate * (gdpShockPct / 2.0);
    // Net state share after federal match (1 - FMAP)
    const stateShare = 1 - entity.subnationalMetrics.fmapFederalShare;
    projectedMedicaidSurgeMillions = baseMedicaidBudget * surgeFraction * stateShare;
  }

  // 3. PPP IFRAM Contingent Liability Triggers (MRGs)
  let pppTotalTriggeredPayoutMillions = 0;
  const trafficShockFactor = 1 - (scenario.pppTrafficDeclinePct / 100);

  for (const ppp of entity.pppConcessions) {
    const shockedRevenue = ppp.currentProjectedRevenue * trafficShockFactor;
    if (shockedRevenue < ppp.mrgTriggerFloor) {
      const shortfall = ppp.mrgTriggerFloor - shockedRevenue;
      const payout = Math.min(ppp.contingentLiabilityExposure, shortfall);
      pppTotalTriggeredPayoutMillions += payout;
    }
  }

  // 4. SOE Bailout Expected Call
  let soeExpectedBailoutCallMillions = 0;
  const soeMultiplier = scenario.soeDistressProbabilityMultiplier;

  for (const soe of entity.stateOwnedEnterprises) {
    // If explicit guarantee or high distress probability
    const adjustedProb = Math.min(0.99, soe.bailoutProbability * soeMultiplier);
    soeExpectedBailoutCallMillions += soe.expectedShortfall95 * adjustedProb;
  }

  // Total fiscal shock
  const totalFiscalShockMillions =
    projectedRevenueDropMillions +
    projectedMedicaidSurgeMillions +
    pppTotalTriggeredPayoutMillions +
    soeExpectedBailoutCallMillions;

  // Shocked DSCR
  const currentDscr = entity.municipalMetrics?.dscrCoverage ?? 1.5;
  const shockedDscr = Math.max(0.65, currentDscr * (1 - (totalFiscalShockMillions / (budgetMillions * 0.4))));

  // Shocked Liquidity Days
  const currentDays = entity.municipalMetrics?.liquidityDaysOfCash ?? 60;
  const shockedLiquidityDays = Math.max(12, currentDays * (1 - (totalFiscalShockMillions / budgetMillions)));

  return {
    projectedRevenueDropMillions: Number(projectedRevenueDropMillions.toFixed(1)),
    projectedRevenueDropPercent: Number(projectedRevenueDropPercent.toFixed(2)),
    projectedMedicaidSurgeMillions: Number(projectedMedicaidSurgeMillions.toFixed(1)),
    pppTotalTriggeredPayoutMillions: Number(pppTotalTriggeredPayoutMillions.toFixed(1)),
    soeExpectedBailoutCallMillions: Number(soeExpectedBailoutCallMillions.toFixed(1)),
    totalFiscalShockMillions: Number(totalFiscalShockMillions.toFixed(1)),
    shockedDscr: Number(shockedDscr.toFixed(2)),
    shockedLiquidityDays: Math.round(shockedLiquidityDays),
    effectiveTaxElasticity: effectiveElasticity,
  };
}

/**
 * Generates 20-Year Actuarial & Demographic Decay Curve
 */
export function generateDemographicDecayTrajectory(
  entity: PublicFinanceEntity
): DemographicDecayPoint[] {
  const points: DemographicDecayPoint[] = [];
  const currentYear = new Date().getFullYear();
  const baseBudget = entity.gdpOrBudgetBillions * 1000;

  // Initial dependency ratio
  let initialDependencyRatio = 28.5; // 28.5 retirees per 100 workers
  if (entity.pensionOpeb && entity.pensionOpeb.activeEmployees > 0) {
    initialDependencyRatio = (entity.pensionOpeb.beneficiaries / entity.pensionOpeb.activeEmployees) * 100;
  }

  for (let t = 0; t <= 20; t += 2) {
    // Demographic aging rate (~1.2% increase in dependency ratio every 2 years)
    const dependencyRatio = initialDependencyRatio + (t * 1.35);
    
    // Tax base contraction due to shrinking working-age labor force
    const taxBaseIndex = Math.max(70, 100 - (t * 0.95));

    // Escalating pension & healthcare draw index
    const pensionDrawIndex = 100 + (t * 2.8);

    // Structural deficit gap ($ millions)
    const revenueShift = baseBudget * ((100 - taxBaseIndex) / 100) * 0.35;
    const outlayShift = (entity.pensionOpeb?.actuariallyDeterminedContribution ?? 800) * ((pensionDrawIndex - 100) / 100);
    const structuralDeficitGapMillions = revenueShift + outlayShift;

    points.push({
      year: currentYear + t,
      dependencyRatio: Number(dependencyRatio.toFixed(1)),
      taxBaseIndex: Number(taxBaseIndex.toFixed(1)),
      pensionDrawIndex: Number(pensionDrawIndex.toFixed(1)),
      structuralDeficitGapMillions: Math.round(structuralDeficitGapMillions),
    });
  }

  return points;
}
