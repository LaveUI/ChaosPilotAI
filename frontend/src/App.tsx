import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, Bot, Box, Check, ChevronDown,
  CircleHelp, Clock3, Cpu, Download, ExternalLink, FileText, FlaskConical, GitBranch,
  LayoutDashboard, LoaderCircle, Menu, Network, Play, RefreshCw, Search, ShieldCheck,
  ShieldAlert, Siren, Sparkles, X,
} from "lucide-react";
import {
  Background, Controls, Handle, MarkerType, Position, ReactFlow,
  type Edge, type Node, type NodeProps,
} from "@xyflow/react";
import {
  Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import {
  api, type ActiveRun, type DependencyEdge, type Environment, type Experiment,
  type FaultAction, type Overview, type Preview, type Recommendation, type RunDetail,
  type RunSummary, type WeaknessEvidence,
  type Service,
} from "./api";

const PUBLIC_DEMO = import.meta.env.VITE_PUBLIC_DEMO === "true";

type Page = "overview" | "services" | "lab" | "investigation" | "recommendations" | "history";

const NAV: { id: Page; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "services", label: "Service explorer", icon: Network },
  { id: "lab", label: "Experiment lab", icon: FlaskConical },
  { id: "investigation", label: "AI investigation", icon: Bot },
  { id: "recommendations", label: "Fix recommendations", icon: Sparkles },
  { id: "history", label: "Reports & history", icon: FileText },
];

const ACTIONS: { id: FaultAction; label: string; icon: typeof Box; text: string }[] = [
  { id: "pod-failure", label: "Pod failure", icon: Box, text: "Test whether the application remains available when one pod stops." },
  { id: "network-delay", label: "Network delay", icon: Activity, text: "Test how dependent services behave when network calls become slower." },
  { id: "cpu-stress", label: "CPU stress", icon: Cpu, text: "Test response time while a service pod experiences CPU pressure." },
];

function StatusDot({ status }: { status: string }) {
  return <span className={`status-dot status-${status.replaceAll(" ", "-")}`} aria-label={status} />;
}

function Metric({
  label, value, hint, icon: Icon, accent = "blue", trend,
}: {
  label: string; value: string; hint: string; icon: typeof Activity;
  accent?: string; trend?: "up" | "down";
}) {
  return (
    <article className={`metric-card accent-${accent}`}>
      <div className="metric-top"><span>{label}</span><span className="metric-icon"><Icon size={17} /></span></div>
      <strong>{value}</strong>
      <div className="metric-hint">{trend && (trend === "up" ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />)}{hint}</div>
    </article>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return <div className="empty-state"><div className="empty-icon"><CircleHelp size={21} /></div><strong>{title}</strong><p>{body}</p></div>;
}

function CardTitle({ icon: Icon, title, hint, action }: {
  icon: typeof Activity; title: string; hint?: string; action?: ReactNode;
}) {
  return <div className="card-title"><div className="card-title-main"><span className="title-icon"><Icon size={16} /></span><div><h2>{title}</h2>{hint && <p>{hint}</p>}</div></div>{action}</div>;
}

interface ServiceNodeData extends Record<string, unknown> {
  service: Service;
  onSelect: (service: Service) => void;
}

function ServiceNode({ data }: NodeProps<Node<ServiceNodeData>>) {
  const { service, onSelect } = data;
  return (
    <button type="button" className={`flow-service flow-${service.status}`} onClick={() => onSelect(service)}>
      <Handle type="target" position={Position.Left} />
      <div className="flow-service-top"><StatusDot status={service.status} /><span>{service.status}</span><span className="flow-service-count">{service.replicas}×</span></div>
      <strong>{service.name}</strong>
      <small>{service.transitive_dependents} dependent services</small>
      <Handle type="source" position={Position.Right} />
    </button>
  );
}

const nodeTypes = { service: ServiceNode };

function DependencyMap({ services, edges, onSelect, selected }: {
  services: Service[]; edges: DependencyEdge[]; onSelect: (service: Service) => void; selected?: string;
}) {
  const nodes = useMemo<Node<ServiceNodeData>[]>(() => services.map((service, index) => ({
    id: service.name,
    type: "service",
    position: { x: (index % 4) * 226, y: Math.floor(index / 4) * 132 },
    data: { service, onSelect },
    selected: service.name === selected,
  })), [services, onSelect, selected]);
  const graphEdges = useMemo<Edge[]>(() => edges.map((edge, index) => ({
    id: `${edge.from}-${edge.to}-${index}`,
    source: edge.from,
    target: edge.to,
    label: edge.via === "manual" ? "manual" : undefined,
    markerEnd: { type: MarkerType.ArrowClosed, color: "#42516b" },
    style: { stroke: "#42516b", strokeWidth: 1.4 },
    labelStyle: { fill: "#8794aa", fontSize: 10 },
  })), [edges]);
  if (!services.length) return <EmptyState title="Service map unavailable" body="Generate graph.json with the existing map command, or check the API connection." />;
  return (
    <div className="flow-wrap" aria-label="Interactive microservice dependency map">
      <ReactFlow nodes={nodes} edges={graphEdges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.18 }}
        minZoom={0.25} maxZoom={1.7} nodesDraggable={false} nodesConnectable={false}
        aria-label="Service dependency graph">
        <Background color="#26334b" gap={22} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

function EvidenceChart({ experiments }: { experiments: Experiment[] }) {
  const values = [...experiments].reverse().flatMap((experiment) =>
    ["before", "during", "recovery", "after"].map((phase) => {
      const metrics = experiment.phase_metrics?.[phase];
      if (!metrics || (!metrics.samples && metrics.p95_ms == null && metrics.error_rate == null)) return null;
      return {
        label: `${experiment.id} · ${phase}`,
        latency: metrics.p95_ms ?? null,
        error: metrics.error_rate == null ? null : Number((metrics.error_rate * 100).toFixed(1)),
      };
    }).filter((value): value is { label: string; latency: number | null; error: number | null } => value !== null),
  );
  if (!values.length) return <EmptyState title="No recorded timeline data" body="Experiment charts will appear here after a run saves phase metrics." />;
  return (
    <div className="chart-box">
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={values} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid stroke="#202c41" strokeDasharray="4 4" />
          <XAxis dataKey="label" tick={{ fill: "#8d9ab0", fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis yAxisId="left" tick={{ fill: "#8d9ab0", fontSize: 10 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fill: "#8d9ab0", fontSize: 10 }} />
          <Tooltip contentStyle={{ background: "#101a2b", border: "1px solid #28364e", borderRadius: 10 }} />
          <Legend />
          <Line yAxisId="left" type="monotone" dataKey="latency" name="p95 latency (ms)" stroke="#55c7f0" strokeWidth={2} connectNulls dot={{ r: 3 }} />
          <Line yAxisId="right" type="monotone" dataKey="error" name="Error rate (%)" stroke="#f0737d" strokeWidth={2} connectNulls dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function PhaseBars({ experiments }: { experiments: Experiment[] }) {
  const data = [...experiments].reverse().map((experiment) => ({
    name: experiment.id,
    before: experiment.phase_metrics?.before?.p95_ms ?? null,
    during: experiment.phase_metrics?.during?.p95_ms ?? null,
    recovery: experiment.phase_metrics?.recovery?.p95_ms ?? null,
    after: experiment.phase_metrics?.after?.p95_ms ?? null,
  }));
  if (!data.some((item) => item.before !== null || item.during !== null)) {
    return <EmptyState title="No saved experiment metrics" body="Saved phase measurements are shown here when available." />;
  }
  return <div className="chart-box"><ResponsiveContainer width="100%" height={210}>
    <AreaChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
      <defs><linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#49bfe8" stopOpacity={0.25} /><stop offset="100%" stopColor="#49bfe8" stopOpacity={0} /></linearGradient></defs>
      <CartesianGrid stroke="#202c41" strokeDasharray="4 4" />
      <XAxis dataKey="name" tick={{ fill: "#8d9ab0", fontSize: 10 }} />
      <YAxis tick={{ fill: "#8d9ab0", fontSize: 10 }} />
      <Tooltip contentStyle={{ background: "#101a2b", border: "1px solid #28364e", borderRadius: 10 }} />
      <Legend />
      <Area type="monotone" dataKey="before" name="Before" stroke="#55c7f0" fill="url(#latencyGradient)" connectNulls />
      <Area type="monotone" dataKey="during" name="During" stroke="#f0737d" fill="transparent" connectNulls />
      <Area type="monotone" dataKey="recovery" name="Recovery" stroke="#b392fb" fill="transparent" connectNulls />
      <Area type="monotone" dataKey="after" name="After" stroke="#33c791" fill="transparent" connectNulls />
    </AreaChart>
  </ResponsiveContainer></div>;
}

function App() {
  const [page, setPage] = useState<Page>("overview");
  const [demo, setDemo] = useState(true);
  const [beginner, setBeginner] = useState(() => localStorage.getItem("chaospilot-beginner") !== "false");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [edges, setEdges] = useState<DependencyEdge[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [runDetailLoading, setRunDetailLoading] = useState(false);
  const [runDetailError, setRunDetailError] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [finding, setFinding] = useState<{ run_id: string | null; findings: Array<Record<string, unknown>>; data_available: boolean } | null>(null);
  const [agentStatus, setAgentStatus] = useState<Record<string, unknown> | null>(null);
  const [activeRun, setActiveRun] = useState<ActiveRun | null>(null);
  const [selectedService, setSelectedService] = useState<Service | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [search, setSearch] = useState("");
  const [environment, setEnvironment] = useState<Environment>("simulated");
  const [serviceName, setServiceName] = useState("");
  const [action, setAction] = useState<FaultAction>("pod-failure");
  const [duration, setDuration] = useState(30);
  const [plannerMode, setPlannerMode] = useState<"auto" | "llm" | "rule-based">("auto");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [confirmReal, setConfirmReal] = useState(false);
  const [startLoading, setStartLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const lastTerminalRun = useRef("");

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setRefreshing(true);
    try {
      const [overviewData, serviceData, runData, recommendationData, findingData, agentData] = await Promise.all([
        api<Overview>(`/api/overview?demo=${demo}`),
        api<{ services: Service[]; edges: DependencyEdge[] }>(`/api/services?demo=${demo}`),
        api<{ runs: RunSummary[] }>("/api/runs"),
        api<{ recommendations: Recommendation[] }>("/api/recommendations"),
        api<typeof finding>("/api/findings"),
        api<Record<string, unknown>>("/api/agents/status"),
      ]);
      setOverview(overviewData);
      setServices(serviceData.services);
      setEdges(serviceData.edges);
      setRuns(runData.runs);
      setRecommendations(recommendationData.recommendations);
      setFinding(findingData);
      setAgentStatus(agentData);
      setError(null);
      setServiceName((current) => current || serviceData.services.find((service) => service.status !== "unknown" && service.name !== "frontend")?.name || serviceData.services.find((service) => service.name !== "frontend")?.name || "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Dashboard data could not be loaded.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [demo]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { void refresh(true); }, 12000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const state = await api<{ active: boolean; run: ActiveRun | null }>("/api/experiments/status");
        if (!cancelled) {
          setActiveRun(state.run);
          if (state.run && !state.active && lastTerminalRun.current !== `${state.run.run_id}:${state.run.status}`) {
            lastTerminalRun.current = `${state.run.run_id}:${state.run.status}`;
            await refresh(true);
          }
        }
      } catch {
        // The page-level refresh presents API failures; avoid turning a temporary poll failure into a false state.
      }
    };
    void poll();
    const timer = window.setInterval(() => { void poll(); }, 1500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [refresh]);

  useEffect(() => {
    localStorage.setItem("chaospilot-beginner", String(beginner));
  }, [beginner]);

  const doPreview = async () => {
    setActionMessage(null);
    setPreviewLoading(true);
    setPreview(null);
    setConfirmReal(false);
    try {
      const value = await api<Preview>("/api/experiments/preview", {
        method: "POST",
        body: JSON.stringify({ service: serviceName, action, duration_s: duration, environment }),
      });
      setPreview(value);
    } catch (cause) {
      setActionMessage(cause instanceof Error ? cause.message : "Preview failed.");
    } finally {
      setPreviewLoading(false);
    }
  };

  const startExperiment = async () => {
    if (!preview || (environment === "kubernetes" && (!confirmReal || !preview.real_run_allowed))) return;
    setStartLoading(true);
    setActionMessage(null);
    try {
      const started = await api<{ run_id: string; status: string; message: string }>("/api/experiments/start", {
        method: "POST",
        body: JSON.stringify({
          service: serviceName, action, duration_s: duration, environment,
          planner_mode: plannerMode, confirm_real_experiment: true,
        }),
      });
      setActiveRun({
        run_id: started.run_id, status: started.status, phase: started.status,
        service: serviceName, action, environment,
      });
      setActionMessage(`Run ${started.run_id} has been queued.`);
      setPreview(null);
      await refresh(true);
    } catch (cause) {
      setActionMessage(cause instanceof Error ? cause.message : "Could not start the experiment.");
    } finally {
      setStartLoading(false);
    }
  };

  const stopExperiment = async () => {
    try {
      const stopped = await api<{ status: string; message: string }>("/api/experiments/stop", { method: "POST" });
      setActionMessage(stopped.message);
      setActiveRun((current) => current ? { ...current, status: "stopping", phase: "stopping" } : null);
    } catch (cause) {
      setActionMessage(cause instanceof Error ? cause.message : "Stop request failed.");
    }
  };

  const inspectRun = async (runId: string) => {
    setSelectedRun(null);
    setRunDetailError(null);
    setRunDetailLoading(true);
    try {
      setSelectedRun(await api<RunDetail>(`/api/runs/${encodeURIComponent(runId)}`));
    } catch (cause) {
      setRunDetailError(cause instanceof Error ? cause.message : "Could not load saved run details.");
    } finally {
      setRunDetailLoading(false);
    }
  };

  const currentPage = NAV.find((item) => item.id === page) ?? NAV[0];
  const mainRunActive = activeRun && ["queued", "running", "stopping", "cleanup_pending"].includes(activeRun.status);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand"><div className="brand-mark"><Activity size={20} /></div><div><b>ChaosPilot</b><span>RESILIENCE CONTROL</span></div></div>
        <div className="workspace-pill"><span className="workspace-avatar">OB</span><span><b>Online Boutique</b><small>Local workspace</small></span><ChevronDown size={14} /></div>
        <div className="nav-section">COMMAND CENTER</div>
        <nav aria-label="Main navigation">
          {NAV.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${page === id ? "active" : ""}`} onClick={() => { setPage(id); setMobileNav(false); }}><Icon size={17} /><span>{label}</span>{id === "lab" && mainRunActive && <i className="nav-live" />}</button>)}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-safety"><div className="safety-heading"><ShieldCheck size={16} /> Safety envelope</div><div className="safety-row"><span>Error rate</span><b>{overview ? `${(overview.safety.max_error_rate * 100).toFixed(0)}% max` : "—"}</b></div><div className="safety-row"><span>p95 latency</span><b>{overview ? `${overview.safety.p95_limit_ms} ms` : "—"}</b></div><div className="safety-row"><span>Extra unhealthy pods</span><b>{overview?.safety.max_extra_unhealthy_pods ?? "—"}</b></div></div>
        <div className="sidebar-user"><span className="user-avatar">CP</span><span><b>ChaosPilot operator</b><small>Local dashboard</small></span><span className="online-mark" /></div>
      </aside>

      {mobileNav && <button aria-label="Close navigation" className="nav-scrim" onClick={() => setMobileNav(false)} />}
      <main className="main-area">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileNav(true)}><Menu size={19} /></button>
          <div className="breadcrumbs"><span>ChaosPilot</span><span className="crumb-divider">/</span><b>{currentPage.label}</b></div>
          <div className="topbar-actions">
            <button className={`mode-pill ${demo ? "mode-demo" : "mode-live"}`} disabled={PUBLIC_DEMO} onClick={() => { setDemo((value) => !value); setPreview(null); }} aria-label={`Switch environment mode, currently ${demo ? "Demo" : "Live"}`}>
              <span className="mode-indicator" />{demo ? "Demo mode" : "Live cluster"}<ChevronDown size={13} />
            </button>
            <button className="beginner-toggle" onClick={() => setBeginner((value) => !value)} aria-pressed={beginner}><span className={`toggle-track ${beginner ? "toggle-on" : ""}`}><i /></span><span>Beginner</span></button>
            <button className="icon-button" aria-label="Refresh dashboard" onClick={() => void refresh()}><RefreshCw size={16} className={refreshing ? "spin" : ""} /></button>
          </div>
        </header>

        <div className="page-content">
          {error && <div className="notice notice-error" role="alert"><AlertTriangle size={17} /><span><b>Could not load dashboard data</b>{error}</span><button className="notice-close" onClick={() => void refresh()}><RefreshCw size={15} /></button></div>}
          {demo && <div className="notice notice-demo"><Sparkles size={16} /><span><b>Saved-data demo</b> {PUBLIC_DEMO ? "Public read-only demo: experiment execution and live access are disabled." : "Metrics come from saved simulated runs."} Unknown values stay unknown; no synthetic health is shown.</span>{!PUBLIC_DEMO && <button onClick={() => setDemo(false)}>Connect live cluster<ArrowUpRight size={14} /></button>}</div>}
          {!demo && <div className="notice notice-live"><AlertTriangle size={16} /><span><b>Live cluster view</b> Read-only diagnostics are live. Starting an experiment requires an approved context and explicit confirmation.</span></div>}
          {loading ? <LoadingState /> : (
            <>
              {page === "overview" && <OverviewPage overview={overview} services={services} edges={edges} onSelect={(service) => { setSelectedService(service); setPage("services"); }} onLab={() => setPage("lab")} onHistory={() => setPage("history")} beginner={beginner} />}
              {page === "services" && <ServicesPage services={services} edges={edges} selected={selectedService} setSelected={setSelectedService} beginner={beginner} />}
              {page === "lab" && <ExperimentLab services={services} environment={environment} setEnvironment={(value) => { setEnvironment(value); setPreview(null); setConfirmReal(false); }} serviceName={serviceName} setServiceName={setServiceName} action={action} setAction={setAction} duration={duration} setDuration={setDuration} plannerMode={plannerMode} setPlannerMode={setPlannerMode} preview={preview} previewLoading={previewLoading} onPreview={doPreview} onStart={startExperiment} onStop={stopExperiment} activeRun={activeRun} startLoading={startLoading} confirmReal={confirmReal} setConfirmReal={setConfirmReal} message={actionMessage} setMessage={setActionMessage} />}
              {page === "investigation" && <InvestigationPage status={agentStatus} finding={finding} experiments={overview?.recent_experiments ?? []} activeRun={activeRun} beginner={beginner} />}
              {page === "recommendations" && <RecommendationsPage recommendations={recommendations} beginner={beginner} />}
              {page === "history" && <HistoryPage runs={runs} search={search} setSearch={setSearch} selectedRun={selectedRun} runDetailLoading={runDetailLoading} runDetailError={runDetailError} onInspect={inspectRun} onCloseInspection={() => { setSelectedRun(null); setRunDetailError(null); }} />}
            </>
          )}
        </div>
        <footer className="app-footer"><span>ChaosPilot AI <i /> Local-first resilience engineering</span><span>Data source: {overview?.source ?? "waiting for API"}</span></footer>
      </main>
    </div>
  );
}

function LoadingState() {
  return <div className="loading-state"><LoaderCircle size={22} className="spin" /><span>Loading saved and live project data…</span></div>;
}

function PageHeading({ eyebrow, title, description, action }: {
  eyebrow: string; title: string; description: string; action?: ReactNode;
}) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{description}</p></div>{action}</div>;
}

function OverviewPage({ overview, services, edges, onSelect, onLab, onHistory, beginner }: {
  overview: Overview | null; services: Service[]; edges: DependencyEdge[];
  onSelect: (service: Service) => void; onLab: () => void; onHistory: () => void; beginner: boolean;
}) {
  if (!overview) return <EmptyState title="Overview unavailable" body="Connect to the dashboard API and load saved data to see project health." />;
  const finding = overview.recent_experiments.find((experiment) => experiment.ai_diagnosis);
  const planned = overview.suggested_experiments.slice(0, 3);
  const weaknessDetails = overview.weakness_details ?? [];
  return <>
    <PageHeading eyebrow="RESILIENCE SNAPSHOT" title="Resilience command center" description="Understand your application, investigate weak points, and run safety-bounded experiments." action={<button className="primary-button" onClick={onLab}><FlaskConical size={16} /> New experiment</button>} />
    <div className="metric-grid">
      <Metric label="Resilience score" value={overview.resilience_score == null ? "—" : `${overview.resilience_score}`} hint={overview.run_id ? `From run ${overview.run_id}` : "No saved score"} icon={ShieldCheck} accent="purple" />
      <Metric label="Healthy services" value={overview.healthy_services == null ? `— / ${overview.services_total}` : `${overview.healthy_services} / ${overview.services_total}`} hint={overview.health_known ? "Based on recorded cluster data" : "Runtime health not recorded"} icon={Network} accent="green" />
      <Metric label="Weaknesses found" value={String(overview.weaknesses)} hint={overview.weaknesses ? "From saved experiment findings" : "No recorded weaknesses"} icon={AlertTriangle} accent={overview.weaknesses ? "amber" : "blue"} />
      <Metric label="Experiments completed" value={String(overview.experiments_completed)} hint={overview.environment === "simulated" ? "Saved simulation run" : "Latest Kubernetes run"} icon={FlaskConical} accent="blue" />
    </div>

    {weaknessDetails.length > 0 && <section className="panel overview-weakness-panel">
      <CardTitle icon={AlertTriangle} title="Recorded weaknesses" hint={`${weaknessDetails.length} from saved run ${overview.run_id ?? ""} · historical evidence, not current health`} />
      <div className="weakness-grid">{weaknessDetails.map((weakness, index) => <WeaknessCard key={`${weakness.service}-${weakness.action}-${index}`} weakness={weakness} index={index} />)}</div>
    </section>}

    {overview.active_experiment && <div className="active-banner"><span className="pulse" /><div><b>Experiment {overview.active_experiment.status}</b><small>{overview.active_experiment.action} on {overview.active_experiment.service} · {overview.active_experiment.phase}</small></div><span className="active-environment">{overview.active_experiment.environment}</span></div>}

    <div className="dashboard-grid">
      <section className="panel panel-map span-2">
        <CardTitle icon={GitBranch} title="Microservice dependency map" hint={`${services.length} services · ${edges.length} dependency links`} action={<button className="text-button" onClick={() => { if (services[0]) onSelect(services[0]); }}>Explore map <ArrowUpRight size={14} /></button>} />
        <DependencyMap services={services} edges={edges} onSelect={onSelect} />
        <div className="map-legend"><span><StatusDot status="healthy" />Healthy</span><span><StatusDot status="degraded" />Degraded</span><span><StatusDot status="failed" />Failed</span><span><StatusDot status="unknown" />Unknown</span><small>Click a node to inspect · drag to pan · scroll to zoom</small></div>
      </section>

      <section className="panel">
        <CardTitle icon={Activity} title="Application health over time" hint="Recorded experiment phases · p95 latency and error rate" />
        <EvidenceChart experiments={overview.recent_experiments} />
        {beginner && <p className="plain-note"><b>p95 latency</b> is the response time that 95 out of 100 requests were at or below.</p>}
      </section>

      <section className="panel">
        <CardTitle icon={ShieldAlert} title="Safety status" hint="Limits enforced by trusted Python code" />
        <div className="safety-status-row"><span><ShieldCheck size={16} /> Guard thresholds</span><b className="tag tag-green">Active</b></div>
        <div className="safety-status-row"><span>Error rate</span><b>{(overview.safety.max_error_rate * 100).toFixed(0)}%</b></div>
        <div className="safety-status-row"><span>Latency limit</span><b>{overview.safety.p95_limit_ms} ms</b></div>
        <div className="safety-status-row"><span>Extra unhealthy pods</span><b>{overview.safety.max_extra_unhealthy_pods}</b></div>
        <div className="safety-status-row"><span>Latest cleanup</span><b className={`tag ${overview.cleanup_confirmed === true ? "tag-green" : overview.cleanup_confirmed === false ? "tag-red" : "tag-neutral"}`}>{overview.cleanup_confirmed === true ? "Verified" : overview.cleanup_confirmed === false ? "Unverified" : "Not recorded"}</b></div>
        <p className="safety-footnote">Emergency stop requests cleanup; a fault is only considered removed after cleanup is verified.</p>
      </section>

      <section className="panel">
        <CardTitle icon={Clock3} title="Recent experiments" hint="Actual saved experiment results" action={<button className="text-button" onClick={onHistory}>View history <ArrowUpRight size={14} /></button>} />
        {overview.recent_experiments.length ? <div className="compact-list">{overview.recent_experiments.slice(0, 4).map((experiment) => <ExperimentRow key={experiment.id} experiment={experiment} />)}</div> : <EmptyState title="No experiments yet" body="Run a simulation or an approved Kubernetes test to populate this list." />}
      </section>

      <section className="panel">
        <CardTitle icon={Sparkles} title="Recorded recommendations" hint="Recommendations from saved evidence" />
        {planned.length ? <div className="compact-list">{planned.map((item, index) => <div className="suggestion-row" key={`${item.service}-${item.action}-${index}`}><span className="suggestion-icon"><Network size={15} /></span><div><b>{item.service}</b><small>{item.action} · {item.rationale ?? "Recorded candidate"}</small></div><span className="tag tag-blue">Recorded plan</span></div>)}</div> : <EmptyState title="No plan recorded" body="Candidates appear here only when an experiment plan has been saved." />}
      </section>

      <section className="panel panel-finding">
        <CardTitle icon={Bot} title="Latest AI finding" hint="Evidence from the latest saved experiment" />
        {finding?.ai_diagnosis ? <><p className="finding-copy">{finding.ai_diagnosis}</p><div className="finding-meta"><span className={`tag tag-${finding.severity ?? "neutral"}`}>{finding.severity ?? "Severity not recorded"}</span><span>{finding.service} · {finding.action}</span></div></> : <EmptyState title="No diagnosis recorded" body="This panel will show an agent diagnosis after an experiment has been analyzed." />}
      </section>
    </div>
  </>;
}

function ExperimentRow({ experiment }: { experiment: Experiment }) {
  const score = experiment.score;
  return <div className="experiment-row"><span className={`fault-icon fault-${experiment.action}`}><FaultIcon action={experiment.action} /></span><div className="experiment-row-main"><b>{experiment.service}</b><small>{experiment.action} · {experiment.duration_s}s</small></div><span className={`tag ${experiment.aborted ? "tag-red" : experiment.recovered ? "tag-green" : "tag-amber"}`}>{experiment.aborted ? "Safety abort" : experiment.recovered ? "Recovered" : "Review"}</span><strong className="score-cell">{score == null ? "—" : score}</strong></div>;
}

function FaultIcon({ action }: { action: FaultAction }) {
  const Icon = ACTIONS.find((option) => option.id === action)?.icon ?? Box;
  return <Icon size={15} />;
}

function ServicesPage({ services, edges, selected, setSelected, beginner }: {
  services: Service[]; edges: DependencyEdge[]; selected: Service | null;
  setSelected: (service: Service) => void; beginner: boolean;
}) {
  const active = selected ? services.find((service) => service.name === selected.name) ?? selected : services[0];
  const setSelection = (service: Service) => setSelected(service);
  const dependents = active ? services.filter((service) => active.depended_by.includes(service.name)) : [];
  const dependencies = active ? services.filter((service) => active.depends_on.includes(service.name)) : [];
  return <>
    <PageHeading eyebrow="SERVICE TOPOLOGY" title="Service explorer" description="Explore recorded service relationships and distinguish observed health from unknown runtime state." />
    <div className="service-layout">
      <section className="panel service-map-panel"><CardTitle icon={Network} title="Dependency topology" hint="Interactive graph · select a service to inspect" /><DependencyMap services={services} edges={edges} onSelect={setSelection} selected={active?.name} /></section>
      <aside className="panel service-detail">
        {active ? <>
          <div className="detail-header"><span className={`service-emblem emblem-${active.status}`}><Box size={19} /></span><div><h2>{active.name}</h2><span className={`status-label label-${active.status}`}><StatusDot status={active.status} />{active.status}</span></div></div>
          <p className="muted-copy">Observed health comes from the selected data source. A gray state means no runtime observation was saved.</p>
          <div className="detail-stats"><div><span>Replicas in manifest</span><b>{active.replicas}</b></div><div><span>Ready now</span><b>{active.ready_replicas == null ? "Unknown" : `${active.ready_replicas} / ${active.desired_replicas}`}</b></div><div><span>Transitive dependents</span><b>{active.transitive_dependents}</b></div></div>
          <ServiceRelations title="Depends on" rows={dependencies} empty="No dependencies recorded." />
          <ServiceRelations title="Services depending on this" rows={dependents} empty="No direct dependents recorded." />
          {active.latest_experiment && <div className="last-experiment"><span className="eyebrow">LATEST EXPERIMENT</span><ExperimentRow experiment={active.latest_experiment} /></div>}
          {beginner && <div className="plain-note"><b>Replicas</b> are copies of a service pod. More replicas can help availability, but data stores need a replication strategy before scaling.</div>}
        </> : <EmptyState title="Select a service" body="Click a node on the graph to inspect its dependencies and recorded status." />}
      </aside>
    </div>
  </>;
}

function ServiceRelations({ title, rows, empty }: { title: string; rows: Service[]; empty: string }) {
  return <div className="relation-list"><h3>{title}<span>{rows.length}</span></h3>{rows.length ? rows.map((service) => <div key={service.name}><StatusDot status={service.status} /><span>{service.name}</span><small>{service.status}</small></div>) : <p>{empty}</p>}</div>;
}

function ExperimentLab({
  services, environment, setEnvironment, serviceName, setServiceName, action, setAction,
  duration, setDuration, plannerMode, setPlannerMode, preview, previewLoading, onPreview,
  onStart, onStop, activeRun, startLoading, confirmReal, setConfirmReal, message, setMessage,
}: {
  services: Service[]; environment: Environment; setEnvironment: (value: Environment) => void;
  serviceName: string; setServiceName: (value: string) => void; action: FaultAction;
  setAction: (value: FaultAction) => void; duration: number; setDuration: (value: number) => void;
  plannerMode: "auto" | "llm" | "rule-based"; setPlannerMode: (value: "auto" | "llm" | "rule-based") => void;
  preview: Preview | null; previewLoading: boolean; onPreview: () => void; onStart: () => void;
  onStop: () => void; activeRun: ActiveRun | null; startLoading: boolean; confirmReal: boolean;
  setConfirmReal: (value: boolean) => void; message: string | null; setMessage: (value: string | null) => void;
}) {
  const eligibleServices = services.filter((service) => service.name !== "frontend" && service.name !== "loadgenerator");
  const busy = activeRun && ["queued", "running", "stopping", "cleanup_pending"].includes(activeRun.status);
  const selectedAction = ACTIONS.find((item) => item.id === action) ?? ACTIONS[0];
  return <>
    <PageHeading eyebrow="CONTROLLED EXPERIMENTS" title="Experiment lab" description="Preview the service impact and safety envelope before an agent-guided test begins." action={busy ? <button className="stop-button" onClick={onStop}><Siren size={16} /> Emergency stop</button> : undefined} />
    <div className="lab-grid">
      <section className="panel lab-form">
        <CardTitle icon={FlaskConical} title="Configure a test" hint="Every request is validated again by the backend." />
        <div className="form-grid">
          <label className="field full-field"><span>Test environment</span><select value={environment} onChange={(event) => setEnvironment(event.target.value as Environment)}><option value="simulated">Offline simulator · no Kubernetes</option>{!PUBLIC_DEMO && <option value="kubernetes">Live Kubernetes · real fault injection</option>}</select><small>Begin with the simulator. Live mode requires an approved context and explicit confirmation.</small></label>
          <label className="field"><span>Target service</span><select value={serviceName} onChange={(event) => setServiceName(event.target.value)}>{eligibleServices.map((service) => <option value={service.name} key={service.name}>{service.name} · {service.status}</option>)}</select></label>
          <label className="field"><span>Duration <small title="Maximum time for the selected fault before automatic cleanup is requested.">ⓘ</small></span><div className="duration-input"><input type="number" min={15} max={60} value={duration} onChange={(event) => setDuration(Number(event.target.value))} /><span>seconds</span></div><small>Allowed range: 15–{60} seconds.</small></label>
          <fieldset className="field full-field fault-picker"><legend>Fault type</legend>{ACTIONS.map((item) => <button type="button" key={item.id} className={`fault-option ${action === item.id ? "fault-selected" : ""}`} onClick={() => { setAction(item.id); setMessage(null); }}><span><item.icon size={16} /></span><b>{item.label}</b><small>{item.text}</small>{action === item.id && <Check size={16} className="fault-check" />}</button>)}</fieldset>
          <label className="field full-field"><span>Planner mode</span><select value={plannerMode} onChange={(event) => setPlannerMode(event.target.value as typeof plannerMode)}><option value="auto">Auto · Gemini when available, otherwise rules</option><option value="llm">Require Gemini</option><option value="rule-based">Rule-based only</option></select><small>The Planner is constrained to the selected service and fault; its output is validated.</small></label>
        </div>
        <button className="primary-button preview-button" onClick={onPreview} disabled={PUBLIC_DEMO || previewLoading || !!busy || !serviceName || duration < 15 || duration > 60}>{previewLoading ? <LoaderCircle size={16} className="spin" /> : <ShieldCheck size={16} />} Preview safety & impact</button>
        {busy && <div className="active-run-card"><div className="active-run-top"><span className="live-indicator" />Experiment in progress<span className="tag tag-purple">{activeRun.phase}</span></div><div className="active-run-main"><b>{activeRun.action}</b><span>on {activeRun.service}</span></div><div className="run-id">Run ID {activeRun.run_id}</div><small>Cleanup status: {activeRun.cleanup_confirmed === true ? "verified" : activeRun.cleanup_confirmed === false ? "not verified" : "pending"}</small></div>}
        {message && <div className="inline-message" role="status"><AlertTriangle size={15} />{message}<button onClick={() => setMessage(null)} aria-label="Dismiss"><X size={14} /></button></div>}
      </section>

      <section className="panel preview-panel">
        <CardTitle icon={ShieldCheck} title="Pre-flight review" hint="Review the blast radius before confirming." />
        {!preview ? <div className="preview-placeholder"><div className="preview-orb"><ShieldCheck size={25} /></div><h3>Know the impact before you run</h3><p>Choose a service and fault, then preview expected behavior, affected dependencies, duration, and rollback checks.</p><div className="preview-steps"><span><i>1</i>Configure</span><span><i>2</i>Review safety</span><span><i>3</i>Confirm & run</span></div></div> : <div className="preview-content">
          <div className={`environment-card ${environment === "kubernetes" ? "environment-warning" : ""}`}><span className="environment-icon">{environment === "simulated" ? <Sparkles size={18} /> : <AlertTriangle size={18} />}</span><div><b>{environment === "simulated" ? "Offline simulator" : "Live Kubernetes experiment"}</b><small>{preview.simulation_notice ?? preview.warning}</small></div></div>
          <div className="preview-target"><div><span>Target</span><b>{preview.service}</b></div><div><span>Fault</span><b>{selectedAction.label}</b></div><div><span>Duration</span><b>{preview.duration_s}s <small>max {preview.max_duration_s}s</small></b></div></div>
          <div className="preview-explanation"><selectedAction.icon size={17} /><div><b>What to expect</b><p>{preview.fault_explanation}</p></div></div>
          <div className="preview-risk"><div className="risk-heading"><Network size={16} /><b>Potential blast radius</b><span className="tag tag-amber">{preview.transitive_dependents} dependent services</span></div><p>{preview.blast_radius}</p>{preview.direct_dependents.length > 0 && <small>Direct callers: {preview.direct_dependents.join(", ")}</small>}</div>
          <div className="safety-checklist"><div><Check size={14} /> Error rate abort: {Math.round(preview.safety_thresholds.max_error_rate * 100)}%</div><div><Check size={14} /> p95 latency limit: {preview.safety_thresholds.p95_limit_ms} ms</div><div><Check size={14} /> Unhealthy pod cap: {preview.safety_thresholds.max_extra_unhealthy_pods}</div><div><Check size={14} /> Cleanup is verified after rollback</div></div>
          <div className="planner-note"><Bot size={15} /><span>{preview.planner_note}</span><span className={`tag ${preview.gemini_key_available ? "tag-purple" : "tag-neutral"}`}>{preview.gemini_key_available ? "Gemini key present" : "Rule fallback available"}</span></div>
          {environment === "kubernetes" && <div className={`context-check ${preview.real_run_allowed ? "context-ok" : "context-blocked"}`}>{preview.real_run_allowed ? <Check size={15} /> : <ShieldAlert size={15} />}<span><b>Current context:</b> {preview.context?.current ?? "Unavailable"}<small>Approved: {preview.context?.approved ?? "Not configured"} · namespace: configured in config.yaml</small>{!preview.real_run_allowed && <small>Set CHAOSAI_APPROVED_CONTEXT to the exact current context before a real run.</small>}</span></div>}
          {environment === "kubernetes" && <label className="confirm-check"><input type="checkbox" checked={confirmReal} onChange={(event) => setConfirmReal(event.target.checked)} /><span>I understand this test injects a real fault into <b>{preview.service}</b> in my Kubernetes cluster.</span></label>}
          <button className={environment === "kubernetes" ? "warning-button confirm-start" : "primary-button confirm-start"} onClick={onStart} disabled={PUBLIC_DEMO || startLoading || !!busy || (environment === "kubernetes" && (!confirmReal || !preview.real_run_allowed))}>{startLoading ? <LoaderCircle size={16} className="spin" /> : <Play size={16} />}{environment === "kubernetes" ? "Confirm & start live experiment" : "Confirm & start simulation"}</button>
        </div>}
      </section>
    </div>
  </>;
}

function InvestigationPage({ status, finding, experiments, activeRun, beginner }: {
  status: Record<string, unknown> | null;
  finding: { run_id: string | null; findings: Array<Record<string, unknown>>; data_available: boolean } | null;
  experiments: Experiment[]; activeRun: ActiveRun | null; beginner: boolean;
}) {
  const agentsList = (status?.agents as Array<{ name: string; status: string; calls: Array<Record<string, unknown>> }> | undefined) ?? [];
  const timeline = (status?.timeline as Array<Record<string, unknown>> | undefined) ?? [];
  const names = ["observer", "planner", "injector", "analyst", "reporter"];
  return <>
    <PageHeading eyebrow="RECORDED AGENT ACTIVITY" title="AI investigation" description="Review agent decisions, recorded evidence, and Gemini-versus-fallback provenance. Chain-of-thought is never displayed." />
    <section className="panel investigation-panel">
      <CardTitle icon={Bot} title="Five-agent investigation" hint={status?.run_id ? `Run ${status.run_id}` : "No run selected"} />
      <div className="agent-flow">{names.map((name, index) => {
        const record = agentsList.find((item) => item.name === name);
        const active = activeRun && activeRun.phase?.toLowerCase().includes(name);
        const source = record?.status ?? "not recorded";
        return <div className="agent-step-wrap" key={name}><article className={`agent-step ${active ? "agent-active" : ""}`}><div className="agent-step-head"><span className="agent-avatar"><Bot size={15} /></span><span className={`tag ${source.toLowerCase().includes("gemini") ? "tag-purple" : source === "not recorded" ? "tag-neutral" : "tag-blue"}`}>{source}</span></div><b>{name[0].toUpperCase() + name.slice(1)}</b><small>{active ? "Working now" : source === "not recorded" ? "No execution record" : "Decision recorded"}</small>{record?.calls?.length ? <span className="agent-call-count">{record.calls.length} recorded call(s)</span> : null}</article>{index < names.length - 1 && <span className="agent-flow-arrow">→</span>}</div>;
      })}</div>
      {beginner && <p className="plain-note"><b>What this shows:</b> recorded outcomes and whether a call used Gemini or a rule fallback. It does not expose hidden model reasoning.</p>}
    </section>
    <div className="dashboard-grid investigation-grid">
      <section className="panel span-2"><CardTitle icon={Clock3} title="Investigation timeline" hint="Recorded agent and experiment events" />
        {activeRun && <div className="timeline-live"><span className="pulse" /><b>Current run</b><span>{activeRun.phase}</span><small>{activeRun.status}</small></div>}
        {timeline.length ? <div className="timeline-list">{timeline.slice(-30).map((event, index) => <div className="timeline-event" key={`${String(event.timestamp ?? event.round ?? index)}-${index}`}><span className="timeline-bullet" /><div><b>{String(event.phase ?? event.outcome ?? "Recorded step")}</b><small>{String(event.summary ?? event.event ?? "")}</small></div><span className="timeline-time">{String(event.timestamp ?? (event.round ? `Round ${event.round}` : ""))}</span></div>)}</div> : <EmptyState title="No timeline events saved" body="Run a guided experiment to record agent activity here." />}
      </section>
      <section className="panel"><CardTitle icon={Activity} title="Recorded phase metrics" hint="p95 latency by experiment phase" /><PhaseBars experiments={experiments} /></section>
      <section className="panel"><CardTitle icon={Sparkles} title="Evidence-backed finding" hint="Latest stored finding" />
        {finding?.data_available ? <div className="finding-stack">{finding.findings.map((item, index) => <article className="finding-card" key={index}><span className="tag tag-purple">{String(item.type ?? "finding")}</span><p>{String(item.text ?? "No text recorded.")}</p>{typeof item.service === "string" && <small>{item.service} · {String(item.action)}</small>}{Array.isArray(item.evidence) && item.evidence.length > 0 && <div className="evidence-list">{item.evidence.map((evidence, evidenceIndex) => <span key={evidenceIndex}><Check size={13} />{String(evidence)}</span>)}</div>}</article>)}</div> : <EmptyState title="No finding saved" body="This panel will display only persisted findings, not an invented diagnosis." />}
      </section>
    </div>
  </>;
}

function RecommendationsPage({ recommendations, beginner }: { recommendations: Recommendation[]; beginner: boolean }) {
  return <>
    <PageHeading eyebrow="EVIDENCE-BASED REMEDIATION" title="Fix recommendations" description="Prioritized from saved experiment results. Guidance does not execute commands or change cluster state." />
    {recommendations.length ? <div className="recommendation-grid">{recommendations.map((item, index) => <article className="panel recommendation-card" key={`${item.run_id}-${item.service}-${item.title}-${index}`}><div className="recommendation-head"><span className={`priority-badge priority-${item.severity ?? "unknown"}`}>P{index + 1}</span><span className={`tag tag-${item.severity ?? "neutral"}`}>{item.severity ?? "Priority not recorded"}</span><span className="recommendation-source">{item.environment === "simulated" ? "Simulation evidence" : "Kubernetes evidence"}</span></div><h2>{item.title}</h2><div className="recommendation-service"><Box size={14} />{item.service}<span>· {item.action}</span></div><p>{item.detail}</p><div className="evidence-callout"><b>Evidence</b><span>{item.score == null ? "Score not recorded" : `Experiment score ${item.score}/100`}; recommendation is linked to run {item.run_id}.</span></div><div className="implementation-panel"><b>How to implement</b><ol><li>Review the service deployment and the evidence in its experiment report.</li><li>Apply this change through your normal reviewed deployment workflow.</li><li>Measure a fresh baseline, then rerun the same experiment to verify.</li></ol>{beginner && <small>ChaosPilot does not run generated shell commands or automatically apply this recommendation.</small>}</div><div className="recommendation-meta"><span>Confidence: not recorded</span><span>Effort: not recorded</span><span>Change risk: not recorded</span></div></article>)}</div> : <section className="panel"><EmptyState title="No recommendations in saved runs" body="Recommendations are shown only when generated from experiment evidence. Run an experiment before expecting remediation guidance." /></section>}
  </>;
}

function HistoryPage({
  runs, search, setSearch, selectedRun, runDetailLoading, runDetailError, onInspect, onCloseInspection,
}: {
  runs: RunSummary[];
  search: string;
  setSearch: (value: string) => void;
  selectedRun: RunDetail | null;
  runDetailLoading: boolean;
  runDetailError: string | null;
  onInspect: (runId: string) => void;
  onCloseInspection: () => void;
}) {
  const filtered = runs.filter((run) => `${run.run_id} ${run.env} ${run.planner} ${run.llm_execution?.overall_source ?? ""}`.toLowerCase().includes(search.toLowerCase()));
  return <>
    <PageHeading eyebrow="EXPERIMENT ARCHIVE" title="Reports & history" description="Search saved run results and open or download the existing HTML report generated by ChaosPilot." />
    {runDetailLoading && <div className="notice notice-demo"><LoaderCircle size={16} className="spin" />Loading saved run evidence…</div>}
    {runDetailError && <div className="notice notice-error" role="alert"><AlertTriangle size={16} /><span>{runDetailError}</span></div>}
    {selectedRun && <RunWeaknessInspection run={selectedRun} onClose={onCloseInspection} />}
    <section className="panel history-panel">
      <CardTitle icon={FileText} title="Saved runs" hint={`${filtered.length} of ${runs.length} run(s)`} action={<label className="search-field"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Filter runs…" /></label>} />
      {filtered.length ? <div className="history-table-wrap"><table className="history-table"><thead><tr><th>Run</th><th>Environment</th><th>Planner provenance</th><th>Experiments</th><th>Score</th><th>Weaknesses</th><th>Reports</th></tr></thead><tbody>{filtered.map((run) => <tr key={run.run_id}><td><b>{run.run_id}</b><small>{run.planner}</small></td><td><span className={`tag ${run.env === "simulated" ? "tag-blue" : "tag-green"}`}>{run.env === "simulated" ? "Simulation" : "Kubernetes"}</span></td><td><span className={`tag ${run.llm_execution?.overall_source?.includes("Gemini") ? "tag-purple" : "tag-neutral"}`}>{run.llm_execution?.overall_source ?? "Not recorded"}</span><small>{run.llm_model ?? "Model not recorded"}</small></td><td>{run.experiment_count}</td><td className="table-score">{run.resilience_score ?? "—"}</td><td><button className="text-button" onClick={() => onInspect(run.run_id)} aria-label={`Inspect ${run.weaknesses?.length ?? 0} weaknesses in run ${run.run_id}`}>{run.weaknesses?.length ?? 0} weakness(es) · Inspect</button></td><td><div className="report-actions"><a href={`/api/runs/${encodeURIComponent(run.run_id)}/report`} target="_blank" rel="noreferrer" aria-label={`Open report ${run.run_id}`}><ExternalLink size={15} /></a><a href={`/api/runs/${encodeURIComponent(run.run_id)}/report?download=true`} aria-label={`Download report ${run.run_id}`}><Download size={15} /></a></div></td></tr>)}</tbody></table></div> : <EmptyState title={runs.length ? "No matching runs" : "No saved runs"} body={runs.length ? "Change the filter to see other saved runs." : "Run records will appear here after an experiment is saved; Demo Mode does not create fake history."} />}
    </section>
  </>;
}

function RunWeaknessInspection({ run, onClose }: { run: RunDetail; onClose: () => void }) {
  return <section className="panel run-inspection" aria-label={`Weakness details for run ${run.run_id}`}>
    <div className="run-inspection-heading">
      <div><p className="eyebrow">SAVED RUN EVIDENCE · {run.env === "simulated" ? "SIMULATION" : "KUBERNETES"}</p><h2>Weaknesses found: {run.weaknesses.length}</h2><p>Historical measurements from run {run.run_id}. These are saved results, not current cluster health.</p></div>
      <button className="icon-button" aria-label="Close weakness details" onClick={onClose}><X size={16} /></button>
    </div>
    {run.ai_report?.overall && <p className="run-summary-copy">{run.ai_report.overall}</p>}
    {run.weaknesses.length ? <div className="weakness-grid">{run.weaknesses.map((weakness, index) => {
      const experiment = run.experiments.find((item) => item.service === weakness.service && item.action === weakness.action);
      const evidence: WeaknessEvidence = {
        ...weakness,
        severity: experiment?.severity,
        error_rate: experiment?.error_rate,
        p95_ms: experiment?.p95_ms,
        recovered: experiment?.recovered,
        recommendations: experiment?.recommendations?.map(({ title, detail }) => ({ title, detail })) ?? [],
      };
      return <WeaknessCard key={`${weakness.service}-${weakness.action}-${index}`} weakness={evidence} index={index} />;
    })}</div> : <EmptyState title="No weaknesses recorded" body="This run did not save any weakness entries." />}
  </section>;
}

function WeaknessCard({ weakness, index }: { weakness: WeaknessEvidence; index: number }) {
  return <article className="weakness-card">
    <div className="weakness-card-heading"><span className="priority-badge">W{index + 1}</span><div><h3>{weakness.service}</h3><small>{weakness.action}</small></div><span className="tag tag-amber">Score {weakness.score}</span></div>
    <div className="weakness-measurements">
      <div><span>Error rate</span><b>{weakness.error_rate == null ? "Not recorded" : `${(weakness.error_rate * 100).toFixed(1)}%`}</b></div>
      <div><span>p95 latency</span><b>{weakness.p95_ms == null ? "Not recorded" : `${weakness.p95_ms} ms`}</b></div>
      <div><span>Recovery</span><b>{weakness.recovered == null ? "Not recorded" : weakness.recovered ? "Recovered" : "Not recovered"}</b></div>
    </div>
    {weakness.recommendations.length ? <div className="weakness-recommendations"><b>Recorded recommendations</b><ul>{weakness.recommendations.map((recommendation, recommendationIndex) => <li key={`${recommendation.title}-${recommendationIndex}`}><strong>{recommendation.title}</strong><span>{recommendation.detail}</span></li>)}</ul></div> : <p className="muted-copy">No recommendations were saved for this weakness.</p>}
  </article>;
}

export default App;
