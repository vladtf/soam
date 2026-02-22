/** Copilot and error reporting API. */
import { doFetch, getConfig } from './apiCore';

// ── Error reporting ─────────────────────────────────────────────

export interface ClientErrorRow {
  id: number;
  message: string;
  stack?: string | null;
  url?: string | null;
  component?: string | null;
  context?: string | null;
  severity?: string | null;
  user_agent?: string | null;
  session_id?: string | null;
  extra?: Record<string, unknown> | null;
  created_at?: string | null;
}

export const fetchErrors = (limit: number = 200): Promise<ClientErrorRow[]> => {
  const { backendUrl } = getConfig();
  return doFetch<ClientErrorRow[]>(`${backendUrl}/api/errors/?limit=${limit}`);
};

// ── Copilot ─────────────────────────────────────────────────────

export interface ComputationRequest {
  user_prompt: string;
  context?: string;
  preferred_dataset?: string;
}

export interface ComputationSuggestion {
  title: string;
  description: string;
  dataset: string;
  definition: Record<string, unknown>;
  confidence: number;
  explanation: string;
  suggested_columns: string[];
}

export const generateComputationWithCopilot = (request: ComputationRequest): Promise<ComputationSuggestion> => {
  const { backendUrl } = getConfig();
  return doFetch<ComputationSuggestion>(`${backendUrl}/api/copilot/generate-computation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const getCopilotContext = (): Promise<any> => {
  const { backendUrl } = getConfig();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return doFetch<any>(`${backendUrl}/api/copilot/context`);
};

export const getCopilotHealth = (): Promise<{ available: boolean; reason?: string; endpoint?: string }> => {
  const { backendUrl } = getConfig();
  return doFetch<{ available: boolean; reason?: string; endpoint?: string }>(`${backendUrl}/api/copilot/health`);
};
