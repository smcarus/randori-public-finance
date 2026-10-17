import React, { useState } from 'react';
import { SAMPLE_ENTITIES, PRESET_SCENARIOS } from './data/sampleEntities';
import { PublicFinanceEntity, StressScenario } from './types/finance';
import { TopBar } from './components/TopBar';
import { EntitySelector } from './components/EntitySelector';
import { TierOverviewTab } from './components/TierOverviewTab';
import { DebtArchitectureTab } from './components/DebtArchitectureTab';
import { DsaMonteCarloTab } from './components/DsaMonteCarloTab';
import { ContingentLiabilitiesTab } from './components/ContingentLiabilitiesTab';
import { MarketSpreadsTab } from './components/MarketSpreadsTab';
import { LiveDataFeedTab } from './components/LiveDataFeedTab';
import { GeopoliticalVaRTab } from './components/GeopoliticalVaRTab';
import { ScenarioStressModal } from './components/ScenarioStressModal';
import { PythonExcelModal } from './components/PythonExcelModal';
import { FormulaGuideModal } from './components/FormulaGuideModal';
import { PullEntityModal } from './components/PullEntityModal';

export default function App() {
  const [entities, setEntities] = useState<PublicFinanceEntity[]>(SAMPLE_ENTITIES);
  const [selectedEntity, setSelectedEntity] = useState<PublicFinanceEntity>(SAMPLE_ENTITIES[0]);
  const [activeScenario, setActiveScenario] = useState<StressScenario>(PRESET_SCENARIOS[0]);
  const [activeTab, setActiveTab] = useState<'overview' | 'debt-architecture' | 'dsa-monte-carlo' | 'contingent-ppp' | 'market-cds' | 'live-data' | 'geopolitical-var'>('overview');

  // Handle live data sync from IMF/World Bank/BIS/UN Comtrade into active model
  const handleUpdateEntityWithLiveData = (updatedEntity: PublicFinanceEntity) => {
    setSelectedEntity(updatedEntity);
    setEntities((prev) =>
      prev.map((e) => (e.id === updatedEntity.id ? updatedEntity : e))
    );
  };

  // Handle ingestion of newly pulled sovereign or custom entity
  const handleAddEntity = (newEntity: PublicFinanceEntity) => {
    setEntities((prev) => [newEntity, ...prev.filter((e) => e.id !== newEntity.id)]);
    setSelectedEntity(newEntity);
  };

  // Modal visibility states
  const [isStressModalOpen, setIsStressModalOpen] = useState<boolean>(false);
  const [isPythonModalOpen, setIsPythonModalOpen] = useState<boolean>(false);
  const [isFormulaModalOpen, setIsFormulaModalOpen] = useState<boolean>(false);
  const [isPullModalOpen, setIsPullModalOpen] = useState<boolean>(false);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* 3-Zone Top Navigation Contract */}
      <TopBar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenStressModal={() => setIsStressModalOpen(true)}
        onOpenPythonModal={() => setIsPythonModalOpen(true)}
        onOpenFormulaModal={() => setIsFormulaModalOpen(true)}
      />

      {/* Tier Switcher & Entity Profile Strip */}
      <EntitySelector
        entities={entities}
        selectedEntity={selectedEntity}
        onSelectEntity={setSelectedEntity}
        activeScenario={activeScenario}
        onOpenStressModal={() => setIsStressModalOpen(true)}
        onOpenPullModal={() => setIsPullModalOpen(true)}
      />

      {/* Main Viewport Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'overview' && (
          <TierOverviewTab
            entity={selectedEntity}
            allEntities={entities}
            onSelectEntity={setSelectedEntity}
            activeScenario={activeScenario}
            onOpenStressModal={() => setIsStressModalOpen(true)}
            onOpenFormulaModal={() => setIsFormulaModalOpen(true)}
          />
        )}

        {activeTab === 'geopolitical-var' && (
          <GeopoliticalVaRTab
            activeEntity={selectedEntity}
            allEntities={entities}
            onOpenFormulaModal={() => setIsFormulaModalOpen(true)}
            onOpenPullModal={() => setIsPullModalOpen(true)}
          />
        )}

        {activeTab === 'live-data' && (
          <LiveDataFeedTab
            entity={selectedEntity}
            onUpdateEntityWithLiveData={handleUpdateEntityWithLiveData}
            onOpenFormulaModal={() => setIsFormulaModalOpen(true)}
          />
        )}

        {activeTab === 'debt-architecture' && (
          <DebtArchitectureTab
            entity={selectedEntity}
            onOpenFormulaModal={() => setIsFormulaModalOpen(true)}
          />
        )}

        {activeTab === 'dsa-monte-carlo' && (
          <DsaMonteCarloTab
            entity={selectedEntity}
            activeScenario={activeScenario}
            onOpenFormulaModal={() => setIsFormulaModalOpen(true)}
          />
        )}

        {activeTab === 'contingent-ppp' && (
          <ContingentLiabilitiesTab
            entity={selectedEntity}
            activeScenario={activeScenario}
            onOpenFormulaModal={() => setIsFormulaModalOpen(true)}
          />
        )}

        {activeTab === 'market-cds' && (
          <MarketSpreadsTab
            entity={selectedEntity}
            onOpenFormulaModal={() => setIsFormulaModalOpen(true)}
          />
        )}
      </main>

      {/* Institutional Terminal Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 px-6 py-4 mt-auto">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500">
          <div className="flex items-center gap-3">
            <span>Public Finance Risk & Analytics Engine</span>
            <span aria-hidden="true">·</span>
            <span>IMF DSA & World Bank Standards Compliant</span>
            <span aria-hidden="true">·</span>
            <span>GASB 67/68 Actuarial Protocols</span>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setIsFormulaModalOpen(true)}
              className="hover:text-slate-300 transition-colors"
            >
              Methodology & Equations
            </button>
            <button
              onClick={() => setIsPythonModalOpen(true)}
              className="hover:text-cyan-400 transition-colors"
            >
              Export SciPy & CSV
            </button>
          </div>
        </div>
      </footer>

      {/* Interactive Modal Dialogs */}
      <ScenarioStressModal
        isOpen={isStressModalOpen}
        onClose={() => setIsStressModalOpen(false)}
        entity={selectedEntity}
        activeScenario={activeScenario}
        onSelectScenario={setActiveScenario}
      />

      <PythonExcelModal
        isOpen={isPythonModalOpen}
        onClose={() => setIsPythonModalOpen(false)}
        entity={selectedEntity}
        activeScenario={activeScenario}
      />

      <FormulaGuideModal
        isOpen={isFormulaModalOpen}
        onClose={() => setIsFormulaModalOpen(false)}
      />

      <PullEntityModal
        isOpen={isPullModalOpen}
        onClose={() => setIsPullModalOpen(false)}
        onAddEntity={handleAddEntity}
      />
    </div>
  );
}
