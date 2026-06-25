import { formatDateTime } from "../utils/formatUtils";

export default function SummaryPanel({
  total,
  normal,
  abnormal,
  lastRefresh,
  autoRefresh,
  onAutoRefreshChange,
  onRefresh,
  loading,
}) {
  return (
    <section className="summary-panel">
      <div className="summary-card">
        <span className="summary-card__label">Σύνολο καναλιών</span>
        <strong>{total}</strong>
      </div>

      <div className="summary-card summary-card--normal">
        <span className="summary-card__label">Κανονικά</span>
        <strong>{normal}</strong>
      </div>

      <div className="summary-card summary-card--abnormal">
        <span className="summary-card__label">Μη κανονικά</span>
        <strong>{abnormal}</strong>
      </div>

      <div className="summary-card">
        <span className="summary-card__label">Τελευταία ανανέωση</span>
        <strong>{formatDateTime(lastRefresh)}</strong>
      </div>

      <div className="summary-actions">
        <label className="switch-row">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(event) => onAutoRefreshChange(event.target.checked)}
          />
          <span>Auto-refresh 10″</span>
        </label>

        <button type="button" className="primary-button" onClick={onRefresh} disabled={loading}>
          {loading ? "Φόρτωση..." : "Ανανέωση"}
        </button>
      </div>
    </section>
  );
}