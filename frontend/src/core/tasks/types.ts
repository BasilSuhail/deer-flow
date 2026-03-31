import type { AIMessage } from "@langchain/langgraph-sdk";

export interface ResearchScore {
  agent_index: number;
  accuracy: number;
  completeness: number;
  source_quality: number;
  clarity: number;
  cross_validation_bonus: number;
  weighted_total: number;
  details: Record<string, unknown>;
}

export interface Subtask {
  id: string;
  status: "in_progress" | "completed" | "failed";
  subagent_type: string;
  description: string;
  latestMessage?: AIMessage;
  prompt: string;
  result?: string;
  error?: string;
  score?: ResearchScore;
  started_at?: string;
  completed_at?: string;
}
