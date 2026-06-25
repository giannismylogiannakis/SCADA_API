import { formatDateTime } from "../utils/formatUtils";

export default function SummaryPanel({
  overview,
  lastRefresh,
  autoRefresh,
  onAutoRefreshChange,
  onRefresh,
  loading,
}) {
  const refreshTime = overview?.last_refresh || overview?.fetched_at || lastRefresh;

  return (
    <section className="summary-panel">
      <div className="summary-card">
        <span className="summary-card__label">Σύνολο καναλιών</span>
        <strong>{overview?.total_channels ?? 0}</strong>
      </div>

      <div className="summary-card summary-card--normal">
        <span className="summary-card__label">Κανονικά</span>
        <strong>{overview?.normal_count ?? 0}</strong>
      </div>

      <div className="summary-card summary-card--warning">
        <span className="summary-card__label">Προειδοποιήσεις</span>
        <strong>{overview?.warning_count ?? 0}</strong>
      </div>

      <div className="summary-card summary-card--critical">
        <span className="summary-card__label">Κρίσιμα</span>
        <strong>{overview?.critical_count ?? 0}</strong>
      </div>

      <div className="summary-card summary-card--invalid">
        <span className="summary-card__label">Μη έγκυρες τιμές</span>
        <strong>{overview?.invalid_count ?? 0}</strong>
      </div>

      <div className="summary-card summary-card--scada">
        <span className="summary-card__label">SCADA μη κανονικά</span>
        <strong>{overview?.scada_abnormal_count ?? 0}</strong>
      </div>

      <div className="summary-card summary-card--alerts">
        <span className="summary-card__label">Ενεργά alerts</span>
        <strong>{overview?.alerts_count ?? 0}</strong>
      </div>

      <div className="summary-card">
        <span className="summary-card__label">Τελευταίο refresh</span>
        <strong>{formatDateTime(refreshTime)}</strong>
      </div>

      <div className="summary-actions">
        <label className="switch-row">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(event) => onAutoRefreshChange(event.target.checked)}
          />
          <span>Auto-refresh 30″</span>
        </label>

        <button
          type="button"
          className="primary-button"
          onClick={onRefresh}
          disabled={loading}
        >
          {loading ? "Φόρτωση..." : "Ανανέωση"}
        </button>
      </div>
    </section>
  );
}