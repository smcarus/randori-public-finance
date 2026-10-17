import { BondTranche, RefundingAnalysisResult } from '../types/finance';

/**
 * Institutional Public Finance Bond Refunding & Defeasance Escrow Optimizer
 * 
 * Rules:
 * - Minimum 3.0% Net Present Value (NPV) Savings Threshold rule of thumb in US Public Finance.
 * - Current Refunding: Refunding issue settles within 90 days of the call date (tax-exempt eligible).
 * - Advance Refunding: Refunding issue settles >90 days before call date (since TCJA 2017, must be issued taxable, or as crossover structure).
 * - Negative Arbitrage: Escrow yield restriction where reinvestment rate < refunding bond rate.
 */

export interface EscrowCashFlowMatchItem {
  periodDate: string;
  refundedDebtService: number; // Principal + coupon due ($)
  escrowMaturityReceipt: number; // Treasury zero/SLGS maturing ($)
  escrowCouponReceipt: number;
  netVariance: number;
  treasurySecurityType: 'SLGS Certificate' | 'SLGS Note' | 'Treasury Strip';
}

export function evaluateBondRefunding(
  bond: BondTranche,
  marketRefundingYieldPct: number,
  issuanceCostsPct: number = 0.85
): RefundingAnalysisResult {
  const par = bond.parAmount;
  const currentCoupon = bond.coupon / 100;
  const refundingYield = marketRefundingYieldPct / 100;
  
  // Calculate remaining years to maturity / call
  const maturityYear = new Date(bond.maturityDate).getFullYear();
  const currentYear = new Date().getFullYear();
  const remainingYears = Math.max(1, maturityYear - currentYear);
  
  // Call date analysis
  let yearsToCall = 0;
  let isAdvanceRefunding = false;
  if (bond.callDate) {
    const callYear = new Date(bond.callDate).getFullYear();
    yearsToCall = Math.max(0, callYear - currentYear);
    isAdvanceRefunding = yearsToCall > 0.25; // > 90 days
  }

  // Refunding type classification
  const refundingType = !bond.isCallable
    ? 'Crossover'
    : isAdvanceRefunding
    ? 'Taxable Advance Refunding'
    : 'Current Refunding';

  // If taxable advance refunding, bump the refunding yield by 65-100 bps
  const effectiveRefundingYield = isAdvanceRefunding ? refundingYield + 0.0075 : refundingYield;

  // Annual old coupon payment
  const oldAnnualCoupon = par * currentCoupon;
  // Annual new coupon payment
  const newAnnualCoupon = par * effectiveRefundingYield;
  const annualCashSavings = oldAnnualCoupon - newAnnualCoupon;

  // Total gross savings over remaining horizon
  const grossSavings = Math.max(0, annualCashSavings * remainingYears);

  // Present Value of annuity savings discounted at the refunding yield:
  // PV = C * (1 - (1 + y)^-n) / y
  let pvSavings = 0;
  if (effectiveRefundingYield > 0) {
    const annuityFactor = (1 - Math.pow(1 + effectiveRefundingYield, -remainingYears)) / effectiveRefundingYield;
    pvSavings = annualCashSavings * annuityFactor;
  } else {
    pvSavings = annualCashSavings * remainingYears;
  }

  // Subtract costs of issuance (legal, underwriting, rating agency, escrow agent)
  const issuanceCosts = par * (issuanceCostsPct / 100);
  const netPresentValueSavings = Math.max(0, pvSavings - issuanceCosts);

  // NPV Savings Percentage = (NPV Savings / Refunded Par Amount) * 100
  const npvSavingsPercent = (netPresentValueSavings / par) * 100;

  // Negative Arbitrage estimate for advance refunding escrows
  // If escrow yield is capped below refunding bond yield
  const negativeArbitrageLoss = isAdvanceRefunding
    ? par * 0.012 * Math.min(5, yearsToCall)
    : 0;

  const adjustedPresentValue = Math.max(0, netPresentValueSavings - negativeArbitrageLoss);
  const adjustedNpvPercent = (adjustedPresentValue / par) * 100;

  // Institutional 3.0% threshold
  const meetsThreshold = adjustedNpvPercent >= 3.0;

  // Efficiency ratio: PV savings / (PV savings + negative arbitrage)
  const efficiencyRatio = adjustedPresentValue + negativeArbitrageLoss > 0
    ? (adjustedPresentValue / (adjustedPresentValue + negativeArbitrageLoss)) * 100
    : 100;

  return {
    candidateBond: bond,
    currentYield: bond.coupon,
    refundingYield: Number((effectiveRefundingYield * 100).toFixed(2)),
    grossSavings: Number(grossSavings.toFixed(2)),
    presentValueSavings: Number(adjustedPresentValue.toFixed(2)),
    npvSavingsPercent: Number(adjustedNpvPercent.toFixed(2)),
    meetsThreshold,
    negativeArbitrageLoss: Number(negativeArbitrageLoss.toFixed(2)),
    efficiencyRatio: Number(efficiencyRatio.toFixed(1)),
    refundingType,
  };
}

/**
 * Generate synthetic linear programming cash flow matching schedule
 * for a Defeasance Escrow using SLGS (State & Local Government Series)
 */
export function generateDefeasanceEscrowSchedule(
  refundedParMillions: number,
  couponPct: number,
  yearsToCall: number
): EscrowCashFlowMatchItem[] {
  const schedule: EscrowCashFlowMatchItem[] = [];
  const semiAnnualCoupon = (refundedParMillions * (couponPct / 100)) / 2;
  const numPeriods = Math.max(2, Math.round(yearsToCall * 2));
  const currentYear = new Date().getFullYear();

  for (let i = 1; i <= numPeriods; i++) {
    const isCallMaturity = i === numPeriods;
    const debtServiceDue = isCallMaturity ? refundedParMillions + semiAnnualCoupon : semiAnnualCoupon;
    const yearOffset = Math.floor((i - 1) / 2);
    const month = (i % 2 === 1) ? '06-01' : '12-01';
    const periodDate = `${currentYear + yearOffset}-${month}`;

    const securityType: 'SLGS Certificate' | 'SLGS Note' | 'Treasury Strip' =
      i <= 2 ? 'SLGS Certificate' : isCallMaturity ? 'Treasury Strip' : 'SLGS Note';

    schedule.push({
      periodDate,
      refundedDebtService: Number(debtServiceDue.toFixed(2)),
      escrowMaturityReceipt: Number(debtServiceDue.toFixed(2)),
      escrowCouponReceipt: 0,
      netVariance: 0.00, // Exact cash flow matched
      treasurySecurityType: securityType,
    });
  }

  return schedule;
}
