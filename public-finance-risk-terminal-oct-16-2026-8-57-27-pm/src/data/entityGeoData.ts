import { PublicFinanceEntity, GovernmentTier } from '../types/finance';

export interface NeighborEntity {
  id: string;
  name: string;
  tier: GovernmentTier;
  creditRating: string;
  ratingOutlook: 'Stable' | 'Negative' | 'Positive' | 'Watch';
  fiscalStressScore: number; // 0 to 100
  totalDebtMillions: number;
  latitude: number;
  longitude: number;
  distanceMiles: number;
  bearing: string; // e.g. "NE", "SW", "Adjacent"
  contagionExposure: 'Low' | 'Medium' | 'High' | 'Critical';
  relationshipType: string;
  relationshipDescription: string;
  isTerminalEntity?: boolean; // If already available in workspace
}

export interface EntityGeoProfile {
  entityId: string;
  canonicalName: string;
  latitude: number;
  longitude: number;
  regionName: string;
  corridorName: string;
  zoomLevel: number;
  neighbors: NeighborEntity[];
}

export const GEO_DATABASE: Record<string, EntityGeoProfile> = {
  // 1. City of Chicago
  'chicago-muni': {
    entityId: 'chicago-muni',
    canonicalName: 'City of Chicago',
    latitude: 41.8781,
    longitude: -87.6298,
    regionName: 'Cook County, Illinois',
    corridorName: 'Great Lakes & Midwest Transportation Spine',
    zoomLevel: 10,
    neighbors: [
      {
        id: 'cook-county-il',
        name: 'Cook County Government',
        tier: 'municipal',
        creditRating: 'AA-',
        ratingOutlook: 'Stable',
        fiscalStressScore: 45,
        totalDebtMillions: 4850,
        latitude: 41.8150,
        longitude: -87.7500,
        distanceMiles: 12,
        bearing: 'W',
        contagionExposure: 'High',
        relationshipType: 'Overlapping Tax Jurisdiction',
        relationshipDescription: 'Shares identical commercial & residential property tax base; co-funds Cook County Health and hospital system.',
        isTerminalEntity: false,
      },
      {
        id: 'state-illinois',
        name: 'State of Illinois',
        tier: 'subnational',
        creditRating: 'A-',
        ratingOutlook: 'Positive',
        fiscalStressScore: 48,
        totalDebtMillions: 36400,
        latitude: 39.7817,
        longitude: -89.6501,
        distanceMiles: 185,
        bearing: 'SW',
        contagionExposure: 'Critical',
        relationshipType: 'Parent Subnational State',
        relationshipDescription: 'Statutory Local Government Distributive Fund (LGDF) revenue sharing, pension intercept provisions, and CTA transit support.',
        isTerminalEntity: true,
      },
      {
        id: 'dupage-county-il',
        name: 'DuPage County',
        tier: 'municipal',
        creditRating: 'AAA',
        ratingOutlook: 'Stable',
        fiscalStressScore: 22,
        totalDebtMillions: 1420,
        latitude: 41.8500,
        longitude: -88.0800,
        distanceMiles: 25,
        bearing: 'W',
        contagionExposure: 'Low',
        relationshipType: 'Suburban Collar County',
        relationshipDescription: 'Western collar county; economic interdependence via O\'Hare Airport logistics corridor and Metra commuter rail.',
        isTerminalEntity: false,
      },
      {
        id: 'evanston-il',
        name: 'City of Evanston',
        tier: 'municipal',
        creditRating: 'AA+',
        ratingOutlook: 'Stable',
        fiscalStressScore: 28,
        totalDebtMillions: 310,
        latitude: 42.0451,
        longitude: -87.6877,
        distanceMiles: 12,
        bearing: 'N',
        contagionExposure: 'Low',
        relationshipType: 'Bordering Municipality',
        relationshipDescription: 'North Shore bordering city; purchase contract for wholesale Chicago Lake Michigan treated water system.',
        isTerminalEntity: false,
      },
      {
        id: 'gary-in',
        name: 'City of Gary & Lake County, IN',
        tier: 'municipal',
        creditRating: 'BB+',
        ratingOutlook: 'Negative',
        fiscalStressScore: 68,
        totalDebtMillions: 480,
        latitude: 41.5934,
        longitude: -87.3464,
        distanceMiles: 28,
        bearing: 'SE',
        contagionExposure: 'Medium',
        relationshipType: 'Cross-Border Industrial Basin',
        relationshipDescription: 'South Shore rail transit corridor; shared Lake Michigan environmental and steel manufacturing supply chain.',
        isTerminalEntity: false,
      },
      {
        id: 'milwaukee-wi',
        name: 'City of Milwaukee',
        tier: 'municipal',
        creditRating: 'A-',
        ratingOutlook: 'Stable',
        fiscalStressScore: 52,
        totalDebtMillions: 1890,
        latitude: 43.0389,
        longitude: -87.9065,
        distanceMiles: 82,
        bearing: 'N',
        contagionExposure: 'Medium',
        relationshipType: 'Regional Great Lakes Peer',
        relationshipDescription: 'Amtrak Hiawatha high-density commuter rail corridor and interconnected Midwest manufacturing labor market.',
        isTerminalEntity: false,
      },
      {
        id: 'will-county-il',
        name: 'Will County Logistics Hub',
        tier: 'municipal',
        creditRating: 'AA+',
        ratingOutlook: 'Stable',
        fiscalStressScore: 30,
        totalDebtMillions: 890,
        latitude: 41.5000,
        longitude: -88.0500,
        distanceMiles: 35,
        bearing: 'SW',
        contagionExposure: 'Low',
        relationshipType: 'Inland Port Logistics Hub',
        relationshipDescription: 'Largest North American inland intermodal freight container center serving Chicago distribution networks.',
        isTerminalEntity: false,
      },
    ],
  },

  // 2. Bay Area Regional Transportation District (BART)
  'sf-bay-transport': {
    entityId: 'sf-bay-transport',
    canonicalName: 'Bay Area Regional Transportation District',
    latitude: 37.7749,
    longitude: -122.4194,
    regionName: 'San Francisco Bay Area, California',
    corridorName: 'Northern California Megaregion Transit Spine',
    zoomLevel: 10,
    neighbors: [
      {
        id: 'sf-city-county',
        name: 'City & County of San Francisco',
        tier: 'municipal',
        creditRating: 'AAA',
        ratingOutlook: 'Stable',
        fiscalStressScore: 35,
        totalDebtMillions: 4850,
        latitude: 37.7749,
        longitude: -122.4400,
        distanceMiles: 3,
        bearing: 'W',
        contagionExposure: 'Critical',
        relationshipType: 'Core Station Hub & Tax Base',
        relationshipDescription: 'Transbay Tube destination hub; generates 44% of weekday farebox revenue and significant dedicated sales tax.',
        isTerminalEntity: false,
      },
      {
        id: 'oakland-alameda',
        name: 'City of Oakland & Alameda County',
        tier: 'municipal',
        creditRating: 'AA-',
        ratingOutlook: 'Negative',
        fiscalStressScore: 48,
        totalDebtMillions: 2750,
        latitude: 37.8044,
        longitude: -122.2712,
        distanceMiles: 8,
        bearing: 'E',
        contagionExposure: 'High',
        relationshipType: 'Operations & Maintenance Core',
        relationshipDescription: 'Primary maintenance yards, administrative headquarters, and MacArthur/19th St trunk transfer stations.',
        isTerminalEntity: false,
      },
      {
        id: 'state-california',
        name: 'State of California',
        tier: 'subnational',
        creditRating: 'AA-',
        ratingOutlook: 'Stable',
        fiscalStressScore: 32,
        totalDebtMillions: 118000,
        latitude: 38.5816,
        longitude: -121.4944,
        distanceMiles: 75,
        bearing: 'NE',
        contagionExposure: 'High',
        relationshipType: 'Parent Subnational State',
        relationshipDescription: 'State Transit Assistance (STA) funding, Cap-and-Trade climate grants, and statutory fiscal oversight framework.',
        isTerminalEntity: true,
      },
      {
        id: 'vta-santa-clara',
        name: 'Santa Clara Valley Transportation (VTA)',
        tier: 'municipal',
        creditRating: 'AA',
        ratingOutlook: 'Stable',
        fiscalStressScore: 38,
        totalDebtMillions: 1980,
        latitude: 37.3382,
        longitude: -121.8863,
        distanceMiles: 42,
        bearing: 'S',
        contagionExposure: 'High',
        relationshipType: 'Phase II Extension Compact',
        relationshipDescription: 'Silicon Valley BART extension partner through Berryessa, Downtown San Jose, and Santa Clara stations.',
        isTerminalEntity: false,
      },
      {
        id: 'contra-costa-county',
        name: 'Contra Costa County',
        tier: 'municipal',
        creditRating: 'AA+',
        ratingOutlook: 'Stable',
        fiscalStressScore: 26,
        totalDebtMillions: 1120,
        latitude: 37.9500,
        longitude: -122.0500,
        distanceMiles: 22,
        bearing: 'NE',
        contagionExposure: 'Medium',
        relationshipType: 'Dedicated Sales Tax Partner',
        relationshipDescription: 'Yellow Line Antioch corridor suburban stations; allocates 0.50% dedicated sales tax revenues to BART.',
        isTerminalEntity: false,
      },
      {
        id: 'san-mateo-county',
        name: 'San Mateo County & SFO Airport',
        tier: 'municipal',
        creditRating: 'AAA',
        ratingOutlook: 'Stable',
        fiscalStressScore: 24,
        totalDebtMillions: 1450,
        latitude: 37.5630,
        longitude: -122.3255,
        distanceMiles: 18,
        bearing: 'S',
        contagionExposure: 'Medium',
        relationshipType: 'SFO Airport Station Agreement',
        relationshipDescription: 'Special joint powers agreement operating direct air-rail extension into San Francisco International Airport.',
        isTerminalEntity: false,
      },
    ],
  },

  // 3. State of Illinois
  'state-illinois': {
    entityId: 'state-illinois',
    canonicalName: 'State of Illinois',
    latitude: 40.0417,
    longitude: -89.1965,
    regionName: 'Springfield / Central Midwest',
    corridorName: 'Midwest Agriculture & Heavy Industry Belt',
    zoomLevel: 7,
    neighbors: [
      {
        id: 'chicago-muni',
        name: 'City of Chicago',
        tier: 'municipal',
        creditRating: 'BBB+',
        ratingOutlook: 'Stable',
        fiscalStressScore: 54,
        totalDebtMillions: 11450,
        latitude: 41.8781,
        longitude: -87.6298,
        distanceMiles: 185,
        bearing: 'NE',
        contagionExposure: 'Critical',
        relationshipType: 'Primary Economic Engine',
        relationshipDescription: 'Chicago metropolitan area generates over 68% of total state corporate, individual income, and sales tax receipts.',
        isTerminalEntity: true,
      },
      {
        id: 'state-indiana',
        name: 'State of Indiana',
        tier: 'subnational',
        creditRating: 'AAA',
        ratingOutlook: 'Stable',
        fiscalStressScore: 24,
        totalDebtMillions: 3800,
        latitude: 39.7684,
        longitude: -86.1581,
        distanceMiles: 160,
        bearing: 'E',
        contagionExposure: 'Medium',
        relationshipType: 'Adjacent State / Tax Competition',
        relationshipDescription: 'Direct tax competition along the Gary/Hammond border; contrasting flat tax structures and right-to-work policies.',
        isTerminalEntity: false,
      },
      {
        id: 'state-wisconsin',
        name: 'State of Wisconsin',
        tier: 'subnational',
        creditRating: 'AA+',
        ratingOutlook: 'Stable',
        fiscalStressScore: 28,
        totalDebtMillions: 13900,
        latitude: 43.0731,
        longitude: -89.4012,
        distanceMiles: 210,
        bearing: 'N',
        contagionExposure: 'Medium',
        relationshipType: 'Adjacent State / Commuter Compact',
        relationshipDescription: 'Interstate income tax reciprocity compact negotiations and Foxconn corridor manufacturing integration.',
        isTerminalEntity: false,
      },
      {
        id: 'state-missouri',
        name: 'State of Missouri',
        tier: 'subnational',
        creditRating: 'AAA',
        ratingOutlook: 'Stable',
        fiscalStressScore: 26,
        totalDebtMillions: 5600,
        latitude: 38.5767,
        longitude: -92.1735,
        distanceMiles: 190,
        bearing: 'SW',
        contagionExposure: 'Medium',
        relationshipType: 'Bi-State Metropolitan Compact',
        relationshipDescription: 'Joint stewardship of the St. Louis metropolitan area and Bi-State Development Agency (Metro transit & bridges).',
        isTerminalEntity: false,
      },
      {
        id: 'state-iowa',
        name: 'State of Iowa',
        tier: 'subnational',
        creditRating: 'AAA',
        ratingOutlook: 'Stable',
        fiscalStressScore: 22,
        totalDebtMillions: 2400,
        latitude: 41.5868,
        longitude: -93.6250,
        distanceMiles: 220,
        bearing: 'W',
        contagionExposure: 'Low',
        relationshipType: 'Mississippi River Bordering State',
        relationshipDescription: 'Quad Cities bi-state economic integration and Mississippi River freight lock & dam agricultural navigation.',
        isTerminalEntity: false,
      },
      {
        id: 'state-kentucky',
        name: 'Commonwealth of Kentucky',
        tier: 'subnational',
        creditRating: 'A+',
        ratingOutlook: 'Stable',
        fiscalStressScore: 42,
        totalDebtMillions: 12500,
        latitude: 38.2009,
        longitude: -84.8733,
        distanceMiles: 240,
        bearing: 'SE',
        contagionExposure: 'Low',
        relationshipType: 'Ohio River Basin Border State',
        relationshipDescription: 'Southern Illinois coal and grain barge transit along the Ohio River logistics basin.',
        isTerminalEntity: false,
      },
    ],
  },

  // 4. State of California
  'state-california': {
    entityId: 'state-california',
    canonicalName: 'State of California',
    latitude: 36.7783,
    longitude: -119.4179,
    regionName: 'Sacramento / Pacific Coast',
    corridorName: 'Pacific Rim Global Trade & Technology Corridor',
    zoomLevel: 6,
    neighbors: [
      {
        id: 'sf-bay-transport',
        name: 'Bay Area Regional Transportation (BART)',
        tier: 'municipal',
        creditRating: 'AA-',
        ratingOutlook: 'Negative',
        fiscalStressScore: 42,
        totalDebtMillions: 3820,
        latitude: 37.7749,
        longitude: -122.4194,
        distanceMiles: 150,
        bearing: 'NW',
        contagionExposure: 'Medium',
        relationshipType: 'Major Regional Transit District',
        relationshipDescription: 'Key beneficiary of California Cap-and-Trade auction revenues and Senate Bill 1 transit capital grants.',
        isTerminalEntity: true,
      },
      {
        id: 'la-county',
        name: 'County of Los Angeles',
        tier: 'municipal',
        creditRating: 'AA+',
        ratingOutlook: 'Stable',
        fiscalStressScore: 36,
        totalDebtMillions: 6200,
        latitude: 34.0522,
        longitude: -118.2437,
        distanceMiles: 190,
        bearing: 'S',
        contagionExposure: 'High',
        relationshipType: 'Largest Sub-Jurisdiction',
        relationshipDescription: 'Accounts for nearly 27% of California\'s total population (9.8M residents) and major Medi-Cal program matching.',
        isTerminalEntity: false,
      },
      {
        id: 'state-nevada',
        name: 'State of Nevada',
        tier: 'subnational',
        creditRating: 'AA+',
        ratingOutlook: 'Stable',
        fiscalStressScore: 32,
        totalDebtMillions: 4100,
        latitude: 39.1638,
        longitude: -119.7674,
        distanceMiles: 180,
        bearing: 'NE',
        contagionExposure: 'Medium',
        relationshipType: 'Adjacent State / Tax Arbitrage',
        relationshipDescription: 'Significant destination for California high-net-worth tax migration, Lake Tahoe environmental compact, and Hoover power.',
        isTerminalEntity: false,
      },
      {
        id: 'state-arizona',
        name: 'State of Arizona',
        tier: 'subnational',
        creditRating: 'AA',
        ratingOutlook: 'Stable',
        fiscalStressScore: 34,
        totalDebtMillions: 6400,
        latitude: 33.4484,
        longitude: -112.0740,
        distanceMiles: 380,
        bearing: 'E',
        contagionExposure: 'High',
        relationshipType: 'Colorado River Water Compact',
        relationshipDescription: 'Critical co-signatory to the Colorado River Basin 7-State Drought Contingency Plan and Imperial Valley agriculture.',
        isTerminalEntity: false,
      },
      {
        id: 'state-oregon',
        name: 'State of Oregon',
        tier: 'subnational',
        creditRating: 'AA+',
        ratingOutlook: 'Stable',
        fiscalStressScore: 28,
        totalDebtMillions: 8900,
        latitude: 44.9384,
        longitude: -123.0304,
        distanceMiles: 450,
        bearing: 'N',
        contagionExposure: 'Low',
        relationshipType: 'Pacific Coast Climate Compact',
        relationshipDescription: 'Western Energy Imbalance Market (WEIM) transmission interties and West Coast carbon reduction framework.',
        isTerminalEntity: false,
      },
      {
        id: 'baja-california',
        name: 'State of Baja California (Mexico)',
        tier: 'subnational',
        creditRating: 'BBB-',
        ratingOutlook: 'Stable',
        fiscalStressScore: 56,
        totalDebtMillions: 1200,
        latitude: 32.5149,
        longitude: -117.0382,
        distanceMiles: 320,
        bearing: 'S',
        contagionExposure: 'Medium',
        relationshipType: 'Cross-Border Manufacturing Corridor',
        relationshipDescription: 'Tijuana-San Diego CaliBaja mega-region; Otay Mesa commercial port of entry processing $50B+ in annual bilateral freight.',
        isTerminalEntity: false,
      },
    ],
  },

  // 5. Republic of South Africa
  'sovereign-south-africa': {
    entityId: 'sovereign-south-africa',
    canonicalName: 'Republic of South Africa',
    latitude: -30.5595,
    longitude: 22.9375,
    regionName: 'Pretoria / Cape Town',
    corridorName: 'Southern African Development Community (SADC) Gateway',
    zoomLevel: 5,
    neighbors: [
      {
        id: 'namibia',
        name: 'Republic of Namibia',
        tier: 'sovereign',
        creditRating: 'BB-',
        ratingOutlook: 'Stable',
        fiscalStressScore: 55,
        totalDebtMillions: 8400,
        latitude: -22.5609,
        longitude: 17.0658,
        distanceMiles: 750,
        bearing: 'NW',
        contagionExposure: 'High',
        relationshipType: 'Common Monetary Area (CMA)',
        relationshipDescription: 'Namibian Dollar is pegged 1:1 to the South African Rand; shares South African Reserve Bank liquidity facilities.',
        isTerminalEntity: false,
      },
      {
        id: 'botswana',
        name: 'Republic of Botswana',
        tier: 'sovereign',
        creditRating: 'BBB+',
        ratingOutlook: 'Stable',
        fiscalStressScore: 35,
        totalDebtMillions: 4800,
        latitude: -24.6541,
        longitude: 25.9087,
        distanceMiles: 480,
        bearing: 'N',
        contagionExposure: 'Medium',
        relationshipType: 'SACU Customs Partner',
        relationshipDescription: 'Southern African Customs Union (SACU) revenue sharing pool; interconnected Eskom electricity pool.',
        isTerminalEntity: false,
      },
      {
        id: 'zimbabwe',
        name: 'Republic of Zimbabwe',
        tier: 'sovereign',
        creditRating: 'CCC',
        ratingOutlook: 'Negative',
        fiscalStressScore: 86,
        totalDebtMillions: 17200,
        latitude: -17.8252,
        longitude: 31.0335,
        distanceMiles: 820,
        bearing: 'NE',
        contagionExposure: 'Critical',
        relationshipType: 'Beitbridge Border Trade Spine',
        relationshipDescription: 'Busiest regional trade corridor in sub-Saharan Africa; significant cross-border remittances and migration flows.',
        isTerminalEntity: false,
      },
      {
        id: 'mozambique',
        name: 'Republic of Mozambique',
        tier: 'sovereign',
        creditRating: 'CCC+',
        ratingOutlook: 'Stable',
        fiscalStressScore: 78,
        totalDebtMillions: 14600,
        latitude: -25.9692,
        longitude: 32.5732,
        distanceMiles: 620,
        bearing: 'E',
        contagionExposure: 'High',
        relationshipType: 'Maputo Port & Gas Pipeline',
        relationshipDescription: 'Sasol natural gas pipeline from Pande/Temane to Secunda; Maputo Development Corridor export route for Gauteng.',
        isTerminalEntity: false,
      },
      {
        id: 'lesotho',
        name: 'Kingdom of Lesotho',
        tier: 'sovereign',
        creditRating: 'B',
        ratingOutlook: 'Negative',
        fiscalStressScore: 66,
        totalDebtMillions: 1650,
        latitude: -29.3151,
        longitude: 27.4869,
        distanceMiles: 220,
        bearing: 'E',
        contagionExposure: 'Critical',
        relationshipType: 'Highlands Water Treaty & Enclave',
        relationshipDescription: 'Completely enclaved by South Africa; Lesotho Highlands Water Project supplies 60%+ of Gauteng\'s municipal fresh water.',
        isTerminalEntity: false,
      },
      {
        id: 'eswatini',
        name: 'Kingdom of Eswatini',
        tier: 'sovereign',
        creditRating: 'B-',
        ratingOutlook: 'Stable',
        fiscalStressScore: 68,
        totalDebtMillions: 1980,
        latitude: -26.3261,
        longitude: 31.1442,
        distanceMiles: 490,
        bearing: 'E',
        contagionExposure: 'High',
        relationshipType: 'CMA & SACU Revenue Dependence',
        relationshipDescription: 'Lilangeni pegged 1:1 to SA Rand; over 40% of national government revenue derived from the SACU customs tariff pool.',
        isTerminalEntity: false,
      },
    ],
  },

  // 6. Federative Republic of Brazil
  'sovereign-brazil': {
    entityId: 'sovereign-brazil',
    canonicalName: 'Federative Republic of Brazil',
    latitude: -14.2350,
    longitude: -51.9253,
    regionName: 'Brasília / South America',
    corridorName: 'Mercosur Southern Cone Economic Basin',
    zoomLevel: 4,
    neighbors: [
      {
        id: 'argentina',
        name: 'Argentine Republic',
        tier: 'sovereign',
        creditRating: 'CCC-',
        ratingOutlook: 'Watch',
        fiscalStressScore: 89,
        totalDebtMillions: 395000,
        latitude: -34.6037,
        longitude: -58.3816,
        distanceMiles: 1450,
        bearing: 'S',
        contagionExposure: 'Critical',
        relationshipType: 'Mercosur Bilateral Trade Anchor',
        relationshipDescription: 'Largest bilateral automotive, industrial machinery, and agricultural export destination in South America.',
        isTerminalEntity: false,
      },
      {
        id: 'paraguay',
        name: 'Republic of Paraguay',
        tier: 'sovereign',
        creditRating: 'BBB-',
        ratingOutlook: 'Positive',
        fiscalStressScore: 44,
        totalDebtMillions: 14200,
        latitude: -25.2637,
        longitude: -57.5759,
        distanceMiles: 950,
        bearing: 'SW',
        contagionExposure: 'Medium',
        relationshipType: 'Itaipu Dam Hydroelectric Treaty',
        relationshipDescription: 'World\'s 2nd largest hydro plant (14 GW); bi-national treaty supplying 11% of Brazil\'s total electricity grid.',
        isTerminalEntity: false,
      },
      {
        id: 'uruguay',
        name: 'Eastern Republic of Uruguay',
        tier: 'sovereign',
        creditRating: 'BBB+',
        ratingOutlook: 'Stable',
        fiscalStressScore: 36,
        totalDebtMillions: 38400,
        latitude: -34.9011,
        longitude: -56.1645,
        distanceMiles: 1380,
        bearing: 'S',
        contagionExposure: 'Low',
        relationshipType: 'Mercosur Port Logistics Hub',
        relationshipDescription: 'Deepwater maritime transshipment at Montevideo and financial services conduit for Mercosur grain exports.',
        isTerminalEntity: false,
      },
      {
        id: 'bolivia',
        name: 'Plurinational State of Bolivia',
        tier: 'sovereign',
        creditRating: 'CCC+',
        ratingOutlook: 'Negative',
        fiscalStressScore: 82,
        totalDebtMillions: 18500,
        latitude: -16.5000,
        longitude: -68.1500,
        distanceMiles: 1200,
        bearing: 'W',
        contagionExposure: 'High',
        relationshipType: 'GASBOL Natural Gas Pipeline',
        relationshipDescription: '3,150 km pipeline supplying Bolivian natural gas to industrial centers across São Paulo, Paraná, and Rio Grande do Sul.',
        isTerminalEntity: false,
      },
      {
        id: 'colombia',
        name: 'Republic of Colombia',
        tier: 'sovereign',
        creditRating: 'BB+',
        ratingOutlook: 'Negative',
        fiscalStressScore: 52,
        totalDebtMillions: 178000,
        latitude: 4.7110,
        longitude: -74.0721,
        distanceMiles: 1850,
        bearing: 'NW',
        contagionExposure: 'Low',
        relationshipType: 'Amazon Basin Security Pact',
        relationshipDescription: 'Amazon Cooperation Treaty Organization (ACTO) partner and growing Pacific-Atlantic trade bridge.',
        isTerminalEntity: false,
      },
      {
        id: 'peru',
        name: 'Republic of Peru',
        tier: 'sovereign',
        creditRating: 'BBB',
        ratingOutlook: 'Stable',
        fiscalStressScore: 48,
        totalDebtMillions: 62000,
        latitude: -12.0464,
        longitude: -77.0428,
        distanceMiles: 1780,
        bearing: 'W',
        contagionExposure: 'Low',
        relationshipType: 'Interoceanic Highway Corridor',
        relationshipDescription: 'Trans-continental transit route connecting Acre and Brazilian agribusiness to Peruvian Pacific ports.',
        isTerminalEntity: false,
      },
    ],
  },
};

// Color resolver utility by Rating
export const getRatingColor = (rating: string): { bg: string; text: string; hex: string } => {
  const clean = rating.trim().toUpperCase();
  if (clean.startsWith('AAA')) return { bg: 'bg-emerald-950', text: 'text-emerald-400', hex: '#10b981' };
  if (clean.startsWith('AA')) return { bg: 'bg-teal-950', text: 'text-teal-400', hex: '#14b8a6' };
  if (clean.startsWith('A')) return { bg: 'bg-cyan-950', text: 'text-cyan-400', hex: '#06b6d4' };
  if (clean.startsWith('BBB')) return { bg: 'bg-amber-950', text: 'text-amber-400', hex: '#f59e0b' };
  if (clean.startsWith('BB')) return { bg: 'bg-orange-950', text: 'text-orange-400', hex: '#f97316' };
  return { bg: 'bg-rose-950', text: 'text-rose-400', hex: '#f43f5e' };
};

// Color resolver utility by Stress Score
export const getStressScoreColor = (score: number): { bg: string; text: string; hex: string } => {
  if (score < 30) return { bg: 'bg-emerald-950', text: 'text-emerald-400', hex: '#10b981' };
  if (score < 50) return { bg: 'bg-amber-950', text: 'text-amber-400', hex: '#f59e0b' };
  if (score < 70) return { bg: 'bg-orange-950', text: 'text-orange-400', hex: '#f97316' };
  return { bg: 'bg-rose-950', text: 'text-rose-400', hex: '#f43f5e' };
};

// Color resolver utility by Tier
export const getTierColor = (tier: GovernmentTier): { bg: string; text: string; hex: string } => {
  if (tier === 'municipal') return { bg: 'bg-cyan-950', text: 'text-cyan-400', hex: '#06b6d4' };
  if (tier === 'subnational') return { bg: 'bg-purple-950', text: 'text-purple-400', hex: '#a855f7' };
  return { bg: 'bg-indigo-950', text: 'text-indigo-400', hex: '#6366f1' };
};

// Color resolver utility by Contagion Exposure
export const getContagionColor = (exposure: string): { bg: string; text: string; hex: string } => {
  if (exposure === 'Critical') return { bg: 'bg-rose-950', text: 'text-rose-400', hex: '#e11d48' };
  if (exposure === 'High') return { bg: 'bg-amber-950', text: 'text-amber-400', hex: '#f59e0b' };
  if (exposure === 'Medium') return { bg: 'bg-sky-950', text: 'text-sky-400', hex: '#0284c7' };
  return { bg: 'bg-slate-800', text: 'text-slate-300', hex: '#64748b' };
};

// Dynamic helper to resolve or generate a GeoProfile for any entity
export const resolveEntityGeoProfile = (
  entity: PublicFinanceEntity,
  allEntities: PublicFinanceEntity[] = []
): EntityGeoProfile => {
  // Check direct database lookup
  if (GEO_DATABASE[entity.id]) {
    const profile = { ...GEO_DATABASE[entity.id] };
    // Synchronize terminal status for neighbors
    profile.neighbors = profile.neighbors.map((n) => {
      const match = allEntities.find((e) => e.id === n.id);
      return {
        ...n,
        isTerminalEntity: !!match || n.isTerminalEntity,
      };
    });
    return profile;
  }

  // Synthesize geo profile based on entity tier, jurisdiction, and name
  let lat = 40.7128;
  let lng = -74.0060;
  let region = entity.jurisdiction || 'North America';
  let corridor = 'Regional Public Finance District';

  const nameLower = entity.name.toLowerCase();
  const idLower = entity.id.toLowerCase();

  if (nameLower.includes('new york') || idLower.includes('nyc')) {
    lat = 40.7128;
    lng = -74.0060;
    region = 'New York Metropolitan Area';
    corridor = 'Northeast Megalopolis Transit Corridor';
  } else if (nameLower.includes('los angeles') || idLower.includes('la')) {
    lat = 34.0522;
    lng = -118.2437;
    region = 'Southern California Megaregion';
    corridor = 'Pacific Gateway Intermodal Corridor';
  } else if (nameLower.includes('miami')) {
    lat = 25.7617;
    lng = -80.1918;
    region = 'Miami-Dade County, Florida';
    corridor = 'Southeast Maritime Logistics Hub';
  } else if (nameLower.includes('austin') || nameLower.includes('texas')) {
    lat = 30.2672;
    lng = -97.7431;
    region = 'Central Texas Interstate Corridor';
    corridor = 'Texas Triangle Economic Basin';
  } else if (nameLower.includes('seattle')) {
    lat = 47.6062;
    lng = -122.3321;
    region = 'Puget Sound, Washington';
    corridor = 'Cascadia Technology & Port Corridor';
  } else if (nameLower.includes('philadelphia')) {
    lat = 39.9526;
    lng = -75.1652;
    region = 'Delaware Valley, Pennsylvania';
    corridor = 'Mid-Atlantic Industrial Basin';
  } else if (nameLower.includes('italy')) {
    lat = 41.8719;
    lng = 12.5674;
    region = 'Southern Europe / Mediterranean';
    corridor = 'Eurozone Mediterranean Corridor';
  } else if (nameLower.includes('nigeria')) {
    lat = 9.0820;
    lng = 8.6753;
    region = 'West Africa / ECOWAS';
    corridor = 'Gulf of Guinea Hydrocarbon Hub';
  } else if (nameLower.includes('argentina')) {
    lat = -38.4161;
    lng = -63.6167;
    region = 'Southern Cone / South America';
    corridor = 'Pampas Agribusiness Basin';
  }

  // Generate 4-5 realistic surrounding neighbors for custom or dynamic entity
  const defaultNeighbors: NeighborEntity[] = [
    {
      id: `${entity.id}-nbr-1`,
      name: `${entity.name.split(' ')[0]} Regional Authority`,
      tier: 'municipal',
      creditRating: 'AA',
      ratingOutlook: 'Stable',
      fiscalStressScore: Math.max(15, Math.min(85, entity.marketAccessStressScore - 8)),
      totalDebtMillions: Math.round(entity.totalDirectDebtMillions * 0.45),
      latitude: lat + 0.18,
      longitude: lng - 0.22,
      distanceMiles: 16,
      bearing: 'NW',
      contagionExposure: 'High',
      relationshipType: 'Overlapping Regional District',
      relationshipDescription: 'Shares utility trunk infrastructure and co-dependent tax assessments.',
      isTerminalEntity: false,
    },
    {
      id: `${entity.id}-nbr-2`,
      name: `Adjacent Metro Sub-District`,
      tier: 'municipal',
      creditRating: 'A+',
      ratingOutlook: 'Stable',
      fiscalStressScore: Math.max(20, Math.min(90, entity.marketAccessStressScore + 5)),
      totalDebtMillions: Math.round(entity.totalDirectDebtMillions * 0.28),
      latitude: lat - 0.24,
      longitude: lng + 0.15,
      distanceMiles: 21,
      bearing: 'SE',
      contagionExposure: 'Medium',
      relationshipType: 'Bordering Municipal Entity',
      relationshipDescription: 'Interconnected commuter transit lines and shared sales tax collections.',
      isTerminalEntity: false,
    },
    {
      id: `${entity.id}-nbr-3`,
      name: `Parent Subnational / State Jurisdiction`,
      tier: 'subnational',
      creditRating: 'AA-',
      ratingOutlook: 'Stable',
      fiscalStressScore: Math.max(20, Math.min(80, entity.marketAccessStressScore - 12)),
      totalDebtMillions: Math.round(entity.totalDirectDebtMillions * 2.8),
      latitude: lat + 0.85,
      longitude: lng + 0.95,
      distanceMiles: 92,
      bearing: 'NE',
      contagionExposure: 'Critical',
      relationshipType: 'Statutory Parent Sovereign/State',
      relationshipDescription: 'Direct statutory revenue sharing formulas, bond covenants, and budget intercept statutes.',
      isTerminalEntity: false,
    },
    {
      id: `${entity.id}-nbr-4`,
      name: `Interstate / Regional Port Corridor`,
      tier: 'municipal',
      creditRating: 'AAA',
      ratingOutlook: 'Stable',
      fiscalStressScore: 18,
      totalDebtMillions: Math.round(entity.totalDirectDebtMillions * 0.65),
      latitude: lat - 0.65,
      longitude: lng - 0.72,
      distanceMiles: 68,
      bearing: 'SW',
      contagionExposure: 'Low',
      relationshipType: 'Intermodal Freight Connector',
      relationshipDescription: 'Key multimodal freight terminal linking regional supply chains.',
      isTerminalEntity: false,
    },
  ];

  return {
    entityId: entity.id,
    canonicalName: entity.name,
    latitude: lat,
    longitude: lng,
    regionName: region,
    corridorName: corridor,
    zoomLevel: 9,
    neighbors: defaultNeighbors,
  };
};
