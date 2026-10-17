import React, { useState } from 'react';
import { PublicFinanceEntity, StressScenario } from '../types/finance';
import { generatePythonScript, generateExcelCsv } from '../utils/codeGenerators';
import { X, Copy, Check, Download, FileCode, FileSpreadsheet, Terminal } from 'lucide-react';

interface PythonExcelModalProps {
  isOpen: boolean;
  onClose: () => void;
  entity: PublicFinanceEntity;
  activeScenario: StressScenario;
}

export const PythonExcelModal: React.FC<PythonExcelModalProps> = ({
  isOpen,
  onClose,
  entity,
  activeScenario,
}) => {
  if (!isOpen) return null;

  const [activeSubTab, setActiveSubTab] = useState<'python' | 'excel'>('python');
  const [copied, setCopied] = useState<boolean>(false);

  const pythonCode = generatePythonScript(entity, activeScenario);
  const csvContent = generateExcelCsv(entity);

  const handleCopy = () => {
    const textToCopy = activeSubTab === 'python' ? pythonCode : csvContent;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const isPy = activeSubTab === 'python';
    const filename = `${entity.id}_${activeScenario.id}_model.${isPy ? 'py' : 'csv'}`;
    const mimeType = isPy ? 'text/x-python' : 'text/csv';
    const content = isPy ? pythonCode : csvContent;

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700/80 rounded w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded bg-cyan-950/60 border border-cyan-500/50 flex items-center justify-center text-cyan-400">
              <Terminal className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100">
                Quantitative Integration: Python Engine & Excel Data Model
              </h2>
              <p className="text-xs text-slate-400">
                Executable SciPy Defeasance Optimizer · Statsmodels SVAR · PowerQuery Excel Model
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

        {/* Tab switch bar */}
        <div className="px-6 py-2.5 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveSubTab('python')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                activeSubTab === 'python'
                  ? 'bg-slate-800 text-cyan-300 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileCode className="w-3.5 h-3.5" />
              <span>Python Script (SciPy & Statsmodels)</span>
            </button>
            <button
              onClick={() => setActiveSubTab('excel')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                activeSubTab === 'excel'
                  ? 'bg-slate-800 text-emerald-300 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              <span>Structured CSV (Excel / PowerQuery)</span>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="px-2.5 py-1 text-xs text-slate-300 hover:text-white bg-slate-900 border border-slate-700 rounded flex items-center gap-1.5 transition-colors font-mono"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
            <button
              onClick={handleDownload}
              className="px-3 py-1 text-xs font-semibold text-slate-950 bg-cyan-400 hover:bg-cyan-300 rounded flex items-center gap-1.5 transition-colors font-sans"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download File</span>
            </button>
          </div>
        </div>

        {/* Code / CSV Viewport */}
        <div className="p-6 overflow-y-auto font-mono text-xs text-slate-300 bg-slate-950 select-text leading-relaxed">
          <pre className="whitespace-pre-wrap">
            {activeSubTab === 'python' ? pythonCode : csvContent}
          </pre>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-900 flex items-center justify-between text-xs text-slate-400">
          <span>
            {activeSubTab === 'python'
              ? 'Ready to run in Jupyter Notebook, Google Colab, or local Python 3.10+ runtime.'
              : 'Formats cleanly into Microsoft Excel Structured Tables, PowerPivot, and PowerQuery.'}
          </span>
          <button
            onClick={onClose}
            className="text-xs text-slate-300 hover:text-white transition-colors"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
};
