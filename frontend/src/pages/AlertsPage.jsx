import { useCallback, useEffect, useState } from "react";
import { fetchAlerts } from "../api/alertsApi";
import OperationalBadge from "../components/OperationalBadge";
import { formatDateTime, formatValue } from "../utils/formatUtils";

const CATEGORY_OPTIONS = [
  { value: "all", label: "Όλες οι κατηγορίες" },
  { value: "flow", label: "Ροές" },
  { value: "cumulative_flow", label: "Υδρόμετρα / Σύνολα Ροής" },
  { value: "level", label: "Στάθμες" },
  { value: "quality", label: "Ποιότητα" },
  { value: "motor_current", label: "Αντλίες / Εντάσεις" },
  { value: "pressure", label: "Πίεση" },
  { value: "unknown", label: "Άγνωστα" },
];

const SEVERITY_OPTIONS = [
  { value: "all", label: "Όλες οι σοβαρότητες" },
  { value: "critical", label: "Κρίσιμα" },
  { value: "warning", label: "Προειδοποιήσεις" },
  { value: "unknown", label: "Άγνωστα" },
];

function formatValueWithUnit(alert) {
  const value = formatValue(alert.current_value);
  const unit = alert.unit ? ` ${alert.unit}` : "";

  return `${value}${unit}`;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [lastRefresh, setLastRefresh] = useState(null);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    setErrorMessage("");

    try {
      const payload = await fetchAlerts({
        category: categoryFilter,
        severity: severityFilter,
      });

      setAlerts(payload.alerts || []);
      setLastRefresh(payload.fetched_at || new Date().toISOString());
    } catch (error) {
      setErrorMessage(
        error.message ||
          "Αποτυχία φόρτωσης προειδοποιήσεων από το backend."
      );
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, severityFilter]);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  return (
    <section id="alerts" className="page">
      <div className="page-title">
        <div>
          <p className="eyebrow">Προειδοποιήσεις</p>
          <h2>Ενεργές επιχειρησιακές προειδοποιήσεις</h2>
        </div>

        <p className="page-title__description">
          Λίστα ενεργών alerts από το rules engine. Τα κρίσιμα εμφανίζονται πρώτα.
        </p>
      </div>

      <section className="alerts-toolbar">
        <div className="field">
          <label htmlFor="alerts-severity-filter">Σοβαρότητα</label>
          <select
            id="alerts-severity-filter"
            value={severityFilter}
            onChange={(event) => setSeverityFilter(event.target.value)}
          >
            {SEVERITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="alerts-category-filter">Κατηγορία</label>
          <select
            id="alerts-category-filter"
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
          >
            {CATEGORY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="alerts-toolbar__meta">
          <span>Τελευταία ανάγνωση</span>
          <strong>{formatDateTime(lastRefresh)}</strong>
        </div>

        <button
          type="button"
          className="primary-button"
          onClick={loadAlerts}
          disabled={loading}
        >
          {loading ? "Φόρτωση..." : "Ανανέωση"}
        </button>
      </section>

      {loading && (
        <div className="state-box state-box--loading">
          Φόρτωση προειδοποιήσεων...
        </div>
      )}

      {errorMessage && (
        <div className="state-box state-box--error">
          <strong>Σφάλμα σύνδεσης</strong>
          <span>{errorMessage}</span>
        </div>
      )}

      {!loading && !errorMessage && alerts.length === 0 && (
        <div className="state-box">
          Δεν υπάρχουν ενεργές προειδοποιήσεις για τα τρέχοντα φίλτρα.
        </div>
      )}

      {!loading && !errorMessage && alerts.length > 0 && (
        <>
          <div className="results-meta">
            Εμφανίζονται {alerts.length} ενεργές προειδοποιήσεις.
          </div>

          <div className="alerts-table-wrap">
            <table className="alerts-table">
              <thead>
                <tr>
                  <th>Σοβαρότητα</th>
                  <th>Κανάλι</th>
                  <th>Κατηγορία</th>
                  <th>Τρέχουσα τιμή</th>
                  <th>Λόγος</th>
                  <th>Τελευταία ανάγνωση</th>
                </tr>
              </thead>

              <tbody>
                {alerts.map((alert) => (
                  <tr
                    key={alert.alert_id}
                    className={`alerts-table__row alerts-table__row--${alert.severity}`}
                  >
                    <td>
                      <OperationalBadge severity={alert.severity} />
                    </td>

                    <td>
                      <strong>{alert.display_name || alert.channel_name || "—"}</strong>
                      <span className="alerts-table__subtext">
                        Cnl #{alert.cnl_num}
                      </span>
                    </td>

                    <td>{alert.category_label || alert.category || "—"}</td>

                    <td>
                      <strong>{formatValueWithUnit(alert)}</strong>
                    </td>

                    <td>{alert.reason || "—"}</td>

                    <td>{formatDateTime(alert.last_update || alert.fetched_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}