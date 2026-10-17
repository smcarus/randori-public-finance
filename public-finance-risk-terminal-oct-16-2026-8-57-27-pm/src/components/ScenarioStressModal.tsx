import React from 'react';
import { PublicFinanceEntity, StressScenario } from '../types/finance';
import { PRESET_SCENARIOS } from '../data/sampleEntities';
import { calculateMacroStressImpact } from '../utils/macroStressEngine';
import { X, SlidersHorizontal, AlertTriangle, ShieldCheck, Check, Sparkles } from 'lucide-react';

interface ScenarioStressModalProps {
  isOpen: boolean;
  onClose: () => void;
  entity: PublicFinanceEntity;
  activeScenario: StressScenario;
  onSelectScenario: (scenario: StressScenario) => void;
}

export const ScenarioStressModal: React.FC<ScenarioStressModalProps> = ({
  isOpen,
  onClose,
  entity,
  activeScenario,
  onSelectScenario,
}) => {
  if (!isOpen) return null;

  const stressImpact = calculateMacroStressImpact(entity, activeScenario);

  const handleSliderChange = (field: keyof StressScenario, value: number) => {
    onSelectScenario({
      ...activeScenario,
      id: 'custom',
      name: 'Custom Parameter Stress Sandbox',
      [field]: value,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700/80 rounded w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded bg-amber-950/60 border border-amber-600/50 flex items-center justify-center text-amber-400">
              <SlidersHorizontal className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100">
                Macroeconomic Stress Testing & Contingent Shock Engine
              </h2>
              <p className="text-xs text-slate-400">
                Active Entity: {entity.name} ({entity.tier.toUpperCase()})
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 text-slate-400 hover:text-slate-100 rounded hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Preset Scenario Cards */}
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-2">
              Select Macro Scenario Archetype:
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {PRESET_SCENARIOS.map((preset) => {
                const isSelected = activeScenario.id === preset.id;
                return (
                  <button
                    key={preset.id}
                    onClick={() => onSelectScenario(preset)}
                    className={`p-3 text-left rounded border transition-all ${
                      isSelected
                        ? 'bg-cyan-950/50 border-cyan-500/80 text-cyan-200 ring-1 ring-cyan-500/50'
                        : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold font-sans">{preset.name}</span>
                      {isSelected && <Check className="w-3.5 h-3.5 text-cyan-400" />}
                    </div>
                    <p className="text-[11px] text-slate-400 line-clamp-2">
                      {preset.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Real-Time Stress Results Banner */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded space-y-3">
            <div className="text-xs font-semibold text-slate-300 flex items-center justify-between">
              <span>Simulated Instant Fiscal Impact ({activeScenario.name}):</span>
              <span className="font-mono text-rose-400 font-bold tabular-nums">
                Total Shock: -${stressImpact.totalFiscalShockMillions.toLocaleString()}M
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
              <div className="p-2.5 bg-slate-900 border border-slate-800 rounded">
                <span className="text-slate-500 block text-[11px]">Revenue Contraction</span>
                <span className="text-rose-400 font-semibold tabular-nums">
                  -${stressImpact.projectedRevenueDropMillions.toLocaleString()}M (-{stressImpact.projectedRevenueDropPercent.toFixed(1)}%)
                </span>
              </div>
              <div className="p-2.5 bg-slate-900 border border-slate-800 rounded">
                <span className="text-slate-500 block text-[11px]">Medicaid / Safety Drag</span>
                <span className="text-amber-400 font-semibold tabular-nums">
                  +${stressImpact.projectedMedicaidSurgeMillions.toLocaleString()}M
                </span>
              </div>
              <div className="p-2.5 bg-slate-900 border border-slate-800 rounded">
                <span className="text-slate-500 block text-[11px]">PPP Shortfall Payouts</span>
                <span className="text-amber-300 font-semibold tabular-nums">
                  ${stressImpact.pppTotalTriggeredPayoutMillions.toFixed(1)}M
                </span>
              </div>
              <div className="p-2.5 bg-slate-900 border border-slate-800 rounded">
                <span className="text-slate-500 block text-[11px]">Shocked DSCR</span>
                <span className={`font-semibold tabular-nums ${stressImpact.shockedDscr < 1.2 ? 'text-rose-400' : 'text-cyan-300'}`}>
                  {stressImpact.shockedDscr.toFixed(2)}x
                </span>
              </div>
            </div>
          </div>

          {/* Granular Variable Adjustment Sliders */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold text-slate-300">
              Granular Parameter Perturbations:
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Interest Rate Delta */}
              <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Interest Rate Spike:</span>
                  <span className="font-mono text-cyan-300 font-bold tabular-nums">
                    +{activeScenario.interestRateDeltaBps} bps
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="500"
                  step="25"
                  value={activeScenario.interestRateDeltaBps}
                  onChange={(e) => handleSliderChange('interestRateDeltaBps', Number(e.target.value))}
                  aria-label="Interest Rate Spike in basis points"
                  className="w-full accent-cyan-400 h-1.5 bg-slate-800 rounded cursor-pointer"
                />
              </div>

              {/* GDP Growth Shock */}
              <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Real GDP Growth Shock:</span>
                  <span className="font-mono text-rose-400 font-bold tabular-nums">
                    {activeScenario.gdpGrowthShockPct > 0 ? `+${activeScenario.gdpGrowthShockPct}%` : `${activeScenario.gdpGrowthShockPct}%`}
                  </span>
                </div>
                <input
                  type="range"
                  min="-6.0"
                  max="2.0"
                  step="0.5"
                  value={activeScenario.gdpGrowthShockPct}
                  onChange={(e) => handleSliderChange('gdpGrowthShockPct', Number(e.target.value))}
                  aria-label="Real GDP Growth Shock Percentage"
                  className="w-full accent-rose-400 h-1.5 bg-slate-800 rounded cursor-pointer"
                />
              </div>

              {/* Property Assessed Value Decline */}
              <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Property / Commercial AV Contraction:</span>
                  <span className="font-mono text-amber-300 font-bold tabular-nums">
                    {activeScenario.propertyValueDeclinePct}%
                  </span>
                </div>
                <input
                  type="range"
                  min="-40"
                  max="0"
                  step="1"
                  value={activeScenario.propertyValueDeclinePct}
                  onChange={(e) => handleSliderChange('propertyValueDeclinePct', Number(e.target.value))}
                  aria-label="Property Assessed Value Contraction Percentage"
                  className="w-full accent-amber-400 h-1.5 bg-slate-800 rounded cursor-pointer"
                />
              </div>

              {/* Concession / PPP Volume Shock */}
              <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">PPP Concession Traffic / Volume Drop:</span>
                  <span className="font-mono text-cyan-300 font-bold tabular-nums">
                    -{activeScenario.pppTrafficDeclinePct}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="50"
                  step="2"
                  value={activeScenario.pppTrafficDeclinePct}
                  onChange={(e) => handleSliderChange('pppTrafficDeclinePct', Number(e.target.value))}
                  aria-label="PPP Traffic Decline Percentage"
                  className="w-full accent-cyan-400 h-1.5 bg-slate-800 rounded cursor-pointer"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between">
          <button
            onClick={() => onSelectScenario(PRESET_SCENARIOS[0])}
            className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            Reset to Baseline
          </button>
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold text-slate-950 bg-cyan-400 hover:bg-cyan-300 rounded transition-colors"
          >
            Apply Scenario & Return
          </button>
        </div>
      </div>
    </div>
  );
};
