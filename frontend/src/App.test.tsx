import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import App from "./App";

vi.mock("./api", () => ({ api: vi.fn() }));

const overview = {
  data_available: false,
  environment: "simulated" as const,
  source: "no saved simulation",
  run_id: null,
  resilience_score: null,
  services_total: 0,
  healthy_services: null,
  health_known: false,
  weaknesses: 0,
  experiments_completed: 0,
  active_experiment: null,
  safety: { max_error_rate: 0.5, p95_limit_ms: 1500, max_extra_unhealthy_pods: 3 },
  cleanup_confirmed: null,
  services: [],
  weakness_details: [],
  recent_experiments: [],
  suggested_experiments: [],
};

const runDetail = {
  run_id: "20261011-001852-556282",
  env: "kubernetes" as const,
  planner: "rule-based",
  llm_model: null,
  resilience_score: 49.6,
  weaknesses: [
    { service: "cartservice", action: "network-delay" as const, score: 26.4 },
    { service: "productcatalogservice", action: "pod-failure" as const, score: 47.5 },
    { service: "currencyservice", action: "cpu-stress" as const, score: 75 },
  ],
  experiment_count: 3,
  report_available: true,
  experiments: [
    { id: "exp1", service: "cartservice", action: "network-delay" as const, duration_s: 30, score: 26.4, error_rate: 0.6, p95_ms: 4230, recovered: true, recommendations: [{ title: "Add circuit breaker", detail: "Bound retries and latency." }] },
    { id: "exp2", service: "productcatalogservice", action: "pod-failure" as const, duration_s: 30, score: 47.5, error_rate: 0.6, p95_ms: 2100, recovered: true, recommendations: [{ title: "Run at least 2 replicas", detail: "Losing its pod caused errors." }] },
    { id: "exp3", service: "currencyservice", action: "cpu-stress" as const, duration_s: 30, score: 75, error_rate: 0, p95_ms: 900, recovered: true, recommendations: [{ title: "Set CPU limits", detail: "CPU pressure raised response latency." }] },
  ],
};

function mockDashboardApi(overrides: Record<string, unknown> = {}) {
  vi.mocked(api).mockImplementation(async <T,>(path: string) => {
    const responses: Record<string, unknown> = {
      "/api/overview": overview,
      "/api/services": { environment: "simulated", services: [], edges: [] },
      "/api/runs": {
        runs: [{
          run_id: runDetail.run_id,
          env: runDetail.env,
          planner: runDetail.planner,
          llm_model: runDetail.llm_model,
          resilience_score: runDetail.resilience_score,
          weaknesses: runDetail.weaknesses,
          experiment_count: runDetail.experiment_count,
          report_available: runDetail.report_available,
        }],
        data_available: true,
      },
      "/api/recommendations": { recommendations: [], data_available: false },
      "/api/findings": { run_id: null, findings: [], data_available: false },
      "/api/agents/status": { run_id: null, status: "idle", agents: [], timeline: [] },
      "/api/experiments/status": { active: false, run: null, timeline: [] },
      ...overrides,
    };
    if (path === `/api/runs/${runDetail.run_id}`) return runDetail as T;
    return responses[path.split("?")[0]] as T;
  });
}

beforeEach(() => {
  mockDashboardApi();
});

afterEach(cleanup);

describe("ChaosPilot dashboard", () => {
  it("renders saved-data empty states without inventing runtime health", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Resilience command center" })).toBeInTheDocument();
    expect(screen.getByText("— / 0")).toBeInTheDocument();
    expect(screen.getByText("Saved-data demo")).toBeInTheDocument();
  });

  it("inspects and displays all three saved weaknesses with their run evidence", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "Resilience command center" });

    fireEvent.click(within(screen.getByRole("navigation", { name: "Main navigation" })).getByRole("button", { name: /Reports & history/ }));

    expect(await screen.findByRole("heading", { name: "Reports & history" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Inspect 3 weaknesses in run/ }));

    expect(await screen.findByRole("heading", { name: "Weaknesses found: 3" })).toBeInTheDocument();
    expect(screen.getByText("cartservice")).toBeInTheDocument();
    expect(screen.getByText("productcatalogservice")).toBeInTheDocument();
    expect(screen.getByText("currencyservice")).toBeInTheDocument();
    expect(screen.getByText("Add circuit breaker")).toBeInTheDocument();
  });

  it("shows all three recorded weaknesses on the overview when the selected run has them", async () => {
    mockDashboardApi({
      "/api/overview": {
        ...overview,
        run_id: runDetail.run_id,
        weaknesses: runDetail.weaknesses.length,
        weakness_details: runDetail.weaknesses.map((weakness, index) => ({
          ...weakness,
          error_rate: runDetail.experiments[index].error_rate,
          p95_ms: runDetail.experiments[index].p95_ms,
          recovered: runDetail.experiments[index].recovered,
          recommendations: runDetail.experiments[index].recommendations,
        })),
      },
    });
    render(<App />);

    expect(await screen.findByText("Recorded weaknesses")).toBeInTheDocument();
    expect(screen.getByText("cartservice")).toBeInTheDocument();
    expect(screen.getByText("productcatalogservice")).toBeInTheDocument();
    expect(screen.getByText("currencyservice")).toBeInTheDocument();
  });
});
