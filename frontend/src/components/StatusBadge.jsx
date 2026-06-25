import { getStatusLabel, getStatusTone } from "../utils/statusUtils";

export default function StatusBadge({ channel }) {
  const tone = getStatusTone(channel);
  const label = getStatusLabel(channel);

  return <span className={`status-badge status-badge--${tone}`}>{label}</span>;
}