import React, { useState, useMemo } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import type { SiteRiskScore, Deviation } from '../types';

interface RiskHeatmapViewProps {
  scores: SiteRiskScore[];
  deviations: Deviation[];
  onSelectSite: (siteId: string) => void;
  onRecomputeRisk: () => void;
  isRecomputing: boolean;
}

export const RiskHeatmapView: React.FC<RiskHeatmapViewProps> = ({
  scores,
  deviations,
  onSelectSite,
  onRecomputeRisk,
  isRecomputing,
}) => {
  const [sortField, setSortField] = useState<'score' | 'site_id' | 'deviations'>('score');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Augment score records with counts from deviations
  const enrichedSites = useMemo(() => {
    return scores.map((s) => {
      const siteDevs = deviations.filter((d) => d.site_id === s.site_id);
      const majorCount = siteDevs.filter(
        (d) => (d.final_severity || d.severity).toLowerCase() === 'major'
      ).length;

      // Determine risk tier
      let tier: 'High' | 'Medium' | 'Low' = 'Low';
      if (s.score >= 60) tier = 'High';
      else if (s.score >= 35) tier = 'Medium';

      // Trend indicator based on major deviation proportion or scoring factors
      const trendRatio = s.contributing_factors.find((f) => f.factor === 'deviation_trend')?.raw_value || 1.0;
      let trend: 'up' | 'down' | 'stable' = 'stable';
      if (trendRatio > 1.05) trend = 'up';
      else if (trendRatio < 0.95) trend = 'down';

      return {
        ...s,
        tier,
        deviation_count: siteDevs.length,
        major_deviation_count: majorCount,
        trend,
      };
    });
  }, [scores, deviations]);

  // Sort sites
  const sortedSites = useMemo(() => {
    return [...enrichedSites].sort((a, b) => {
      let comparison = 0;
      if (sortField === 'score') {
        comparison = a.score - b.score;
      } else if (sortField === 'site_id') {
        comparison = a.site_id.localeCompare(b.site_id);
      } else if (sortField === 'deviations') {
        comparison = (a.deviation_count || 0) - (b.deviation_count || 0);
      }
      return sortOrder === 'desc' ? -comparison : comparison;
    });
  }, [enrichedSites, sortField, sortOrder]);

  const toggleSort = (field: 'score' | 'site_id' | 'deviations') => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const getTierColors = (tier: 'High' | 'Medium' | 'Low') => {
    switch (tier) {
      case 'High':
        return {
          bg: 'bg-rose-50 border-rose-200',
          badge: 'bg-rose-100 text-rose-800 border-rose-300',
          bar: 'bg-rose-500',
          text: 'text-rose-700',
        };
      case 'Medium':
        return {
          bg: 'bg-amber-50 border-amber-200',
          badge: 'bg-amber-100 text-amber-800 border-amber-300',
          bar: 'bg-amber-500',
          text: 'text-amber-700',
        };
      case 'Low':
        return {
          bg: 'bg-emerald-50 border-emerald-200',
          badge: 'bg-emerald-100 text-emerald-800 border-emerald-300',
          bar: 'bg-emerald-500',
          text: 'text-emerald-700',
        };
    }
  };

  return (
    <div className="space-y-6">
      {/* Title & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h2 className="text-lg font-bold text-slate-900 m-0">Site Risk Evaluation Heatmap</h2>
          <p className="text-sm text-slate-500 m-0">
            Multi-factor composite risk scores (0–100) computed from protocol deviations, staff turnover, and operational signals.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50 p-1 text-xs">
            <span className="px-2 font-medium text-slate-500">Sort by:</span>
            <button
              onClick={() => toggleSort('score')}
              className={`px-2.5 py-1 rounded font-semibold transition ${
                sortField === 'score' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Score {sortField === 'score' && (sortOrder === 'desc' ? '↓' : '↑')}
            </button>
            <button
              onClick={() => toggleSort('deviations')}
              className={`px-2.5 py-1 rounded font-semibold transition ${
                sortField === 'deviations' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Deviations {sortField === 'deviations' && (sortOrder === 'desc' ? '↓' : '↑')}
            </button>
            <button
              onClick={() => toggleSort('site_id')}
              className={`px-2.5 py-1 rounded font-semibold transition ${
                sortField === 'site_id' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Site ID {sortField === 'site_id' && (sortOrder === 'desc' ? '↓' : '↑')}
            </button>
          </div>

          <button
            onClick={onRecomputeRisk}
            disabled={isRecomputing}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-lg bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold shadow transition disabled:opacity-50"
          >
            <Sparkles className={`w-3.5 h-3.5 ${isRecomputing ? 'animate-spin' : ''}`} />
            <span>{isRecomputing ? 'Computing...' : 'Recalculate Risk'}</span>
          </button>
        </div>
      </div>

      {/* Heatmap Ranked Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {sortedSites.map((site, index) => {
          const colors = getTierColors(site.tier);
          const topFactor = [...site.contributing_factors].sort(
            (a, b) => b.contribution - a.contribution
          )[0];

          return (
            <div
              key={site.site_id}
              onClick={() => onSelectSite(site.site_id)}
              className={`rounded-xl border p-5 transition cursor-pointer hover:shadow-md relative overflow-hidden bg-white hover:border-slate-400 group`}
            >
              {/* Colored top indicator strip */}
              <div className={`absolute top-0 left-0 right-0 h-1.5 ${colors.bar}`} />

              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center space-x-2">
                  <span className="w-6 h-6 rounded-full bg-slate-100 text-slate-600 font-bold text-xs flex items-center justify-center">
                    #{index + 1}
                  </span>
                  <h3 className="font-bold text-base text-slate-900 m-0 group-hover:text-teal-600 transition">
                    {site.site_id}
                  </h3>
                </div>

                {/* Score & Tier Badge */}
                <div className="flex items-center space-x-2">
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${colors.badge}`}>
                    {site.tier} Risk
                  </span>
                </div>
              </div>

              {/* Big Score Display */}
              <div className="flex items-baseline justify-between my-3">
                <div className="flex items-baseline space-x-1.5">
                  <span className={`text-3xl font-extrabold tracking-tight ${colors.text}`}>
                    {site.score.toFixed(1)}
                  </span>
                  <span className="text-slate-400 text-xs font-medium">/ 100</span>
                </div>

                {/* Trend indicator */}
                <div className="flex items-center space-x-1 text-xs font-semibold">
                  {site.trend === 'up' ? (
                    <span className="flex items-center text-rose-600 bg-rose-50 px-2 py-0.5 rounded" title="Risk increasing vs baseline">
                      <TrendingUp className="w-3.5 h-3.5 mr-1" />
                      Rising
                    </span>
                  ) : site.trend === 'down' ? (
                    <span className="flex items-center text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded" title="Risk decreasing / improving">
                      <TrendingDown className="w-3.5 h-3.5 mr-1" />
                      Improving
                    </span>
                  ) : (
                    <span className="flex items-center text-slate-500 bg-slate-50 px-2 py-0.5 rounded">
                      <Minus className="w-3.5 h-3.5 mr-1" />
                      Stable
                    </span>
                  )}
                </div>
              </div>

              {/* Progress bar representing risk score */}
              <div className="w-full bg-slate-100 rounded-full h-2 mb-4 overflow-hidden">
                <div
                  className={`h-2 rounded-full ${colors.bar}`}
                  style={{ width: `${Math.min(site.score, 100)}%` }}
                />
              </div>

              {/* Site Quick Stats */}
              <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 mb-3 bg-slate-50 p-2.5 rounded-lg">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">Deviations</span>
                  <span className="font-bold text-slate-800">
                    {site.deviation_count} total
                    {site.major_deviation_count ? (
                      <span className="text-rose-600 font-semibold ml-1">
                        ({site.major_deviation_count} major)
                      </span>
                    ) : null}
                  </span>
                </div>

                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">Top Risk Driver</span>
                  <span className="font-semibold text-slate-800 truncate block" title={topFactor?.name}>
                    {topFactor ? topFactor.name : 'Routine monitoring'}
                  </span>
                </div>
              </div>

              {/* Action Link */}
              <div className="flex items-center justify-between text-xs text-teal-600 font-semibold pt-1 border-t border-slate-100">
                <span>View Timeline &amp; Factor Breakdown</span>
                <ChevronRight className="w-4 h-4 transform group-hover:translate-x-1 transition" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
