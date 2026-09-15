import React, { useState } from 'react';
import {
  FileCheck2,
  FileDown,
  FileText,
  Calendar,
  User,
  Sparkles,
  ChevronRight,
} from 'lucide-react';
import type { CAPAReport } from '../types';
import { getCapaExportUrl } from '../api/client';

interface CapaViewProps {
  capaReports: CAPAReport[];
  onTriggerCapaGeneration: () => void;
  isGenerating: boolean;
}

export const CapaView: React.FC<CapaViewProps> = ({
  capaReports,
  onTriggerCapaGeneration,
  isGenerating,
}) => {
  const [selectedCapa, setSelectedCapa] = useState<CAPAReport | null>(null);

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'open':
        return 'bg-rose-100 text-rose-800 border-rose-300';
      case 'in_progress':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      case 'pending_review':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      case 'closed':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-300';
    }
  };

  return (
    <div className="space-y-6">
      {/* Title & Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h2 className="text-lg font-bold text-slate-900 m-0">
            Corrective &amp; Preventive Action (CAPA) Reports
          </h2>
          <p className="text-sm text-slate-500 m-0">
            Automated cluster-based CAPA generation. Export formal compliance documentation directly to PDF or Markdown.
          </p>
        </div>

        <button
          onClick={onTriggerCapaGeneration}
          disabled={isGenerating}
          className="flex items-center space-x-1.5 px-3.5 py-2 rounded-lg bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold shadow transition disabled:opacity-50"
        >
          <Sparkles className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
          <span>{isGenerating ? 'Clustering Deviations...' : 'Auto-Generate CAPAs'}</span>
        </button>
      </div>

      {/* CAPA Reports Table / Cards */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-semibold">
              <tr>
                <th className="py-3 px-4">CAPA ID</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Finding Summary</th>
                <th className="py-3 px-4">Assigned Owner</th>
                <th className="py-3 px-4">Due Date</th>
                <th className="py-3 px-4 text-right">Export Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {capaReports.map((capa) => (
                <tr
                  key={capa.capa_id}
                  className="hover:bg-slate-50/80 transition cursor-pointer"
                  onClick={() => setSelectedCapa(capa)}
                >
                  <td className="py-3.5 px-4 font-mono font-bold text-slate-900 whitespace-nowrap">
                    {capa.capa_id}
                  </td>

                  <td className="py-3.5 px-4 whitespace-nowrap">
                    <span className={`px-2.5 py-0.5 rounded-full font-bold border text-[11px] ${getStatusBadge(capa.status)}`}>
                      {capa.status.toUpperCase()}
                    </span>
                  </td>

                  <td className="py-3.5 px-4 text-slate-700 max-w-md">
                    <p className="line-clamp-2 m-0 font-medium leading-relaxed">
                      {capa.finding || 'Clustered protocol deviations requiring corrective intervention.'}
                    </p>
                    <span className="text-[11px] text-slate-400">
                      Covers {capa.deviation_ids?.length || 0} deviation(s)
                    </span>
                  </td>

                  <td className="py-3.5 px-4 text-slate-600 whitespace-nowrap">
                    <div className="flex items-center space-x-1.5">
                      <User className="w-3.5 h-3.5 text-slate-400" />
                      <span>{capa.owner || 'Unassigned'}</span>
                    </div>
                  </td>

                  <td className="py-3.5 px-4 text-slate-600 whitespace-nowrap">
                    <div className="flex items-center space-x-1.5">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      <span>{capa.due_date ? new Date(capa.due_date).toLocaleDateString() : 'Pending'}</span>
                    </div>
                  </td>

                  {/* Export Buttons */}
                  <td className="py-3.5 px-4 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center justify-end space-x-2">
                      <a
                        href={getCapaExportUrl(capa.capa_id, 'markdown')}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-[11px] transition border border-slate-200"
                        title="Download Markdown Report"
                      >
                        <FileText className="w-3 h-3 text-slate-500" />
                        <span>MD</span>
                      </a>

                      <a
                        href={getCapaExportUrl(capa.capa_id, 'pdf')}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-teal-50 hover:bg-teal-100 text-teal-700 font-semibold text-[11px] transition border border-teal-200"
                        title="Download Formal PDF Report"
                      >
                        <FileDown className="w-3 h-3 text-teal-600" />
                        <span>PDF</span>
                      </a>

                      <button
                        onClick={() => setSelectedCapa(capa)}
                        className="p-1 text-slate-400 hover:text-slate-600"
                        title="View Full Details"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}

              {capaReports.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400">
                    <FileCheck2 className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                    <p className="font-medium text-sm">No CAPA reports have been generated yet.</p>
                    <button
                      onClick={onTriggerCapaGeneration}
                      className="mt-2 text-xs font-semibold text-teal-600 hover:underline"
                    >
                      Run Auto-Generation to cluster deviations
                    </button>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detailed CAPA Viewer Modal */}
      {selectedCapa && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden my-auto animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-200 flex items-center justify-between bg-slate-50/80">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-lg bg-teal-600 flex items-center justify-center text-white">
                  <FileCheck2 className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="text-base font-bold text-slate-900 m-0">
                      {selectedCapa.capa_id}
                    </h3>
                    <span className={`px-2 py-0.5 rounded-full font-bold border text-[11px] ${getStatusBadge(selectedCapa.status)}`}>
                      {selectedCapa.status.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 m-0">
                    Assigned: {selectedCapa.owner} | Due: {selectedCapa.due_date}
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <a
                  href={getCapaExportUrl(selectedCapa.capa_id, 'pdf')}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-teal-600 text-white text-xs font-semibold hover:bg-teal-700 transition"
                >
                  <FileDown className="w-3.5 h-3.5" />
                  <span>Download PDF</span>
                </a>
                <button
                  onClick={() => setSelectedCapa(null)}
                  className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-700 flex-1">
              {/* Finding */}
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                <h4 className="font-bold text-slate-900 uppercase tracking-wider text-[11px] mb-1">
                  Deviation Finding Summary
                </h4>
                <p className="m-0 leading-relaxed font-medium">
                  {selectedCapa.finding || 'Protocol deviations detected at site.'}
                </p>
                <div className="mt-2 text-slate-400 font-mono text-[11px]">
                  Associated Deviations: {JSON.stringify(selectedCapa.deviation_ids)}
                </div>
              </div>

              {/* Root Cause */}
              <div>
                <h4 className="font-bold text-slate-900 uppercase tracking-wider text-[11px] mb-1 flex items-center space-x-1">
                  <span>Root Cause Analysis (ICH E6-R2)</span>
                </h4>
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 leading-relaxed">
                  {selectedCapa.root_cause}
                </div>
              </div>

              {/* Corrective Action */}
              <div>
                <h4 className="font-bold text-slate-900 uppercase tracking-wider text-[11px] mb-1">
                  Immediate Corrective Action
                </h4>
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 leading-relaxed">
                  {selectedCapa.corrective_action}
                </div>
              </div>

              {/* Preventive Action */}
              <div>
                <h4 className="font-bold text-slate-900 uppercase tracking-wider text-[11px] mb-1">
                  Long-term Preventive Action
                </h4>
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 leading-relaxed">
                  {selectedCapa.preventive_action}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 flex justify-between items-center text-xs">
              <a
                href={getCapaExportUrl(selectedCapa.capa_id, 'markdown')}
                target="_blank"
                rel="noreferrer"
                className="text-teal-600 hover:underline font-semibold flex items-center space-x-1"
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Export as Raw Markdown</span>
              </a>

              <button
                onClick={() => setSelectedCapa(null)}
                className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-semibold transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
