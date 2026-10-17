import React from 'react';
import { GovernmentTier, PublicFinanceEntity, StressScenario } from '../types/finance';
import { Building2, Landmark, Globe2, ShieldAlert, Sparkles } from 'lucide-react';

interface EntitySelectorProps {
  entities: PublicFinanceEntity[];
  selectedEntity: PublicFinanceEntity;
  onSelectEntity: (entity: PublicFinanceEntity) => void;
  activeScenario: StressScenario;
  onOpenStressModal: () => void;
  onOpenPullModal?: () => void;
}

export const EntitySelector: React.FC<EntitySelectorProps> = ({
  entities,
  selectedEntity,
  onSelectEntity,
  activeScenario,
  onOpenStressModal,
  onOpenPullModal,
}) => {
  const tiers: { id: GovernmentTier; label: string; icon: React.ReactNode }[] = [
    { id: 'municipal', label: 'Municipal / Local', icon: <Building2 className="w-3.5 h-3.5" /> },
    { id: 'subnational', label: 'Subnational / State', icon: <Landmark className="w-3.5 h-3.5" /> },
    { id: 'sovereign', label: 'Sovereign / Central', icon: <Globe2 className="w-3.5 h-3.5" /> },
  ];

  const currentTierEntities = entities.filter((e) => e.tier === selectedEntity.tier);

  return (
    <div className="bg-slate-900/80 border-b border-slate-800 px-6 py-3 flex flex-col md:flex-row md:items-center justify-between gap-4">
      {/* Tier Switcher Segmented Control */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center p-1 bg-slate-950 border border-slate-800 rounded">
          {tiers.map((t) => {
            const isActive = selectedEntity.tier === t.id;
            return (
              <button
                key={t.id}
                onClick={() => {
                  const firstInTier = entities.find((e) => e.tier === t.id);
                  if (firstInTier) onSelectEntity(firstInTier);
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap ${
                  isActive
                    ? 'bg-slate-800 text-cyan-300 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {t.icon}
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>

        {/* Entity Selector Dropdown */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Active Entity:</span>
          <select
            value={selectedEntity.id}
            onChange={(e) => {
              const target = entities.find((ent) => ent.id === e.target.value);
              if (target) onSelectEntity(target);
            }}
            aria-label="Select Active Public Finance Entity"
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded px-2.5 py-1.5 focus:outline-none focus:border-cyan-500 font-mono"
          >
            {currentTierEntities.map((ent) => (
              <option key={ent.id} value={ent.id}>
                {ent.name} ({ent.creditRating} / {ent.jurisdiction})
              </option>
            ))}
          </select>

          {/* Pull Entity Button */}
          {onOpenPullModal && (
            <button
              onClick={onOpenPullModal}
              title="Pull new sovereign from IMF/WB/BIS/UN or create custom entity"
              className="px-2.5 py-1.5 text-xs font-medium text-cyan-300 hover:text-white bg-cyan-950/60 hover:bg-cyan-900/60 border border-cyan-800/80 rounded flex items-center gap-1.5 transition-colors whitespace-nowrap"
            >
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              <span>+ Pull Entity</span>
            </button>
          )}
        </div>
      </div>

      {/* Unboxed Metadata & Scenario Badge */}
      <div className="flex items-center gap-4 text-xs text-slate-400 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-slate-500">Credit Rating:</span>
          <span className="font-mono font-semibold text-slate-200">{selectedEntity.creditRating}</span>
          <span aria-hidden="true" className="text-slate-700">·</span>
          <span className="text-slate-500">Outlook:</span>
          <span className={`font-medium ${
            selectedEntity.ratingOutlook === 'Positive' ? 'text-emerald-400' :
            selectedEntity.ratingOutlook === 'Negative' ? 'text-rose-400' : 'text-slate-300'
          }`}>
            {selectedEntity.ratingOutlook}
          </span>
          <span aria-hidden="true" className="text-slate-700">·</span>
          <span className="text-slate-500">Direct Debt:</span>
          <span className="font-mono text-cyan-300 tabular-nums">
            ${selectedEntity.totalDirectDebtMillions >= 1000
              ? `${(selectedEntity.totalDirectDebtMillions / 1000).toFixed(1)}B`
              : `${selectedEntity.totalDirectDebtMillions}M`}
          </span>
        </div>

        {/* Active Scenario Indicator Button */}
        <button
          onClick={onOpenStressModal}
          className={`px-2.5 py-1 text-xs rounded border flex items-center gap-1.5 transition-colors ${
            activeScenario.id === 'baseline'
              ? 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
              : 'bg-amber-950/40 border-amber-600/50 text-amber-300 hover:bg-amber-950/60'
          }`}
        >
          {activeScenario.id === 'baseline' ? (
            <Sparkles className="w-3 h-3 text-slate-400" />
          ) : (
            <ShieldAlert className="w-3 h-3 text-amber-400" />
          )}
          <span>Stress: {activeScenario.name}</span>
        </button>
      </div>
    </div>
  );
};
