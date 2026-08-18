const formatCurrency = (value) =>
  typeof value === "number" ? `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}` : "—";

const RECOMMENDATION_CLASS = {
  HIGH: "recommendation-callout recommendation-high",
  MEDIUM: "recommendation-callout recommendation-medium",
  LOW: "recommendation-callout recommendation-low",
};

export default function CaseSummary({ summary, riskLevel, claimedAmount, potentialLeakage }) {
  if (!summary) return null;

  const netExpected = Math.max((claimedAmount || 0) - (potentialLeakage || 0), 0);
  const leakagePercent = claimedAmount ? Math.min((potentialLeakage / claimedAmount) * 100, 100) : 0;
  const recommendationClass = RECOMMENDATION_CLASS[riskLevel] || "recommendation-callout";

  return (
    <div className="case-summary-panel">
      <p className="case-overview">{summary.overview}</p>

      {claimedAmount > 0 && (
        <div className="financial-breakdown">
          <div className="financial-breakdown-header">
            <span>Financial Breakdown</span>
            <span>{formatCurrency(claimedAmount)} claimed</span>
          </div>
          <div className="breakdown-bar">
            <div className="breakdown-bar-net" style={{ width: `${100 - leakagePercent}%` }} />
            <div className="breakdown-bar-leak" style={{ width: `${leakagePercent}%` }} />
          </div>
          <div className="breakdown-legend">
            <span>
              <i className="legend-dot legend-dot-net" /> Net Expected: {formatCurrency(netExpected)}
            </span>
            <span>
              <i className="legend-dot legend-dot-leak" /> Potential Leakage: {formatCurrency(potentialLeakage)} (
              {leakagePercent.toFixed(1)}%)
            </span>
          </div>
        </div>
      )}

      {!summary.tariffReferenceAvailable && (
        <p className="tariff-warning">
          ⚠ No contracted tariff reference data exists in the knowledge graph for this hospital/procedure
          combination — tariff checks were skipped for this claim.
        </p>
      )}

      {summary.evidenceSources?.length > 0 && (
        <div className="evidence-tags">
          {summary.evidenceSources.map((source) => (
            <span className="evidence-tag" key={source}>
              {source}
            </span>
          ))}
        </div>
      )}

      <div className={recommendationClass}>
        <span className="recommendation-label">Recommendation</span>
        <span>{summary.recommendation}</span>
      </div>
    </div>
  );
}
