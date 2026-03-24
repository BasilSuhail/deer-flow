/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import {
  CpuIcon,
  HardDriveIcon,
  WifiIcon,
  WifiOffIcon,
  BrainIcon,
  ZapIcon,
} from "lucide-react";
import { useEffect, useState, useMemo } from "react";

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
    // Match "qwen2.5:7b" to "qwen2.5:7b" or "deepseek-r1:7b" to "deepseek-r1:7b"
    return ollamaName === configModel || ollamaName.startsWith(configModel);
  }) ?? null;
}

// Role labels for configured models by position
const MODEL_ROLES: { label: string; icon: typeof BrainIcon; description: string }[] = [
  { label: "Lead Agent", icon: BrainIcon, description: "Planning & reasoning" },
  { label: "Subagent", icon: ZapIcon, description: "Execution & tools" },
];

export function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [error, setError] = useState(false);

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
    };
    fetchStats();
    const interval = setInterval(fetchStats, 3000);
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
  const ollamaModels: any[] = ollama?.models ?? [];

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

      {/* Ollama connection header */}
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

        {/* Model VRAM bar (combined) */}
        {totalVram > 0 && (
          <div className="mb-2">
            <ProgressBar percent={vramPercent} color="bg-violet-500" />
            <p className="text-muted-foreground mt-1">
              VRAM: {formatBytes(totalVram)} / {formatBytes(sysRam.total)}
            </p>
          </div>
        )}

        {/* Per-model cards with role + usage merged */}
        <div className="space-y-2">
          {configuredModels.map((cm: any, i: number) => {
            const role = MODEL_ROLES[i] ?? MODEL_ROLES[MODEL_ROLES.length - 1];
            const RoleIcon = role.icon;
            const live = findOllamaModel(cm, ollamaModels);
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
                {/* Row 1: role + status */}
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
                      <>
                        <span className="inline-block size-1.5 rounded-full bg-muted-foreground" />
                        <span className="text-muted-foreground">
                          {ollama?.reachable ? "standby" : "offline"}
                        </span>
                      </>
                    )}
                  </span>
                </div>

                {/* Row 2: model name */}
                <div className="font-mono text-muted-foreground truncate" title={cm.model}>
                  {cm.display_name ?? cm.model}
                </div>

                {/* Row 3: VRAM + role description */}
                <div className="flex items-center justify-between mt-1 text-muted-foreground">
                  <span>{role.description}</span>
                  {isLoaded && vram > 0 && (
                    <span className="text-foreground">{formatBytes(vram)}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Show any Ollama models loaded that aren't in config */}
        {ollamaModels
          .filter((om: any) => !configuredModels.some((cm: any) => findOllamaModel(cm, [om])))
          .map((om: any, i: number) => (
            <div key={`extra-${i}`} className="rounded-md p-2 bg-secondary/20 mt-2">
              <div className="flex items-center justify-between">
                <span className="font-mono text-muted-foreground truncate">{om.name}</span>
                <span className="text-muted-foreground">{formatBytes(om.size_vram)}</span>
              </div>
            </div>
          ))}
      </section>
    </div>
  );
}
