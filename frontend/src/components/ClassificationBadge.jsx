const STATUS_META = {
  MATCHED_WITHIN_RATE: { label: "Within Rate", className: "class-badge class-within" },
  MATCHED_OVER_RATE: { label: "Over Rate", className: "class-badge class-over" },
  MATCHED_UNDER_RATE: { label: "Under Rate", className: "class-badge class-under" },
  NOT_COVERED: { label: "Not Covered", className: "class-badge class-not-covered" },
  UNMAPPED_AMBIGUOUS: { label: "Ambiguous", className: "class-badge class-ambiguous" },
  DUPLICATE_QUANTITY: { label: "Duplicate", className: "class-badge class-duplicate" },
};

export default function ClassificationBadge({ status }) {
  const meta = STATUS_META[status] || { label: status || "—", className: "class-badge" };
  return <span className={meta.className}>{meta.label}</span>;
}
