"use client";

import { useRef } from "react";
import { FileIcon, ShieldIcon, UploadIcon } from "./icons";

const MAX_FILE_BYTES = 100_000;

interface Props {
  loading: boolean;
  source: "sample" | "upload" | null;
  fileName: string | null;
  piiScrubbed: number;
  injectionsBlocked: number;
  liveAiEnabled: boolean | null;
  onLoadSample: () => void;
  onUpload: (csvText: string, fileName: string) => void;
  onError: (message: string) => void;
}

export function ControlBar({
  loading,
  source,
  fileName,
  piiScrubbed,
  injectionsBlocked,
  liveAiEnabled,
  onLoadSample,
  onUpload,
  onError,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      onError("Please upload a .csv bank statement export.");
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      onError("That file is larger than 100 KB. FinGuard analyses up to 200 transactions.");
      return;
    }
    onUpload(await file.text(), file.name);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <section
      aria-label="Statement controls"
      className="flex flex-col gap-3 rounded-2xl border border-line bg-card p-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onLoadSample}
          disabled={loading}
          className="inline-flex h-10 items-center gap-2 rounded-full bg-accent px-4 text-sm font-semibold text-accent-ink transition hover:opacity-90 disabled:opacity-50"
        >
          <FileIcon />
          Load Sample UK Statement
        </button>
        <label
          className={`inline-flex h-10 cursor-pointer items-center gap-2 rounded-full border border-line bg-card px-4 text-sm font-semibold text-ink transition hover:bg-card-2 ${
            loading ? "pointer-events-none opacity-50" : ""
          }`}
        >
          <UploadIcon />
          Upload CSV
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            onChange={(e) => handleFile(e.target.files?.[0])}
            disabled={loading}
          />
        </label>
        {source && (
          <span className="truncate text-xs text-muted" title={fileName ?? undefined}>
            {source === "sample" ? "Sample statement loaded" : `Loaded ${fileName ?? "upload"}`}
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {liveAiEnabled !== null && (
          <span
            className={`inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-xs font-medium ${
              liveAiEnabled ? "bg-good-soft text-good" : "bg-card-2 text-ink-2"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${liveAiEnabled ? "bg-good" : "bg-muted"}`}
              aria-hidden="true"
            />
            {liveAiEnabled ? "Live Gemini agent" : "Deterministic mode"}
          </span>
        )}
        <div
          role="status"
          aria-live="polite"
          className="inline-flex h-8 items-center gap-2 rounded-full border border-line bg-card-2 px-3 text-xs font-medium text-ink-2"
          title="Security telemetry: PII is hashed and prompt injections are neutralised before any data reaches the AI."
        >
          <ShieldIcon className="text-good" />
          <span>
            PII Fields Scrubbed: <strong className="font-semibold text-ink">{piiScrubbed}</strong>
          </span>
          <span className="text-line" aria-hidden="true">
            |
          </span>
          <span>
            Injections Blocked:{" "}
            <strong className={`font-semibold ${injectionsBlocked ? "text-bad" : "text-ink"}`}>
              {injectionsBlocked}
            </strong>
          </span>
        </div>
      </div>
    </section>
  );
}
