import { createContext, useCallback, useContext, useState } from "react";

import type { ResearchScore, Subtask } from "./types";

export interface SubtaskContextValue {
  tasks: Record<string, Subtask>;
  setTasks: (tasks: Record<string, Subtask>) => void;
  scores: ResearchScore[];
  setScores: (scores: ResearchScore[]) => void;
}

export const SubtaskContext = createContext<SubtaskContextValue>({
  tasks: {},
  setTasks: () => {
    /* noop */
  },
  scores: [],
  setScores: () => {
    /* noop */
  },
});

export function SubtasksProvider({ children }: { children: React.ReactNode }) {
  const [tasks, setTasks] = useState<Record<string, Subtask>>({});
  const [scores, setScores] = useState<ResearchScore[]>([]);
  return (
    <SubtaskContext.Provider value={{ tasks, setTasks, scores, setScores }}>
      {children}
    </SubtaskContext.Provider>
  );
}

export function useSubtaskContext() {
  const context = useContext(SubtaskContext);
  if (context === undefined) {
    throw new Error(
      "useSubtaskContext must be used within a SubtaskContext.Provider",
    );
  }
  return context;
}

export function useSubtask(id: string) {
  const { tasks } = useSubtaskContext();
  return tasks[id];
}

export function useScores() {
  const { scores } = useSubtaskContext();
  return scores;
}

export function useUpdateSubtask() {
  const { tasks, setTasks } = useSubtaskContext();
  const updateSubtask = useCallback(
    (task: Partial<Subtask> & { id: string }) => {
      const existing = tasks[task.id] || {};
      tasks[task.id] = { ...existing, ...task } as Subtask;
      // Always trigger a re-render to reflect status changes, results, or timestamps
      setTasks({ ...tasks });
    },
    [tasks, setTasks],
  );
  return updateSubtask;
}
