import {
  CheckCircleIcon,
  ChevronUp,
  ClipboardListIcon,
  Loader2Icon,
  XCircleIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Streamdown } from "streamdown";

import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtStep,
} from "@/components/ai-elements/chain-of-thought";
import { Shimmer } from "@/components/ai-elements/shimmer";
import { Button } from "@/components/ui/button";
import { ShineBorder } from "@/components/ui/shine-border";
import { useI18n } from "@/core/i18n/hooks";
import { hasToolCalls } from "@/core/messages/utils";
import { useRehypeSplitWordsIntoSpans } from "@/core/rehype";
import { streamdownPluginsWithWordAnimation } from "@/core/streamdown";
import { useSubtask } from "@/core/tasks/context";
import { explainLastToolCall } from "@/core/tools/utils";
import { cn } from "@/lib/utils";

import { CitationLink } from "../citations/citation-link";
import { FlipDisplay } from "../flip-display";

import { MarkdownContent } from "./markdown-content";

export function SubtaskCard({
  className,
  taskId,
  isLoading,
}: {
  className?: string;
  taskId: string;
  isLoading: boolean;
}) {
  const { t } = useI18n();
  const [collapsed, setCollapsed] = useState(true);
  const rehypePlugins = useRehypeSplitWordsIntoSpans(isLoading);
  const task = useSubtask(taskId)!;

  const duration = useMemo(() => {
    if (task.started_at && task.completed_at) {
      const start = new Date(task.started_at).getTime();
      const end = new Date(task.completed_at).getTime();
      const secs = Math.round((end - start) / 1000);
      return secs > 0 ? `${secs}s` : null;
    }
    return null;
  }, [task.started_at, task.completed_at]);

  const icon = useMemo(() => {
    if (task.status === "completed") {
      return <CheckCircleIcon className="size-3.5 text-green-500" />;
    } else if (task.status === "failed") {
      return <XCircleIcon className="size-3.5 text-red-500" />;
    } else if (task.status === "in_progress") {
      return <Loader2Icon className="size-3.5 animate-spin text-amber-500" />;
    }
  }, [task.status]);

  return (
    <ChainOfThought
      className={cn("relative w-full gap-2 rounded-xl border py-0 shadow-sm transition-all duration-300", 
        task.status === "in_progress" ? "border-amber-500/30 ring-1 ring-amber-500/10" : "",
        className)}
      open={!collapsed}
    >
      <div
        className={cn(
          "ambilight z-[-1]",
          task.status === "in_progress" ? "enabled" : "",
        )}
      ></div>
      {task.status === "in_progress" && (
        <>
          <ShineBorder
            borderWidth={2}
            duration={6}
            shineColor={["#A07CFE", "#FE8FB5", "#FFBE7B", "#4ade80", "#60a5fa"]}
          />
        </>
      )}
      <div className="bg-background/95 flex w-full flex-col rounded-xl overflow-hidden">
        <div className="flex w-full items-center justify-between p-1">
          <Button
            className="w-full items-start justify-start text-left h-auto py-2 hover:bg-accent/50"
            variant="ghost"
            onClick={() => setCollapsed(!collapsed)}
          >
            <div className="flex w-full items-center justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0">
                <div className="shrink-0 p-1.5 rounded-full bg-secondary/50">
                  <ClipboardListIcon className="size-4 text-muted-foreground" />
                </div>
                <div className="flex flex-col min-w-0">
                  <span className={cn(
                    "text-sm font-medium leading-tight break-words",
                    task.status === "in_progress" ? "text-foreground" : "text-muted-foreground"
                  )}>
                    {task.status === "in_progress" ? (
                      <Shimmer duration={2} spread={2}>
                        {task.description}
                      </Shimmer>
                    ) : (
                      task.description
                    )}
                  </span>
                  {duration && (
                    <span className="text-[10px] text-muted-foreground mt-1">
                      Completed in {duration}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {collapsed && (
                  <div
                    className={cn(
                      "text-muted-foreground flex items-center gap-1.5 text-xs font-normal bg-secondary/30 px-2 py-1 rounded-md border border-border/50",
                      task.status === "failed" ? "text-red-500 bg-red-500/5 border-red-500/10" : "",
                    )}
                  >
                    {icon}
                    <FlipDisplay
                      className="max-w-[200px] sm:max-w-[400px]"
                      uniqueKey={task.latestMessage?.id ?? task.status}
                    >
                      <span className="block break-words line-clamp-2 sm:line-clamp-none">
                        {task.status === "in_progress" &&
                        task.latestMessage &&
                        hasToolCalls(task.latestMessage)
                          ? explainLastToolCall(task.latestMessage, t)
                          : t.subtasks[task.status]}
                      </span>
                    </FlipDisplay>
                  </div>
                )}
                <ChevronUp
                  className={cn(
                    "text-muted-foreground size-4 transition-transform duration-200",
                    !collapsed ? "" : "rotate-180",
                  )}
                />
              </div>
            </div>
          </Button>
        </div>
        <ChainOfThoughtContent className="px-12 pb-6 border-t border-border/50 pt-4 bg-secondary/5">
          {task.prompt && (
            <div className="mb-6 p-3 rounded-lg bg-background border border-border/50 shadow-inner">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold mb-2">Objective</p>
              <Streamdown
                {...streamdownPluginsWithWordAnimation}
                components={{ a: CitationLink }}
                className="text-sm text-foreground/80 italic leading-relaxed"
              >
                {task.prompt}
              </Streamdown>
            </div>
          )}
          
          {task.status === "in_progress" &&
            task.latestMessage &&
            hasToolCalls(task.latestMessage) && (
              <ChainOfThoughtStep
                label={<span className="font-medium">{t.subtasks.in_progress}</span>}
                icon={<Loader2Icon className="size-4 animate-spin text-amber-500" />}
                status="active"
              >
                <div className="mt-1 text-sm text-muted-foreground">
                  {explainLastToolCall(task.latestMessage, t)}
                </div>
              </ChainOfThoughtStep>
            )}

          {task.status === "completed" && (
            <div className="space-y-6">
              <ChainOfThoughtStep
                label={<span className="font-semibold text-green-600 dark:text-green-400">Research Phase Complete</span>}
                icon={<CheckCircleIcon className="size-4 text-green-500" />}
                status="complete"
              />
              
              {task.result && (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <MarkdownContent
                    content={task.result}
                    isLoading={false}
                    rehypePlugins={rehypePlugins}
                    className="text-sm leading-relaxed"
                  />
                </div>
              )}
            </div>
          )}

          {task.status === "failed" && (
            <ChainOfThoughtStep
              label={<div className="text-red-500 font-medium">{task.error}</div>}
              icon={<XCircleIcon className="size-4 text-red-500" />}
              status="complete"
            ></ChainOfThoughtStep>
          )}
        </ChainOfThoughtContent>
      </div>
    </ChainOfThought>
  );
}
