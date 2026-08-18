const RISK_CLASS = {
  HIGH: "risk-badge risk-high",
  MEDIUM: "risk-badge risk-medium",
  LOW: "risk-badge risk-low",
};

export default function RiskBadge({ level }) {
  if (!level) return <span className="risk-badge risk-unknown">—</span>;
  const className = RISK_CLASS[level] || "risk-badge risk-unknown";
  return <span className={className}>{level}</span>;
}
