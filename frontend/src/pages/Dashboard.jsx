import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getClaims } from "../api.js";
import RiskBadge from "../components/RiskBadge.jsx";

const formatCurrency = (value) =>
  typeof value === "number" ? `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}` : "—";

export default function Dashboard() {
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getClaims()
      .then(setClaims)
      .catch(() => setError("Could not load claims. Is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  const totalLeakage = claims.reduce((sum, c) => sum + (c.potentialLeakage || 0), 0);
  const highRiskCount = claims.filter((c) => c.riskLevel === "HIGH").length;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Claims Workbench</h1>
        <Link to="/upload" className="primary-btn">
          + Upload Claim
        </Link>
      </div>

      <div className="stat-row">
        <div className="stat-card">
          <span className="stat-label">Claims Processed</span>
          <span className="stat-value">{claims.length}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">High Risk Claims</span>
          <span className="stat-value stat-danger">{highRiskCount}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Potential Leakage Identified</span>
          <span className="stat-value stat-danger">{formatCurrency(totalLeakage)}</span>
        </div>
      </div>

      {loading && <p className="muted">Loading claims…</p>}
      {error && <p className="error-text">{error}</p>}

      {!loading && !error && claims.length === 0 && (
        <div className="empty-state">
          <p>No claims processed yet.</p>
          <Link to="/upload" className="primary-btn">
            Upload your first claim
          </Link>
        </div>
      )}

      {!loading && claims.length > 0 && (
        <table className="claims-table">
          <thead>
            <tr>
              <th>Claim ID</th>
              <th>Patient</th>
              <th>Hospital</th>
              <th>Procedure</th>
              <th>Claimed Amount</th>
              <th>Recommended Settlement</th>
              <th>Risk</th>
              <th>Potential Leakage</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => (
              <tr key={claim.claimId}>
                <td>
                  <Link to={`/claims/${claim.claimId}`} className="claim-link">
                    {claim.claimId}
                  </Link>
                </td>
                <td>{claim.patientName || "—"}</td>
                <td>{claim.hospitalName || "—"}</td>
                <td>{claim.procedure || "—"}</td>
                <td>{formatCurrency(claim.claimedAmount)}</td>
                <td>{formatCurrency(claim.recommendedSettlementAmount)}</td>
                <td>
                  <RiskBadge level={claim.riskLevel} />
                </td>
                <td className={claim.potentialLeakage ? "leakage-cell" : ""}>
                  {formatCurrency(claim.potentialLeakage)}
                </td>
                <td>
                  <span className="status-pill">{claim.status || "—"}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
