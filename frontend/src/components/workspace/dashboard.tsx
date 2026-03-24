/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import {
  CpuIcon,
  LayersIcon,
  HardDriveIcon,
  WifiIcon,
  WifiOffIcon,
  ActivityIcon,
} from "lucide-react";
import { useEffect, useState } from "react";

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

function StatusDot({ status }: { status: string }) {
  const color =
    status === "busy"
      ? "bg-yellow-500 animate-pulse"
      : status === "error"
        ? "bg-red-500"
        : "bg-green-500";
  return <span className={`inline-block size-2 rounded-full ${color}`} />;
}

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
  const agents = stats.agents ?? {};
  const configuredModels = stats.configured_models ?? [];
  const ollamaModels = ollama?.models ?? [];

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

      {/* Ollama Status + Models */}
      <section>
        <div className="flex items-center gap-1.5 mb-1.5 font-medium text-foreground">
          <CpuIcon className="size-3.5" />
          <span>Ollama Models</span>
          {ollama?.reachable ? (
            <WifiIcon className="size-3 text-green-500 ml-auto" />
          ) : (
            <WifiOffIcon className="size-3 text-red-400 ml-auto" />
          )}
        </div>

        {ollamaModels.length > 0 ? (
          <div className="space-y-2">
            {ollamaModels.map((m: any, i: number) => (
              <div key={i} className="bg-secondary/40 rounded-md p-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-foreground truncate" title={m.name}>
                    {m.name}
                  </span>
                  <span className="text-green-500 ml-2 shrink-0">loaded</span>
                </div>
                <div className="text-muted-foreground">
                  VRAM: {formatBytes(m.size_vram)}
                </div>
              </div>
            ))}
            <p className="text-muted-foreground">
              Total VRAM: {formatBytes(ollama.total_vram_used)}
            </p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {configuredModels.length > 0 ? (
              configuredModels.map((m: any, i: number) => (
                <div key={i} className="bg-secondary/40 rounded-md p-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-foreground truncate" title={m.model}>
                      {m.display_name ?? m.model}
                    </span>
                    <span className="text-muted-foreground ml-2 shrink-0">
                      {ollama?.reachable ? "not loaded" : "unreachable"}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-muted-foreground">No models configured</p>
            )}
          </div>
        )}
      </section>

      {/* Agent Status */}
      <section>
        <div className="flex items-center gap-1.5 mb-1.5 font-medium text-foreground">
          <ActivityIcon className="size-3.5" />
          <span>Agents</span>
          {Object.values(agents).some((s) => s === "busy") && (
            <LayersIcon className="size-3 text-yellow-500 ml-auto animate-pulse" />
          )}
        </div>
        <div className="space-y-1">
          {Object.entries(agents).map(([name, status]) => (
            <div key={name} className="flex items-center justify-between">
              <span className="text-muted-foreground">{name}</span>
              <div className="flex items-center gap-1.5">
                <span className={status === "busy" ? "text-yellow-500" : "text-green-500"}>
                  {status as string}
                </span>
                <StatusDot status={status as string} />
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
