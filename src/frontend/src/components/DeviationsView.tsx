import React, { useState, useMemo } from 'react';
import {
  AlertTriangle,
  Sparkles,
  Search,
  ChevronDown,
  ChevronUp,
  FileCode,
  Calendar,
  RefreshCw,
} from 'lucide-react';
import type { Deviation } from '../types';

interface DeviationsViewProps {
  deviations: Deviation[];
  onTriggerDetection: () => void;
  isDetecting: boolean;
}

export const DeviationsView: React.FC<DeviationsViewProps> = ({
  deviations,
  onTriggerDetection,
  isDetecting,
}) => {
  const [siteFilter, setSiteFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [onlyAiAdjusted, setOnlyAiAdjusted] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedDevId, setExpandedDevId] = useState<string | null>(null);

  // Collect unique sites and types for dropdowns
  const availableSites = useMemo(() => {
    return Array.from(new Set(deviations.map((d) => d.site_id))).sort();
  }, [deviations]);

  const availableTypes = useMemo(() => {
    return Array.from(new Set(deviations.map((d) => d.type))).sort();
  }, [deviations]);

  // Filtered deviations
  const filteredDeviations = useMemo(() => {
    return deviations.filter((dev) => {
      if (siteFilter !== 'all' && dev.site_id !== siteFilter) return false;
      if (typeFilter !== 'all' && dev.type !== typeFilter) return false;

      const finalSev = (dev.final_severity || dev.severity).toLowerCase();
      if (severityFilter !== 'all' && finalSev !== severityFilter.toLowerCase()) return false;

      const isOverride =
        dev.severity_source === 'llm_override' ||
        (dev.default_severity && dev.final_severity && dev.default_severity !== dev.final_severity);

      if (onlyAiAdjusted && !isOverride) return false;

      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesId = dev.deviation_id.toLowerCase().includes(query);
        const matchesRationale = (dev.severity_rationale || '').toLowerCase().includes(query);
        const matchesType = dev.type.toLowerCase().includes(query);
        if (!matchesId && !matchesRationale && !matchesType) return false;
      }

      return true;
    });
  }, [deviations, siteFilter, typeFilter, severityFilter, onlyAiAdjusted, searchQuery]);

  const toggleExpand = (id: string) => {
    setExpandedDevId(expandedDevId === id ? null : id);
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'major':
        return 'bg-rose-100 text-rose-800 border-rose-300';
      case 'minor':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      case 'administrative':
        return 'bg-slate-100 text-slate-700 border-slate-300';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-300';
    }
  };

  return (
    <div className="space-y-6">
      {/* Title & Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h2 className="text-lg font-bold text-slate-900 m-0">Protocol Deviations &amp; Severity Audit</h2>
          <p className="text-sm text-slate-500 m-0">
            Detected breaches showing deterministic rule defaults, AI/LLM clinical reviews, and audit trail evidence.
          </p>
        </div>

        <button
          onClick={onTriggerDetection}
          disabled={isDetecting}
          className="flex items-center space-x-1.5 px-3.5 py-2 rounded-lg bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold shadow transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isDetecting ? 'animate-spin' : ''}`} />
          <span>{isDetecting ? 'Running Engine...' : 'Run Detection Engine'}</span>
        </button>
      </div>

      {/* Filter Controls Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* Search box */}
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search ID, type, rationale..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs focus:ring-1 focus:ring-teal-500 focus:bg-white text-slate-800 placeholder-slate-400"
            />
          </div>

          {/* Site Filter */}
          <div>
            <select
              value={siteFilter}
              onChange={(e) => setSiteFilter(e.target.value)}
              className="w-full py-1.5 px-3 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:ring-1 focus:ring-teal-500"
            >
              <option value="all">All Sites ({availableSites.length})</option>
              {availableSites.map((site) => (
                <option key={site} value={site}>
                  {site}
                </option>
              ))}
            </select>
          </div>

          {/* Type Filter */}
          <div>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full py-1.5 px-3 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:ring-1 focus:ring-teal-500"
            >
              <option value="all">All Deviation Types</option>
              {availableTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

          {/* Severity Filter */}
          <div>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="w-full py-1.5 px-3 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:ring-1 focus:ring-teal-500"
            >
              <option value="all">All Severities</option>
              <option value="major">Major</option>
              <option value="minor">Minor</option>
              <option value="administrative">Administrative</option>
            </select>
          </div>

          {/* AI Adjusted Toggle */}
          <div className="flex items-center">
            <label className="flex items-center space-x-2 text-xs font-semibold text-slate-700 cursor-pointer select-none bg-slate-50 p-1.5 rounded-lg border border-slate-200 w-full hover:bg-slate-100">
              <input
                type="checkbox"
                checked={onlyAiAdjusted}
                onChange={(e) => setOnlyAiAdjusted(e.target.checked)}
                className="rounded border-slate-300 text-teal-600 focus:ring-teal-500 w-3.5 h-3.5"
              />
              <span className="flex items-center space-x-1">
                <Sparkles className="w-3.5 h-3.5 text-purple-600" />
                <span>AI Adjusted Only</span>
              </span>
            </label>
          </div>
        </div>

        {/* Results summary counter */}
        <div className="text-xs text-slate-500 pt-1 flex items-center justify-between">
          <span>
            Showing <strong className="text-slate-800">{filteredDeviations.length}</strong> of{' '}
            {deviations.length} deviations
          </span>
          {(siteFilter !== 'all' || typeFilter !== 'all' || severityFilter !== 'all' || onlyAiAdjusted || searchQuery) && (
            <button
              onClick={() => {
                setSiteFilter('all');
                setTypeFilter('all');
                setSeverityFilter('all');
                setOnlyAiAdjusted(false);
                setSearchQuery('');
              }}
              className="text-teal-600 hover:text-teal-700 font-medium"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Deviations List */}
      <div className="space-y-3">
        {filteredDeviations.map((dev) => {
          const finalSev = dev.final_severity || dev.severity;
          const defaultSev = dev.default_severity || dev.severity;
          const isAiAdjusted =
            dev.severity_source === 'llm_override' ||
            (dev.default_severity && dev.final_severity && dev.default_severity !== dev.final_severity);
          const isExpanded = expandedDevId === dev.deviation_id;

          return (
            <div
              key={dev.deviation_id}
              className={`bg-white rounded-xl border transition overflow-hidden shadow-sm ${
                isAiAdjusted ? 'border-purple-200 hover:border-purple-400' : 'border-slate-200 hover:border-slate-300'
              }`}
            >
              {/* Row summary header */}
              <div
                onClick={() => toggleExpand(dev.deviation_id)}
                className="p-4 flex flex-wrap items-center justify-between gap-3 cursor-pointer hover:bg-slate-50/70 select-none"
              >
                <div className="flex items-center space-x-3">
                  <span className="font-mono font-bold text-xs text-slate-900 bg-slate-100 px-2 py-1 rounded">
                    {dev.deviation_id}
                  </span>

                  <span className="font-semibold text-xs text-slate-800">
                    {dev.site_id}
                  </span>

                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                    {dev.type}
                  </span>

                  {/* AI Adjusted Badge */}
                  {isAiAdjusted ? (
                    <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-purple-100 text-purple-800 border border-purple-300">
                      <Sparkles className="w-3 h-3 text-purple-600" />
                      <span>AI Adjusted: {defaultSev} → {finalSev}</span>
                    </span>
                  ) : (
                    <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${getSeverityBadge(finalSev)}`}>
                      {finalSev.toUpperCase()}
                    </span>
                  )}
                </div>

                <div className="flex items-center space-x-4 text-xs text-slate-400">
                  {dev.detected_at && (
                    <span className="flex items-center">
                      <Calendar className="w-3.5 h-3.5 mr-1 text-slate-400" />
                      {new Date(dev.detected_at).toLocaleDateString()}
                    </span>
                  )}
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-slate-500" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-500" />
                  )}
                </div>
              </div>

              {/* Rationale callout */}
              <div className="px-4 pb-3">
                {isAiAdjusted ? (
                  <div className="bg-purple-50/80 border border-purple-200 rounded-lg p-3 text-xs text-purple-900 mb-1">
                    <span className="font-bold flex items-center mb-1 text-purple-800">
                      <Sparkles className="w-3.5 h-3.5 mr-1 text-purple-600" />
                      AI Severity Review Override:
                    </span>
                    <p className="m-0 leading-relaxed font-medium">
                      AI adjusted this deviation from <strong className="uppercase">{defaultSev}</strong> to{' '}
                      <strong className="uppercase">{finalSev}</strong>: {dev.severity_rationale}
                    </p>
                  </div>
                ) : (
                  <p className="text-xs text-slate-600 font-medium m-0">
                    <span className="text-slate-400 mr-1.5 font-semibold">Rationale:</span>
                    {dev.severity_rationale || 'Evaluated against deterministic protocol rules.'}
                  </p>
                )}
              </div>

              {/* Expandable Audit Evidence Inspector */}
              {isExpanded && (
                <div className="border-t border-slate-100 bg-slate-50 p-4 space-y-3">
                  <div className="flex items-center justify-between text-xs text-slate-600">
                    <span className="font-bold uppercase tracking-wider flex items-center space-x-1 text-slate-700">
                      <FileCode className="w-3.5 h-3.5 text-teal-600 mr-1" />
                      Deterministic Audit Trail Evidence
                    </span>
                    <span className="font-mono text-[11px] text-slate-400">
                      Record: {dev.record_id || 'N/A'}
                    </span>
                  </div>

                  <div className="bg-slate-900 text-slate-200 p-3 rounded-lg text-xs font-mono overflow-x-auto">
                    <pre className="m-0 leading-relaxed">
                      {JSON.stringify(dev.evidence || {}, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {filteredDeviations.length === 0 && (
          <div className="text-center py-12 bg-white rounded-xl border border-slate-200 text-slate-400">
            <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-slate-300" />
            <p className="text-sm font-medium">No protocol deviations match the current filter criteria.</p>
          </div>
        )}
      </div>
    </div>
  );
};
