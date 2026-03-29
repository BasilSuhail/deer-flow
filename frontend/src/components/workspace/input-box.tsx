/* eslint-disable @typescript-eslint/no-unused-vars */
"use client";

import type { ChatStatus } from "ai";
import {
  CheckIcon,
  GraduationCapIcon,
  LightbulbIcon,
  PaperclipIcon,
  PlusIcon,
  SparklesIcon,
  RocketIcon,
  XIcon,
  ZapIcon,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
} from "react";

import {
  PromptInput,
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuItem,
  PromptInputActionMenuTrigger,
  PromptInputAttachment,
  PromptInputAttachments,
  PromptInputBody,
  PromptInputButton,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  usePromptInputAttachments,
  usePromptInputController,
  type PromptInputMessage,
} from "@/components/ai-elements/prompt-input";
import { Button } from "@/components/ui/button";
import { ConfettiButton } from "@/components/ui/confetti-button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { getBackendBaseURL } from "@/core/config";
import { useI18n } from "@/core/i18n/hooks";
import { useModels } from "@/core/models/hooks";
import type { AgentThreadContext } from "@/core/threads";
import { textOfMessage } from "@/core/threads/utils";
import { cn } from "@/lib/utils";

import {
  ModelSelector,
  ModelSelectorContent,
  ModelSelectorInput,
  ModelSelectorItem,
  ModelSelectorList,
  ModelSelectorName,
  ModelSelectorTrigger,
} from "../ai-elements/model-selector";
import { Suggestion, Suggestions } from "../ai-elements/suggestion";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";

import { useThread } from "./messages/context";
import { ModeHoverGuide } from "./mode-hover-guide";
import { Tooltip } from "./tooltip";

type InputMode = "flash" | "thinking" | "pro" | "ultra";

function getResolvedMode(
  mode: InputMode | undefined,
  supportsThinking: boolean,
): InputMode {
  // Allow all modes for all models. Non-thinking models simply skip the
  // thinking step but still benefit from plan mode (pro) and subagents (ultra).
  if (mode) {
    return mode;
  }
  // Default: "pro" gives plan mode; use "flash" only as an explicit opt-in
  return "pro";
}

export function InputBox({
  className,
  disabled,
  autoFocus,
  status = "ready",
  context,
  extraHeader,
  isNewThread,
  threadId,
  initialValue,
  onContextChange,
  onSubmit,
  onStop,
  ...props
}: Omit<ComponentProps<typeof PromptInput>, "onSubmit"> & {
  assistantId?: string | null;
  status?: ChatStatus;
  disabled?: boolean;
  context: Omit<
    AgentThreadContext,
    "thread_id" | "is_plan_mode" | "thinking_enabled" | "subagent_enabled"
  > & {
    mode: "flash" | "thinking" | "pro" | "ultra" | undefined;
    reasoning_effort?: "minimal" | "low" | "medium" | "high";
  };
  extraHeader?: React.ReactNode;
  isNewThread?: boolean;
  threadId: string;
  initialValue?: string;
  onContextChange?: (
    context: Omit<
      AgentThreadContext,
      "thread_id" | "is_plan_mode" | "thinking_enabled" | "subagent_enabled"
    > & {
      mode: "flash" | "thinking" | "pro" | "ultra" | undefined;
      reasoning_effort?: "minimal" | "low" | "medium" | "high";
    },
  ) => void;
  onSubmit?: (message: PromptInputMessage) => void;
  onStop?: () => void;
}) {
  const { t } = useI18n();
  const searchParams = useSearchParams();
  const [modelDialogOpen, setModelDialogOpen] = useState(false);
  const { models } = useModels();
  const { thread, isMock } = useThread();
  const { textInput } = usePromptInputController();
  const promptRootRef = useRef<HTMLDivElement | null>(null);

  // Defer Radix Dialog rendering until after hydration to avoid ID mismatches
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const [followups, setFollowups] = useState<string[]>([]);
  const [followupsHidden, setFollowupsHidden] = useState(false);
  const [followupsLoading, setFollowupsLoading] = useState(false);
  const lastGeneratedForAiIdRef = useRef<string | null>(null);
  const wasStreamingRef = useRef(false);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingSuggestion, setPendingSuggestion] = useState<string | null>(
    null,
  );

  useEffect(() => {
    if (models.length === 0) {
      return;
    }
    const currentModel = models.find((m) => m.name === context.model_name);
    const fallbackModel = currentModel ?? models[0]!;
    const supportsThinking = fallbackModel.supports_thinking ?? false;
    const nextModelName = fallbackModel.name;
    const nextMode = getResolvedMode(context.mode, supportsThinking);

    if (context.model_name === nextModelName && context.mode === nextMode) {
      return;
    }

    onContextChange?.({
      ...context,
      model_name: nextModelName,
      mode: nextMode,
    });
  }, [context, models, onContextChange]);

  const selectedModel = useMemo(() => {
    if (models.length === 0) {
      return undefined;
    }
    return models.find((m) => m.name === context.model_name) ?? models[0];
  }, [context.model_name, models]);

  const supportThinking = useMemo(
    () => selectedModel?.supports_thinking ?? false,
    [selectedModel],
  );

  const supportReasoningEffort = useMemo(
    () => selectedModel?.supports_reasoning_effort ?? false,
    [selectedModel],
  );

  const handleModelSelect = useCallback(
    (model_name: string) => {
      const model = models.find((m) => m.name === model_name);
      if (!model) {
        return;
      }
      onContextChange?.({
        ...context,
        model_name,
        mode: getResolvedMode(context.mode, model.supports_thinking ?? false),
        reasoning_effort: context.reasoning_effort,
      });
      setModelDialogOpen(false);
    },
    [onContextChange, context, models],
  );

  const handleModeSelect = useCallback(
    (mode: InputMode) => {
      onContextChange?.({
        ...context,
        mode: getResolvedMode(mode, supportThinking),
        reasoning_effort: mode === "ultra" ? "high" : mode === "pro" ? "medium" : mode === "thinking" ? "low" : "minimal",
      });
    },
    [onContextChange, context, supportThinking],
  );

  const handleReasoningEffortSelect = useCallback(
    (effort: "minimal" | "low" | "medium" | "high") => {
      onContextChange?.({
        ...context,
        reasoning_effort: effort,
      });
    },
    [onContextChange, context],
  );

  const handleSubmit = useCallback(
    async (message: PromptInputMessage) => {
      if (status === "streaming") {
        onStop?.();
        return;
      }
      if (!message.text) {
        return;
      }
      setFollowups([]);
      setFollowupsHidden(false);
      setFollowupsLoading(false);
      onSubmit?.(message);
    },
    [onSubmit, onStop, status],
  );

  const requestFormSubmit = useCallback(() => {
    const form = promptRootRef.current?.querySelector("form");
    form?.requestSubmit();
  }, []);

  const handleFollowupClick = useCallback(
    (suggestion: string) => {
      if (status === "streaming") {
        return;
      }
      const current = (textInput.value ?? "").trim();
      if (current) {
        setPendingSuggestion(suggestion);
        setConfirmOpen(true);
        return;
      }
      textInput.setInput(suggestion);
      setFollowupsHidden(true);
      setTimeout(() => requestFormSubmit(), 0);
    },
    [requestFormSubmit, status, textInput],
  );

  const confirmReplaceAndSend = useCallback(() => {
    if (!pendingSuggestion) {
      setConfirmOpen(false);
      return;
    }
    textInput.setInput(pendingSuggestion);
    setFollowupsHidden(true);
    setConfirmOpen(false);
    setPendingSuggestion(null);
    setTimeout(() => requestFormSubmit(), 0);
  }, [pendingSuggestion, requestFormSubmit, textInput]);

  const confirmAppendAndSend = useCallback(() => {
    if (!pendingSuggestion) {
      setConfirmOpen(false);
      return;
    }
    const current = (textInput.value ?? "").trim();
    const next = current ? `${current}\n${pendingSuggestion}` : pendingSuggestion;
    textInput.setInput(next);
    setFollowupsHidden(true);
    setConfirmOpen(false);
    setPendingSuggestion(null);
    setTimeout(() => requestFormSubmit(), 0);
  }, [pendingSuggestion, requestFormSubmit, textInput]);

  useEffect(() => {
    const streaming = status === "streaming";
    const wasStreaming = wasStreamingRef.current;
    wasStreamingRef.current = streaming;
    if (!wasStreaming || streaming) {
      return;
    }

    if (disabled || isMock) {
      return;
    }

    const lastAi = [...thread.messages].reverse().find((m) => m.type === "ai");
    const lastAiId = lastAi?.id ?? null;
    if (!lastAiId || lastAiId === lastGeneratedForAiIdRef.current) {
      return;
    }
    lastGeneratedForAiIdRef.current = lastAiId;

    const recent = thread.messages
      .filter((m) => m.type === "human" || m.type === "ai")
      .map((m) => {
        const role = m.type === "human" ? "user" : "assistant";
        const content = textOfMessage(m) ?? "";
        return { role, content };
      })
      .filter((m) => m.content.trim().length > 0)
      .slice(-6);

    if (recent.length === 0) {
      return;
    }

    const controller = new AbortController();
    setFollowupsHidden(false);
    setFollowupsLoading(true);
    setFollowups([]);

    fetch(`${getBackendBaseURL()}/api/threads/${threadId}/suggestions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: recent,
        n: 3,
        model_name: context.model_name ?? undefined,
      }),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) {
          return { suggestions: [] as string[] };
        }
        return (await res.json()) as { suggestions?: string[] };
      })
      .then((data) => {
        const suggestions = (data.suggestions ?? [])
          .map((s) => (typeof s === "string" ? s.trim() : ""))
          .filter((s) => s.length > 0)
          .slice(0, 5);
        setFollowups(suggestions);
      })
      .catch(() => {
        setFollowups([]);
      })
      .finally(() => {
        setFollowupsLoading(false);
      });

    return () => controller.abort();
  }, [context.model_name, disabled, isMock, status, thread.messages, threadId]);

  return (
    <div ref={promptRootRef} className="relative">
      <PromptInput
        className={cn(
          "bg-background/85 rounded-2xl backdrop-blur-sm transition-all duration-300 ease-out *:data-[slot='input-group']:rounded-2xl",
          className,
        )}
        disabled={disabled}
        globalDrop
        multiple
        onSubmit={handleSubmit}
        {...props}
      >
        {extraHeader && (
          <div className="absolute top-0 right-0 left-0 z-10">
            <div className="absolute right-0 bottom-0 left-0 flex items-center justify-center">
              {extraHeader}
            </div>
          </div>
        )}
        <PromptInputAttachments>
          {(attachment) => <PromptInputAttachment data={attachment} />}
        </PromptInputAttachments>
        <PromptInputBody className="absolute top-0 right-0 left-0 z-3">
          <PromptInputTextarea
            className={cn("size-full")}
            disabled={disabled}
            placeholder={t.inputBox.placeholder}
            autoFocus={autoFocus}
            defaultValue={initialValue}
          />
        </PromptInputBody>
        <PromptInputFooter className="flex">
          <PromptInputTools>
          {/* TODO: Add more connectors here
          <PromptInputActionMenu>
            <PromptInputActionMenuTrigger className="px-2!" />
            <PromptInputActionMenuContent>
              <PromptInputActionAddAttachments
                label={t.inputBox.addAttachments}
              />
            </PromptInputActionMenuContent>
          </PromptInputActionMenu> */}
          <AddAttachmentsButton className="px-2!" />
        </PromptInputTools>
        <PromptInputTools>
          {/* Mode selector buttons */}
          {(["flash", "pro", "ultra"] as const).map((mode) => {
            const isActive = (context.mode ?? "pro") === mode;
            const labels: Record<string, { icon: typeof ZapIcon; label: string }> = {
              flash: { icon: ZapIcon, label: "Just Answer" },
              pro: { icon: GraduationCapIcon, label: "Think & Plan" },
              ultra: { icon: RocketIcon, label: "All Agents" },
            };
            const { icon: ModeIcon, label } = labels[mode]!;
            return (
              <Button
                key={mode}
                type="button"
                variant={isActive ? "secondary" : "ghost"}
                size="sm"
                className={cn(
                  "h-7 gap-1 rounded-full px-2.5 text-xs font-normal",
                  isActive && "font-medium",
                )}
                onClick={() => handleModeSelect(mode)}
              >
                <ModeIcon className="size-3" />
                {label}
              </Button>
            );
          })}
        </PromptInputTools>
        <PromptInputTools>
          {mounted && (
            <ModelSelector
              open={modelDialogOpen}
              onOpenChange={setModelDialogOpen}
            >
              <ModelSelectorTrigger asChild>
                <PromptInputButton>
                  <div className="flex min-w-0 flex-col items-start text-left">
                    <ModelSelectorName className="text-xs font-normal">
                      {selectedModel?.display_name}
                    </ModelSelectorName>
                    {selectedModel?.model && (
                      <span className="text-muted-foreground w-full truncate text-[10px] leading-none">
                        {selectedModel.model}
                      </span>
                    )}
                  </div>
                </PromptInputButton>
              </ModelSelectorTrigger>
              <ModelSelectorContent>
                <ModelSelectorInput placeholder={t.inputBox.searchModels} />
                <ModelSelectorList>
                  {models.map((m) => (
                    <ModelSelectorItem
                      key={m.name}
                      value={m.name}
                      onSelect={() => handleModelSelect(m.name)}
                    >
                      <div className="flex min-w-0 flex-1 flex-col">
                        <ModelSelectorName>{m.display_name}</ModelSelectorName>
                        <span className="text-muted-foreground truncate text-[10px]">
                          {m.model}
                        </span>
                      </div>
                      {m.name === context.model_name ? (
                        <CheckIcon className="ml-auto size-4" />
                      ) : (
                        <div className="ml-auto size-4" />
                      )}
                    </ModelSelectorItem>
                  ))}
                </ModelSelectorList>
              </ModelSelectorContent>
            </ModelSelector>
          )}
          <PromptInputSubmit
            className="rounded-full"
            disabled={disabled}
            variant="outline"
            status={status}
          />
        </PromptInputTools>
      </PromptInputFooter>
      {!isNewThread && (
        <div className="bg-background absolute right-0 -bottom-[17px] left-0 z-0 h-4"></div>
      )}
      </PromptInput>

      {!disabled &&
        !isNewThread &&
        !followupsHidden &&
        (followupsLoading || followups.length > 0) && (
          <div className="absolute right-0 -top-20 left-0 z-20 flex items-center justify-center">
            <div className="flex items-center gap-2">
              {followupsLoading ? (
                <div className="text-muted-foreground bg-background/80 rounded-full border px-4 py-2 text-xs backdrop-blur-sm">
                  {t.inputBox.followupLoading}
                </div>
              ) : (
                <Suggestions className="min-h-16 w-fit items-start">
                  {followups.map((s) => (
                    <Suggestion
                      key={s}
                      suggestion={s}
                      onClick={() => handleFollowupClick(s)}
                    />
                  ))}
                  <Button
                    aria-label={t.common.close}
                    className="text-muted-foreground cursor-pointer rounded-full px-3 text-xs font-normal"
                    variant="outline"
                    size="sm"
                    type="button"
                    onClick={() => setFollowupsHidden(true)}
                  >
                    <XIcon className="size-4" />
                  </Button>
                </Suggestions>
              )}
            </div>
          </div>
        )}

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.inputBox.followupConfirmTitle}</DialogTitle>
            <DialogDescription>
              {t.inputBox.followupConfirmDescription}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button variant="secondary" onClick={confirmAppendAndSend}>
              {t.inputBox.followupConfirmAppend}
            </Button>
            <Button onClick={confirmReplaceAndSend}>
              {t.inputBox.followupConfirmReplace}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SuggestionList() {
  const { t } = useI18n();
  const { textInput } = usePromptInputController();
  const handleSuggestionClick = useCallback(
    (prompt: string | undefined) => {
      if (!prompt) return;
      textInput.setInput(prompt);
      setTimeout(() => {
        const textarea = document.querySelector<HTMLTextAreaElement>(
          "textarea[name='message']",
        );
        if (textarea) {
          const selStart = prompt.indexOf("[");
          const selEnd = prompt.indexOf("]");
          if (selStart !== -1 && selEnd !== -1) {
            textarea.setSelectionRange(selStart, selEnd + 1);
            textarea.focus();
          }
        }
      }, 500);
    },
    [textInput],
  );
  return (
    <Suggestions className="min-h-16 w-fit items-start">
      <ConfettiButton
        className="text-muted-foreground cursor-pointer rounded-full px-4 text-xs font-normal"
        variant="outline"
        size="sm"
        onClick={() => handleSuggestionClick(t.inputBox.surpriseMePrompt)}
      >
        <SparklesIcon className="size-4" /> {t.inputBox.surpriseMe}
      </ConfettiButton>
      {t.inputBox.suggestions.map((suggestion) => (
        <Suggestion
          key={suggestion.suggestion}
          icon={suggestion.icon}
          suggestion={suggestion.suggestion}
          onClick={() => handleSuggestionClick(suggestion.prompt)}
        />
      ))}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Suggestion icon={PlusIcon} suggestion={t.common.create} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuGroup>
            {t.inputBox.suggestionsCreate.map((suggestion, index) =>
              "type" in suggestion && suggestion.type === "separator" ? (
                <DropdownMenuSeparator key={index} />
              ) : (
                !("type" in suggestion) && (
                  <DropdownMenuItem
                    key={suggestion.suggestion}
                    onClick={() => handleSuggestionClick(suggestion.prompt)}
                  >
                    {suggestion.icon && <suggestion.icon className="size-4" />}
                    {suggestion.suggestion}
                  </DropdownMenuItem>
                )
              ),
            )}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </Suggestions>
  );
}

function AddAttachmentsButton({ className }: { className?: string }) {
  const { t } = useI18n();
  const attachments = usePromptInputAttachments();
  return (
    <Tooltip content={t.inputBox.addAttachments}>
      <PromptInputButton
        className={cn("px-2!", className)}
        onClick={() => attachments.openFileDialog()}
      >
        <PaperclipIcon className="size-3" />
      </PromptInputButton>
    </Tooltip>
  );
}
