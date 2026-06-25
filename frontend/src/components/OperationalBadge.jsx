const STATUS_LABELS = {
  normal: "Κανονικό",
  warning: "Προειδοποίηση",
  critical: "Κρίσιμο",
  unknown: "Άγνωστο",
};

export default function OperationalBadge({ channel, severity }) {
  const status = severity || channel?.operational_status || "unknown";
  const label =
    channel?.operational_status_label ||
    STATUS_LABELS[status] ||
    STATUS_LABELS.unknown;

  return (
    <span className={`operational-badge operational-badge--${status}`}>
      {label}
    </span>
  );
}