import React, { useState, useMemo } from 'react';
import { PublicFinanceEntity } from '../types/finance';
import {
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  TrendingDown,
  Scale,
  Coins,
  Building2,
  Activity,
  Layers,
  ChevronRight,
  Info,
  SlidersHorizontal,
  Users,
  Target
} from 'lucide-react';

export interface FiscalRadarMetric {
  id: 'solvency' | 'liquidity' | 'dscr' | 'pension' | 'marketAccess';
  label: string;
  shortLabel: string;
  description: string;
  unit: string;
  higherIsBetter: boolean;
  getEntityRawValue: (e: PublicFinanceEntity) => number;
  formatRawValue: (val: number) => string;
  getNormalizedScore: (e: PublicFinanceEntity) => number; // 0 to 100
}

export const FISCAL_METRICS_CONFIG: FiscalRadarMetric[] = [
  {
    id: 'solvency',
    label: 'Debt Solvency & Leverage',
    shortLabel: 'Solvency',
    description: 'Direct debt obligation relative to annual operating budget or GDP scale. Lower debt burden indicates greater balance sheet headroom.',
    unit: '% of Budget',
    higherIsBetter: true,
    getEntityRawValue: (e) => {
      const budgetMillions = e.gdpOrBudgetBillions * 1000;
      if (budgetMillions <= 0) return 0;
      return (e.totalDirectDebtMillions / budgetMillions) * 100;
    },
    formatRawValue: (val) => `${val.toFixed(1)}%`,
    getNormalizedScore: (e) => {
      const budgetMillions = e.gdpOrBudgetBillions * 1000;
      const debtRatio = (e.totalDirectDebtMillions / Math.max(1, budgetMillions)) * 100;
      // Lower debt ratio is healthier: 15% -> 95 score, 70% -> 55 score, 150%+ -> 15 score
      const score = Math.max(10, Math.min(100, 105 - (debtRatio * 0.70)));
      return Math.round(score * 10) / 10;
    },
  },
  {
    id: 'liquidity',
    label: 'Cash Reserves & Liquidity',
    shortLabel: 'Liquidity',
    description: 'Unrestricted cash and liquid reserves measured in days of operating expenditures or external coverage cushion.',
    unit: 'Days',
    higherIsBetter: true,
    getEntityRawValue: (e) => {
      if (e.municipalMetrics?.liquidityDaysOfCash) {
        return e.municipalMetrics.liquidityDaysOfCash;
      }
      if (e.subnationalMetrics?.rainyDayFundReserveMonths) {
        return Math.round(e.subnationalMetrics.rainyDayFundReserveMonths * 30.5);
      }
      if (e.sovereignMetrics?.greenspanGuidottiRatio) {
        // Greenspan-Guidotti rule: 1.0 ratio = 90 days FX coverage
        return Math.round(e.sovereignMetrics.greenspanGuidottiRatio * 90);
      }
      return 60;
    },
    formatRawValue: (val) => `${Math.round(val)}d`,
    getNormalizedScore: (e) => {
      let days = 60;
      if (e.municipalMetrics?.liquidityDaysOfCash) {
        days = e.municipalMetrics.liquidityDaysOfCash;
      } else if (e.subnationalMetrics?.rainyDayFundReserveMonths) {
        days = e.subnationalMetrics.rainyDayFundReserveMonths * 30.5;
      } else if (e.sovereignMetrics?.greenspanGuidottiRatio) {
        days = e.sovereignMetrics.greenspanGuidottiRatio * 90;
      }
      // 30 days = 25, 60 days = 50, 90 days = 70, 180+ days = 95
      const score = Math.max(10, Math.min(100, 15 + (days / 180) * 80));
      return Math.round(score * 10) / 10;
    },
  },
  {
    id: 'dscr',
    label: 'Debt Service Coverage (DSCR)',
    shortLabel: 'DSCR Margin',
    description: 'Operating revenues available to satisfy annual principal & interest debt service covenants without distress.',
    unit: 'x Coverage',
    higherIsBetter: true,
    getEntityRawValue: (e) => {
      if (e.municipalMetrics?.dscrCoverage) {
        return e.municipalMetrics.dscrCoverage;
      }
      if (e.subnationalMetrics) {
        // Subnational proxy: based on transfer dependence & Medicaid burdens
        const proxy = 1.65 - (e.subnationalMetrics.transferDependenceRatio * 0.6);
        return Math.max(1.05, proxy);
      }
      if (e.sovereignMetrics) {
        // Sovereign proxy: primary balance impact on debt service
        const proxy = 1.35 + (e.sovereignMetrics.primaryBalancePctGdp * 0.08);
        return Math.max(0.9, proxy);
      }
      return 1.30;
    },
    formatRawValue: (val) => `${val.toFixed(2)}x`,
    getNormalizedScore: (e) => {
      let dscr = 1.30;
      if (e.municipalMetrics?.dscrCoverage) {
        dscr = e.municipalMetrics.dscrCoverage;
      } else if (e.subnationalMetrics) {
        dscr = 1.65 - (e.subnationalMetrics.transferDependenceRatio * 0.6);
      } else if (e.sovereignMetrics) {
        dscr = 1.35 + (e.sovereignMetrics.primaryBalancePctGdp * 0.08);
      }
      // DSCR: 1.0x -> 30, 1.25x -> 55, 1.50x -> 75, 2.0x+ -> 95
      const score = Math.max(10, Math.min(100, ((dscr - 0.8) / 1.3) * 80 + 15));
      return Math.round(score * 10) / 10;
    },
  },
  {
    id: 'pension',
    label: 'Pension & OPEB Balance Sheet Health',
    shortLabel: 'Pension Health',
    description: 'Actuarial funded ratio of pension and post-employment medical liabilities under GASB 67/68 and actuarial accounting.',
    unit: '% Funded',
    higherIsBetter: true,
    getEntityRawValue: (e) => {
      if (e.pensionOpeb?.fundedRatio) {
        return e.pensionOpeb.fundedRatio;
      }
      if (e.subnationalMetrics?.pensionFundedRatio) {
        return e.subnationalMetrics.pensionFundedRatio;
      }
      return 68.0;
    },
    formatRawValue: (val) => `${val.toFixed(1)}%`,
    getNormalizedScore: (e) => {
      let funded = 68.0;
      if (e.pensionOpeb?.fundedRatio) {
        funded = e.pensionOpeb.fundedRatio;
      } else if (e.subnationalMetrics?.pensionFundedRatio) {
        funded = e.subnationalMetrics.pensionFundedRatio;
      }
      // Funded Ratio: 20% -> 18, 50% -> 48, 75% -> 76, 95%+ -> 96
      const score = Math.max(10, Math.min(100, (funded / 100) * 88 + 8));
      return Math.round(score * 10) / 10;
    },
  },
  {
    id: 'marketAccess',
    label: 'Market Access & Refinancing Resilience',
    shortLabel: 'Market Access',
    description: 'Inverted sovereign/municipal rollover stress index factoring in duration gap, liquidity spreads, and investor access.',
    unit: 'Index (0-100)',
    higherIsBetter: true,
    getEntityRawValue: (e) => {
      return 100 - e.marketAccessStressScore;
    },
    formatRawValue: (val) => `${Math.round(val)}/100`,
    getNormalizedScore: (e) => {
      const score = Math.max(10, Math.min(100, 100 - e.marketAccessStressScore));
      return Math.round(score * 10) / 10;
    },
  },
];

interface PeerRadarComparisonProps {
  entity: PublicFinanceEntity;
  allEntities?: PublicFinanceEntity[];
  onOpenFormulaModal?: () => void;
}

export const PeerRadarComparison: React.FC<PeerRadarComparisonProps> = ({
  entity,
  allEntities = [],
  onOpenFormulaModal,
}) => {
  // Benchmark mode: 'tier' (same tier), 'rating' (same rating band), 'all' (entire universe), or 'head-to-head' (specific entity)
  const [benchmarkMode, setBenchmarkMode] = useState<'tier' | 'rating' | 'all' | 'custom-entity'>('tier');
  const [customPeerId, setCustomPeerId] = useState<string>('');
  const [hoveredMetricId, setHoveredMetricId] = useState<string | null>(null);

  // Entities universe: combine passed allEntities or fall back to at least selected entity
  const entityUniverse = useMemo(() => {
    if (allEntities && allEntities.length > 0) {
      return allEntities;
    }
    return [entity];
  }, [allEntities, entity]);

  // Determine peer entities based on chosen benchmarkMode
  const peerEntities = useMemo(() => {
    if (benchmarkMode === 'tier') {
      const filtered = entityUniverse.filter((e) => e.tier === entity.tier && e.id !== entity.id);
      return filtered.length > 0 ? filtered : entityUniverse.filter((e) => e.tier === entity.tier);
    }
    if (benchmarkMode === 'rating') {
      const entityRatingPrefix = entity.creditRating.replace(/[^A-Za-z]/g, '').slice(0, 2);
      const filtered = entityUniverse.filter(
        (e) => e.creditRating.startsWith(entityRatingPrefix) && e.id !== entity.id
      );
      return filtered.length > 0 ? filtered : entityUniverse;
    }
    if (benchmarkMode === 'custom-entity') {
      const selected = entityUniverse.find((e) => e.id === customPeerId);
      return selected ? [selected] : entityUniverse.filter((e) => e.id !== entity.id);
    }
    // 'all'
    const filtered = entityUniverse.filter((e) => e.id !== entity.id);
    return filtered.length > 0 ? filtered : entityUniverse;
  }, [benchmarkMode, customPeerId, entityUniverse, entity]);

  // Set default custom peer if none selected
  const availablePeers = useMemo(() => {
    return entityUniverse.filter((e) => e.id !== entity.id);
  }, [entityUniverse, entity.id]);

  const activeCustomPeer = useMemo(() => {
    if (benchmarkMode === 'custom-entity') {
      return entityUniverse.find((e) => e.id === customPeerId) || availablePeers[0];
    }
    return null;
  }, [benchmarkMode, customPeerId, entityUniverse, availablePeers]);

  // Compute metric scores & averages
  const comparisonData = useMemo(() => {
    return FISCAL_METRICS_CONFIG.map((metric) => {
      const entityScore = metric.getNormalizedScore(entity);
      const entityRaw = metric.getEntityRawValue(entity);

      let peerScore: number;
      let peerRaw: number;

      if (benchmarkMode === 'custom-entity' && activeCustomPeer) {
        peerScore = metric.getNormalizedScore(activeCustomPeer);
        peerRaw = metric.getEntityRawValue(activeCustomPeer);
      } else {
        const scores = peerEntities.map((p) => metric.getNormalizedScore(p));
        const rawValues = peerEntities.map((p) => metric.getEntityRawValue(p));

        peerScore =
          scores.length > 0
            ? Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 10) / 10
            : entityScore;

        peerRaw =
          rawValues.length > 0
            ? rawValues.reduce((a, b) => a + b, 0) / rawValues.length
            : entityRaw;
      }

      const scoreDelta = Math.round((entityScore - peerScore) * 10) / 10;
      const isOutperforming = scoreDelta >= 0;

      return {
        metric,
        entityScore,
        entityRaw,
        peerScore,
        peerRaw,
        scoreDelta,
        isOutperforming,
      };
    });
  }, [entity, peerEntities, benchmarkMode, activeCustomPeer]);

  // Composite Fiscal Index (0-100 mean across the 5 dimensions)
  const compositeEntityScore = useMemo(() => {
    const sum = comparisonData.reduce((acc, curr) => acc + curr.entityScore, 0);
    return Math.round((sum / comparisonData.length) * 10) / 10;
  }, [comparisonData]);

  const compositePeerScore = useMemo(() => {
    const sum = comparisonData.reduce((acc, curr) => acc + curr.peerScore, 0);
    return Math.round((sum / comparisonData.length) * 10) / 10;
  }, [comparisonData]);

  const compositeDelta = Math.round((compositeEntityScore - compositePeerScore) * 10) / 10;

  // Strongest and weakest vectors
  const sortedByDelta = useMemo(() => {
    return [...comparisonData].sort((a, b) => b.scoreDelta - a.scoreDelta);
  }, [comparisonData]);

  const topStrength = sortedByDelta[0];
  const topVulnerability = sortedByDelta[sortedByDelta.length - 1];

  // SVG Geometry calculations for 5-axis Radar
  const size = 360;
  const center = size / 2;
  const radius = 120;
  const numAxes = FISCAL_METRICS_CONFIG.length; // 5

  // Calculate coordinates for an angle and radius
  const getCoordinates = (index: number, valueScore: number) => {
    // 0 index starts at top (-PI/2), then steps clockwise: 2*PI / 5
    const angle = (index * 2 * Math.PI) / numAxes - Math.PI / 2;
    const r = (valueScore / 100) * radius;
    const x = center + r * Math.cos(angle);
    const y = center + r * Math.sin(angle);
    return { x, y, angle };
  };

  // Concentric polygon grids (20, 40, 60, 80, 100)
  const gridLevels = [20, 40, 60, 80, 100];
  const gridPolygons = gridLevels.map((level) => {
    const points = Array.from({ length: numAxes }).map((_, i) => {
      const { x, y } = getCoordinates(i, level);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    return { level, points };
  });

  // Entity polygon points
  const entityPoints = comparisonData.map((d, i) => {
    const { x, y } = getCoordinates(i, d.entityScore);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  // Peer polygon points
  const peerPoints = comparisonData.map((d, i) => {
    const { x, y } = getCoordinates(i, d.peerScore);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  // Peer label title
  const peerGroupTitle = useMemo(() => {
    if (benchmarkMode === 'custom-entity' && activeCustomPeer) {
      return activeCustomPeer.name;
    }
    if (benchmarkMode === 'tier') {
      const tierLabel =
        entity.tier === 'municipal' ? 'US Municipal Tier' :
        entity.tier === 'subnational' ? 'Subnational States' : 'Sovereign Debtors';
      return `${tierLabel} Average (n=${peerEntities.length})`;
    }
    if (benchmarkMode === 'rating') {
      return `Rating Band [${entity.creditRating.slice(0, 2)}] Peer Avg (n=${peerEntities.length})`;
    }
    return `Global Terminal Universe Avg (n=${peerEntities.length})`;
  }, [benchmarkMode, activeCustomPeer, entity.tier, entity.creditRating, peerEntities.length]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden p-5 space-y-6">
      {/* Header Strip with Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <Scale className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-bold tracking-tight text-slate-100 uppercase">
              Cross-Sectional Peer Benchmark Radar & Fiscal Metrics Scorecard
            </h3>
            <span className="px-2 py-0.5 text-[10px] font-mono font-semibold bg-cyan-950 text-cyan-400 border border-cyan-800/60 rounded">
              5-Axis Radar
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Multivariate balance-sheet benchmarking comparing <span className="text-slate-200 font-semibold">{entity.name}</span> against comparative peer groups across five key public finance stress dimensions.
          </p>
        </div>

        {/* Peer Benchmark Switcher */}
        <div className="flex items-center flex-wrap gap-2 text-xs">
          <span className="text-slate-400 flex items-center gap-1">
            <SlidersHorizontal className="w-3.5 h-3.5 text-slate-500" />
            <span>Benchmark:</span>
          </span>

          <div className="inline-flex rounded-md bg-slate-950 p-0.5 border border-slate-800">
            <button
              onClick={() => setBenchmarkMode('tier')}
              className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                benchmarkMode === 'tier'
                  ? 'bg-cyan-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Same Tier ({entity.tier})
            </button>
            <button
              onClick={() => setBenchmarkMode('rating')}
              className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                benchmarkMode === 'rating'
                  ? 'bg-cyan-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Rating Band ({entity.creditRating.slice(0, 2)})
            </button>
            <button
              onClick={() => setBenchmarkMode('all')}
              className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                benchmarkMode === 'all'
                  ? 'bg-cyan-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All Universe
            </button>
            <button
              onClick={() => {
                setBenchmarkMode('custom-entity');
                if (!customPeerId && availablePeers.length > 0) {
                  setCustomPeerId(availablePeers[0].id);
                }
              }}
              className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                benchmarkMode === 'custom-entity'
                  ? 'bg-cyan-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              1-on-1 Overlay
            </button>
          </div>

          {/* If 1-on-1 Overlay selected, show dropdown */}
          {benchmarkMode === 'custom-entity' && availablePeers.length > 0 && (
            <select
              value={customPeerId || availablePeers[0].id}
              onChange={(e) => setCustomPeerId(e.target.value)}
              className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded px-2.5 py-1 focus:outline-hidden focus:border-cyan-500 font-mono"
            >
              {availablePeers.map((p) => (
                <option key={p.id} value={p.id}>
                  vs. {p.name} ({p.creditRating})
                </option>
              ))}
            </select>
          )}

          {onOpenFormulaModal && (
            <button
              onClick={onOpenFormulaModal}
              title="View Normalization & Radar Methodology"
              className="p-1 text-slate-400 hover:text-cyan-300 transition-colors ml-1"
            >
              <Info className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Main Grid: Radar Chart Visual (Left) + Detailed Scorecard Matrix (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
        {/* Left Column: Interactive Radar Canvas */}
        <div className="lg:col-span-5 flex flex-col items-center justify-center p-3 bg-slate-950/70 border border-slate-800/80 rounded-lg relative">
          {/* Radar Chart SVG */}
          <div className="relative w-full max-w-[360px] aspect-square flex items-center justify-center">
            <svg
              viewBox={`0 0 ${size} ${size}`}
              className="w-full h-full overflow-visible select-none"
            >
              <defs>
                {/* Radial Gradient for Selected Entity */}
                <radialGradient id="entityRadarGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.45" />
                  <stop offset="70%" stopColor="#0891b2" stopOpacity="0.20" />
                  <stop offset="100%" stopColor="#0e7490" stopOpacity="0.05" />
                </radialGradient>

                {/* Radial Gradient for Peer Benchmark */}
                <radialGradient id="peerRadarGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.30" />
                  <stop offset="70%" stopColor="#d97706" stopOpacity="0.12" />
                  <stop offset="100%" stopColor="#b45309" stopOpacity="0.02" />
                </radialGradient>

                {/* Filter for glowing vertex circles */}
                <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="2" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* Concentric Reference Grid Rings (Pentagons) */}
              {gridPolygons.map(({ level, points }) => (
                <g key={`grid-${level}`}>
                  <polygon
                    points={points}
                    fill={level === 100 ? 'rgba(15, 23, 42, 0.4)' : 'none'}
                    stroke={level === 100 ? '#334155' : '#1e293b'}
                    strokeWidth={level === 100 ? '1.5' : '1'}
                    strokeDasharray={level % 40 === 0 ? undefined : '2 2'}
                  />
                  {/* Subtle level label on top-vertical axis */}
                  <text
                    x={center + 4}
                    y={center - (level / 100) * radius + 3}
                    className="text-[9px] fill-slate-600 font-mono select-none"
                  >
                    {level}
                  </text>
                </g>
              ))}

              {/* Radial Axis Spokes */}
              {FISCAL_METRICS_CONFIG.map((metric, i) => {
                const { x, y } = getCoordinates(i, 100);
                const isHovered = hoveredMetricId === metric.id;
                return (
                  <line
                    key={`spoke-${metric.id}`}
                    x1={center}
                    y1={center}
                    x2={x}
                    y2={y}
                    stroke={isHovered ? '#38bdf8' : '#334155'}
                    strokeWidth={isHovered ? '2' : '1'}
                    strokeDasharray={isHovered ? undefined : '3 3'}
                    className="transition-all duration-200"
                  />
                );
              })}

              {/* Peer Benchmark Polygon (Amber/Gold) */}
              <polygon
                points={peerPoints}
                fill="url(#peerRadarGlow)"
                stroke="#f59e0b"
                strokeWidth="2"
                strokeDasharray="4 3"
                className="transition-all duration-300"
              />

              {/* Selected Entity Polygon (Cyan/Teal) */}
              <polygon
                points={entityPoints}
                fill="url(#entityRadarGlow)"
                stroke="#06b6d4"
                strokeWidth="2.5"
                className="transition-all duration-300 drop-shadow-sm"
              />

              {/* Peer Benchmark Vertex Points */}
              {comparisonData.map((d, i) => {
                const { x, y } = getCoordinates(i, d.peerScore);
                const isHovered = hoveredMetricId === d.metric.id;
                return (
                  <circle
                    key={`peer-pt-${d.metric.id}`}
                    cx={x}
                    cy={y}
                    r={isHovered ? 5.5 : 3.5}
                    fill="#f59e0b"
                    stroke="#78350f"
                    strokeWidth="1.5"
                    className="transition-all duration-200 cursor-pointer"
                    onMouseEnter={() => setHoveredMetricId(d.metric.id)}
                    onMouseLeave={() => setHoveredMetricId(null)}
                  />
                );
              })}

              {/* Selected Entity Vertex Points */}
              {comparisonData.map((d, i) => {
                const { x, y } = getCoordinates(i, d.entityScore);
                const isHovered = hoveredMetricId === d.metric.id;
                return (
                  <g key={`entity-pt-${d.metric.id}`}>
                    {isHovered && (
                      <circle
                        cx={x}
                        cy={y}
                        r="10"
                        fill="rgba(6, 182, 212, 0.3)"
                        className="animate-ping"
                      />
                    )}
                    <circle
                      cx={x}
                      cy={y}
                      r={isHovered ? 6.5 : 4.5}
                      fill="#06b6d4"
                      stroke="#082f49"
                      strokeWidth="2"
                      filter="url(#glow)"
                      className="transition-all duration-200 cursor-pointer"
                      onMouseEnter={() => setHoveredMetricId(d.metric.id)}
                      onMouseLeave={() => setHoveredMetricId(null)}
                    />
                  </g>
                );
              })}

              {/* Metric Axis Outer Labels */}
              {FISCAL_METRICS_CONFIG.map((metric, i) => {
                const labelRadius = radius + 26;
                const angle = (i * 2 * Math.PI) / numAxes - Math.PI / 2;
                const lx = center + labelRadius * Math.cos(angle);
                const ly = center + labelRadius * Math.sin(angle);
                const isHovered = hoveredMetricId === metric.id;

                let textAnchor: 'middle' | 'start' | 'end' = 'middle';
                if (Math.cos(angle) > 0.3) textAnchor = 'start';
                else if (Math.cos(angle) < -0.3) textAnchor = 'end';

                return (
                  <g
                    key={`label-${metric.id}`}
                    className="cursor-pointer"
                    onMouseEnter={() => setHoveredMetricId(metric.id)}
                    onMouseLeave={() => setHoveredMetricId(null)}
                  >
                    <text
                      x={lx}
                      y={ly}
                      textAnchor={textAnchor}
                      dominantBaseline="central"
                      className={`text-[11px] font-mono transition-colors duration-150 ${
                        isHovered
                          ? 'fill-cyan-300 font-bold'
                          : 'fill-slate-300 font-medium'
                      }`}
                    >
                      {metric.shortLabel}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Legend Strip below Radar */}
          <div className="w-full flex items-center justify-between text-xs px-2 pt-3 border-t border-slate-800/80 font-mono">
            <div className="flex items-center gap-2">
              <span className="w-3.5 h-1.5 bg-cyan-400 rounded-xs shadow-xs" />
              <span className="text-slate-200 font-medium truncate max-w-[140px]">
                {entity.name}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="w-3.5 h-1.5 bg-amber-400 rounded-xs border-dashed" />
              <span className="text-amber-300 font-medium truncate max-w-[160px]" title={peerGroupTitle}>
                {benchmarkMode === 'custom-entity' && activeCustomPeer
                  ? activeCustomPeer.name
                  : 'Peer Group Avg'}
              </span>
            </div>
          </div>
        </div>

        {/* Right Column: Comparative Metrics Matrix & Analytical Breakdown */}
        <div className="lg:col-span-7 space-y-4">
          {/* Top KPI Cards: Composite Index, Top Strength, and Vulnerability */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* Composite Fiscal Health */}
            <div className="p-3 bg-slate-950 border border-slate-800 rounded">
              <div className="text-[11px] text-slate-400 mb-1 flex items-center justify-between">
                <span>Fiscal Resilience Index</span>
                <Target className="w-3.5 h-3.5 text-cyan-400" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-xl font-bold font-mono tabular-nums text-slate-100">
                  {compositeEntityScore}
                </span>
                <span className="text-xs text-slate-500 font-mono">/ 100</span>
                <span className={`text-xs font-mono font-semibold tabular-nums ml-auto ${
                  compositeDelta >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}>
                  {compositeDelta >= 0 ? `+${compositeDelta}` : compositeDelta} vs Peer
                </span>
              </div>
              <div className="text-[10px] text-slate-500 mt-1 truncate">
                Peer Baseline: {compositePeerScore} / 100
              </div>
            </div>

            {/* Top Relative Outperformer */}
            <div className="p-3 bg-slate-950 border border-slate-800 rounded">
              <div className="text-[11px] text-slate-400 mb-1 flex items-center justify-between">
                <span>Top Relative Strength</span>
                <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div className="text-xs font-bold text-slate-100 truncate">
                {topStrength.metric.shortLabel}
              </div>
              <div className="text-xs font-mono text-emerald-400 font-semibold mt-1">
                +{topStrength.scoreDelta > 0 ? topStrength.scoreDelta : 0} pts advantage
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5 font-mono">
                {topStrength.metric.formatRawValue(topStrength.entityRaw)} vs {topStrength.metric.formatRawValue(topStrength.peerRaw)}
              </div>
            </div>

            {/* Top Relative Drag */}
            <div className="p-3 bg-slate-950 border border-slate-800 rounded">
              <div className="text-[11px] text-slate-400 mb-1 flex items-center justify-between">
                <span>Primary Risk Vector</span>
                <TrendingDown className="w-3.5 h-3.5 text-rose-400" />
              </div>
              <div className="text-xs font-bold text-slate-100 truncate">
                {topVulnerability.metric.shortLabel}
              </div>
              <div className={`text-xs font-mono font-semibold mt-1 ${
                topVulnerability.scoreDelta < 0 ? 'text-rose-400' : 'text-slate-300'
              }`}>
                {topVulnerability.scoreDelta < 0 ? `${topVulnerability.scoreDelta} pts deficit` : 'In-line parity'}
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5 font-mono">
                {topVulnerability.metric.formatRawValue(topVulnerability.entityRaw)} vs {topVulnerability.metric.formatRawValue(topVulnerability.peerRaw)}
              </div>
            </div>
          </div>

          {/* 5-Metric Comparative Table */}
          <div className="border border-slate-800 rounded overflow-hidden">
            <div className="bg-slate-950 px-3.5 py-2 border-b border-slate-800 flex items-center justify-between text-[11px] font-mono text-slate-400 uppercase">
              <span>Metric & Definition</span>
              <div className="flex items-center gap-6">
                <span className="w-20 text-right text-cyan-300">{entity.name}</span>
                <span className="w-20 text-right text-amber-300">Peer Group</span>
                <span className="w-16 text-right">Variance</span>
              </div>
            </div>

            <div className="divide-y divide-slate-800/80 bg-slate-900/60">
              {comparisonData.map((d) => {
                const isHovered = hoveredMetricId === d.metric.id;
                return (
                  <div
                    key={d.metric.id}
                    onMouseEnter={() => setHoveredMetricId(d.metric.id)}
                    onMouseLeave={() => setHoveredMetricId(null)}
                    className={`px-3.5 py-2.5 transition-colors duration-150 cursor-pointer ${
                      isHovered ? 'bg-slate-800/70' : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-4">
                      {/* Metric info */}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-bold ${
                            isHovered ? 'text-cyan-300' : 'text-slate-200'
                          }`}>
                            {d.metric.label}
                          </span>
                          <span className="text-[10px] font-mono text-slate-500">
                            [{d.metric.unit}]
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-1">
                          {d.metric.description}
                        </p>
                      </div>

                      {/* Values */}
                      <div className="flex items-center gap-6 shrink-0 font-mono text-xs">
                        {/* Entity Value */}
                        <div className="w-20 text-right">
                          <div className="font-semibold text-slate-100 tabular-nums">
                            {d.metric.formatRawValue(d.entityRaw)}
                          </div>
                          <div className="text-[10px] text-cyan-400 tabular-nums">
                            Score: {d.entityScore}
                          </div>
                        </div>

                        {/* Peer Avg Value */}
                        <div className="w-20 text-right">
                          <div className="font-semibold text-slate-300 tabular-nums">
                            {d.metric.formatRawValue(d.peerRaw)}
                          </div>
                          <div className="text-[10px] text-amber-400 tabular-nums">
                            Score: {d.peerScore}
                          </div>
                        </div>

                        {/* Delta Badge */}
                        <div className="w-16 text-right">
                          <span className={`inline-block px-1.5 py-0.5 text-[10px] font-bold rounded tabular-nums ${
                            d.scoreDelta > 3 ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-800/60' :
                            d.scoreDelta < -3 ? 'bg-rose-950/80 text-rose-400 border border-rose-800/60' :
                            'bg-slate-800 text-slate-300 border border-slate-700'
                          }`}>
                            {d.scoreDelta > 0 ? `+${d.scoreDelta}` : d.scoreDelta}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Comparative Visual Dual-Bar Slider */}
                    <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] font-mono">
                      {/* Entity Bar */}
                      <div className="flex items-center gap-2">
                        <span className="text-slate-500 w-12 truncate">{entity.name.split(' ')[0]}</span>
                        <div className="flex-1 bg-slate-950 h-1.5 rounded-full overflow-hidden border border-slate-800">
                          <div
                            className="bg-cyan-500 h-1.5 rounded-full transition-all duration-300"
                            style={{ width: `${Math.min(100, Math.max(5, d.entityScore))}%` }}
                          />
                        </div>
                      </div>

                      {/* Peer Bar */}
                      <div className="flex items-center gap-2">
                        <span className="text-slate-500 w-12 truncate">Peer Avg</span>
                        <div className="flex-1 bg-slate-950 h-1.5 rounded-full overflow-hidden border border-slate-800">
                          <div
                            className="bg-amber-500 h-1.5 rounded-full transition-all duration-300"
                            style={{ width: `${Math.min(100, Math.max(5, d.peerScore))}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Explanatory Footer Note */}
          <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono px-1">
            <span>
              Benchmarked against <span className="text-slate-400 font-semibold">{peerGroupTitle}</span>
            </span>
            <span>
              Scale normalized 0-100 (100 = Maximum Structural Resilience)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
