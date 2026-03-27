import { FlaskConicalIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useScores } from "@/core/tasks/context";
import { cn } from "@/lib/utils";

import { AgentScoreCard } from "./agent-score-card";

const AGENT_LABELS = ["General Research", "Technical Deep-Dive", "Community & Adoption"];

export function ResearchScores({ className }: { className?: string }) {
  const scores = useScores();
  const [expanded, setExpanded] = useState(false);

  if (!scores || scores.length === 0) return null;

  const bestScore = scores[0]; // Already sorted by backend (best first)

  return (
    <div className={cn("flex w-full flex-col gap-2", className)}>
      <Button
        variant="ghost"
        size="sm"
        className="text-muted-foreground hover:text-foreground flex items-center gap-2 self-start text-xs"
        onClick={() => setExpanded(!expanded)}
      >
        <FlaskConicalIcon className="size-3.5" />
        <span>
          Cross-Validation Scores — Best: {Math.round(bestScore?.weighted_total ?? 0)}/100
        </span>
      </Button>

      {expanded && (
        <div className="animate-in fade-in slide-in-from-top-2 grid gap-2 sm:grid-cols-3">
          {scores.map((score) => (
            <AgentScoreCard
              key={score.agent_index}
              score={score}
              agentLabel={AGENT_LABELS[score.agent_index] ?? `Agent ${score.agent_index + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
