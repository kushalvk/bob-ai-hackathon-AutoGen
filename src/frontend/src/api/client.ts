/**
 * ClinGuard AI API Client.
 * Connects directly to FastAPI backend endpoints.
 */

import type { SiteRiskScore, Deviation, CAPAReport } from '../types';

const API_BASE = '';

export async function checkHealth(): Promise<{ status: string; database: string }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return res.json();
}

export async function fetchRiskScores(siteId?: string): Promise<SiteRiskScore[]> {
  const url = siteId
    ? `${API_BASE}/api/risk/scores?site_id=${encodeURIComponent(siteId)}`
    : `${API_BASE}/api/risk/scores`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch site risk scores: ${res.statusText}`);
  const data = await res.json();
  return data.scores || [];
}

export async function computeRiskScores(siteId?: string): Promise<any> {
  const url = siteId
    ? `${API_BASE}/api/risk/compute?site_id=${encodeURIComponent(siteId)}`
    : `${API_BASE}/api/risk/compute`;
  const res = await fetch(url, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to compute risk scores: ${res.statusText}`);
  return res.json();
}

export async function fetchDeviations(
  siteId?: string,
  deviationType?: string
): Promise<Deviation[]> {
  const params = new URLSearchParams();
  if (siteId) params.append('site_id', siteId);
  if (deviationType) params.append('deviation_type', deviationType);

  const query = params.toString() ? `?${params.toString()}` : '';
  const res = await fetch(`${API_BASE}/api/detect/results${query}`);
  if (!res.ok) throw new Error(`Failed to fetch deviations: ${res.statusText}`);
  const data = await res.json();
  return data.deviations || [];
}

export async function triggerDetectionRun(protocolId: string = 'PROTO-001'): Promise<any> {
  const res = await fetch(
    `${API_BASE}/api/detect/run?protocol_id=${encodeURIComponent(protocolId)}`,
    { method: 'POST' }
  );
  if (!res.ok) throw new Error(`Failed to run detection: ${res.statusText}`);
  return res.json();
}

export async function fetchCapaReports(siteId?: string): Promise<CAPAReport[]> {
  const url = siteId
    ? `${API_BASE}/api/capa/reports?site_id=${encodeURIComponent(siteId)}`
    : `${API_BASE}/api/capa/reports`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch CAPA reports: ${res.statusText}`);
  const data = await res.json();
  return data.reports || [];
}

export async function triggerCapaGeneration(siteId?: string): Promise<any> {
  const url = siteId
    ? `${API_BASE}/api/capa/generate?site_id=${encodeURIComponent(siteId)}`
    : `${API_BASE}/api/capa/generate`;
  const res = await fetch(url, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to generate CAPA reports: ${res.statusText}`);
  return res.json();
}

export function getCapaExportUrl(capaId: string, format: 'pdf' | 'markdown'): string {
  return `${API_BASE}/api/capa/${encodeURIComponent(capaId)}/export?format=${format}`;
}

export async function sendChatMessage(message: string): Promise<{
  answer: string;
  tool_called: string;
  tool_arguments: Record<string, any>;
  tool_result: any;
  grounded: boolean;
}> {
  const res = await fetch(`${API_BASE}/api/chat/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`Chat query failed: ${res.statusText}`);
  return res.json();
}
