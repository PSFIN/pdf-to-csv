"use client";

import { useState, useCallback } from "react";
import FileUpload from "./components/FileUpload";
import ProcessingLog, { LogEntry } from "./components/ProcessingLog";
import Summary from "./components/Summary";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AppState = "idle" | "uploading" | "processing" | "complete";

interface SummaryData {
  total_transactions: number;
  total_credits: string;
  total_debits: string;
  starting_balance: string;
  ending_balance: string;
  date_range: { from: string; to: string };
  balance_errors: number;
  type_breakdown: Record<string, number>;
}

export default function Home() {
  const [state, setState] = useState<AppState>("idle");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [csvUrl, setCsvUrl] = useState("");
  const [error, setError] = useState("");

  const addLog = useCallback(
    (message: string, type: LogEntry["type"] = "step") => {
      const timestamp = new Date().toLocaleTimeString("en-AU", {
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      setLogs((prev) => [...prev, { timestamp, message, type }]);
    },
    []
  );

  const handleUpload = useCallback(
    async (file: File) => {
      setState("uploading");
      setLogs([]);
      setSummary(null);
      setCsvUrl("");
      setError("");

      addLog(`Uploading ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)...`, "step");

      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await fetch(`${API_BASE}/api/upload`, {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          const detail = await res.json().catch(() => ({ detail: "Upload failed" }));
          throw new Error(detail.detail || "Upload failed");
        }

        const { job_id } = await res.json();
        addLog("File uploaded successfully. Starting processing...", "success");

        setState("processing");

        const eventSource = new EventSource(`${API_BASE}/api/stream/${job_id}`);

        eventSource.addEventListener("step", (e) => {
          const data = JSON.parse(e.data);
          addLog(data.message, "step");
        });

        eventSource.addEventListener("progress", (e) => {
          const data = JSON.parse(e.data);
          addLog(data.message, "progress");
        });

        eventSource.addEventListener("summary", (e) => {
          const data = JSON.parse(e.data);
          setSummary(data);
        });

        eventSource.addEventListener("done", (e) => {
          const data = JSON.parse(e.data);
          setCsvUrl(`${API_BASE}${data.csv_url}`);
          addLog("Processing complete! CSV ready for download.", "success");
          eventSource.close();
          setState("complete");
        });

        eventSource.addEventListener("error", (e: Event) => {
          const me = e as MessageEvent;
          if (me.data) {
            try {
              const data = JSON.parse(me.data);
              addLog(data.message, "error");
              setError(data.message);
            } catch {
              addLog("Connection lost. Processing may still be running.", "error");
            }
          }
          eventSource.close();
          setState("complete");
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to upload file";
        addLog(message, "error");
        setError(message);
        setState("idle");
      }
    },
    [addLog]
  );

  const handleReset = useCallback(() => {
    setState("idle");
    setLogs([]);
    setSummary(null);
    setCsvUrl("");
    setError("");
  }, []);

  return (
    <main className="min-h-screen bg-gray-950 px-4 py-12">
      <div className="mx-auto max-w-3xl">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-gray-800 bg-gray-900 px-4 py-1.5 text-xs text-gray-400">
            <svg
              className="h-3.5 w-3.5 text-emerald-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
              />
            </svg>
            Bank Statement Converter
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-white">
            PDF to CSV
          </h1>
          <p className="mt-2 text-gray-500">
            Upload your bank statement PDF and watch the extraction in real-time
          </p>
        </div>

        {/* Upload area - shown in idle and uploading states */}
        {(state === "idle" || state === "uploading") && (
          <div className={state === "uploading" ? "pointer-events-none opacity-50" : ""}>
            <FileUpload onUpload={handleUpload} />
          </div>
        )}

        {/* Uploading spinner */}
        {state === "uploading" && (
          <div className="mt-4 flex items-center justify-center gap-2 text-sm text-gray-400">
            <svg
              className="h-4 w-4 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 0 1 4 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Uploading...
          </div>
        )}

        {/* Processing log and results */}
        {(state === "processing" || state === "complete") && (
          <div className="space-y-0">
            <ProcessingLog logs={logs} isProcessing={state === "processing"} />
            {summary && (
              <Summary data={summary} csvUrl={csvUrl} onReset={handleReset} />
            )}
          </div>
        )}

        {/* Error banner */}
        {error && state === "idle" && (
          <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}
      </div>
    </main>
  );
}
