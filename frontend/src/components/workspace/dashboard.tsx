/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import {
  CpuIcon,
  HardDriveIcon,
  WifiIcon,
  WifiOffIcon,
  BrainIcon,
  ZapIcon,
  LoaderIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  FlaskConicalIcon,
} from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const gb = bytes / (1024 * 1024 * 1024);
  if (gb >= 1) return `${gb.toFixed(1)} GB`;
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(0)} MB`;
}

function ProgressBar({ percent, color = "bg-primary" }: { percent: number; color?: string }) {
  return (
    <div className="w-full bg-secondary rounded-full h-1.5">
      <div
        className={`${color} h-1.5 rounded-full transition-all duration-500`}
        style={{ width: `${Math.min(percent, 100)}%` }}
      />
    </div>
  );
}

/** Match a configured model to its live Ollama process data by model ID. */
function findOllamaModel(configured: any, ollamaModels: any[]): any | null {
  if (!configured?.model) return null;
  return ollamaModels.find((om) => {
    const ollamaName = (om.name ?? "").toLowerCase();
    const configModel = configured.model.toLowerCase();
    return ollamaName === configModel || ollamaName.startsWith(configModel);
  }) ?? null;
}

function SubagentStatusIcon({ status }: { status: string }) {
  switch (status) {
    case "running":
      return <LoaderIcon className="size-3 text-yellow-500 animate-spin" />;
    case "completed":
      return <CheckCircleIcon className="size-3 text-green-500" />;
    case "failed":
      return <XCircleIcon className="size-3 text-red-500" />;
    case "timed_out":
      return <ClockIcon className="size-3 text-orange-500" />;
    default:
      return <ClockIcon className="size-3 text-muted-foreground" />;
  }
}

function SubagentStatusLabel({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "text-muted-foreground",
    running: "text-yellow-500",
    completed: "text-green-500",
    failed: "text-red-500",
    timed_out: "text-orange-500",
  };
  return <span className={styles[status] ?? "text-muted-foreground"}>{status}</span>;
}

// Role labels for configured models by position
const MODEL_ROLES: { label: string; icon: typeof BrainIcon; description: string }[] = [
  { label: "Lead Agent", icon: BrainIcon, description: "Planning, tool calling & orchestration" },
  { label: "Subagent", icon: ZapIcon, description: "Research, execution & web search" },
];

const DISCOVER_MODELS = [
  { name: "llama3.1:8b", description: "Meta's most capable 8B model" },
  { name: "qwen2.5:7b", description: "Strong reasoning, excellent for subagents" },
  { name: "mistral:7b", description: "The classic high-performance 7B" },
  { name: "phi3:mini", description: "Fast, compact, ideal for small tasks" },
  { name: "nomic-embed-text", description: "Required for document processing" },
];

const SCORE_LABELS = ["General", "Technical", "Community"];

function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="w-full bg-secondary rounded-full h-1">
      <div
        className={`${color} h-1 rounded-full transition-all duration-500`}
        style={{ width: `${Math.min(value, 100)}%` }}
      />
    </div>
  );
}

export function Dashboard() {
  const pathname = usePathname();
  const [stats, setStats] = useState<any>(null);
  const [scores, setScores] = useState<any>(null);
  const [error, setError] = useState(false);
  const [activeTab, setActiveTab] = useState<"installed" | "discover">("installed");
  const prevPathRef = useRef(pathname);

  // Model Pulling State
  const [pullModelName, setPullModelName] = useState("");
  const [isPulling, setIsPulling] = useState(false);
  const [pullStatus, setPullStatus] = useState("");
  const [pullProgress, setPullProgress] = useState(0);

  const handlePullModel = async (name?: string) => {
    const target = name || pullModelName;
    let sanitizedName = target.trim().toLowerCase().replace(/\s+/g, '');
    if (!sanitizedName) return;

    if (!sanitizedName.includes(':')) {
      sanitizedName += ':latest';
    }

    if (isPulling) return;
    setIsPulling(true);
    setPullModelName(sanitizedName);
    setPullStatus(`Starting pull for ${sanitizedName}...`);
    setPullProgress(0);

    try {
      const res = await fetch("/api/ollama/pull", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: sanitizedName }),
      });

      if (!res.ok || !res.body) {
        throw new Error("Failed to start pull");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let done = false;

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n").filter(Boolean);
          for (const line of lines) {
            try {
              const data = JSON.parse(line);
              if (data.error) {
                setPullStatus(`Error: ${data.error}`);
                setIsPulling(false);
                return;
              }
              setPullStatus(data.status ?? "Pulling...");
              if (data.total && data.completed) {
                setPullProgress(Math.round((data.completed / data.total) * 100));
              }
            } catch {
              // ignore parse error on partial chunks
            }
          }
        }
      }
      setPullStatus("Pull complete!");
      setPullModelName("");
      setTimeout(() => {
        setPullStatus("");
        setPullProgress(0);
      }, 3000);
    } catch (err: any) {
      setPullStatus(`Error: ${err.message}`);
    } finally {
      setIsPulling(false);
    }
  };

  const handleDeleteModel = async (name: string) => {
    if (!confirm(`Delete ${name}? This cannot be undone.`)) return;
    try {
      const res = await fetch("/api/ollama/delete", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: name }),
      });
      if (!res.ok) throw new Error("Delete failed");
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };

  // Clear stale scores and subagent data when navigating to a different chat
  useEffect(() => {
    if (pathname !== prevPathRef.current) {
      prevPathRef.current = pathname;
      setScores(null);
      // Reset subagents in stats to show idle immediately
      setStats((prev: any) => prev ? { ...prev, subagents: [] } : prev);
    }
  }, [pathname]);

  useEffect(() => {
    const fetchStats = () => {
      fetch("/api/stats")
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then((data) => {
          setStats(data);
          setError(false);
        })
        .catch(() => setError(true));

      fetch("/api/threads/research-scores")
        .then((res) => res.ok ? res.json() : null)
        .then((data) => {
          if (data?.scores?.length) setScores(data);
          else setScores(null);
        })
        .catch(() => {
          /* ignore */
        });
    };
    fetchStats();
    const interval = setInterval(fetchStats, 2000);
    return () => clearInterval(interval);
  }, []);

  if (error) {
    return (
      <div className="p-3 text-xs text-muted-foreground flex items-center gap-2">
        <WifiOffIcon className="size-3.5 text-red-400" />
        <span>Dashboard offline</span>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="p-3 text-xs text-muted-foreground animate-pulse">
        Loading stats...
      </div>
    );
  }

  const sysRam = stats.system_ram;
  const ollama = stats.ollama;
  const configuredModels: any[] = stats.configured_models ?? [];
  const runningModels: any[] = ollama?.models ?? [];
  const availableModels: any[] = ollama?.available ?? [];
  const subagents: any[] = stats.subagents ?? [];

  // Active subagents count
  const activeSubagents = subagents.filter((s: any) => s.status === "running" || s.status === "pending");

  // Compute total VRAM as percentage of system RAM for the combined bar
  const totalVram = ollama?.total_vram_used ?? 0;
  const vramPercent = sysRam.total > 0 ? (totalVram / sysRam.total) * 100 : 0;

  return (
    <div className="p-3 space-y-4 text-xs">
      {/* System RAM */}
      <section>
        <div className="flex items-center gap-1.5 mb-1.5 font-medium text-foreground">
          <HardDriveIcon className="size-3.5" />
          <span>System RAM</span>
          <span className="ml-auto text-muted-foreground font-normal">
            {sysRam.percent}%
          </span>
        </div>
        <ProgressBar
          percent={sysRam.percent}
          color={sysRam.percent > 85 ? "bg-red-500" : sysRam.percent > 70 ? "bg-yellow-500" : "bg-primary"}
        />
        <p className="text-muted-foreground mt-1">
          {formatBytes(sysRam.used)} / {formatBytes(sysRam.total)}
        </p>
      </section>

      {/* Ollama section */}
      <section>
        <div className="flex items-center gap-1.5 mb-2 font-medium text-foreground">
          <CpuIcon className="size-3.5" />
          <span>Models</span>
          {ollama?.reachable ? (
            <WifiIcon className="size-3 text-green-500 ml-auto" />
          ) : (
            <WifiOffIcon className="size-3 text-red-400 ml-auto" />
          )}
        </div>

        {/* Tab Switcher */}
        <div className="flex gap-4 mb-3 border-b border-border/50">
          <button
            onClick={() => setActiveTab("installed")}
            className={`pb-1 transition-colors ${activeTab === "installed" ? "text-primary border-b border-primary" : "text-muted-foreground hover:text-foreground"}`}
          >
            Installed
          </button>
          <button
            onClick={() => setActiveTab("discover")}
            className={`pb-1 transition-colors ${activeTab === "discover" ? "text-primary border-b border-primary" : "text-muted-foreground hover:text-foreground"}`}
          >
            Discover
          </button>
        </div>

        {activeTab === "installed" && (
          <div className="space-y-4">
            {/* Model VRAM bar (combined) */}
            {totalVram > 0 && (
              <div className="mb-2">
                <ProgressBar percent={vramPercent} color="bg-violet-500" />
                <p className="text-muted-foreground mt-1">
                  VRAM: {formatBytes(totalVram)} / {formatBytes(sysRam.total)}
                </p>
              </div>
            )}

            {/* Configured Roles */}
            <div className="space-y-2">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-bold">Roles</span>
              {configuredModels.map((cm: any, i: number) => {
                const role = MODEL_ROLES[i] ?? MODEL_ROLES[MODEL_ROLES.length - 1]!;
                const RoleIcon = role.icon;
                const live = findOllamaModel(cm, runningModels);
                const isLoaded = live !== null;
                const vram = live?.size_vram ?? 0;

                return (
                  <div
                    key={cm.name}
                    className={`rounded-md p-2 border transition-colors ${
                      isLoaded
                        ? "bg-secondary/40 border-primary/20"
                        : "bg-secondary/20 border-transparent"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <RoleIcon className="size-3 text-muted-foreground" />
                      <span className="font-medium text-foreground">{role.label}</span>
                      <span className="ml-auto flex items-center gap-1">
                        {isLoaded ? (
                          <>
                            <span className="inline-block size-1.5 rounded-full bg-green-500" />
                            <span className="text-green-500">active</span>
                          </>
                        ) : (
                          <span className="text-muted-foreground">standby</span>
                        )}
                      </span>
                    </div>
                    <div className="font-mono text-muted-foreground truncate" title={cm.model}>
                      {cm.display_name ?? cm.model}
                    </div>
                    <div className="flex items-center justify-between mt-1 text-muted-foreground">
                      <span>{role.description}</span>
                      {isLoaded && vram > 0 && <span className="text-foreground">{formatBytes(vram)}</span>}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Other Installed Models */}
            {availableModels.length > 0 && (
              <div className="space-y-2">
                <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-bold">Library</span>
                <div className="max-h-[200px] overflow-y-auto pr-1 space-y-1.5 custom-scrollbar">
                  {availableModels
                    .filter(am => !configuredModels.some(cm => cm.model.toLowerCase() === am.name.toLowerCase()))
                    .map((am: any) => (
                      <div key={am.name} className="group flex items-center justify-between p-1.5 rounded hover:bg-secondary/30 transition-colors border border-transparent hover:border-border/50">
                        <div className="min-w-0 flex-1 mr-2">
                          <div className="font-mono truncate" title={am.name}>{am.name}</div>
                          <div className="text-[10px] text-muted-foreground">{formatBytes(am.size)}</div>
                        </div>
                        <button
                          onClick={() => handleDeleteModel(am.name)}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/10 text-red-500/70 hover:text-red-500 transition-all"
                          title="Delete model"
                        >
                          <XCircleIcon className="size-3" />
                        </button>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "discover" && (
          <div className="space-y-3">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-bold">Catalog</span>
            <div className="grid grid-cols-1 gap-2">
              {DISCOVER_MODELS.map(m => {
                const isInstalled = availableModels.some(am => am.name.toLowerCase().startsWith(m.name.toLowerCase()));
                return (
                  <div key={m.name} className="p-2 rounded-md border bg-secondary/10 flex items-center justify-between">
                    <div>
                      <div className="font-bold">{m.name}</div>
                      <div className="text-[10px] text-muted-foreground">{m.description}</div>
                    </div>
                    <button
                      onClick={() => handlePullModel(m.name)}
                      disabled={isPulling || isInstalled}
                      className={`px-2 py-1 rounded text-[10px] font-bold ${isInstalled ? "bg-green-500/10 text-green-500" : "bg-primary text-primary-foreground hover:opacity-90"}`}
                    >
                      {isInstalled ? "Installed" : "Pull"}
                    </button>
                  </div>
                );
              })}
            </div>
            
            <div className="pt-2 border-t border-border/50">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-bold block mb-2">Custom Name</span>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={pullModelName}
                  onChange={(e) => setPullModelName(e.target.value)}
                  placeholder="e.g. gemma2:2b"
                  className="flex-1 rounded border bg-background px-2 py-1 text-[11px] outline-none"
                  disabled={isPulling}
                />
                <button
                  onClick={() => handlePullModel()}
                  disabled={isPulling || !pullModelName.trim()}
                  className="rounded bg-primary text-primary-foreground px-2 py-1 text-[11px] font-medium disabled:opacity-50"
                >
                  Pull
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Pulling Progress (global for section) */}
        {pullStatus && (
          <div className="mt-3 p-2 rounded-md bg-blue-500/5 border border-blue-500/20 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-blue-500 font-medium truncate flex-1 pr-2">{pullStatus}</span>
              {pullProgress > 0 && <span className="font-mono text-[10px] text-blue-500">{pullProgress}%</span>}
            </div>
            {pullProgress > 0 && <ProgressBar percent={pullProgress} color="bg-blue-500" />}
          </div>
        )}
      </section>

      {/* Subagent Activity */}
      <section>
        <div className="flex items-center gap-1.5 mb-2 font-medium text-foreground">
          <ZapIcon className="size-3.5" />
          <span>Subagents</span>
          {activeSubagents.length > 0 && (
            <span className="ml-auto flex items-center gap-1 text-yellow-500">
              <LoaderIcon className="size-3 animate-spin" />
              <span>{activeSubagents.length}/3</span>
            </span>
          )}
          {activeSubagents.length === 0 && (
            <span className="ml-auto text-muted-foreground font-normal">idle</span>
          )}
        </div>

        {/* Subagent slots - always show 3 slots */}
        <div className="space-y-1.5">
          {[0, 1, 2].map((slot) => {
            const task = subagents[slot];
            if (!task) {
              return (
                <div
                  key={`slot-${slot}`}
                  className="rounded-md p-1.5 bg-secondary/20 border border-transparent flex items-center gap-1.5"
                >
                  <span className="inline-block size-1.5 rounded-full bg-muted-foreground/30" />
                  <span className="text-muted-foreground/50">Slot {slot + 1} — available</span>
                </div>
              );
            }
            const isActive = task.status === "running" || task.status === "pending";
            return (
              <div
                key={task.task_id}
                className={`rounded-md p-1.5 border flex items-center gap-1.5 ${
                  isActive
                    ? "bg-yellow-500/5 border-yellow-500/20"
                    : task.status === "completed"
                      ? "bg-green-500/5 border-green-500/20"
                      : "bg-red-500/5 border-red-500/20"
                }`}
              >
                <SubagentStatusIcon status={task.status} />
                <span className="text-foreground truncate flex-1" title={task.description}>
                  {task.description}
                </span>
                <SubagentStatusLabel status={task.status} />
              </div>
            );
          })}
        </div>
      </section>

      {/* Cross-Validation Scores */}
      {scores?.scores?.length > 0 && (
        <section>
          <div className="flex items-center gap-1.5 mb-2 font-medium text-foreground">
            <FlaskConicalIcon className="size-3.5" />
            <span>Scores</span>
            <span className="ml-auto text-muted-foreground font-normal">
              Best: {Math.round(scores.scores[0]?.weighted_total ?? 0)}/100
            </span>
          </div>
          <div className="space-y-2">
            {scores.scores.map((s: any, i: number) => (
              <div key={i} className="rounded-md p-2 bg-secondary/20 border border-transparent">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-foreground">
                    {SCORE_LABELS[s.agent_index] ?? `Agent ${s.agent_index + 1}`}
                  </span>
                  <span className={`font-mono font-medium ${
                    s.weighted_total >= 50 ? "text-green-500" :
                    s.weighted_total >= 30 ? "text-yellow-500" : "text-red-400"
                  }`}>
                    {Math.round(s.weighted_total)}
                  </span>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground w-14">Accuracy</span>
                    <ScoreBar value={s.accuracy} color="bg-emerald-500" />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground w-14">Sources</span>
                    <ScoreBar value={s.source_quality} color="bg-violet-500" />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground w-14">Clarity</span>
                    <ScoreBar value={s.clarity} color="bg-amber-500" />
                  </div>
                </div>
                {s.cross_validation_bonus > 0 && (
                  <div className="text-muted-foreground mt-1 flex items-center gap-1">
                    <CheckCircleIcon className="size-2.5 text-emerald-500" />
                    +{s.cross_validation_bonus.toFixed(1)} cross-validated
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
