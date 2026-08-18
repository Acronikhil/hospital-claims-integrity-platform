import { useState } from "react";

const STATUS_META = {
  success: { icon: "✓", className: "pipeline-status-success", label: "Passed" },
  warning: { icon: "⚠", className: "pipeline-status-warning", label: "Flagged" },
  skipped: { icon: "⊘", className: "pipeline-status-skipped", label: "Skipped" },
  info: { icon: "ℹ", className: "pipeline-status-info", label: "Info" },
};

function PipelineRow({ step }) {
  const [expanded, setExpanded] = useState(false);
  const meta = STATUS_META[step.status] || STATUS_META.info;

  return (
    <div className={`pipeline-row ${meta.className}`}>
      <div className="pipeline-row-main" onClick={() => step.detail && setExpanded((v) => !v)}>
        <span className="pipeline-icon" title={meta.label}>
          {meta.icon}
        </span>
        <div className="pipeline-row-text">
          <div className="pipeline-row-header">
            <span className="pipeline-step-name">{step.step}</span>
            <span className="pipeline-agent-name">{step.agent}</span>
          </div>
          <p className="pipeline-summary">{step.summary}</p>
        </div>
        <div className="pipeline-row-meta">
          {typeof step.durationMs === "number" && <span className="pipeline-duration">{step.durationMs} ms</span>}
          {step.detail && <span className="pipeline-expand-toggle">{expanded ? "Hide details ▲" : "View details ▼"}</span>}
        </div>
      </div>
      {expanded && step.detail && <pre className="pipeline-detail">{step.detail}</pre>}
    </div>
  );
}

export default function PipelineView({ pipeline }) {
  if (!pipeline || pipeline.length === 0) return null;

  return (
    <div className="pipeline-view">
      {pipeline.map((step, idx) => (
        <PipelineRow key={`${step.step}-${idx}`} step={step} />
      ))}
    </div>
  );
}
