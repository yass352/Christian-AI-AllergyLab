export type AgentStatus = 'reponse' | 'abstention';

export interface TokenUsage {
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
}

export interface AgentStep {
  code: string;
}

export interface AgentResponse {
  status: AgentStatus;
  value: string | number | null;
  justification: string;
  usage: TokenUsage | null;
  steps: AgentStep[];
  duration_s: number | null;
  reused: boolean;
  /** Turned away by the team's guard (equipe/outils/garde_fous.py), with no model call. */
  blocked: boolean;
}

export interface ColumnSummary {
  name: string;
  missing: number;
  completeness_percent: number;
}

export interface DatasetSummary {
  rows: number;
  columns: number;
  clinical_columns: number;
  dosage_columns: number;
  missing_cells: number;
  completeness_percent: number;
  chips: Record<string, number>;
  sampling_months: number[];
  sampling_month_missing: number;
  fields: ColumnSummary[];
}

export interface PollenTaxon {
  taxon: string;
  family: string;
  acc_allergens: string;
  monthly_mean: number[];
}

export interface PollenCalendar {
  source: string;
  taxa: PollenTaxon[];
}

async function getJson<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
      ...options,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new Error('Serveur inaccessible. Démarre FastAPI sur 127.0.0.1:8000.');
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => ({}));
    const detail = typeof body === 'object' && body !== null &&
      'detail' in body && typeof body.detail === 'string' ? body.detail : null;
    throw new Error(detail ?? `Erreur du serveur (${response.status}).`);
  }

  return response.json() as Promise<T>;
}

export function askAgent(question: string, signal?: AbortSignal): Promise<AgentResponse> {
  return getJson<AgentResponse>('/api/agent/ask', {
    method: 'POST',
    body: JSON.stringify({ question }),
    signal,
  });
}

export function getDatasetSummary(): Promise<DatasetSummary> {
  return getJson<DatasetSummary>('/api/dataset/summary');
}

export function getPollenCalendar(): Promise<PollenCalendar> {
  return getJson<PollenCalendar>('/api/pollens/calendar');
}
