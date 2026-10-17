import { DsaTrajectoryPoint, PublicFinanceEntity, StressScenario } from '../types/finance';

/**
 * IMF/World Bank Debt Sustainability Analysis (DSA) Engine
 * 
 * Debt Dynamics Equation:
 *   Delta d_t = ((r_t - g_t) / (1 + g_t)) * d_{t-1} - p_t
 * 
 * Where:
 *   d_t = Debt-to-GDP (or Debt-to-Revenue for Subnational/Muni) ratio at time t
 *   r_t = Real effective interest rate on public debt
 *   g_t = Real GDP / Economic growth rate
 *   p_t = Primary balance (as % of GDP or Revenue)
 * 
 * Debt-Stabilizing Primary Balance:
 *   p* = ((r - g) / (1 + g)) * d
 */

export interface DsaSimulationParams {
  entity: PublicFinanceEntity;
  scenario: StressScenario;
  projectionYears?: number;
  numSimulations?: number;
  initialDebtRatio?: number; // %
  baselineRealInterestRate?: number; // %
  baselineGrowthRate?: number; // %
  baselinePrimaryBalance?: number; // %
}

export interface DsaSimulationResult {
  trajectory: DsaTrajectoryPoint[];
  debtStabilizingPrimaryBalance: number;
  initialDebtRatio: number;
  terminalMedianDebtRatio: number;
  probabilityOfExceeding90Pct: number;
  riskTrajectoryClassification: 'Sustainable (Debt Declining)' | 'Borderline / Stabilizing' | 'Unsustainable (Explosive)';
  effectiveSnowballEffect: number; // (r - g) / (1 + g)
}

/**
 * Deterministic single-step debt dynamics
 */
export function calculateNextPeriodDebtRatio(
  previousDebtRatio: number,
  realInterestRatePct: number,
  realGrowthRatePct: number,
  primaryBalancePct: number
): number {
  const r = realInterestRatePct / 100;
  const g = realGrowthRatePct / 100;
  const p = primaryBalancePct / 100;

  // Snowball factor: (r - g) / (1 + g)
  const snowballFactor = (r - g) / (1 + g);
  const deltaDebt = (snowballFactor * (previousDebtRatio / 100)) - p;
  
  return Math.max(0, previousDebtRatio + (deltaDebt * 100));
}

/**
 * Calculates debt-stabilizing primary balance (% of GDP / Budget)
 */
export function calculateDebtStabilizingPrimaryBalance(
  debtRatioPct: number,
  realInterestRatePct: number,
  realGrowthRatePct: number
): number {
  const r = realInterestRatePct / 100;
  const g = realGrowthRatePct / 100;
  const d = debtRatioPct / 100;

  const requiredP = ((r - g) / (1 + g)) * d;
  return requiredP * 100;
}

/**
 * Run full stochastic Monte Carlo DSA Simulation
 */
export function runDsaMonteCarlo(params: DsaSimulationParams): DsaSimulationResult {
  const { entity, scenario, projectionYears = 10, numSimulations = 1000 } = params;

  // Derive initial debt ratio based on tier
  let initialDebtRatio = 60.0;
  let basePrimaryBalance = 0.0;
  let baseRealRate = 2.5;
  let baseGrowthRate = 2.0;

  if (entity.tier === 'sovereign' && entity.sovereignMetrics) {
    initialDebtRatio = entity.sovereignMetrics.publicDebtToGdp;
    basePrimaryBalance = entity.sovereignMetrics.primaryBalancePctGdp;
    baseRealRate = 3.2;
    baseGrowthRate = 1.8;
  } else if (entity.tier === 'subnational') {
    // Direct debt as % of budget
    initialDebtRatio = (entity.totalDirectDebtMillions / (entity.gdpOrBudgetBillions * 1000)) * 100;
    basePrimaryBalance = 0.5;
    baseRealRate = 2.2;
    baseGrowthRate = 2.1;
  } else {
    // Municipal: direct debt / annual budget %
    initialDebtRatio = (entity.totalDirectDebtMillions / (entity.gdpOrBudgetBillions * 1000)) * 100;
    basePrimaryBalance = 1.0;
    baseRealRate = 1.9;
    baseGrowthRate = 2.4;
  }

  // Apply scenario shocks
  const shockedInterestRate = baseRealRate + (scenario.interestRateDeltaBps / 100);
  const shockedGrowthRate = baseGrowthRate + scenario.gdpGrowthShockPct;
  const shockedPrimaryBalance = basePrimaryBalance - (Math.abs(scenario.gdpGrowthShockPct) * 0.4);

  const debtStabilizingPrimaryBalance = calculateDebtStabilizingPrimaryBalance(
    initialDebtRatio,
    shockedInterestRate,
    shockedGrowthRate
  );

  const effectiveSnowballEffect = ((shockedInterestRate / 100) - (shockedGrowthRate / 100)) / (1 + (shockedGrowthRate / 100));

  // Deterministic baseline trajectory
  const baselineTraj: number[] = [initialDebtRatio];
  for (let t = 1; t <= projectionYears; t++) {
    const nextDebt = calculateNextPeriodDebtRatio(
      baselineTraj[t - 1],
      shockedInterestRate,
      shockedGrowthRate,
      shockedPrimaryBalance
    );
    baselineTraj.push(nextDebt);
  }

  // Stochastic Monte Carlo paths
  // Using pseudo-random generator with box-muller for Gaussian distribution
  const simMatrix: number[][] = []; // [simIndex][yearIndex]

  const sigmaR = 1.25; // std dev for real interest rate
  const sigmaG = 1.75; // std dev for real growth
  const sigmaP = 1.10; // std dev for primary balance shock

  for (let s = 0; s < numSimulations; s++) {
    const path: number[] = [initialDebtRatio];
    let currentD = initialDebtRatio;

    for (let t = 1; t <= projectionYears; t++) {
      // Shocks
      const u1 = Math.max(1e-9, Math.random());
      const u2 = Math.random();
      const zR = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);

      const u3 = Math.max(1e-9, Math.random());
      const u4 = Math.random();
      const zG = Math.sqrt(-2.0 * Math.log(u3)) * Math.cos(2.0 * Math.PI * u4);

      const u5 = Math.max(1e-9, Math.random());
      const u6 = Math.random();
      const zP = Math.sqrt(-2.0 * Math.log(u5)) * Math.cos(2.0 * Math.PI * u6);

      // Correlation: growth slowdown often coincides with rate hikes (stagflation) or primary balance deterioration
      const simRate = shockedInterestRate + (zR * sigmaR);
      const simGrowth = shockedGrowthRate + (zG * sigmaG);
      const simPB = shockedPrimaryBalance + (zP * sigmaP) + (zG * 0.35); // automatic fiscal stabilizers

      currentD = calculateNextPeriodDebtRatio(currentD, simRate, simGrowth, simPB);
      path.push(currentD);
    }
    simMatrix.push(path);
  }

  // Extract percentiles for each year t
  const trajectory: DsaTrajectoryPoint[] = [];
  const currentYear = new Date().getFullYear();

  for (let t = 0; t <= projectionYears; t++) {
    const valuesAtT = simMatrix.map((p) => p[t]).sort((a, b) => a - b);
    
    const p10 = valuesAtT[Math.floor(numSimulations * 0.10)];
    const p25 = valuesAtT[Math.floor(numSimulations * 0.25)];
    const p50 = valuesAtT[Math.floor(numSimulations * 0.50)];
    const p75 = valuesAtT[Math.floor(numSimulations * 0.75)];
    const p90 = valuesAtT[Math.floor(numSimulations * 0.90)];

    const yearLabel = currentYear + t;
    trajectory.push({
      year: yearLabel,
      baseline: Number(baselineTraj[t].toFixed(1)),
      p10: Number(p10.toFixed(1)),
      p25: Number(p25.toFixed(1)),
      p50: Number(p50.toFixed(1)),
      p75: Number(p75.toFixed(1)),
      p90: Number(p90.toFixed(1)),
      debtStabilizingPrimaryBalance: Number(debtStabilizingPrimaryBalance.toFixed(2)),
    });
  }

  const terminalValues = simMatrix.map((p) => p[projectionYears]);
  const terminalMedianDebtRatio = trajectory[projectionYears].p50;
  const exceedCount = terminalValues.filter((v) => v > 90.0).length;
  const probabilityOfExceeding90Pct = (exceedCount / numSimulations) * 100;

  let riskTrajectoryClassification: 'Sustainable (Debt Declining)' | 'Borderline / Stabilizing' | 'Unsustainable (Explosive)';
  if (terminalMedianDebtRatio < initialDebtRatio * 0.95) {
    riskTrajectoryClassification = 'Sustainable (Debt Declining)';
  } else if (terminalMedianDebtRatio <= initialDebtRatio * 1.15) {
    riskTrajectoryClassification = 'Borderline / Stabilizing';
  } else {
    riskTrajectoryClassification = 'Unsustainable (Explosive)';
  }

  return {
    trajectory,
    debtStabilizingPrimaryBalance,
    initialDebtRatio,
    terminalMedianDebtRatio,
    probabilityOfExceeding90Pct,
    riskTrajectoryClassification,
    effectiveSnowballEffect,
  };
}
