"use client";

import { SearchIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { cn } from "@/lib/utils";

import { AuroraText } from "../ui/aurora-text";

export function Welcome({
  className,
}: {
  className?: string;
  mode?: "ultra" | "pro" | "thinking" | "flash";
}) {
  const [waved, setWaved] = useState(false);
  const colors = useMemo(
    () => ["#efefbb", "#e9c665", "#e3a812"],
    [],
  );
  useEffect(() => {
    setWaved(true);
  }, []);
  return (
    <div
      className={cn(
        "mx-auto flex w-full flex-col items-center justify-center gap-3 px-8 py-4 text-center",
        className,
      )}
    >
      <div className="text-2xl font-bold">
        <div className="flex items-center gap-2">
          <div className={cn("inline-block", !waved ? "animate-wave" : "")}>
            <SearchIcon className="size-6 text-amber-500" />
          </div>
          <AuroraText colors={colors}>Deep Research Engine</AuroraText>
        </div>
      </div>
      <p className="text-muted-foreground max-w-md text-sm">
        Ask anything. 3 AI agents will search the web in parallel,
        cross-validate their findings, and synthesize a comprehensive answer.
      </p>
    </div>
  );
}
