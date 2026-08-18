const formatCurrency = (value) =>
  typeof value === "number" ? `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}` : "—";

export default function FindingCard({ finding, index }) {
  return (
    <div className="finding-card">
      <div className="finding-header">
        <span className="finding-index">{index}</span>
        <div>
          <div className="finding-description">{finding.description}</div>
          <div className="finding-agent">{finding.agent}</div>
        </div>
        <span className="finding-confidence">{finding.confidence}% confidence</span>
      </div>
      <p className="finding-reason">{finding.reason}</p>
      <div className="finding-evidence-grid">
        <div>
          <span className="label">Billed</span>
          <span className="value">{formatCurrency(finding.billedAmount)}</span>
        </div>
        <div>
          <span className="label">Allowed</span>
          <span className="value">{formatCurrency(finding.allowedAmount)}</span>
        </div>
        <div>
          <span className="label">Potential Impact</span>
          <span className="value impact">{formatCurrency(finding.variance)}</span>
        </div>
      </div>
      <div className="finding-footer">
        <div>
          <span className="label">Source</span>
          <p className="source">{finding.source}</p>
        </div>
        <div>
          <span className="label">Recommended Action</span>
          <p className="action">{finding.recommendedAction}</p>
        </div>
      </div>
    </div>
  );
}
