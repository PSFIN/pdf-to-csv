"use client";

import { useEffect, useRef } from "react";

export interface LogEntry {
  timestamp: string;
  message: string;
  type: "step" | "progress" | "success" | "error";
}

interface ProcessingLogProps {
  logs: LogEntry[];
  isProcessing: boolean;
}

function getIndicator(type: LogEntry["type"]) {
  switch (type) {
    case "step":
      return <span className="text-emerald-400">{">"}</span>;
    case "progress":
      return <span className="text-blue-400">{">"}</span>;
    case "success":
      return <span className="text-green-400">{"✓"}</span>;
    case "error":
      return <span className="text-red-400">{"✗"}</span>;
  }
}

function getMessageColor(type: LogEntry["type"]) {
  switch (type) {
    case "step":
      return "text-gray-300";
    case "progress":
      return "text-gray-400";
    case "success":
      return "text-green-300";
    case "error":
      return "text-red-300";
  }
}

export default function ProcessingLog({ logs, isProcessing }: ProcessingLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Calculate progress from logs
  const lastProgress = [...logs].reverse().find((l) => l.type === "progress");
  let progressPercent = 0;
  if (lastProgress) {
    const match = lastProgress.message.match(/page (\d+)\/(\d+)/);
    if (match) {
      progressPercent = Math.round((parseInt(match[1]) / parseInt(match[2])) * 100);
    }
  }
  if (!isProcessing && logs.length > 0) {
    progressPercent = 100;
  }

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
      {/* Terminal title bar */}
      <div className="flex items-center gap-2 border-b border-gray-800 bg-gray-900/80 px-4 py-3">
        <div className="flex gap-1.5">
          <div className="h-3 w-3 rounded-full bg-red-500/80" />
          <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
          <div className="h-3 w-3 rounded-full bg-green-500/80" />
        </div>
        <span className="ml-2 text-xs font-medium text-gray-500">
          Processing Log
        </span>
        {isProcessing && (
          <span className="ml-auto text-xs text-blue-400 progress-pulse">
            Processing...
          </span>
        )}
        {!isProcessing && logs.length > 0 && (
          <span className="ml-auto text-xs text-green-400">Complete</span>
        )}
      </div>

      {/* Progress bar */}
      {(isProcessing || progressPercent > 0) && (
        <div className="h-0.5 bg-gray-800">
          <div
            className="h-full bg-emerald-500 transition-all duration-300 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      )}

      {/* Log content */}
      <div className="terminal-scroll max-h-[500px] overflow-y-auto p-4 font-mono text-sm">
        {logs.map((log, i) => (
          <div key={i} className="log-entry flex gap-3 py-0.5">
            <span className="shrink-0 text-gray-600 select-none">
              {log.timestamp}
            </span>
            <span className="shrink-0 w-4 text-center select-none">
              {getIndicator(log.type)}
            </span>
            <span className={getMessageColor(log.type)}>{log.message}</span>
          </div>
        ))}

        {/* Blinking cursor while processing */}
        {isProcessing && (
          <div className="flex items-center gap-3 py-0.5 mt-1">
            <span className="text-gray-600 select-none">
              {new Date().toLocaleTimeString("en-AU", {
                hour12: false,
              })}
            </span>
            <span className="w-4 text-center">
              <span className="inline-block h-4 w-1.5 bg-emerald-400 cursor-blink" />
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
