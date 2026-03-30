import { BarChart3Icon, CheckCircleIcon, ShieldCheckIcon, SparklesIcon } from "lucide-react";
import { useMemo } from "react";

import type { ResearchScore } from "@/core/tasks/types";
import { cn } from "@/lib/utils";


function ScoreBar({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="text-muted-foreground flex w-24 items-center gap-1.5 text-xs">
        {icon}
        <span>{label}</span>
      </div>
      <div className="bg-muted h-1.5 flex-1 overflow-hidden rounded-full">
        <div
          className={cn("h-full rounded-full transition-all duration-700 ease-out", color)}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
      <span className="text-muted-foreground w-8 text-right text-xs tabular-nums">
        {Math.round(value)}
      </span>
    </div>
  );
}

export function AgentScoreCard({
  className,
  score,
  agentLabel,
}: {
  className?: string;
  score: ResearchScore;
  agentLabel: string;
}) {
  const qualityLabel = useMemo(() => {
    if (score.weighted_total >= 60) return { text: "High Quality", color: "text-emerald-500" };
    if (score.weighted_total >= 35) return { text: "Medium Quality", color: "text-amber-500" };
    return { text: "Low Quality", color: "text-red-400" };
  }, [score.weighted_total]);

  return (
    <div
      className={cn(
        "border-border/50 bg-card/50 flex flex-col gap-3 rounded-lg border p-3 backdrop-blur-sm",
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="bg-primary/10 text-primary flex size-6 items-center justify-center rounded-full text-xs font-medium">
            {score.agent_index + 1}
          </div>
          <span className="text-sm font-medium">{agentLabel}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={cn("text-xs font-medium", qualityLabel.color)}>
            {qualityLabel.text}
          </span>
          <span className="bg-primary/10 text-primary rounded-md px-2 py-0.5 text-xs font-bold tabular-nums">
            {Math.round(score.weighted_total)}/100
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <ScoreBar
          label="Accuracy"
          value={score.accuracy}
          icon={<CheckCircleIcon className="size-3" />}
          color="bg-emerald-500"
        />
        <ScoreBar
          label="Complete"
          value={score.completeness}
          icon={<BarChart3Icon className="size-3" />}
          color="bg-blue-500"
        />
        <ScoreBar
          label="Sources"
          value={score.source_quality}
          icon={<ShieldCheckIcon className="size-3" />}
          color="bg-violet-500"
        />
        <ScoreBar
          label="Clarity"
          value={score.clarity}
          icon={<SparklesIcon className="size-3" />}
          color="bg-amber-500"
        />
      </div>

      {score.cross_validation_bonus > 0 && (
        <div className="text-muted-foreground flex items-center gap-1 text-xs">
          <ShieldCheckIcon className="size-3 text-emerald-500" />
          <span>+{score.cross_validation_bonus.toFixed(1)} cross-validation bonus</span>
        </div>
      )}
    </div>
  );
}
