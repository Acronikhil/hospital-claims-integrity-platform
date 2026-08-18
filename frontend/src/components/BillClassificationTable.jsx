import ClassificationBadge from "./ClassificationBadge.jsx";

const formatCurrency = (value) =>
  typeof value === "number" ? `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}` : "—";

export default function BillClassificationTable({ classifications }) {
  if (!classifications || classifications.length === 0) {
    return <p className="muted">No tariff-matching classification available for this claim.</p>;
  }

  return (
    <div className="table-scroll">
      <table className="bill-table classification-table">
        <thead>
          <tr>
            <th>Bill Item</th>
            <th>Matched Tariff Entry</th>
            <th>Confidence</th>
            <th>Billed</th>
            <th>Tariff Rate</th>
            <th>Variance</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {classifications.map((c) => (
            <tr key={c.billItemId}>
              <td>{c.description}</td>
              <td className="muted">{c.matchedTariffDescription || "—"}</td>
              <td>{c.confidence}%</td>
              <td>{formatCurrency(c.billedAmount)}</td>
              <td>{formatCurrency(c.matchedRate)}</td>
              <td className={c.variance ? "leakage-cell" : ""}>{c.variance ? formatCurrency(c.variance) : "—"}</td>
              <td>
                <ClassificationBadge status={c.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
