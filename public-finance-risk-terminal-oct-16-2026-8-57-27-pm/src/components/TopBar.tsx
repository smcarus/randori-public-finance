import React from 'react';
import { SlidersHorizontal, Terminal, FileCode2, BookOpen } from 'lucide-react';

interface TopBarProps {
  activeTab: 'overview' | 'debt-architecture' | 'dsa-monte-carlo' | 'contingent-ppp' | 'market-cds' | 'live-data' | 'geopolitical-var';
  setActiveTab: (tab: 'overview' | 'debt-architecture' | 'dsa-monte-carlo' | 'contingent-ppp' | 'market-cds' | 'live-data' | 'geopolitical-var') => void;
  onOpenStressModal: () => void;
  onOpenPythonModal: () => void;
  onOpenFormulaModal: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  activeTab,
  setActiveTab,
  onOpenStressModal,
  onOpenPythonModal,
  onOpenFormulaModal,
}) => {
  return (
    <header className="sticky top-0 z-40 bg-slate-950/95 backdrop-blur-md border-b border-slate-800/80 px-6 py-3.5 flex items-center justify-between gap-8">
      {/* Zone 1: Single text element wordmark */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="w-8 h-8 rounded bg-cyan-950 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
          <Terminal className="w-4 h-4" />
        </div>
        <span className="text-base font-bold tracking-tight text-slate-100 whitespace-nowrap">
          Public Finance Risk Terminal
        </span>
      </div>

      {/* Zone 2: Clean single-line navigation links */}
      <nav className="hidden lg:flex items-center gap-5 text-xs font-medium text-slate-400">
        <button
          onClick={() => setActiveTab('overview')}
          className={`hover:text-slate-100 transition-colors whitespace-nowrap shrink-0 pb-0.5 border-b-2 ${
            activeTab === 'overview'
              ? 'text-cyan-400 border-cyan-400 font-semibold'
              : 'border-transparent text-slate-400'
          }`}
        >
          Tier Risk Overview
        </button>
        <button
          onClick={() => setActiveTab('geopolitical-var')}
          className={`hover:text-slate-100 transition-colors whitespace-nowrap shrink-0 pb-0.5 border-b-2 ${
            activeTab === 'geopolitical-var'
              ? 'text-cyan-400 border-cyan-400 font-semibold'
              : 'border-transparent text-slate-400'
          }`}
        >
          Geopolitical VaR & PRI
        </button>
        <button
          onClick={() => setActiveTab('live-data')}
          className={`hover:text-slate-100 transition-colors whitespace-nowrap shrink-0 pb-0.5 border-b-2 ${
            activeTab === 'live-data'
              ? 'text-cyan-400 border-cyan-400 font-semibold'
              : 'border-transparent text-slate-400'
          }`}
        >
          Live Feeds: IMF · WB · BIS · UN
        </button>
        <button
          onClick={() => setActiveTab('debt-architecture')}
          className={`hover:text-slate-100 transition-colors whitespace-nowrap shrink-0 pb-0.5 border-b-2 ${
            activeTab === 'debt-architecture'
              ? 'text-cyan-400 border-cyan-400 font-semibold'
              : 'border-transparent text-slate-400'
          }`}
        >
          Debt Architecture & Refunding
        </button>
        <button
          onClick={() => setActiveTab('dsa-monte-carlo')}
          className={`hover:text-slate-100 transition-colors whitespace-nowrap shrink-0 pb-0.5 border-b-2 ${
            activeTab === 'dsa-monte-carlo'
              ? 'text-cyan-400 border-cyan-400 font-semibold'
              : 'border-transparent text-slate-400'
          }`}
        >
          DSA & Monte Carlo
        </button>
        <button
          onClick={() => setActiveTab('contingent-ppp')}
          className={`hover:text-slate-100 transition-colors whitespace-nowrap shrink-0 pb-0.5 border-b-2 ${
            activeTab === 'contingent-ppp'
              ? 'text-cyan-400 border-cyan-400 font-semibold'
              : 'border-transparent text-slate-400'
          }`}
        >
          PPP & Contingent Liabilities
        </button>
        <button
          onClick={() => setActiveTab('market-cds')}
          className={`hover:text-slate-100 transition-colors whitespace-nowrap shrink-0 pb-0.5 border-b-2 ${
            activeTab === 'market-cds'
              ? 'text-cyan-400 border-cyan-400 font-semibold'
              : 'border-transparent text-slate-400'
          }`}
        >
          Market Spreads & CDS Basis
        </button>
      </nav>

      {/* Zone 3: Primary and Secondary Action Buttons */}
      <div className="flex items-center gap-2.5 shrink-0">
        <button
          onClick={onOpenFormulaModal}
          title="Equation Inspector & Methodology"
          className="px-2.5 py-1.5 text-xs text-slate-300 hover:text-white bg-slate-900 hover:bg-slate-800 border border-slate-700/70 rounded flex items-center gap-1.5 transition-colors whitespace-nowrap"
        >
          <BookOpen className="w-3.5 h-3.5 text-slate-400" />
          <span className="hidden sm:inline">Formulas</span>
        </button>
        <button
          onClick={onOpenPythonModal}
          className="px-2.5 py-1.5 text-xs text-slate-300 hover:text-white bg-slate-900 hover:bg-slate-800 border border-slate-700/70 rounded flex items-center gap-1.5 transition-colors whitespace-nowrap"
        >
          <FileCode2 className="w-3.5 h-3.5 text-cyan-400" />
          <span className="hidden sm:inline">Python / Excel Export</span>
        </button>
        <button
          onClick={onOpenStressModal}
          className="px-3.5 py-1.5 text-xs font-semibold text-slate-950 bg-cyan-400 hover:bg-cyan-300 rounded flex items-center gap-1.5 shadow-sm transition-colors whitespace-nowrap"
        >
          <SlidersHorizontal className="w-3.5 h-3.5 text-slate-950" />
          <span>Macro Stress Engine</span>
        </button>
      </div>
    </header>
  );
};
