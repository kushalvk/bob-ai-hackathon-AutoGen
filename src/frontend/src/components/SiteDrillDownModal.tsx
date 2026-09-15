import React from 'react';
import {
  X,
  Calendar,
  AlertTriangle,
  Building2,
  Activity,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from 'recharts';
import type { SiteRiskScore, Deviation } from '../types';

interface SiteDrillDownModalProps {
  siteId: string | null;
  score: SiteRiskScore | undefined;
  deviations: Deviation[];
  onClose: () => void;
  onSelectDeviation?: (dev: Deviation) => void;
}

export const SiteDrillDownModal: React.FC<SiteDrillDownModalProps> = ({
  siteId,
  score,
  deviations,
  onClose,
  onSelectDeviation: _onSelectDeviation,
}) => {
  if (!siteId || !score) return null;

  // Filter deviations for this site and sort chronologically
  const siteDeviations = deviations
    .filter((d) => d.site_id === siteId)
    .sort((a, b) => {
      const dateA = a.detected_at ? new Date(a.detected_at).getTime() : 0;
      const dateB = b.detected_at ? new Date(b.detected_at).getTime() : 0;
      return dateB - dateA; // Most recent first
    });

  // Prepare Recharts bar chart data for the 7 contributing factors
  const chartData = (score.contributing_factors || []).map((f) => ({
    factor: f.name || f.factor,
    contribution: Number(f.contribution.toFixed(2)),
    raw_value: f.raw_value,
    weight: Math.round(f.weight * 100),
    normalized: Math.round(f.normalized_score),
  })).sort((a, b) => b.contribution - a.contribution);

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

  const getTierColor = (s: number) => {
    if (s >= 60) return 'text-rose-600 bg-rose-50 border-rose-200';
    if (s >= 35) return 'text-amber-600 bg-amber-50 border-amber-200';
    return 'text-emerald-600 bg-emerald-50 border-emerald-200';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden my-auto animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="p-6 border-b border-slate-200 flex items-center justify-between bg-slate-50/80">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-teal-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
              <Building2 className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-xl font-bold text-slate-900 m-0">{siteId}</h2>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${getTierColor(score.score)}`}>
                  Score: {score.score.toFixed(1)} / 100
                </span>
              </div>
              <p className="text-xs text-slate-500 m-0">
                Detailed Risk Breakdown &amp; Protocol Deviation Timeline
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-8 flex-1">
          {/* Section 1: Contributing Factors Breakdown (Recharts) */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2 m-0">
                <Activity className="w-4 h-4 text-teal-600" />
                <span>Contributing Risk Factors (7-Factor Model)</span>
              </h3>
              <span className="text-xs text-slate-400">Values in weighted points contributed to total score</span>
            </div>

            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={chartData}
                    layout="vertical"
                    margin={{ top: 5, right: 30, left: 140, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                    <XAxis type="number" domain={[0, 'dataMax + 5']} tick={{ fontSize: 11 }} />
                    <YAxis
                      dataKey="factor"
                      type="category"
                      tick={{ fontSize: 11, fill: '#334155' }}
                      width={130}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="bg-slate-900 text-white p-3 rounded-lg shadow-lg text-xs space-y-1">
                              <p className="font-bold text-teal-300">{data.factor}</p>
                              <p>Points Contribution: <span className="font-semibold text-white">+{data.contribution} pts</span></p>
                              <p>Raw Metric Value: <span className="font-semibold text-slate-300">{data.raw_value}</span></p>
                              <p>Formula Weight: <span className="font-semibold text-slate-300">{data.weight}%</span></p>
                              <p>Normalized Score: <span className="font-semibold text-slate-300">{data.normalized}/100</span></p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Bar dataKey="contribution" radius={[0, 4, 4, 0]}>
                      {chartData.map((entry, idx) => (
                        <Cell
                          key={`cell-${idx}`}
                          fill={
                            entry.contribution > 15
                              ? '#f43f5e' // rose-500
                              : entry.contribution > 8
                              ? '#f59e0b' // amber-500
                              : '#0d9488' // teal-600
                          }
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Section 2: Deviation Timeline */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2 m-0">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                <span>Site Deviation Timeline ({siteDeviations.length} Detected)</span>
              </h3>
            </div>

            {siteDeviations.length === 0 ? (
              <div className="text-center py-8 bg-slate-50 rounded-xl border border-slate-200 text-slate-400 text-sm">
                No protocol deviations recorded for this site.
              </div>
            ) : (
              <div className="relative border-l-2 border-slate-200 ml-4 space-y-6">
                {siteDeviations.map((dev) => {
                  const sev = dev.final_severity || dev.severity;
                  return (
                    <div key={dev.deviation_id} className="relative pl-6 group">
                      {/* Timeline dot */}
                      <div
                        className={`absolute -left-[9px] top-1.5 w-4 h-4 rounded-full border-2 border-white ${
                          sev.toLowerCase() === 'major'
                            ? 'bg-rose-500'
                            : sev.toLowerCase() === 'minor'
                            ? 'bg-amber-500'
                            : 'bg-slate-400'
                        }`}
                      />

                      <div className="bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl p-4 transition shadow-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                          <div className="flex items-center space-x-2">
                            <span className="font-mono font-bold text-xs text-slate-900">
                              {dev.deviation_id}
                            </span>
                            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-200 text-slate-800">
                              {dev.type}
                            </span>
                            <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold border ${getSeverityBadge(sev)}`}>
                              {sev.toUpperCase()}
                            </span>
                          </div>

                          <div className="flex items-center text-xs text-slate-400 space-x-3">
                            {dev.detected_at && (
                              <span className="flex items-center">
                                <Calendar className="w-3.5 h-3.5 mr-1" />
                                {new Date(dev.detected_at).toLocaleDateString()}
                              </span>
                            )}
                            {dev.record_id && (
                              <span className="font-mono">Rec: {dev.record_id}</span>
                            )}
                          </div>
                        </div>

                        {/* Rationale */}
                        <p className="text-xs text-slate-700 mb-2 font-medium">
                          {dev.severity_rationale || 'Protocol deviation detected by deterministic audit engine.'}
                        </p>

                        {/* Evidence preview */}
                        {dev.evidence && Object.keys(dev.evidence).length > 0 && (
                          <div className="text-[11px] bg-white p-2.5 rounded-lg border border-slate-200 font-mono text-slate-600">
                            <span className="font-semibold text-slate-400 block mb-0.5">Evidence:</span>
                            {JSON.stringify(dev.evidence, null, 2)}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-200 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold transition"
          >
            Close Drill-Down
          </button>
        </div>
      </div>
    </div>
  );
};
