import { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { RiskHeatmapView } from './components/RiskHeatmapView';
import { SiteDrillDownModal } from './components/SiteDrillDownModal';
import { DeviationsView } from './components/DeviationsView';
import { CapaView } from './components/CapaView';
import { ChatPanel } from './components/ChatPanel';
import {
  fetchRiskScores,
  fetchDeviations,
  fetchCapaReports,
  computeRiskScores,
  triggerDetectionRun,
  triggerCapaGeneration,
} from './api/client';
import type { SiteRiskScore, Deviation, CAPAReport } from './types';
import { AlertCircle, Loader2 } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<'heatmap' | 'deviations' | 'capa'>('heatmap');
  const [scores, setScores] = useState<SiteRiskScore[]>([]);
  const [deviations, setDeviations] = useState<Deviation[]>([]);
  const [capaReports, setCapaReports] = useState<CAPAReport[]>([]);

  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null);
  const [isChatOpen, setIsChatOpen] = useState<boolean>(false);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isDetecting, setIsDetecting] = useState<boolean>(false);
  const [isRecomputingRisk, setIsRecomputingRisk] = useState<boolean>(false);
  const [isGeneratingCapa, setIsGeneratingCapa] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Load all data from real backend API
  const loadData = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setIsRefreshing(true);
    setErrorMessage(null);

    try {
      const [scoresData, devsData, capaData] = await Promise.all([
        fetchRiskScores(),
        fetchDeviations(),
        fetchCapaReports(),
      ]);

      setScores(scoresData);
      setDeviations(devsData);
      setCapaReports(capaData);
    } catch (err: any) {
      console.error('Data loading failed:', err);
      setErrorMessage(
        err.message || 'Failed to connect to ClinGuard backend. Please ensure the backend server is running.'
      );
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handler: Run deviation detection engine
  const handleTriggerDetection = async () => {
    setIsDetecting(true);
    try {
      await triggerDetectionRun('PROTO-001');
      await loadData();
    } catch (err: any) {
      alert(`Detection run failed: ${err.message}`);
    } finally {
      setIsDetecting(false);
    }
  };

  // Handler: Recompute site risk scores
  const handleRecomputeRisk = async () => {
    setIsRecomputingRisk(true);
    try {
      await computeRiskScores();
      await loadData();
    } catch (err: any) {
      alert(`Risk calculation failed: ${err.message}`);
    } finally {
      setIsRecomputingRisk(false);
    }
  };

  // Handler: Auto-generate CAPAs
  const handleTriggerCapa = async () => {
    setIsGeneratingCapa(true);
    try {
      await triggerCapaGeneration();
      await loadData();
    } catch (err: any) {
      alert(`CAPA generation failed: ${err.message}`);
    } finally {
      setIsGeneratingCapa(false);
    }
  };

  // Computed global metrics
  const totalDeviations = deviations.length;
  const majorDeviations = deviations.filter(
    (d) => (d.final_severity || d.severity).toLowerCase() === 'major'
  ).length;

  const highestRisk = scores.reduce(
    (max, s) => (s.score > max.score ? s : max),
    { site_id: '', score: 0 } as { site_id: string; score: number }
  );

  const selectedSiteScore = scores.find((s) => s.site_id === selectedSiteId);

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans text-slate-800">
      {/* Top Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        siteCount={scores.length}
        totalDeviations={totalDeviations}
        majorDeviations={majorDeviations}
        highestRiskScore={highestRisk.score}
        highestRiskSite={highestRisk.site_id}
        onRefresh={() => loadData(true)}
        isRefreshing={isRefreshing}
        toggleChat={() => setIsChatOpen(!isChatOpen)}
        isChatOpen={isChatOpen}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Error message banner if backend is unreachable */}
        {errorMessage && (
          <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start space-x-3 text-xs shadow-xs">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-sm mb-0.5">Backend Connection Alert</p>
              <p className="m-0 leading-relaxed">{errorMessage}</p>
              <button
                onClick={() => loadData(true)}
                className="mt-2 px-2.5 py-1 bg-rose-600 text-white rounded font-semibold hover:bg-rose-700 transition"
              >
                Retry Connection
              </button>
            </div>
          </div>
        )}

        {/* Loading Spinner */}
        {isLoading ? (
          <div className="py-24 flex flex-col items-center justify-center space-y-3 text-slate-400">
            <Loader2 className="w-8 h-8 text-teal-600 animate-spin" />
            <p className="text-xs font-semibold uppercase tracking-wider">
              Loading Live Trial Compliance Data...
            </p>
          </div>
        ) : (
          <>
            {/* View 1: Risk Heatmap */}
            {activeTab === 'heatmap' && (
              <RiskHeatmapView
                scores={scores}
                deviations={deviations}
                onSelectSite={(siteId) => setSelectedSiteId(siteId)}
                onRecomputeRisk={handleRecomputeRisk}
                isRecomputing={isRecomputingRisk}
              />
            )}

            {/* View 2: Deviations Inspector */}
            {activeTab === 'deviations' && (
              <DeviationsView
                deviations={deviations}
                onTriggerDetection={handleTriggerDetection}
                isDetecting={isDetecting}
              />
            )}

            {/* View 3: CAPA Reports & Export */}
            {activeTab === 'capa' && (
              <CapaView
                capaReports={capaReports}
                onTriggerCapaGeneration={handleTriggerCapa}
                isGenerating={isGeneratingCapa}
              />
            )}
          </>
        )}
      </main>

      {/* Site Drill-Down Modal */}
      {selectedSiteId && (
        <SiteDrillDownModal
          siteId={selectedSiteId}
          score={selectedSiteScore}
          deviations={deviations}
          onClose={() => setSelectedSiteId(null)}
        />
      )}

      {/* Grounded MCP Chat Panel */}
      <ChatPanel isOpen={isChatOpen} onClose={() => setIsChatOpen(false)} />

      {/* Minimal Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-400">
        <p className="m-0">
          ClinGuard AI • Protocol Compliance, Risk Scoring &amp; CAPA Automation • Grounded in Real Trial Data
        </p>
      </footer>
    </div>
  );
}

export default App;
