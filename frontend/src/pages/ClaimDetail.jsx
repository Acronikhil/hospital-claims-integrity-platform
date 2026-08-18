import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { decideClaim, getClaim } from "../api.js";
import RiskBadge from "../components/RiskBadge.jsx";
import FindingCard from "../components/FindingCard.jsx";
import CaseSummary from "../components/CaseSummary.jsx";
import PipelineView from "../components/PipelineView.jsx";
import SettlementPanel from "../components/SettlementPanel.jsx";
import BillClassificationTable from "../components/BillClassificationTable.jsx";

const formatCurrency = (value) =>
  typeof value === "number" ? `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}` : "—";

export default function ClaimDetail() {
  const { claimId } = useParams();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deciding, setDeciding] = useState(false);
  const [note, setNote] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    getClaim(claimId)
      .then(setDetail)
      .catch(() => setError("Could not load this claim."))
      .finally(() => setLoading(false));
  }, [claimId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleDecision = async (decision) => {
    setDeciding(true);
    try {
      await decideClaim(claimId, { decision, note: note || undefined });
      await load();
    } catch {
      setError("Failed to record decision.");
    } finally {
      setDeciding(false);
    }
  };

  if (loading) return <div className="page">Loading claim…</div>;
  if (error) return <div className="page error-text">{error}</div>;
  if (!detail) return null;

  const { claim, patient, hospital, doctor, diagnosis, procedure, billItems, classifications, findings } = detail;
  const sortedFindings = [...findings].sort((a, b) => (b.variance || 0) - (a.variance || 0));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>{claim.claimId}</h1>
          <p className="muted">
            {claim.status}
            {claim.sourceType === "PDF_UPLOAD" && claim.sourceFileNames?.length > 0 && (
              <span className="source-badge"> · extracted from {claim.sourceFileNames.join(", ")}</span>
            )}
          </p>
        </div>
        <RiskBadge level={claim.riskLevel} />
      </div>

      <div className="detail-grid">
        <div className="info-card">
          <span className="label">Patient</span>
          <span className="value">{patient?.name || "—"}</span>
        </div>
        <div className="info-card">
          <span className="label">Hospital</span>
          <span className="value">{hospital?.name || "—"}</span>
        </div>
        <div className="info-card">
          <span className="label">Doctor</span>
          <span className="value">{doctor?.name || "—"}</span>
        </div>
        <div className="info-card">
          <span className="label">Diagnosis</span>
          <span className="value">{diagnosis?.name || "—"}</span>
        </div>
        <div className="info-card">
          <span className="label">Procedure</span>
          <span className="value">{procedure?.name || "—"}</span>
        </div>
        <div className="info-card">
          <span className="label">Length of Stay</span>
          <span className="value">{claim.lengthOfStayDays} day(s)</span>
        </div>
        <div className="info-card">
          <span className="label">Claimed Amount</span>
          <span className="value">{formatCurrency(claim.claimedAmount)}</span>
        </div>
        <div className="info-card">
          <span className="label">Potential Leakage</span>
          <span className="value stat-danger">{formatCurrency(claim.potentialLeakage)}</span>
        </div>
      </div>

      <section className="section">
        <h2>Settlement &amp; Policy</h2>
        <SettlementPanel settlement={claim.settlement} policy={claim.policy} />
      </section>

      <section className="section">
        <h2>Investigation Pipeline</h2>
        <p className="muted pipeline-intro">
          What each agent did to reach this result — like a CI run, expand a step to see its raw output.
        </p>
        <PipelineView pipeline={claim.pipeline} />
      </section>

      <section className="section">
        <h2>Case Summary</h2>
        <CaseSummary
          summary={claim.summary}
          riskLevel={claim.riskLevel}
          claimedAmount={claim.claimedAmount}
          potentialLeakage={claim.potentialLeakage}
        />
      </section>

      <section className="section">
        <h2>Tariff Matching Breakdown</h2>
        <p className="muted pipeline-intro">
          Every bill item mapped to the hospital's tariff catalog, with match confidence and outcome.
        </p>
        <BillClassificationTable classifications={classifications} />
      </section>

      <section className="section">
        <h2>Bill Items</h2>
        <table className="bill-table">
          <thead>
            <tr>
              <th>Description</th>
              <th>Item Type</th>
              <th>Qty</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {billItems.map((item) => (
              <tr key={item.billItemId}>
                <td>{item.description}</td>
                <td>{item.itemType}</td>
                <td>{item.quantity}</td>
                <td>{formatCurrency(item.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="section">
        <h2>Investigation Findings ({sortedFindings.length})</h2>
        {sortedFindings.length === 0 ? (
          <p className="muted">No issues detected by the Tariff or Duplicate Billing agents.</p>
        ) : (
          <div className="findings-list">
            {sortedFindings.map((finding, idx) => (
              <FindingCard key={finding.findingId} finding={finding} index={idx + 1} />
            ))}
          </div>
        )}
      </section>

      <section className="section decision-section">
        <h2>Adjudicator Decision</h2>
        <textarea
          placeholder="Optional note…"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
        />
        <div className="decision-actions">
          <button className="approve-btn" disabled={deciding} onClick={() => handleDecision("APPROVED")}>
            Approve
          </button>
          <button className="query-btn" disabled={deciding} onClick={() => handleDecision("QUERIED")}>
            Send Query
          </button>
          <button className="deduct-btn" disabled={deciding} onClick={() => handleDecision("DEDUCTED")}>
            Deduct
          </button>
          <button className="escalate-btn" disabled={deciding} onClick={() => handleDecision("ESCALATED")}>
            Escalate
          </button>
        </div>
        {claim.decisionNote && (
          <p className="muted">Last note: {claim.decisionNote}</p>
        )}
      </section>
    </div>
  );
}
