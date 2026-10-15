export type Environment = "simulated" | "kubernetes";
export type FaultAction = "pod-failure" | "network-delay" | "cpu-stress";

export interface Service {
  name: string;
  app_label: string;
  replicas: number;
  ready_replicas: number | null;
  desired_replicas: number | null;
  depends_on: string[];
  depended_by: string[];
  transitive_dependents: number;
  status: "healthy" | "degraded" | "failed" | "unknown";
  latest_experiment?: Experiment | null;
}

export interface Experiment {
  id: string;
  service: string;
  action: FaultAction;
  duration_s: number;
  score?: number;
  severity?: string;
  error_rate?: number;
  p95_ms?: number;
  recovered?: boolean;
  aborted?: boolean;
  abort_reason?: string | null;
  cleanup_confirmed?: boolean;
  phase_metrics?: Record<string, { error_rate?: number; p95_ms?: number; samples?: number }>;
  recommendations?: Recommendation[];
  ai_diagnosis?: string;
}

export interface Recommendation {
  title: string;
  detail: string;
  service: string;
  action: FaultAction;
  score?: number;
  severity?: string;
  run_id: string;
  environment?: Environment;
  auto_fix?: { type: string; service: string; replicas: number };
}

export interface Overview {
  data_available: boolean;
  environment: Environment;
  source: string;
  run_id: string | null;
  resilience_score: number | null;
  services_total: number;
  healthy_services: number | null;
  health_known: boolean;
  weaknesses: number;
  weakness_details?: WeaknessEvidence[];
  experiments_completed: number;
  active_experiment: ActiveRun | null;
  safety: { max_error_rate: number; p95_limit_ms: number; max_extra_unhealthy_pods: number };
  cleanup_confirmed: boolean | null;
  services: Service[];
  recent_experiments: Experiment[];
  suggested_experiments: Array<{ service: string; action: FaultAction; rationale?: string; rank?: number }>;
}

export interface ActiveRun {
  run_id: string;
  status: string;
  phase: string;
  service: string;
  action: FaultAction;
  environment: Environment;
  started_at?: string;
  cleanup_confirmed?: boolean | null;
  error?: string;
}

export interface RunSummary {
  run_id: string;
  env: Environment;
  planner: string;
  llm_model: string | null;
  resilience_score: number | null;
  weaknesses: Array<{ service: string; action: FaultAction; score: number }>;
  llm_execution?: { overall_source?: string; fallback_reason?: string };
  experiment_count: number;
  report_available: boolean;
}

export interface RunWeakness {
  service: string;
  action: FaultAction;
  score: number;
}

export interface WeaknessEvidence extends RunWeakness {
  severity?: string | null;
  error_rate?: number | null;
  p95_ms?: number | null;
  recovered?: boolean | null;
  recommendations: Array<{ title: string; detail: string }>;
}

export interface RunDetail extends RunSummary {
  experiments: Experiment[];
  weaknesses: RunWeakness[];
  ai_report?: { overall?: string; score_explanation?: string } | null;
}

export interface Preview {
  validated: boolean;
  environment: Environment;
  service: string;
  action: FaultAction;
  duration_s: number;
  fault_explanation: string;
  direct_dependents: string[];
  transitive_dependents: number;
  blast_radius: string;
  safety_thresholds: Overview["safety"];
  max_duration_s: number;
  rollback_plan: string;
  context: { available: boolean; current: string | null; approved: string | null; matches: boolean } | null;
  real_run_allowed: boolean;
  gemini_key_available: boolean;
  planner_note: string;
  warning?: string | null;
  simulation_notice?: string | null;
}

export interface DependencyEdge {
  from: string;
  to: string;
  via: string;
}

export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      message = body.detail || message;
    } catch {
      // Keep the HTTP status message when an error response is not JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}
