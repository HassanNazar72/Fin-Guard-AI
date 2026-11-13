import type { ReactNode } from "react";
import { toolLabel } from "@/lib/format";
import type { ExecutionTrace as Trace } from "@/lib/types";
import { ChevronIcon } from "./icons";

const MODE_LABEL: Record<Trace["mode"], string> = {
  live: "Live Gemini call",
  cached: "Pre-computed demo cache",
  fallback: "Deterministic fallback",
  blocked: "Blocked by firewall",
};

function Row({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-t border-line py-1.5 first:border-t-0">
      <dt className="text-muted">{k}</dt>
      <dd className="text-right text-ink">{v}</dd>
    </div>
  );
}

export function ExecutionTrace({ trace }: { trace: Trace }) {
  const tokens =
    trace.input_tokens !== null && trace.output_tokens !== null
      ? `${trace.input_tokens} in / ${trace.output_tokens} out`
      : "-";
  return (
    <details className="group mt-3 rounded-xl border border-line bg-card-2">
      <summary className="flex cursor-pointer select-none items-center gap-1.5 px-3 py-2 text-xs font-medium text-ink-2 hover:text-ink">
        <ChevronIcon width={12} height={12} className="transition group-open:rotate-90" />
        Agent Execution Trace
        <span className="ml-auto font-mono text-[11px] text-muted">{trace.latency_ms.toFixed(0)} ms</span>
      </summary>
      <dl className="px-3 pb-2 font-mono text-[11px]">
        <Row k="Model" v={trace.model} />
        <Row k="Mode" v={MODE_LABEL[trace.mode]} />
        <Row
          k="Tools Called"
          v={
            trace.tools_called.length ? (
              <span className="flex flex-col items-end">
                {trace.tools_called.map((t) => {
                  const timing = trace.tool_timings.find((x) => x.name === t);
                  return (
                    <span key={t} title={toolLabel(t)}>
                      {t}()
                      {timing ? <span className="text-muted"> {timing.duration_ms.toFixed(1)}ms</span> : null}
                    </span>
                  );
                })}
              </span>
            ) : (
              "none"
            )
          }
        />
        <Row k="Confidence Score" v={trace.confidence_score.toFixed(2)} />
        <Row
          k="Schema Validated"
          v={<span className={trace.schema_validated ? "text-good" : "text-bad"}>{String(trace.schema_validated).toUpperCase()}</span>}
        />
        <Row k="Latency (ms)" v={trace.latency_ms.toFixed(1)} />
        <Row k="LLM Calls" v={trace.llm_calls} />
        <Row k="Tokens" v={tokens} />
      </dl>
    </details>
  );
}
