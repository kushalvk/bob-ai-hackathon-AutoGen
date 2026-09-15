import React from 'react';
import {
  ShieldAlert,
  Activity,
  AlertTriangle,
  FileCheck2,
  RefreshCw,
  MessageSquare,
  Building2,
} from 'lucide-react';

interface HeaderProps {
  activeTab: 'heatmap' | 'deviations' | 'capa';
  setActiveTab: (tab: 'heatmap' | 'deviations' | 'capa') => void;
  siteCount: number;
  totalDeviations: number;
  majorDeviations: number;
  highestRiskScore: number;
  highestRiskSite: string;
  onRefresh: () => void;
  isRefreshing: boolean;
  toggleChat: () => void;
  isChatOpen: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  siteCount,
  totalDeviations,
  majorDeviations,
  highestRiskScore,
  highestRiskSite,
  onRefresh,
  isRefreshing,
  toggleChat,
  isChatOpen,
}) => {
  return (
    <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-30 shadow-md">
      {/* Top bar: Brand, Status, and Controls */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4">
        {/* Brand info */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-teal-500/20 border border-teal-500/40 flex items-center justify-center text-teal-400">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-tight text-white m-0">ClinGuard AI</h1>
              <span className="px-2 py-0.5 text-xs font-semibold bg-teal-950 text-teal-300 border border-teal-700/50 rounded-full">
                PROTO-001
              </span>
            </div>
            <p className="text-xs text-slate-400 m-0">
              Protocol Compliance &amp; Automated CAPA Intelligence
            </p>
          </div>
        </div>

        {/* Global Key Metrics Badges */}
        <div className="flex items-center space-x-3 text-xs">
          <div className="bg-slate-800/80 border border-slate-700 rounded-lg px-3 py-1.5 flex items-center space-x-2">
            <Building2 className="w-4 h-4 text-slate-400" />
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-semibold">Sites</span>
              <span className="font-bold text-slate-200">{siteCount}</span>
            </div>
          </div>

          <div className="bg-slate-800/80 border border-slate-700 rounded-lg px-3 py-1.5 flex items-center space-x-2">
            <Activity className="w-4 h-4 text-blue-400" />
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-semibold">Total Devs</span>
              <span className="font-bold text-slate-200">{totalDeviations}</span>
            </div>
          </div>

          <div className="bg-slate-800/80 border border-slate-700 rounded-lg px-3 py-1.5 flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-semibold">Major Devs</span>
              <span className="font-bold text-rose-300">{majorDeviations}</span>
            </div>
          </div>

          <div className="bg-slate-800/80 border border-slate-700 rounded-lg px-3 py-1.5 flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-semibold">Peak Risk</span>
              <span className="font-bold text-amber-300">
                {highestRiskSite ? `${highestRiskSite} (${highestRiskScore.toFixed(1)})` : 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* Actions & Chat Toggle */}
        <div className="flex items-center space-x-2.5">
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition disabled:opacity-50"
            title="Refresh live data from backend"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-teal-400' : ''}`} />
            <span>Sync</span>
          </button>

          <button
            onClick={toggleChat}
            className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition shadow-sm ${
              isChatOpen
                ? 'bg-teal-500 text-slate-950 hover:bg-teal-400'
                : 'bg-teal-600/20 text-teal-300 border border-teal-500/40 hover:bg-teal-600/30'
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            <span>MCP Chat</span>
          </button>
        </div>
      </div>

      {/* Navigation tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex space-x-8 border-t border-slate-800/80">
        <button
          onClick={() => setActiveTab('heatmap')}
          className={`py-2.5 px-1 border-b-2 text-sm font-medium flex items-center space-x-2 transition ${
            activeTab === 'heatmap'
              ? 'border-teal-400 text-teal-300'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>Site Risk Heatmap</span>
        </button>

        <button
          onClick={() => setActiveTab('deviations')}
          className={`py-2.5 px-1 border-b-2 text-sm font-medium flex items-center space-x-2 transition ${
            activeTab === 'deviations'
              ? 'border-teal-400 text-teal-300'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
          }`}
        >
          <AlertTriangle className="w-4 h-4" />
          <span>Protocol Deviations</span>
          <span className="ml-1.5 px-1.5 py-0.5 rounded-full text-[11px] bg-slate-800 text-slate-300">
            {totalDeviations}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('capa')}
          className={`py-2.5 px-1 border-b-2 text-sm font-medium flex items-center space-x-2 transition ${
            activeTab === 'capa'
              ? 'border-teal-400 text-teal-300'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
          }`}
        >
          <FileCheck2 className="w-4 h-4" />
          <span>CAPA Reports &amp; Export</span>
        </button>
      </div>
    </header>
  );
};
