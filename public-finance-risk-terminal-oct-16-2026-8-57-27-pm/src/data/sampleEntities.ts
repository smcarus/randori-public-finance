import { PublicFinanceEntity, StressScenario } from '../types/finance';

export const SAMPLE_ENTITIES: PublicFinanceEntity[] = [
  // MUNICIPAL 1: City of Chicago
  {
    id: 'chicago-muni',
    name: 'City of Chicago',
    tier: 'municipal',
    jurisdiction: 'Illinois, United States',
    creditRating: 'BBB+',
    ratingOutlook: 'Stable',
    currency: 'USD',
    gdpOrBudgetBillions: 16.4, // annual budget in $B
    totalDirectDebtMillions: 11450, // total direct debt $M
    weightedAverageMaturityYears: 13.8,
    modifiedDurationYears: 7.9,
    durationGapYears: 2.4,
    marketAccessStressScore: 54,
    taxElasticityCoefficient: 1.35,
    fiscalMultiplierSpending: 1.12,
    fiscalMultiplierTax: -0.88,

    municipalMetrics: {
      ownSourceRevenueRatio: 0.64, // 64% from local property, sales, utility taxes
      melloRoosOverlappingDebtRatio: 0.082, // Overlapping special tax/CFD debt as % of assessed value
      specialAssessmentDistrictsCount: 142,
      totalAssessedValue: 104.2, // $104.2B assessed value
      millRate: 21.4, // $21.40 per $1,000 assessed value
      millRateSensitivityRevenueDropPer5PctAV: 111.5, // $111.5M revenue loss per 5% drop in AV
      dscrCoverage: 1.32,
      infrastructureBacklog: 4200, // $4.2B deferred maintenance
      infrastructureBacklogPctBudget: 0.256, // 25.6% of budget
      liquidityDaysOfCash: 48, // 48 days
    },

    pensionOpeb: {
      planName: 'Chicago Municipal & Laborers Annuity Fund',
      totalPensionLiability: 36800,
      actuarialValueOfAssets: 8640,
      netPensionLiability: 28160,
      fundedRatio: 23.5, // 23.5% funded
      assumedDiscountRate: 7.00,
      nplAtPlus100Bps: 23900,
      nplAtMinus100Bps: 33400,
      actuariallyDeterminedContribution: 1680,
      actualContribution: 1420,
      opebFundedRatio: 12.4,
      opebNetLiability: 1850,
      activeEmployees: 31200,
      beneficiaries: 29400,
    },

    bonds: [
      {
        id: 'chi-go-2018a',
        name: 'General Obligation Bonds, Ser. 2018A',
        type: 'GO',
        parAmount: 1850,
        coupon: 5.25,
        yieldToMaturity: 4.85,
        maturityDate: '2038-01-01',
        callDate: '2028-01-01',
        callPrice: 100.0,
        rating: 'BBB+',
        isCallable: true,
        spreadOverBenchmarkBps: 145,
        isTaxExempt: true,
      },
      {
        id: 'chi-rev-water-2020',
        name: 'Water Revenue Senior Lien, Ser. 2020',
        type: 'Revenue',
        parAmount: 1420,
        coupon: 5.00,
        yieldToMaturity: 4.10,
        maturityDate: '2042-11-01',
        callDate: '2030-11-01',
        callPrice: 100.0,
        rating: 'A-',
        isCallable: true,
        spreadOverBenchmarkBps: 95,
        isTaxExempt: true,
      },
      {
        id: 'chi-moral-2019',
        name: 'Infrastructure Trust Moral Obligation Notes',
        type: 'MoralObligation',
        parAmount: 480,
        coupon: 5.60,
        yieldToMaturity: 5.35,
        maturityDate: '2034-06-01',
        callDate: '2026-12-01',
        callPrice: 100.0,
        rating: 'BBB-',
        isCallable: true,
        spreadOverBenchmarkBps: 195,
        isTaxExempt: true,
      },
      {
        id: 'chi-tif-2021',
        name: 'Loop Tax Increment Financing (TIF) Allocation Bonds',
        type: 'TIF',
        parAmount: 650,
        coupon: 4.65,
        yieldToMaturity: 4.45,
        maturityDate: '2031-12-01',
        callDate: '2027-12-01',
        callPrice: 100.0,
        rating: 'BBB',
        isCallable: true,
        spreadOverBenchmarkBps: 130,
        isTaxExempt: true,
      },
    ],

    vrdos: [
      {
        id: 'chi-vrdo-01',
        name: 'Multi-Modal GO VRDO Series 2003B',
        parAmount: 450,
        currentResetRate: 3.42,
        liquidityProvider: 'JPMorgan Chase Bank, N.A.',
        locExpirationDate: '2027-04-15',
        remarketingAgent: 'BofA Securities',
        daysToLocExpiry: 181,
        bankBondRate: 8.50,
        mode: 'Weekly',
      },
      {
        id: 'chi-vrdo-02',
        name: 'Wastewater System Variable Subordinated 2008A',
        parAmount: 280,
        currentResetRate: 3.55,
        liquidityProvider: 'Barclays Bank PLC',
        locExpirationDate: '2027-09-30',
        remarketingAgent: 'Citigroup Global Markets',
        daysToLocExpiry: 349,
        bankBondRate: 9.00,
        mode: 'Weekly',
      },
    ],

    pppConcessions: [
      {
        id: 'chi-ppp-parking',
        projectName: 'Chicago Downtown Parking Meter Concession',
        sector: 'Healthcare Facility',
        capitalExpenditure: 1150,
        concessionExpiryYear: 2083,
        concessionaireName: 'Chicago Parking Meters LLC',
        paymentStructure: 'Direct User Fee',
        mrgTriggerFloor: 125, // $M
        currentProjectedRevenue: 138,
        contingentLiabilityExposure: 42,
        status: 'Nominal',
      },
      {
        id: 'chi-ppp-skyway',
        projectName: 'Chicago Skyway Toll Bridge System',
        sector: 'Toll Highway',
        capitalExpenditure: 1830,
        concessionExpiryYear: 2104,
        concessionaireName: 'Skyway Concession Company LLC',
        paymentStructure: 'Shadow Toll',
        mrgTriggerFloor: 94,
        currentProjectedRevenue: 89, // BELOW floor!
        contingentLiabilityExposure: 18.5,
        status: 'Triggered',
      },
    ],

    stateOwnedEnterprises: [
      {
        id: 'soe-cta',
        name: 'Chicago Transit Authority (CTA)',
        sector: 'Public Transit',
        totalDebt: 3450,
        debtServiceCoverageRatio: 1.08,
        explicitGovernmentGuarantee: true,
        bailoutProbability: 0.65,
        expectedShortfall95: 380,
      },
      {
        id: 'soe-mpead',
        name: 'Metropolitan Pier and Exposition Authority (MPEA)',
        sector: 'Port Authority',
        totalDebt: 4120,
        debtServiceCoverageRatio: 1.15,
        explicitGovernmentGuarantee: true,
        bailoutProbability: 0.45,
        expectedShortfall95: 240,
      },
    ],

    marketSpreads: [
      { tenor: '1Y', benchmarkYield: 2.85, entityYield: 3.75, spreadBps: 90, cdsSpreadBps: 115, cdsBondBasisBps: 25 },
      { tenor: '3Y', benchmarkYield: 3.05, entityYield: 4.10, spreadBps: 105, cdsSpreadBps: 130, cdsBondBasisBps: 25 },
      { tenor: '5Y', benchmarkYield: 3.25, entityYield: 4.45, spreadBps: 120, cdsSpreadBps: 155, cdsBondBasisBps: 35 },
      { tenor: '10Y', benchmarkYield: 3.65, entityYield: 5.10, spreadBps: 145, cdsSpreadBps: 190, cdsBondBasisBps: 45 },
      { tenor: '20Y', benchmarkYield: 4.10, entityYield: 5.75, spreadBps: 165, cdsSpreadBps: 215, cdsBondBasisBps: 50 },
      { tenor: '30Y', benchmarkYield: 4.30, entityYield: 6.05, spreadBps: 175, cdsSpreadBps: 230, cdsBondBasisBps: 55 },
    ],

    maturityWall: {
      within12M: 850,
      year1to2: 1120,
      year2to3: 1340,
      year3to5: 2450,
      beyond5Y: 5690,
    },
  },

  // MUNICIPAL 2: Bay Area Transportation & District
  {
    id: 'sf-bay-transport',
    name: 'Bay Area Regional Transportation District',
    tier: 'municipal',
    jurisdiction: 'California, United States',
    creditRating: 'AA-',
    ratingOutlook: 'Negative',
    currency: 'USD',
    gdpOrBudgetBillions: 2.45,
    totalDirectDebtMillions: 3820,
    weightedAverageMaturityYears: 16.2,
    modifiedDurationYears: 8.5,
    durationGapYears: 3.1,
    marketAccessStressScore: 42,
    taxElasticityCoefficient: 1.60,
    fiscalMultiplierSpending: 1.25,
    fiscalMultiplierTax: -0.75,

    municipalMetrics: {
      ownSourceRevenueRatio: 0.48, // heavy farebox + sales tax reliance
      melloRoosOverlappingDebtRatio: 0.054,
      specialAssessmentDistrictsCount: 38,
      totalAssessedValue: 248.0,
      millRate: 6.2,
      millRateSensitivityRevenueDropPer5PctAV: 38.4,
      dscrCoverage: 1.22,
      infrastructureBacklog: 2900,
      infrastructureBacklogPctBudget: 1.18,
      liquidityDaysOfCash: 72,
    },

    pensionOpeb: {
      planName: 'CalPERS - Regional Transit Association',
      totalPensionLiability: 5400,
      actuarialValueOfAssets: 3850,
      netPensionLiability: 1550,
      fundedRatio: 71.3,
      assumedDiscountRate: 6.80,
      nplAtPlus100Bps: 1120,
      nplAtMinus100Bps: 2090,
      actuariallyDeterminedContribution: 195,
      actualContribution: 195,
      opebFundedRatio: 38.0,
      opebNetLiability: 420,
      activeEmployees: 4100,
      beneficiaries: 3600,
    },

    bonds: [
      {
        id: 'bart-sales-2019',
        name: 'Dedicated Sales Tax Revenue Bonds, Ser. 2019',
        type: 'Revenue',
        parAmount: 1200,
        coupon: 4.50,
        yieldToMaturity: 3.85,
        maturityDate: '2039-07-01',
        callDate: '2029-07-01',
        callPrice: 100.0,
        rating: 'AA',
        isCallable: true,
        spreadOverBenchmarkBps: 65,
        isTaxExempt: true,
      },
      {
        id: 'bart-go-measurer',
        name: 'General Obligation Earthquake Safety Bonds 2020',
        type: 'GO',
        parAmount: 1650,
        coupon: 4.25,
        yieldToMaturity: 3.70,
        maturityDate: '2045-08-01',
        callDate: '2030-08-01',
        callPrice: 100.0,
        rating: 'AA-',
        isCallable: true,
        spreadOverBenchmarkBps: 55,
        isTaxExempt: true,
      },
    ],

    vrdos: [
      {
        id: 'bart-vrdo-1',
        name: 'Sales Tax Subordinate VRDO 2012A',
        parAmount: 180,
        currentResetRate: 3.35,
        liquidityProvider: 'Wells Fargo Bank, N.A.',
        locExpirationDate: '2028-03-31',
        remarketingAgent: 'Morgan Stanley',
        daysToLocExpiry: 531,
        bankBondRate: 8.00,
        mode: 'Weekly',
      },
    ],

    pppConcessions: [
      {
        id: 'bart-ppp-connector',
        projectName: 'Airport Automated Rail Feeder Concession',
        sector: 'Transit Rail',
        capitalExpenditure: 480,
        concessionExpiryYear: 2038,
        concessionaireName: 'Doppelmayr Cable Car Bay Area',
        paymentStructure: 'Availability Payment',
        mrgTriggerFloor: 28,
        currentProjectedRevenue: 22.4, // At Risk
        contingentLiabilityExposure: 14.8,
        status: 'Triggered',
      },
    ],

    stateOwnedEnterprises: [
      {
        id: 'soe-ferry',
        name: 'Water Emergency Transportation Authority',
        sector: 'Public Transit',
        totalDebt: 320,
        debtServiceCoverageRatio: 1.18,
        explicitGovernmentGuarantee: false,
        bailoutProbability: 0.30,
        expectedShortfall95: 45,
      },
    ],

    marketSpreads: [
      { tenor: '1Y', benchmarkYield: 2.85, entityYield: 3.25, spreadBps: 40, cdsSpreadBps: 55, cdsBondBasisBps: 15 },
      { tenor: '3Y', benchmarkYield: 3.05, entityYield: 3.55, spreadBps: 50, cdsSpreadBps: 68, cdsBondBasisBps: 18 },
      { tenor: '5Y', benchmarkYield: 3.25, entityYield: 3.82, spreadBps: 57, cdsSpreadBps: 79, cdsBondBasisBps: 22 },
      { tenor: '10Y', benchmarkYield: 3.65, entityYield: 4.35, spreadBps: 70, cdsSpreadBps: 98, cdsBondBasisBps: 28 },
      { tenor: '20Y', benchmarkYield: 4.10, entityYield: 4.95, spreadBps: 85, cdsSpreadBps: 118, cdsBondBasisBps: 33 },
      { tenor: '30Y', benchmarkYield: 4.30, entityYield: 5.25, spreadBps: 95, cdsSpreadBps: 132, cdsBondBasisBps: 37 },
    ],

    maturityWall: {
      within12M: 195,
      year1to2: 260,
      year2to3: 310,
      year3to5: 890,
      beyond5Y: 2165,
    },
  },

  // SUBNATIONAL 1: State of Illinois
  {
    id: 'state-illinois',
    name: 'State of Illinois',
    tier: 'subnational',
    jurisdiction: 'United States',
    creditRating: 'A-',
    ratingOutlook: 'Positive',
    currency: 'USD',
    gdpOrBudgetBillions: 53.2, // annual state operating budget
    totalDirectDebtMillions: 36400,
    weightedAverageMaturityYears: 11.4,
    modifiedDurationYears: 6.8,
    durationGapYears: 1.9,
    marketAccessStressScore: 48,
    taxElasticityCoefficient: 1.28,
    fiscalMultiplierSpending: 1.05,
    fiscalMultiplierTax: -0.92,

    subnationalMetrics: {
      netPensionLiability: 142000, // $142B Net Pension Liability
      pensionFundedRatio: 44.2, // 44.2% funded across GARS, JRS, SERS, SURS, TRS
      pensionDiscountRate: 6.75,
      medicaidExpenditureShare: 0.285, // 28.5% of state general funds
      medicaidCounterCyclicalSurgeRate: 0.26, // +26% cost surge in recession
      fmapFederalShare: 0.505, // 50.5% federal match
      transferDependenceRatio: 0.312, // 31.2% federal grants share
      rainyDayFundReserveMonths: 0.85, // 0.85 months of reserve
    },

    pensionOpeb: {
      planName: 'Teachers Retirement System (TRS) & State Employees (SERS)',
      totalPensionLiability: 254000,
      actuarialValueOfAssets: 112000,
      netPensionLiability: 142000,
      fundedRatio: 44.2,
      assumedDiscountRate: 6.75,
      nplAtPlus100Bps: 118000,
      nplAtMinus100Bps: 172000,
      actuariallyDeterminedContribution: 10400,
      actualContribution: 9800,
      opebFundedRatio: 16.5,
      opebNetLiability: 48500,
      activeEmployees: 245000,
      beneficiaries: 228000,
    },

    bonds: [
      {
        id: 'il-go-2017d',
        name: 'State of Illinois General Obligation 2017D',
        type: 'GO',
        parAmount: 4500,
        coupon: 5.50,
        yieldToMaturity: 4.40,
        maturityDate: '2037-11-01',
        callDate: '2027-11-01',
        callPrice: 100.0,
        rating: 'A-',
        isCallable: true,
        spreadOverBenchmarkBps: 110,
        isTaxExempt: true,
      },
      {
        id: 'il-build-2021',
        name: 'Build Illinois Sales Tax Junior Lien Ser. 2021',
        type: 'Revenue',
        parAmount: 3200,
        coupon: 4.75,
        yieldToMaturity: 4.15,
        maturityDate: '2041-06-15',
        callDate: '2031-06-15',
        callPrice: 100.0,
        rating: 'A',
        isCallable: true,
        spreadOverBenchmarkBps: 85,
        isTaxExempt: true,
      },
      {
        id: 'il-pension-2003',
        name: 'Taxable Pension Funding Bonds Series 2003',
        type: 'GO',
        parAmount: 6800,
        coupon: 5.10,
        yieldToMaturity: 4.95,
        maturityDate: '2033-06-01',
        callDate: undefined,
        rating: 'A-',
        isCallable: false,
        spreadOverBenchmarkBps: 125,
        isTaxExempt: false,
      },
    ],

    vrdos: [
      {
        id: 'il-vrdo-2003b',
        name: 'General Obligation VRDO Series 2003B',
        parAmount: 600,
        currentResetRate: 3.48,
        liquidityProvider: 'PNC Bank, N.A.',
        locExpirationDate: '2027-06-25',
        remarketingAgent: 'Goldman Sachs & Co.',
        daysToLocExpiry: 252,
        bankBondRate: 8.75,
        mode: 'Weekly',
      },
    ],

    pppConcessions: [
      {
        id: 'il-ppp-central-illinois',
        projectName: 'I-55 Managed Lanes Public-Private Concession',
        sector: 'Toll Highway',
        capitalExpenditure: 1250,
        concessionExpiryYear: 2065,
        concessionaireName: 'Illinois Mobility Partners',
        paymentStructure: 'Availability Payment',
        mrgTriggerFloor: 68,
        currentProjectedRevenue: 74,
        contingentLiabilityExposure: 35,
        status: 'Nominal',
      },
    ],

    stateOwnedEnterprises: [
      {
        id: 'soe-tollway',
        name: 'Illinois State Toll Highway Authority',
        sector: 'Public Transit',
        totalDebt: 6850,
        debtServiceCoverageRatio: 2.15,
        explicitGovernmentGuarantee: false,
        bailoutProbability: 0.12,
        expectedShortfall95: 180,
      },
      {
        id: 'soe-ihda',
        name: 'Illinois Housing Development Authority',
        sector: 'Port Authority',
        totalDebt: 2400,
        debtServiceCoverageRatio: 1.35,
        explicitGovernmentGuarantee: true,
        bailoutProbability: 0.28,
        expectedShortfall95: 120,
      },
    ],

    marketSpreads: [
      { tenor: '1Y', benchmarkYield: 2.85, entityYield: 3.55, spreadBps: 70, cdsSpreadBps: 92, cdsBondBasisBps: 22 },
      { tenor: '3Y', benchmarkYield: 3.05, entityYield: 3.90, spreadBps: 85, cdsSpreadBps: 112, cdsBondBasisBps: 27 },
      { tenor: '5Y', benchmarkYield: 3.25, entityYield: 4.25, spreadBps: 100, cdsSpreadBps: 135, cdsBondBasisBps: 35 },
      { tenor: '10Y', benchmarkYield: 3.65, entityYield: 4.75, spreadBps: 110, cdsSpreadBps: 155, cdsBondBasisBps: 45 },
      { tenor: '20Y', benchmarkYield: 4.10, entityYield: 5.35, spreadBps: 125, cdsSpreadBps: 178, cdsBondBasisBps: 53 },
      { tenor: '30Y', benchmarkYield: 4.30, entityYield: 5.70, spreadBps: 140, cdsSpreadBps: 198, cdsBondBasisBps: 58 },
    ],

    maturityWall: {
      within12M: 2450,
      year1to2: 3100,
      year2to3: 3650,
      year3to5: 8200,
      beyond5Y: 19000,
    },
  },

  // SUBNATIONAL 2: State of California
  {
    id: 'state-california',
    name: 'State of California',
    tier: 'subnational',
    jurisdiction: 'United States',
    creditRating: 'AA-',
    ratingOutlook: 'Stable',
    currency: 'USD',
    gdpOrBudgetBillions: 297.0, // annual state general fund budget
    totalDirectDebtMillions: 78500,
    weightedAverageMaturityYears: 14.6,
    modifiedDurationYears: 8.2,
    durationGapYears: 2.7,
    marketAccessStressScore: 32,
    taxElasticityCoefficient: 1.85, // highly volatile progressive capital gains tax
    fiscalMultiplierSpending: 1.20,
    fiscalMultiplierTax: -0.90,

    subnationalMetrics: {
      netPensionLiability: 118000,
      pensionFundedRatio: 72.8,
      pensionDiscountRate: 6.90,
      medicaidExpenditureShare: 0.31, // Medi-Cal 31% of budget
      medicaidCounterCyclicalSurgeRate: 0.22,
      fmapFederalShare: 0.50,
      transferDependenceRatio: 0.29,
      rainyDayFundReserveMonths: 2.1, // BSA Rainy Day Fund reserves
    },

    pensionOpeb: {
      planName: 'CalPERS & CalSTRS Combined Systems',
      totalPensionLiability: 435000,
      actuarialValueOfAssets: 317000,
      netPensionLiability: 118000,
      fundedRatio: 72.8,
      assumedDiscountRate: 6.90,
      nplAtPlus100Bps: 88000,
      nplAtMinus100Bps: 154000,
      actuariallyDeterminedContribution: 16500,
      actualContribution: 16500,
      opebFundedRatio: 24.5,
      opebNetLiability: 65000,
      activeEmployees: 720000,
      beneficiaries: 685000,
    },

    bonds: [
      {
        id: 'ca-go-2020a',
        name: 'Various Purpose General Obligation Bonds 2020A',
        type: 'GO',
        parAmount: 8400,
        coupon: 4.00,
        yieldToMaturity: 3.55,
        maturityDate: '2040-03-01',
        callDate: '2030-03-01',
        callPrice: 100.0,
        rating: 'AA-',
        isCallable: true,
        spreadOverBenchmarkBps: 45,
        isTaxExempt: true,
      },
      {
        id: 'ca-water-rev',
        name: 'Central Valley Project Water Revenue Bonds 2021',
        type: 'Revenue',
        parAmount: 2600,
        coupon: 4.25,
        yieldToMaturity: 3.75,
        maturityDate: '2036-12-01',
        callDate: '2031-12-01',
        callPrice: 100.0,
        rating: 'AA',
        isCallable: true,
        spreadOverBenchmarkBps: 40,
        isTaxExempt: true,
      },
    ],

    vrdos: [
      {
        id: 'ca-vrdo-go',
        name: 'State General Obligation VRDO Series 2004B',
        parAmount: 750,
        currentResetRate: 3.25,
        liquidityProvider: 'Royal Bank of Canada',
        locExpirationDate: '2028-11-15',
        remarketingAgent: 'Morgan Stanley',
        daysToLocExpiry: 760,
        bankBondRate: 7.50,
        mode: 'Weekly',
      },
    ],

    pppConcessions: [
      {
        id: 'ca-ppp-presidio',
        projectName: 'Presidio Parkway Concession Phase II',
        sector: 'Toll Highway',
        capitalExpenditure: 850,
        concessionExpiryYear: 2045,
        concessionaireName: 'Golden Gate Bridge & Highway Joint Venture',
        paymentStructure: 'Availability Payment',
        mrgTriggerFloor: 44,
        currentProjectedRevenue: 46.5,
        contingentLiabilityExposure: 18,
        status: 'Nominal',
      },
      {
        id: 'ca-ppp-court',
        projectName: 'Long Beach Superior Court P3 Facility',
        sector: 'Healthcare Facility',
        capitalExpenditure: 490,
        concessionExpiryYear: 2048,
        concessionaireName: 'Meridiam Infrastructure LLC',
        paymentStructure: 'Availability Payment',
        mrgTriggerFloor: 38,
        currentProjectedRevenue: 38.2,
        contingentLiabilityExposure: 12.5,
        status: 'Nominal',
      },
    ],

    stateOwnedEnterprises: [
      {
        id: 'soe-hsr',
        name: 'California High-Speed Rail Authority',
        sector: 'Public Transit',
        totalDebt: 9800,
        debtServiceCoverageRatio: 0.85,
        explicitGovernmentGuarantee: true,
        bailoutProbability: 0.80,
        expectedShortfall95: 1400,
      },
    ],

    marketSpreads: [
      { tenor: '1Y', benchmarkYield: 2.85, entityYield: 3.10, spreadBps: 25, cdsSpreadBps: 38, cdsBondBasisBps: 13 },
      { tenor: '3Y', benchmarkYield: 3.05, entityYield: 3.38, spreadBps: 33, cdsSpreadBps: 48, cdsBondBasisBps: 15 },
      { tenor: '5Y', benchmarkYield: 3.25, entityYield: 3.65, spreadBps: 40, cdsSpreadBps: 58, cdsBondBasisBps: 18 },
      { tenor: '10Y', benchmarkYield: 3.65, entityYield: 4.12, spreadBps: 47, cdsSpreadBps: 69, cdsBondBasisBps: 22 },
      { tenor: '20Y', benchmarkYield: 4.10, entityYield: 4.70, spreadBps: 60, cdsSpreadBps: 87, cdsBondBasisBps: 27 },
      { tenor: '30Y', benchmarkYield: 4.30, entityYield: 4.98, spreadBps: 68, cdsSpreadBps: 98, cdsBondBasisBps: 30 },
    ],

    maturityWall: {
      within12M: 4200,
      year1to2: 5600,
      year2to3: 6800,
      year3to5: 16400,
      beyond5Y: 45500,
    },
  },

  // SOVEREIGN 1: Republic of South Africa
  {
    id: 'sovereign-south-africa',
    name: 'Republic of South Africa',
    tier: 'sovereign',
    jurisdiction: 'South Africa',
    creditRating: 'BB-',
    ratingOutlook: 'Stable',
    currency: 'ZAR',
    gdpOrBudgetBillions: 405.0, // GDP in $B
    totalDirectDebtMillions: 298000, // Total public debt in $M USD equiv
    weightedAverageMaturityYears: 12.1,
    modifiedDurationYears: 6.4,
    durationGapYears: 2.2,
    marketAccessStressScore: 68,
    taxElasticityCoefficient: 1.15,
    fiscalMultiplierSpending: 0.95,
    fiscalMultiplierTax: -0.70,

    sovereignMetrics: {
      externalDebtToFxReserves: 2.85, // External debt / FX Reserves
      greenspanGuidottiRatio: 0.88, // Below 1.0 threshold -> warning!
      fxReservesTotalUsdBillions: 62.4,
      shortTermExternalDebtUsdBillions: 70.9,
      seigniorageCapacityPctGdp: 0.65, // Max 0.65% GDP before runaway inflation
      centralBankMonetizationLimitPctGdp: 1.20,
      primaryBalancePctGdp: -0.80, // Primary deficit of 0.8% of GDP
      overallFiscalBalancePctGdp: -5.40, // Fiscal deficit 5.4% of GDP
      publicDebtToGdp: 73.6, // 73.6% of GDP
      externalDebtSharePct: 32.4, // 32.4% denominated in foreign currencies
      currentAccountBalancePctGdp: -2.10,
    },

    pensionOpeb: {
      planName: 'Government Employees Pension Fund (GEPF)',
      totalPensionLiability: 135000,
      actuarialValueOfAssets: 112000,
      netPensionLiability: 23000,
      fundedRatio: 83.0,
      assumedDiscountRate: 8.50,
      nplAtPlus100Bps: 16800,
      nplAtMinus100Bps: 31200,
      actuariallyDeterminedContribution: 5200,
      actualContribution: 5100,
      opebFundedRatio: 45.0,
      opebNetLiability: 6400,
      activeEmployees: 1250000,
      beneficiaries: 480000,
    },

    bonds: [
      {
        id: 'za-usd-2030',
        name: 'Republic of South Africa 5.875% USD Eurobond 2030',
        type: 'SovereignExternal',
        parAmount: 2500,
        coupon: 5.875,
        yieldToMaturity: 7.20,
        maturityDate: '2030-09-16',
        callDate: undefined,
        rating: 'BB-',
        isCallable: false,
        spreadOverBenchmarkBps: 345, // Spread over 10Y UST
        isTaxExempt: false,
      },
      {
        id: 'za-zar-r2035',
        name: 'RSA Local Currency Benchmark R2035 8.875%',
        type: 'SovereignLocal',
        parAmount: 14500, // USD equiv
        coupon: 8.875,
        yieldToMaturity: 10.95,
        maturityDate: '2035-02-28',
        callDate: undefined,
        rating: 'BB',
        isCallable: false,
        spreadOverBenchmarkBps: 680,
        isTaxExempt: false,
      },
    ],

    vrdos: [], // Sovereigns rarely issue US VRDOs, structured with short-term T-bills

    pppConcessions: [
      {
        id: 'za-ppp-gautrain',
        projectName: 'Gautrain Rapid Rail Link Concession',
        sector: 'Transit Rail',
        capitalExpenditure: 3200,
        concessionExpiryYear: 2036,
        concessionaireName: 'Bombela Concession Company',
        paymentStructure: 'Shadow Toll',
        mrgTriggerFloor: 180,
        currentProjectedRevenue: 142, // Triggered!
        contingentLiabilityExposure: 78,
        status: 'Triggered',
      },
      {
        id: 'za-ppp-n4-toll',
        projectName: 'N4 Maputo Corridor Toll Road',
        sector: 'Toll Highway',
        capitalExpenditure: 1400,
        concessionExpiryYear: 2028,
        concessionaireName: 'Trans African Concessions (TRAC)',
        paymentStructure: 'Direct User Fee',
        mrgTriggerFloor: 95,
        currentProjectedRevenue: 104,
        contingentLiabilityExposure: 22,
        status: 'Nominal',
      },
    ],

    stateOwnedEnterprises: [
      {
        id: 'soe-eskom',
        name: 'Eskom Holdings SOC Ltd (National Power Utility)',
        sector: 'Electric Power',
        totalDebt: 24500, // $24.5B
        debtServiceCoverageRatio: 0.62, // Severe distress
        explicitGovernmentGuarantee: true,
        bailoutProbability: 0.95,
        expectedShortfall95: 5800, // $5.8B contingent claim
      },
      {
        id: 'soe-transnet',
        name: 'Transnet SOC Ltd (Freight Rail & Ports)',
        sector: 'Port Authority',
        totalDebt: 7800,
        debtServiceCoverageRatio: 0.94,
        explicitGovernmentGuarantee: true,
        bailoutProbability: 0.72,
        expectedShortfall95: 1650,
      },
    ],

    marketSpreads: [
      { tenor: '1Y', benchmarkYield: 3.85, entityYield: 6.75, spreadBps: 290, cdsSpreadBps: 245, cdsBondBasisBps: -45 }, // Negative CDS-bond basis (physical spread higher than synthetic, illiquidity premium)
      { tenor: '3Y', benchmarkYield: 3.95, entityYield: 7.15, spreadBps: 320, cdsSpreadBps: 285, cdsBondBasisBps: -35 },
      { tenor: '5Y', benchmarkYield: 4.05, entityYield: 7.55, spreadBps: 350, cdsSpreadBps: 325, cdsBondBasisBps: -25 },
      { tenor: '10Y', benchmarkYield: 4.25, entityYield: 8.20, spreadBps: 395, cdsSpreadBps: 380, cdsBondBasisBps: -15 },
      { tenor: '20Y', benchmarkYield: 4.55, entityYield: 9.10, spreadBps: 455, cdsSpreadBps: 440, cdsBondBasisBps: -15 },
      { tenor: '30Y', benchmarkYield: 4.75, entityYield: 9.60, spreadBps: 485, cdsSpreadBps: 475, cdsBondBasisBps: -10 },
    ],

    maturityWall: {
      within12M: 32400,
      year1to2: 28500,
      year2to3: 31200,
      year3to5: 68000,
      beyond5Y: 137900,
    },
  },

  // SOVEREIGN 2: Italian Republic
  {
    id: 'sovereign-italy',
    name: 'Italian Republic',
    tier: 'sovereign',
    jurisdiction: 'Eurozone, European Union',
    creditRating: 'BBB',
    ratingOutlook: 'Stable',
    currency: 'EUR',
    gdpOrBudgetBillions: 2280.0, // GDP $2.28 Trillion
    totalDirectDebtMillions: 3120000, // Total public debt
    weightedAverageMaturityYears: 7.1,
    modifiedDurationYears: 5.8,
    durationGapYears: 1.5,
    marketAccessStressScore: 52,
    taxElasticityCoefficient: 1.10,
    fiscalMultiplierSpending: 0.90,
    fiscalMultiplierTax: -0.75,

    sovereignMetrics: {
      externalDebtToFxReserves: 1.45,
      greenspanGuidottiRatio: 1.82, // High liquidity via Eurosystem/ECB TARGET2
      fxReservesTotalUsdBillions: 245.0,
      shortTermExternalDebtUsdBillions: 134.0,
      seigniorageCapacityPctGdp: 0.40, // ECB institutional treaty constraints
      centralBankMonetizationLimitPctGdp: 0.0, // Strictly prohibited under EU Article 123
      primaryBalancePctGdp: 0.20, // Primary surplus +0.2%
      overallFiscalBalancePctGdp: -3.80, // High interest burden ~4.0% of GDP
      publicDebtToGdp: 137.5, // 137.5% of GDP
      externalDebtSharePct: 29.5, // Non-resident holdings
      currentAccountBalancePctGdp: 1.10,
    },

    pensionOpeb: {
      planName: 'INPS National Social Security & Pension System',
      totalPensionLiability: 1250000,
      actuarialValueOfAssets: 420000,
      netPensionLiability: 830000,
      fundedRatio: 33.6, // Pay-as-you-go demographic pressure
      assumedDiscountRate: 3.25,
      nplAtPlus100Bps: 710000,
      nplAtMinus100Bps: 980000,
      actuariallyDeterminedContribution: 78000,
      actualContribution: 74000,
      opebFundedRatio: 22.0,
      opebNetLiability: 145000,
      activeEmployees: 23500000,
      beneficiaries: 16100000,
    },

    bonds: [
      {
        id: 'btp-10y-2034',
        name: 'BTP 10-Year Benchmark 3.85% 2034',
        type: 'SovereignLocal',
        parAmount: 35000,
        coupon: 3.85,
        yieldToMaturity: 3.65,
        maturityDate: '2034-03-01',
        callDate: undefined,
        rating: 'BBB',
        isCallable: false,
        spreadOverBenchmarkBps: 135, // Spread over German Bund
        isTaxExempt: false,
      },
      {
        id: 'btp-30y-2053',
        name: 'BTP 30-Year Benchmark 4.50% 2053',
        type: 'SovereignLocal',
        parAmount: 22000,
        coupon: 4.50,
        yieldToMaturity: 4.35,
        maturityDate: '2053-10-01',
        callDate: undefined,
        rating: 'BBB',
        isCallable: false,
        spreadOverBenchmarkBps: 175,
        isTaxExempt: false,
      },
    ],

    vrdos: [],

    pppConcessions: [
      {
        id: 'it-ppp-autostrade',
        projectName: 'A1 Autostrada del Sole Modernization Concession',
        sector: 'Toll Highway',
        capitalExpenditure: 4600,
        concessionExpiryYear: 2038,
        concessionaireName: 'Autostrade per l’Italia SpA (ASPI)',
        paymentStructure: 'Direct User Fee',
        mrgTriggerFloor: 380,
        currentProjectedRevenue: 410,
        contingentLiabilityExposure: 110,
        status: 'Nominal',
      },
      {
        id: 'it-ppp-brennero',
        projectName: 'Brenner Base Tunnel Access Corridor Rail PPP',
        sector: 'Transit Rail',
        capitalExpenditure: 3100,
        concessionExpiryYear: 2055,
        concessionaireName: 'BBT SE Consortium',
        paymentStructure: 'Availability Payment',
        mrgTriggerFloor: 140,
        currentProjectedRevenue: 135, // Triggered
        contingentLiabilityExposure: 45,
        status: 'Triggered',
      },
    ],

    stateOwnedEnterprises: [
      {
        id: 'soe-fs',
        name: 'Ferrovie dello Stato Italiane SpA (National Railway)',
        sector: 'Public Transit',
        totalDebt: 12400,
        debtServiceCoverageRatio: 1.25,
        explicitGovernmentGuarantee: true,
        bailoutProbability: 0.35,
        expectedShortfall95: 1200,
      },
      {
        id: 'soe-enav',
        name: 'ENAV SpA (Air Navigation Services)',
        sector: 'Port Authority',
        totalDebt: 1100,
        debtServiceCoverageRatio: 2.10,
        explicitGovernmentGuarantee: false,
        bailoutProbability: 0.08,
        expectedShortfall95: 60,
      },
    ],

    marketSpreads: [
      { tenor: '1Y', benchmarkYield: 2.20, entityYield: 2.95, spreadBps: 75, cdsSpreadBps: 90, cdsBondBasisBps: 15 },
      { tenor: '3Y', benchmarkYield: 2.15, entityYield: 3.10, spreadBps: 95, cdsSpreadBps: 110, cdsBondBasisBps: 15 },
      { tenor: '5Y', benchmarkYield: 2.25, entityYield: 3.35, spreadBps: 110, cdsSpreadBps: 128, cdsBondBasisBps: 18 },
      { tenor: '10Y', benchmarkYield: 2.45, entityYield: 3.80, spreadBps: 135, cdsSpreadBps: 158, cdsBondBasisBps: 23 },
      { tenor: '20Y', benchmarkYield: 2.70, entityYield: 4.25, spreadBps: 155, cdsSpreadBps: 182, cdsBondBasisBps: 27 },
      { tenor: '30Y', benchmarkYield: 2.75, entityYield: 4.45, spreadBps: 170, cdsSpreadBps: 202, cdsBondBasisBps: 32 },
    ],

    maturityWall: {
      within12M: 380000,
      year1to2: 340000,
      year2to3: 310000,
      year3to5: 650000,
      beyond5Y: 1440000,
    },
  },
];

export const PRESET_SCENARIOS: StressScenario[] = [
  {
    id: 'baseline',
    name: 'Baseline Macro Trajectory',
    description: 'Current consensus yield curve, standard trend GDP growth, nominal inflation.',
    interestRateDeltaBps: 0,
    gdpGrowthShockPct: 0,
    inflationShockPct: 0,
    propertyValueDeclinePct: 0,
    pensionAssetShockPct: 0,
    pppTrafficDeclinePct: 0,
    soeDistressProbabilityMultiplier: 1.0,
    externalCurrencyDevaluationPct: 0,
  },
  {
    id: 'stagflation-shock',
    name: 'Stagflationary Rate Surge (+300 bps)',
    description: 'Persistent inflation spike forces central banks to raise policy rates +300 bps while real GDP contracts -2.5%.',
    interestRateDeltaBps: 300,
    gdpGrowthShockPct: -2.5,
    inflationShockPct: 4.5,
    propertyValueDeclinePct: -12.0,
    pensionAssetShockPct: -15.0,
    pppTrafficDeclinePct: -18.0,
    soeDistressProbabilityMultiplier: 1.8,
    externalCurrencyDevaluationPct: 18.0,
  },
  {
    id: 'real-estate-crash',
    name: 'Commercial & Property AV Collapse (-25%)',
    description: 'Urban vacancy and cap rate expansions slash assessed valuations by 25%, hitting Mill rate tax caps and local receipts.',
    interestRateDeltaBps: 100,
    gdpGrowthShockPct: -1.8,
    inflationShockPct: 1.2,
    propertyValueDeclinePct: -25.0,
    pensionAssetShockPct: -10.0,
    pppTrafficDeclinePct: -22.0,
    soeDistressProbabilityMultiplier: 1.4,
    externalCurrencyDevaluationPct: 8.0,
  },
  {
    id: 'medicaid-recession',
    name: 'Severe Counter-Cyclical Recession & Medicaid Surge',
    description: 'Severe recession drives entitlement safety net rolls +35%, tax receipts plunge under high elasticity, FMAP lag.',
    interestRateDeltaBps: -75,
    gdpGrowthShockPct: -3.8,
    inflationShockPct: -1.0,
    propertyValueDeclinePct: -8.0,
    pensionAssetShockPct: -18.0,
    pppTrafficDeclinePct: -30.0,
    soeDistressProbabilityMultiplier: 2.2,
    externalCurrencyDevaluationPct: 12.0,
  },
  {
    id: 'ppp-mrg-trigger-crisis',
    name: 'Infrastructure Volume Shock & PPP Guarantees',
    description: 'Severe transport and concession traffic drop invokes Minimum Revenue Guarantees (MRGs) across all shadow toll and P3 contracts.',
    interestRateDeltaBps: 50,
    gdpGrowthShockPct: -1.5,
    inflationShockPct: 2.0,
    propertyValueDeclinePct: -5.0,
    pensionAssetShockPct: -8.0,
    pppTrafficDeclinePct: -42.0,
    soeDistressProbabilityMultiplier: 2.5,
    externalCurrencyDevaluationPct: 15.0,
  },
];
