const formatCurrency = (value) =>
  typeof value === "number" ? `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}` : "—";

export default function SettlementPanel({ settlement, policy }) {
  if (!settlement) return null;

  return (
    <div className="settlement-panel">
      <div className="settlement-figures">
        <div className="settlement-figure">
          <span className="label">Claimed Amount</span>
          <span className="value">{formatCurrency(settlement.claimedAmount)}</span>
        </div>
        <div className="settlement-figure settlement-figure-highlight">
          <span className="label">Recommended Settlement</span>
          <span className="value">{formatCurrency(settlement.recommendedSettlementAmount)}</span>
        </div>
        <div className="settlement-figure">
          <span className="label">Withheld / Pending Review</span>
          <span className="value stat-danger">{formatCurrency(settlement.withheldAmount)}</span>
        </div>
        <div className="settlement-figure">
          <span className="label">Insurer Payable (post co-pay)</span>
          <span className="value">{formatCurrency(settlement.insurerPayableAmount)}</span>
        </div>
      </div>

      {settlement.sumInsuredCapApplied && (
        <p className="tariff-warning">⚠ Recommended settlement was capped at the policy's sum insured.</p>
      )}

      <div className="policy-details">
        {policy?.policyAvailable ? (
          <>
            <div className="policy-detail-row">
              <span className="label">Policy</span>
              <span>
                {policy.policyNumber} — {policy.planName}
              </span>
            </div>
            <div className="policy-detail-row">
              <span className="label">Sum Insured</span>
              <span>{formatCurrency(policy.sumInsuredAmount)}</span>
            </div>
            <div className="policy-detail-row">
              <span className="label">Room Rent Sub-limit</span>
              <span>{policy.roomRentLimitPerDay ? `${formatCurrency(policy.roomRentLimitPerDay)}/day` : "—"}</span>
            </div>
            <div className="policy-detail-row">
              <span className="label">Co-pay</span>
              <span>
                {policy.copayPercentage}% ({formatCurrency(settlement.copayAmount)})
              </span>
            </div>
          </>
        ) : (
          <p className="muted">
            No policy reference data found for {policy?.policyNumber || "this policy number"} — sum insured and
            room rent checks were skipped.
          </p>
        )}
      </div>
    </div>
  );
}
