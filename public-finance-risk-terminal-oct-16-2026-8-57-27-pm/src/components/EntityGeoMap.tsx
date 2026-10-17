import React, { useState, useMemo } from 'react';
import { PublicFinanceEntity, GovernmentTier } from '../types/finance';
import {
  resolveEntityGeoProfile,
  NeighborEntity,
  getRatingColor,
  getStressScoreColor,
  getTierColor,
  getContagionColor,
} from '../data/entityGeoData';
import {
  MapPin,
  Compass,
  Layers,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  SlidersHorizontal,
  Activity,
  AlertTriangle,
  ArrowRight,
  Maximize2,
  Minimize2,
  Info,
  Building,
  Landmark,
  ShieldAlert,
  ShieldCheck,
  Eye,
  CheckCircle2
} from 'lucide-react';

export type MapColorMode = 'rating' | 'stress' | 'tier' | 'contagion';

interface EntityGeoMapProps {
  entity: PublicFinanceEntity;
  allEntities?: PublicFinanceEntity[];
  onSelectEntity?: (entity: PublicFinanceEntity) => void;
  onOpenFormulaModal?: () => void;
}

export const EntityGeoMap: React.FC<EntityGeoMapProps> = ({
  entity,
  allEntities = [],
  onSelectEntity,
  onOpenFormulaModal,
}) => {
  // Color coding mode
  const [colorMode, setColorMode] = useState<MapColorMode>('rating');

  // Map display toggles
  const [showContagionArcs, setShowContagionArcs] = useState<boolean>(true);
  const [showRangeRings, setShowRangeRings] = useState<boolean>(true);
  const [showLabels, setShowLabels] = useState<boolean>(true);

  // Pan and Zoom offsets
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [panOffset, setPanOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Selected neighbor for inspection
  const [selectedNeighborId, setSelectedNeighborId] = useState<string | null>(null);
  const [hoveredNeighborId, setHoveredNeighborId] = useState<string | null>(null);

  // Fullscreen expansion toggle
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  // Filter neighbors by tier
  const [tierFilter, setTierFilter] = useState<'all' | 'municipal' | 'subnational' | 'sovereign'>('all');

  // Resolve Geo Profile for active entity
  const geoProfile = useMemo(() => {
    return resolveEntityGeoProfile(entity, allEntities);
  }, [entity, allEntities]);

  // Filtered neighbors
  const filteredNeighbors = useMemo(() => {
    if (tierFilter === 'all') return geoProfile.neighbors;
    return geoProfile.neighbors.filter((n) => n.tier === tierFilter);
  }, [geoProfile.neighbors, tierFilter]);

  // Active selected neighbor
  const activeNeighbor = useMemo(() => {
    if (!selectedNeighborId) return null;
    return geoProfile.neighbors.find((n) => n.id === selectedNeighborId) || null;
  }, [selectedNeighborId, geoProfile.neighbors]);

  // Hovered neighbor
  const activeHoveredNeighbor = useMemo(() => {
    const id = hoveredNeighborId || selectedNeighborId;
    if (!id) return null;
    return geoProfile.neighbors.find((n) => n.id === id) || null;
  }, [hoveredNeighborId, selectedNeighborId, geoProfile.neighbors]);

  // SVG Canvas dimensions
  const svgWidth = 840;
  const svgHeight = 460;
  const centerX = svgWidth / 2;
  const centerY = svgHeight / 2;

  // Compute spatial bounding box and scale
  const spatialProjection = useMemo(() => {
    const allPoints = [
      { lat: geoProfile.latitude, lng: geoProfile.longitude },
      ...geoProfile.neighbors.map((n) => ({ lat: n.latitude, lng: n.longitude })),
    ];

    const lats = allPoints.map((p) => p.lat);
    const lngs = allPoints.map((p) => p.lng);

    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);

    const latSpan = Math.max(0.5, maxLat - minLat);
    const lngSpan = Math.max(0.5, maxLng - minLng);

    // Padding margin
    const paddingX = 90;
    const paddingY = 70;

    const scaleX = (svgWidth - paddingX * 2) / lngSpan;
    const scaleY = (svgHeight - paddingY * 2) / latSpan;
    const baseScale = Math.min(scaleX, scaleY);

    // Midpoint
    const midLat = (minLat + maxLat) / 2;
    const midLng = (minLng + maxLng) / 2;

    // Convert lat/lng to projected canvas coordinates
    const project = (lat: number, lng: number) => {
      // Standard Mercator-like planar offset relative to midpoint
      const cosLat = Math.cos((midLat * Math.PI) / 180);
      const x = centerX + (lng - midLng) * baseScale * cosLat * zoomLevel + panOffset.x;
      // Invert Y because latitude increases northward (up)
      const y = centerY - (lat - midLat) * baseScale * zoomLevel + panOffset.y;
      return { x, y };
    };

    return { project, baseScale, minLat, maxLat, minLng, maxLng, midLat, midLng };
  }, [geoProfile, zoomLevel, panOffset, svgWidth, svgHeight, centerX, centerY]);

  // Projected position of the central active entity
  const entityPos = spatialProjection.project(geoProfile.latitude, geoProfile.longitude);

  // Projected positions of all neighbors
  const projectedNeighbors = useMemo(() => {
    return filteredNeighbors.map((n) => {
      const pos = spatialProjection.project(n.latitude, n.longitude);
      return {
        ...n,
        x: pos.x,
        y: pos.y,
      };
    });
  }, [filteredNeighbors, spatialProjection]);

  // Color resolver helper for node based on active colorMode
  const getNodeColor = (target: {
    creditRating: string;
    fiscalStressScore: number;
    tier: GovernmentTier;
    contagionExposure?: string;
  }) => {
    if (colorMode === 'rating') {
      return getRatingColor(target.creditRating);
    }
    if (colorMode === 'stress') {
      return getStressScoreColor(target.fiscalStressScore);
    }
    if (colorMode === 'tier') {
      return getTierColor(target.tier);
    }
    // contagion
    return getContagionColor(target.contagionExposure || 'Medium');
  };

  // Center entity color
  const entityColor = getNodeColor({
    creditRating: entity.creditRating,
    fiscalStressScore: entity.marketAccessStressScore,
    tier: entity.tier,
    contagionExposure: 'Low',
  });

  // Reset Pan/Zoom
  const handleResetView = () => {
    setZoomLevel(1);
    setPanOffset({ x: 0, y: 0 });
    setSelectedNeighborId(null);
  };

  // Handle Drag / Panning
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPanOffset({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Concentric distance range rings around active entity
  const rangeRings = useMemo(() => {
    // Determine ring radii based on geographic span
    const maxDist = Math.max(...geoProfile.neighbors.map((n) => n.distanceMiles), 50);
    const ringDistances = maxDist > 500
      ? [250, 500, 1000]
      : maxDist > 150
      ? [50, 100, 200]
      : [15, 30, 60];

    return ringDistances.map((dist) => {
      // Approximate pixel radius using rough miles-to-degrees conversion (1 deg ≈ 69 miles)
      const degRadius = dist / 69;
      const pixelRadius = degRadius * spatialProjection.baseScale * zoomLevel;
      return { dist, pixelRadius };
    });
  }, [geoProfile.neighbors, spatialProjection.baseScale, zoomLevel]);

  return (
    <div
      className={`bg-slate-900 border border-slate-800 rounded-lg overflow-hidden transition-all duration-300 ${
        isFullscreen
          ? 'fixed inset-4 z-50 flex flex-col bg-slate-950/98 shadow-2xl border-cyan-500/50'
          : 'space-y-4 p-5'
      }`}
    >
      {/* Top Header & Geospatial Control Strip */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
              <Compass className="w-3.5 h-3.5" />
            </div>
            <h3 className="text-sm font-bold tracking-tight text-slate-100 uppercase">
              Geographic Location & Neighboring Entities Contagion Map
            </h3>
            <span className="px-2 py-0.5 text-[10px] font-mono font-semibold bg-cyan-950 text-cyan-400 border border-cyan-800/60 rounded">
              {geoProfile.latitude > 0 ? `${geoProfile.latitude.toFixed(4)}°N` : `${Math.abs(geoProfile.latitude).toFixed(4)}°S`},{' '}
              {geoProfile.longitude > 0 ? `${geoProfile.longitude.toFixed(4)}°E` : `${Math.abs(geoProfile.longitude).toFixed(4)}°W`}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Regional balance-sheet topography and fiscal contagion corridors connecting{' '}
            <span className="text-cyan-300 font-semibold">{entity.name}</span> with adjacent municipalities, overlapping counties, and neighboring jurisdictions.
          </p>
        </div>

        {/* Control Bar: Color Mode + View Options */}
        <div className="flex items-center flex-wrap gap-2 text-xs">
          {/* Color Mode Selector */}
          <div className="flex items-center gap-1.5 bg-slate-950 p-1 border border-slate-800 rounded">
            <span className="text-[11px] text-slate-400 px-1 font-medium flex items-center gap-1">
              <SlidersHorizontal className="w-3 h-3 text-slate-500" />
              <span>Color By:</span>
            </span>
            <button
              onClick={() => setColorMode('rating')}
              className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                colorMode === 'rating'
                  ? 'bg-cyan-600 text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Credit Rating
            </button>
            <button
              onClick={() => setColorMode('stress')}
              className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                colorMode === 'stress'
                  ? 'bg-cyan-600 text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Fiscal Stress
            </button>
            <button
              onClick={() => setColorMode('tier')}
              className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                colorMode === 'tier'
                  ? 'bg-cyan-600 text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Tier
            </button>
            <button
              onClick={() => setColorMode('contagion')}
              className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                colorMode === 'contagion'
                  ? 'bg-cyan-600 text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Contagion Risk
            </button>
          </div>

          {/* Toggle buttons */}
          <div className="flex items-center gap-1 bg-slate-950 p-1 border border-slate-800 rounded">
            <button
              onClick={() => setShowContagionArcs((prev) => !prev)}
              title="Toggle Contagion Arcs"
              className={`px-2 py-1 text-xs rounded transition-colors ${
                showContagionArcs ? 'bg-slate-800 text-cyan-300' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              Arcs
            </button>
            <button
              onClick={() => setShowRangeRings((prev) => !prev)}
              title="Toggle Distance Rings"
              className={`px-2 py-1 text-xs rounded transition-colors ${
                showRangeRings ? 'bg-slate-800 text-cyan-300' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              Rings
            </button>
            <button
              onClick={() => setShowLabels((prev) => !prev)}
              title="Toggle Labels"
              className={`px-2 py-1 text-xs rounded transition-colors ${
                showLabels ? 'bg-slate-800 text-cyan-300' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              Labels
            </button>
          </div>

          {/* Zoom & Fullscreen Controls */}
          <div className="flex items-center gap-1 bg-slate-950 p-1 border border-slate-800 rounded">
            <button
              onClick={() => setZoomLevel((z) => Math.min(3, z + 0.25))}
              title="Zoom In"
              className="p-1 text-slate-400 hover:text-slate-100 rounded hover:bg-slate-800"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setZoomLevel((z) => Math.max(0.6, z - 0.25))}
              title="Zoom Out"
              className="p-1 text-slate-400 hover:text-slate-100 rounded hover:bg-slate-800"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleResetView}
              title="Reset View"
              className="p-1 text-slate-400 hover:text-slate-100 rounded hover:bg-slate-800"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setIsFullscreen((f) => !f)}
              title={isFullscreen ? 'Exit Fullscreen' : 'Expand Fullscreen'}
              className="p-1 text-slate-400 hover:text-cyan-300 rounded hover:bg-slate-800"
            >
              {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Main Container: Interactive Map Canvas + Neighbor Inspector Sidebar */}
      <div className={`grid grid-cols-1 lg:grid-cols-12 gap-5 ${isFullscreen ? 'flex-1 p-5 min-h-0' : ''}`}>
        {/* Left Column (8 cols): Interactive Map Viewport */}
        <div className="lg:col-span-8 flex flex-col bg-slate-950 rounded-lg border border-slate-800 overflow-hidden relative">
          {/* Map Top Status Bar */}
          <div className="px-4 py-2 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between text-xs font-mono">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-slate-300 font-semibold">{geoProfile.regionName}</span>
              <span className="text-slate-600">·</span>
              <span className="text-slate-400">{geoProfile.corridorName}</span>
            </div>

            <div className="flex items-center gap-3 text-slate-500 text-[11px]">
              <span>Neighbors: {filteredNeighbors.length} detected</span>
              <span>Zoom: {Math.round(zoomLevel * 100)}%</span>
            </div>
          </div>

          {/* Interactive SVG Canvas */}
          <div
            className="flex-1 w-full min-h-[420px] relative select-none cursor-grab active:cursor-grabbing bg-[#020617] overflow-hidden"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <svg
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              className="w-full h-full overflow-visible"
            >
              <defs>
                {/* Radial gradient background */}
                <radialGradient id="mapVignette" cx="50%" cy="50%" r="60%">
                  <stop offset="0%" stopColor="#0f172a" stopOpacity="0.8" />
                  <stop offset="70%" stopColor="#020617" stopOpacity="0.95" />
                  <stop offset="100%" stopColor="#020617" stopOpacity="1" />
                </radialGradient>

                {/* Glowing beacon gradient for center entity */}
                <radialGradient id="beaconGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor={entityColor.hex} stopOpacity="0.5" />
                  <stop offset="50%" stopColor={entityColor.hex} stopOpacity="0.2" />
                  <stop offset="100%" stopColor={entityColor.hex} stopOpacity="0" />
                </radialGradient>

                {/* Arrow markers for contagion arcs */}
                <marker
                  id="arcArrow"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 8 5 L 0 9 z" fill="#38bdf8" fillOpacity="0.7" />
                </marker>
              </defs>

              {/* Background fill */}
              <rect width={svgWidth} height={svgHeight} fill="url(#mapVignette)" />

              {/* Coordinate Grid Lines (Lat/Long Graticule) */}
              {[-3, -2, -1, 0, 1, 2, 3].map((step) => {
                const yPos = centerY + step * 70 * zoomLevel + (panOffset.y % (70 * zoomLevel));
                const xPos = centerX + step * 100 * zoomLevel + (panOffset.x % (100 * zoomLevel));
                return (
                  <g key={`grid-line-${step}`}>
                    {yPos >= 0 && yPos <= svgHeight && (
                      <line
                        x1="0"
                        y1={yPos}
                        x2={svgWidth}
                        y2={yPos}
                        stroke="#1e293b"
                        strokeWidth="0.8"
                        strokeDasharray="4 6"
                      />
                    )}
                    {xPos >= 0 && xPos <= svgWidth && (
                      <line
                        x1={xPos}
                        y1="0"
                        x2={xPos}
                        y2={svgHeight}
                        stroke="#1e293b"
                        strokeWidth="0.8"
                        strokeDasharray="4 6"
                      />
                    )}
                  </g>
                );
              })}

              {/* Concentric Distance Rings around Active Entity */}
              {showRangeRings &&
                rangeRings.map(({ dist, pixelRadius }) => {
                  if (pixelRadius <= 0) return null;
                  return (
                    <g key={`range-ring-${dist}`}>
                      <circle
                        cx={entityPos.x}
                        cy={entityPos.y}
                        r={pixelRadius}
                        fill="none"
                        stroke="#334155"
                        strokeWidth="1"
                        strokeDasharray="3 4"
                        strokeOpacity="0.6"
                      />
                      <text
                        x={entityPos.x + pixelRadius + 4}
                        y={entityPos.y - 4}
                        fill="#64748b"
                        className="text-[9px] font-mono select-none"
                      >
                        {dist} mi
                      </text>
                    </g>
                  );
                })}

              {/* Contagion Corridor Arcs from Active Entity to Neighbors */}
              {showContagionArcs &&
                projectedNeighbors.map((n) => {
                  const isHovered = hoveredNeighborId === n.id || selectedNeighborId === n.id;
                  const nColor = getNodeColor(n);

                  // Calculate curved quadratic bezier path
                  const dx = n.x - entityPos.x;
                  const dy = n.y - entityPos.y;
                  // Perpendicular offset for curve
                  const cx = (entityPos.x + n.x) / 2 - dy * 0.15;
                  const cy = (entityPos.y + n.y) / 2 + dx * 0.15;

                  const pathD = `M ${entityPos.x} ${entityPos.y} Q ${cx} ${cy} ${n.x} ${n.y}`;

                  return (
                    <g key={`arc-${n.id}`}>
                      {/* Arc line */}
                      <path
                        d={pathD}
                        fill="none"
                        stroke={isHovered ? nColor.hex : '#334155'}
                        strokeWidth={isHovered ? 2.5 : 1.2}
                        strokeDasharray={isHovered ? undefined : '5 4'}
                        strokeOpacity={isHovered ? 0.95 : 0.55}
                        className="transition-all duration-200"
                      />

                      {/* Distance pill badge along the arc */}
                      <g transform={`translate(${cx}, ${cy})`}>
                        <rect
                          x="-22"
                          y="-9"
                          width="44"
                          height="18"
                          rx="4"
                          fill="#020617"
                          stroke={isHovered ? nColor.hex : '#1e293b'}
                          strokeWidth="1"
                        />
                        <text
                          x="0"
                          y="3"
                          textAnchor="middle"
                          fill={isHovered ? nColor.hex : '#94a3b8'}
                          className="text-[9px] font-mono font-medium select-none"
                        >
                          {n.distanceMiles}m
                        </text>
                      </g>
                    </g>
                  );
                })}

              {/* Neighboring Entity Nodes */}
              {projectedNeighbors.map((n) => {
                const isHovered = hoveredNeighborId === n.id || selectedNeighborId === n.id;
                const nColor = getNodeColor(n);
                const nodeRadius = isHovered ? 14 : 10;

                return (
                  <g
                    key={`node-${n.id}`}
                    transform={`translate(${n.x}, ${n.y})`}
                    className="cursor-pointer"
                    onMouseEnter={() => setHoveredNeighborId(n.id)}
                    onMouseLeave={() => setHoveredNeighborId(null)}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedNeighborId(n.id);
                    }}
                  >
                    {/* Pulsing ring on hover/selection */}
                    {isHovered && (
                      <circle
                        r={nodeRadius + 8}
                        fill="none"
                        stroke={nColor.hex}
                        strokeWidth="1.5"
                        strokeOpacity="0.5"
                        className="animate-ping"
                      />
                    )}

                    {/* Outer border circle */}
                    <circle
                      r={nodeRadius}
                      fill="#020617"
                      stroke={nColor.hex}
                      strokeWidth={isHovered ? 3 : 2}
                      className="transition-all duration-200"
                    />

                    {/* Inner core circle */}
                    <circle
                      r={nodeRadius - 3.5}
                      fill={nColor.hex}
                      fillOpacity={isHovered ? 0.9 : 0.75}
                      className="transition-all duration-200"
                    />

                    {/* Small inner label: rating or tier */}
                    <text
                      y="3.5"
                      textAnchor="middle"
                      fill="#020617"
                      className="text-[8px] font-mono font-bold select-none pointer-events-none"
                    >
                      {colorMode === 'rating'
                        ? n.creditRating.slice(0, 3)
                        : colorMode === 'stress'
                        ? Math.round(n.fiscalStressScore)
                        : n.tier[0].toUpperCase()}
                    </text>

                    {/* Entity Name Label */}
                    {showLabels && (
                      <g transform="translate(0, 22)">
                        <rect
                          x={-Math.min(90, n.name.length * 3.5)}
                          y="-10"
                          width={Math.min(180, n.name.length * 7)}
                          height="18"
                          rx="3"
                          fill="#090d16"
                          fillOpacity="0.88"
                          stroke={isHovered ? nColor.hex : '#1e293b'}
                          strokeWidth="1"
                        />
                        <text
                          y="2"
                          textAnchor="middle"
                          fill={isHovered ? '#ffffff' : '#cbd5e1'}
                          className={`text-[10px] font-mono select-none ${
                            isHovered ? 'font-bold' : 'font-medium'
                          }`}
                        >
                          {n.name.length > 22 ? `${n.name.slice(0, 20)}...` : n.name}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}

              {/* Selected Entity Node (Beacon at Center) */}
              <g
                transform={`translate(${entityPos.x}, ${entityPos.y})`}
                className="select-none pointer-events-none"
              >
                {/* Large radiant beacon glow */}
                <circle r="45" fill="url(#beaconGlow)" />

                {/* Animated pulsating outer ring */}
                <circle
                  r="26"
                  fill="none"
                  stroke={entityColor.hex}
                  strokeWidth="2"
                  strokeOpacity="0.4"
                  className="animate-ping"
                />

                {/* Secondary ring */}
                <circle
                  r="18"
                  fill="#020617"
                  stroke={entityColor.hex}
                  strokeWidth="3.5"
                />

                {/* Primary core beacon */}
                <circle
                  r="11"
                  fill={entityColor.hex}
                  className="drop-shadow-lg"
                />

                <MapPin className="w-4 h-4 text-slate-950 -translate-x-2 -translate-y-2 pointer-events-none" />

                {/* Prominent Label for Central Entity */}
                <g transform="translate(0, -28)">
                  <rect
                    x={-Math.min(110, entity.name.length * 4.2)}
                    y="-13"
                    width={Math.min(220, entity.name.length * 8.4)}
                    height="22"
                    rx="4"
                    fill="#020617"
                    stroke={entityColor.hex}
                    strokeWidth="1.5"
                    className="shadow-md"
                  />
                  <text
                    y="2"
                    textAnchor="middle"
                    fill="#38bdf8"
                    className="text-[11px] font-mono font-bold select-none"
                  >
                    ★ {entity.name}
                  </text>
                </g>
              </g>
            </svg>

            {/* Float Overlay Indicator for Hovered Neighbor */}
            {activeHoveredNeighbor && (
              <div className="absolute bottom-3 left-3 bg-slate-950/95 border border-slate-700/80 rounded-md p-3 text-xs shadow-xl backdrop-blur-md pointer-events-none max-w-xs space-y-1">
                <div className="flex items-center justify-between gap-2 font-mono">
                  <span className="font-bold text-slate-100">{activeHoveredNeighbor.name}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${getNodeColor(activeHoveredNeighbor).bg} ${getNodeColor(activeHoveredNeighbor).text}`}>
                    {activeHoveredNeighbor.creditRating} ({activeHoveredNeighbor.ratingOutlook})
                  </span>
                </div>
                <div className="text-[11px] text-slate-400">
                  {activeHoveredNeighbor.distanceMiles} miles {activeHoveredNeighbor.bearing} · {activeHoveredNeighbor.relationshipType}
                </div>
                <div className="text-[10px] text-slate-500 line-clamp-2">
                  {activeHoveredNeighbor.relationshipDescription}
                </div>
              </div>
            )}
          </div>

          {/* Color Mode Legend Strip */}
          <div className="px-4 py-2.5 bg-slate-950 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
            <div className="flex items-center gap-2 text-slate-400">
              <Layers className="w-3.5 h-3.5 text-cyan-400" />
              <span className="font-semibold text-slate-300">
                {colorMode === 'rating' && 'Credit Rating Legend:'}
                {colorMode === 'stress' && 'Fiscal Stress Score Legend:'}
                {colorMode === 'tier' && 'Government Tier Legend:'}
                {colorMode === 'contagion' && 'Contagion Risk Legend:'}
              </span>
            </div>

            {/* Rating Swatches */}
            {colorMode === 'rating' && (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                  <span className="text-slate-300">AAA</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-teal-500" />
                  <span className="text-slate-300">AA</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-cyan-500" />
                  <span className="text-slate-300">A</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                  <span className="text-slate-300">BBB</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-orange-500" />
                  <span className="text-slate-300">BB</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                  <span className="text-slate-300">B/CCC</span>
                </div>
              </div>
            )}

            {/* Stress Swatches */}
            {colorMode === 'stress' && (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                  <span className="text-slate-300">0-30 (Low)</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                  <span className="text-slate-300">31-50 (Moderate)</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-orange-500" />
                  <span className="text-slate-300">51-70 (High)</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                  <span className="text-slate-300">71-100 (Critical)</span>
                </div>
              </div>
            )}

            {/* Tier Swatches */}
            {colorMode === 'tier' && (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-cyan-500" />
                  <span className="text-slate-300">Municipal / County</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-purple-500" />
                  <span className="text-slate-300">Subnational State</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
                  <span className="text-slate-300">Sovereign Debtor</span>
                </div>
              </div>
            )}

            {/* Contagion Swatches */}
            {colorMode === 'contagion' && (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-500" />
                  <span className="text-slate-300">Low</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-sky-500" />
                  <span className="text-slate-300">Medium</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                  <span className="text-slate-300">High</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                  <span className="text-slate-300">Critical Spillover</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column (4 cols): Neighbor Deep-Dive Inspector */}
        <div className="lg:col-span-4 flex flex-col space-y-4">
          {/* Selected Neighbor Detail Card */}
          {activeNeighbor ? (
            <div className="bg-slate-950 border border-cyan-500/40 rounded-lg p-4 space-y-3.5 shadow-md">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider">
                    Neighbor Entity Profile
                  </span>
                  <h4 className="text-sm font-bold text-slate-100 mt-0.5">
                    {activeNeighbor.name}
                  </h4>
                  <div className="text-xs text-slate-400 font-mono mt-0.5">
                    {activeNeighbor.distanceMiles} mi {activeNeighbor.bearing} of {entity.name}
                  </div>
                </div>

                <div className="text-right">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-mono font-bold ${
                    getNodeColor(activeNeighbor).bg
                  } ${getNodeColor(activeNeighbor).text} border border-current/30`}>
                    {activeNeighbor.creditRating}
                  </span>
                  <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                    Outlook: {activeNeighbor.ratingOutlook}
                  </div>
                </div>
              </div>

              {/* Core Metrics Strip */}
              <div className="grid grid-cols-2 gap-2 text-xs font-mono pt-2 border-t border-slate-800">
                <div className="p-2 bg-slate-900/80 rounded border border-slate-800">
                  <div className="text-[10px] text-slate-500">Fiscal Stress Score</div>
                  <div className={`text-sm font-bold tabular-nums ${
                    activeNeighbor.fiscalStressScore > 60 ? 'text-rose-400' :
                    activeNeighbor.fiscalStressScore > 40 ? 'text-amber-400' : 'text-emerald-400'
                  }`}>
                    {activeNeighbor.fiscalStressScore} / 100
                  </div>
                </div>

                <div className="p-2 bg-slate-900/80 rounded border border-slate-800">
                  <div className="text-[10px] text-slate-500">Direct Debt Book</div>
                  <div className="text-sm font-bold text-slate-200 tabular-nums">
                    ${activeNeighbor.totalDebtMillions >= 1000
                      ? `${(activeNeighbor.totalDebtMillions / 1000).toFixed(1)}B`
                      : `${activeNeighbor.totalDebtMillions.toLocaleString()}M`}
                  </div>
                </div>
              </div>

              {/* Relationship Type & Spillover Transmission */}
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-300">
                    {activeNeighbor.relationshipType}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                    getContagionColor(activeNeighbor.contagionExposure).bg
                  } ${getContagionColor(activeNeighbor.contagionExposure).text}`}>
                    {activeNeighbor.contagionExposure} Contagion Risk
                  </span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed bg-slate-900/50 p-2.5 rounded border border-slate-800/80">
                  {activeNeighbor.relationshipDescription}
                </p>
              </div>

              {/* Action: Switch to this entity if loaded in terminal */}
              <div className="pt-2">
                {activeNeighbor.isTerminalEntity && onSelectEntity ? (
                  <button
                    onClick={() => {
                      const match = allEntities.find((e) => e.id === activeNeighbor.id);
                      if (match) onSelectEntity(match);
                    }}
                    className="w-full py-2 px-3 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded flex items-center justify-center gap-2 transition-colors shadow-xs"
                  >
                    <span>Switch Terminal Model to {activeNeighbor.name}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                ) : (
                  <div className="text-[11px] text-slate-500 font-mono text-center py-1 bg-slate-900/30 rounded border border-slate-800/40">
                    Regional External Jurisdiction · Monitored via Network Matrix
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 text-center space-y-2">
              <Compass className="w-6 h-6 text-cyan-400 mx-auto" />
              <div className="text-xs font-bold text-slate-200">
                Interactive Neighbor Inspection
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Click on any neighboring entity node or arc on the map to inspect its balance-sheet transmission channels, credit rating, and shared tax base exposures.
              </p>
            </div>
          )}

          {/* Neighbor Directory List */}
          <div className="flex-1 bg-slate-950 border border-slate-800 rounded-lg overflow-hidden flex flex-col">
            <div className="px-3.5 py-2.5 bg-slate-900/70 border-b border-slate-800 flex items-center justify-between text-xs font-mono">
              <span className="font-semibold text-slate-300">Neighbor Network Matrix</span>
              <div className="flex items-center gap-1 text-[11px]">
                <button
                  onClick={() => setTierFilter('all')}
                  className={`px-1.5 py-0.5 rounded ${
                    tierFilter === 'all' ? 'bg-cyan-950 text-cyan-400 font-bold' : 'text-slate-400'
                  }`}
                >
                  All
                </button>
                <button
                  onClick={() => setTierFilter('municipal')}
                  className={`px-1.5 py-0.5 rounded ${
                    tierFilter === 'municipal' ? 'bg-cyan-950 text-cyan-400 font-bold' : 'text-slate-400'
                  }`}
                >
                  Muni
                </button>
                <button
                  onClick={() => setTierFilter('subnational')}
                  className={`px-1.5 py-0.5 rounded ${
                    tierFilter === 'subnational' ? 'bg-cyan-950 text-cyan-400 font-bold' : 'text-slate-400'
                  }`}
                >
                  State
                </button>
              </div>
            </div>

            {/* List items */}
            <div className="divide-y divide-slate-800/80 overflow-y-auto max-h-[220px]">
              {filteredNeighbors.map((n) => {
                const isSelected = selectedNeighborId === n.id;
                const nColor = getNodeColor(n);

                return (
                  <div
                    key={n.id}
                    onClick={() => setSelectedNeighborId(n.id)}
                    className={`px-3 py-2 flex items-center justify-between gap-3 text-xs cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-slate-800/90 border-l-2 border-cyan-400'
                        : 'hover:bg-slate-900/60'
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="font-medium text-slate-200 truncate flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${nColor.bg}`} />
                        <span>{n.name}</span>
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono mt-0.5 truncate">
                        {n.distanceMiles} mi {n.bearing} · {n.relationshipType}
                      </div>
                    </div>

                    <div className="text-right shrink-0 font-mono">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${nColor.bg} ${nColor.text}`}>
                        {n.creditRating}
                      </span>
                      <div className="text-[10px] text-slate-500 mt-0.5">
                        Stress: {n.fiscalStressScore}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
