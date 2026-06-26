import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchAlerts } from "../api/alertsApi";
import { fetchCurrentChannels } from "../api/currentApi";
import { fetchOverview } from "../api/overviewApi";
import { fetchStatisticsSummary } from "../api/statisticsApi";
import { formatDateTime, formatValue } from "../utils/formatUtils";

const SEVERITY_PRIORITY = {
  critical: 0,
  warning: 1,
  unknown: 2,
  normal: 3,
};

const CATEGORY_SECTIONS = [
  {
    key: "flow",
    title: "Ροές",
    columns: [
      { key: "channel", label: "Κανάλι", render: renderChannelCell },
      { key: "current", label: "Τρέχουσα τιμή", render: renderCurrentValue },
      { key: "avg_1h", label: "Μ.Ο. 1 ώρας", render: renderStat("avg_1h") },
      { key: "avg_24h", label: "Μ.Ο. 24ώρου", render: renderStat("avg_24h") },
      { key: "avg_7d", label: "Μ.Ο. 7 ημερών", render: renderStat("avg_7d") },
      { key: "deviation", label: "Απόκλιση 1 ώρας", render: renderDeviation1h },
      { key: "reason", label: "Λόγος / Παρατήρηση", render: renderReason },
    ],
  },
  {
    key: "cumulative_flow",
    title: "Υδρόμετρα / Σύνολα Ροής",
    columns: [
      { key: "channel", label: "Κανάλι", render: renderChannelCell },
      { key: "current", label: "Τρέχουσα τιμή", render: renderCurrentValue },
      { key: "delta_1h", label: "Διαφορά 1 ώρας", render: renderDelta("delta_1h") },
      { key: "delta_24h", label: "Διαφορά 24ώρου", render: renderDelta("delta_24h") },
      { key: "delta_3d", label: "Διαφορά 3ημέρου", render: renderDelta("delta_3d") },
      { key: "meter_status", label: "Κατάσταση μετρητή", render: renderMeterStatus },
      { key: "reason", label: "Λόγος / Παρατήρηση", render: renderReason },
    ],
  },
  {
    key: "level",
    title: "Στάθμες",
    columns: [
      { key: "channel", label: "Κανάλι", render: renderChannelCell },
      { key: "current", label: "Τρέχουσα τιμή", render: renderCurrentValue },
      { key: "avg_24h", label: "Μ.Ο. 24ώρου", render: renderStat("avg_24h") },
      { key: "min_24h", label: "Ελάχιστο 24ώρου", render: renderStat("min_24h") },
      { key: "max_24h", label: "Μέγιστο 24ώρου", render: renderStat("max_24h") },
      { key: "delta_1h", label: "Μεταβολή 1 ώρας", render: renderDelta("delta_1h") },
      { key: "reason", label: "Λόγος / Παρατήρηση", render: renderReason },
    ],
  },
  {
    key: "quality",
    title: "Ποιότητα",
    columns: [
      { key: "channel", label: "Κανάλι", render: renderChannelCell },
      { key: "current", label: "Τρέχουσα τιμή", render: renderCurrentValue },
      { key: "avg_24h", label: "Μ.Ο. 24ώρου", render: renderStat("avg_24h") },
      { key: "min_24h", label: "Ελάχιστο", render: renderStat("min_24h") },
      { key: "max_24h", label: "Μέγιστο", render: renderStat("max_24h") },
      { key: "reason", label: "Λόγος / Παρατήρηση", render: renderReason },
    ],
  },
  {
    key: "motor_current",
    title: "Εντάσεις Κινητήρων",
    columns: [
      { key: "channel", label: "Κανάλι", render: renderChannelCell },
      { key: "current", label: "Τρέχουσα τιμή", render: renderCurrentValue },
      { key: "avg_24h", label: "Μ.Ο. 24ώρου", render: renderStat("avg_24h") },
      { key: "min_24h", label: "Ελάχιστο", render: renderStat("min_24h") },
      { key: "max_24h", label: "Μέγιστο", render: renderStat("max_24h") },
      { key: "reason", label: "Λόγος / Παρατήρηση", render: renderReason },
    ],
  },
  {
    key: "pressure",
    title: "Πίεση",
    columns: [
      { key: "channel", label: "Κανάλι", render: renderChannelCell },
      { key: "current", label: "Τρέχουσα τιμή", render: renderCurrentValue },
      { key: "avg_24h", label: "Μ.Ο. 24ώρου", render: renderStat("avg_24h") },
      { key: "min_24h", label: "Ελάχιστο", render: renderStat("min_24h") },
      { key: "max_24h", label: "Μέγιστο", render: renderStat("max_24h") },
      { key: "reason", label: "Λόγος / Παρατήρηση", render: renderReason },
    ],
  },
  {
    key: "unknown",
    title: "Άγνωστα",
    columns: [
      { key: "channel", label: "Κανάλι", render: renderChannelCell },
      { key: "current", label: "Τρέχουσα τιμή", render: renderCurrentValue },
      { key: "category", label: "Κατηγορία", render: (row) => row.category_label || row.category || "—" },
      { key: "reason", label: "Λόγος / Παρατήρηση", render: renderReason },
    ],
  },
];

const CATEGORY_FILTER_OPTIONS = [
  { value: "all", label: "Όλες οι κατηγορίες" },
  { value: "flow", label: "Ροές" },
  { value: "cumulative_flow", label: "Υδρόμετρα / Σύνολα Ροής" },
  { value: "level", label: "Στάθμες" },
  { value: "quality", label: "Ποιότητα" },
  { value: "motor_current", label: "Εντάσεις Κινητήρων" },
  { value: "pressure", label: "Πίεση" },
  { value: "unknown", label: "Άγνωστα" },
];

const DEFAULT_OPEN_SECTIONS = CATEGORY_SECTIONS.reduce((result, section) => {
  result[section.key] = true;
  return result;
}, {});

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .trim();
}

function matchesSearch(row, searchTerm) {
  const term = normalizeText(searchTerm);

  if (!term) {
    return true;
  }

  const searchableText = [
    row.display_name,
    row.name,
    row.category_label,
    row.installation,
    row.tag_code,
    row.device_name,
    row.comm_line_name,
    row.cnl_num,
    row.reason,
  ]
    .map(normalizeText)
    .join(" ");

  return searchableText.includes(term);
}

function matchesCategory(row, selectedCategory) {
  if (selectedCategory === "all") {
    return true;
  }

  return (row.category || "unknown") === selectedCategory;
}

function buildFallbackOverview(channels, alerts) {
  const countByStatus = (status) =>
    channels.filter((channel) => channel.operational_status === status).length;

  return {
    total_channels: channels.length,
    normal_count: countByStatus("normal"),
    warning_count: countByStatus("warning"),
    critical_count: countByStatus("critical"),
    unknown_count: countByStatus("unknown"),
    invalid_count: channels.filter(
      (channel) => channel.alert_rule_type === "invalid_value"
    ).length,
    scada_abnormal_count: channels.filter(
      (channel) => Number(channel.scada_status) !== 1
    ).length,
    alerts_count: alerts.length,
  };
}

function buildAlertsByCnlNum(alerts) {
  const result = {};

  for (const alert of alerts) {
    const key = String(alert.cnl_num);
    const current = result[key];

    if (!current) {
      result[key] = alert;
      continue;
    }

    const currentPriority = SEVERITY_PRIORITY[current.severity] ?? 99;
    const nextPriority = SEVERITY_PRIORITY[alert.severity] ?? 99;

    if (nextPriority < currentPriority) {
      result[key] = alert;
    }
  }

  return result;
}

function getRowSeverity(row) {
  return row.alert?.severity || row.operational_status || "normal";
}

function sortOperationalRows(a, b) {
  const severityA = SEVERITY_PRIORITY[getRowSeverity(a)] ?? 99;
  const severityB = SEVERITY_PRIORITY[getRowSeverity(b)] ?? 99;

  if (severityA !== severityB) {
    return severityA - severityB;
  }

  return String(a.display_name || a.name || "").localeCompare(
    String(b.display_name || b.name || ""),
    "el"
  );
}

function groupRowsByCategory(rows) {
  const grouped = {};

  for (const section of CATEGORY_SECTIONS) {
    grouped[section.key] = [];
  }

  for (const row of rows) {
    const category = row.category || "unknown";
    const key = grouped[category] ? category : "unknown";
    grouped[key].push(row);
  }

  for (const key of Object.keys(grouped)) {
    grouped[key] = grouped[key].sort(sortOperationalRows);
  }

  return grouped;
}

function formatDeltaValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return String(value);
  }

  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${formatValue(numericValue)}`;
}

function formatPercent(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return String(value);
  }

  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${numericValue.toFixed(1)}%`;
}

function getMeterStatus(row) {
  const stats = row.statistics;

  if (!stats?.has_history) {
    return "Χωρίς ιστορικό";
  }

  const delta24h = Number(stats.delta_24h);

  if (Number.isFinite(delta24h) && delta24h < 0) {
    return "Πιθανό reset / πτώση";
  }

  if (Number.isFinite(delta24h) && Math.abs(delta24h) <= 0.000001) {
    return "Δεν μεταβλήθηκε";
  }

  if (Number.isFinite(delta24h)) {
    return "Μεταβάλλεται";
  }

  return "Ανεπαρκή δεδομένα";
}

function renderChannelCell(row) {
  return (
    <div className="operational-channel">
      <span className={`severity-dot severity-dot--${getRowSeverity(row)}`} />
      <div>
        <strong>{row.display_name || row.name || "—"}</strong>
        {row.installation ? <small>{row.installation}</small> : null}
      </div>
    </div>
  );
}

function renderCurrentValue(row) {
  return (
    <span className="value-with-unit numeric-cell">
      <strong>{formatValue(row.current_value)}</strong>
      {row.unit ? <span>{row.unit}</span> : null}
    </span>
  );
}

function renderReason(row) {
  if (row.alert?.reason) {
    return row.alert.reason;
  }

  if (getRowSeverity(row) !== "normal") {
    return row.operational_status_label || "Υπάρχει μη κανονική κατάσταση.";
  }

  return "—";
}

function renderMeterStatus(row) {
  return getMeterStatus(row);
}

function renderStat(key) {
  return (row) => {
    return <span className="numeric-cell">{formatValue(row.statistics?.[key])}</span>;
  };
}

function renderDelta(key) {
  return (row) => {
    return <span className="numeric-cell">{formatDeltaValue(row.statistics?.[key])}</span>;
  };
}

function renderDeviation1h(row) {
  const stats = row.statistics;

  if (!stats) {
    return "—";
  }

  const percent = stats.deviation_percent_from_avg_1h;
  const raw = stats.deviation_from_avg_1h;

  if (percent === null || percent === undefined) {
    return formatDeltaValue(raw);
  }

  return `${formatPercent(percent)} (${formatDeltaValue(raw)})`;
}

function SummaryStrip({ overview, lastRefresh, autoRefresh, onAutoRefreshChange, onRefresh, loading }) {
  const refreshTime = overview?.last_refresh || overview?.fetched_at || lastRefresh;

  const items = [
    { label: "Σύνολο", value: overview?.total_channels ?? 0 },
    { label: "Κανονικά", value: overview?.normal_count ?? 0, status: "normal" },
    { label: "Προειδ.", value: overview?.warning_count ?? 0, status: "warning" },
    { label: "Κρίσιμα", value: overview?.critical_count ?? 0, status: "critical" },
    { label: "Μη έγκυρες", value: overview?.invalid_count ?? 0, status: "invalid" },
    { label: "SCADA μη OK", value: overview?.scada_abnormal_count ?? 0, status: "unknown" },
    { label: "Alerts", value: overview?.alerts_count ?? 0, status: "alerts" },
    { label: "Refresh", value: formatDateTime(refreshTime), status: "time" },
  ];

  return (
    <section className="summary-strip">
      <div className="summary-strip__items">
        {items.map((item) => (
          <div key={item.label} className={`summary-strip__item summary-strip__item--${item.status || "default"}`}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>

      <div className="summary-strip__actions">
        <label className="compact-switch">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(event) => onAutoRefreshChange(event.target.checked)}
          />
          Auto 30″
        </label>

        <button type="button" className="scada-button" onClick={onRefresh} disabled={loading}>
          {loading ? "Φόρτωση..." : "Ανανέωση"}
        </button>
      </div>
    </section>
  );
}

function AlertsTopTable({ alerts }) {
  if (!alerts.length) {
    return (
      <section className="scada-panel">
        <div className="scada-panel__header">
          <h3>Ενεργές Προειδοποιήσεις</h3>
        </div>

        <div className="empty-operational-state">
          Δεν υπάρχουν ενεργές προειδοποιήσεις.
        </div>
      </section>
    );
  }

  return (
    <section className="scada-panel">
      <div className="scada-panel__header">
        <h3>Ενεργές Προειδοποιήσεις</h3>
        <span>{alerts.length} ενεργά</span>
      </div>

      <div className="operational-table-wrap">
        <table className="operational-table operational-table--alerts">
          <thead>
            <tr>
              <th>Κανάλι</th>
              <th>Κατηγορία</th>
              <th>Τρέχουσα τιμή</th>
              <th>Λόγος</th>
              <th>Τελευταία ανάγνωση / refresh</th>
            </tr>
          </thead>

          <tbody>
            {alerts.map((alert) => (
              <tr
                key={alert.alert_id}
                className={`operational-table__row operational-table__row--${alert.severity}`}
              >
                <td>
                  <div className="operational-channel">
                    <span className={`severity-dot severity-dot--${alert.severity}`} />
                    <div>
                      <strong>{alert.display_name || alert.channel_name || "—"}</strong>
                    </div>
                  </div>
                </td>

                <td>{alert.category_label || alert.category || "—"}</td>

                <td className="numeric-cell">
                  <span className="value-with-unit">
                    <strong>{formatValue(alert.current_value)}</strong>
                    {alert.unit ? <span>{alert.unit}</span> : null}
                  </span>
                </td>

                <td>{alert.reason || "—"}</td>

                <td>{formatDateTime(alert.last_update || alert.fetched_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CategoryFilterBar({ selectedCategory, onChange, visibleCount, totalCount }) {
  return (
    <section className="category-filter-bar">
      <div>
        <strong>Προβολή κατηγορίας</strong>
        <span>
          Εμφανίζονται {visibleCount} από {totalCount} κανάλια.
        </span>
      </div>

      <select
        value={selectedCategory}
        onChange={(event) => onChange(event.target.value)}
      >
        {CATEGORY_FILTER_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </section>
  );
}

function CategoryDataTable({ section, rows, isOpen, onToggle }) {
  if (!rows.length) {
    return null;
  }

  const criticalCount = rows.filter((row) => getRowSeverity(row) === "critical").length;
  const warningCount = rows.filter((row) => getRowSeverity(row) === "warning").length;

  return (
    <section className="scada-panel">
      <button type="button" className="scada-panel__header scada-panel__header--button" onClick={onToggle}>
        <div>
          <h3>{section.title}</h3>
          <span>
            {rows.length} κανάλια
            {criticalCount ? ` · ${criticalCount} κρίσιμα` : ""}
            {warningCount ? ` · ${warningCount} προειδοποιήσεις` : ""}
          </span>
        </div>

        <strong>{isOpen ? "−" : "+"}</strong>
      </button>

      {isOpen && (
        <div className="operational-table-wrap">
          <table className="operational-table">
            <thead>
              <tr>
                {section.columns.map((column) => (
                  <th key={column.key}>{column.label}</th>
                ))}
              </tr>
            </thead>

            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.cnl_num}
                  className={`operational-table__row operational-table__row--${getRowSeverity(row)}`}
                >
                  {section.columns.map((column) => (
                    <td key={column.key}>{column.render(row)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function OperationalTablesPage() {
  const [channels, setChannels] = useState([]);
  const [overview, setOverview] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [statisticsByCnlNum, setStatisticsByCnlNum] = useState({});
  const [lastRefresh, setLastRefresh] = useState(null);

  const [loading, setLoading] = useState(true);
  const [statisticsLoading, setStatisticsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statisticsErrorMessage, setStatisticsErrorMessage] = useState("");

  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [openSections, setOpenSections] = useState(DEFAULT_OPEN_SECTIONS);

  

  const loadData = useCallback(async ({ silent = false, includeStatistics = true } = {}) => {
    if (!silent) {
      setLoading(true);
    }

    setErrorMessage("");

    if (includeStatistics) {
      setStatisticsLoading(true);
      setStatisticsErrorMessage("");
    }

    try {
      const [currentChannels, overviewPayload, alertsPayload] = await Promise.all([
        fetchCurrentChannels(),
        fetchOverview(),
        fetchAlerts(),
      ]);

      const activeAlerts = Array.isArray(alertsPayload?.alerts) ? alertsPayload.alerts : [];

      setChannels(currentChannels);
      setOverview(overviewPayload);
      setAlerts(activeAlerts);

      setLastRefresh(
        overviewPayload?.last_refresh ||
          overviewPayload?.fetched_at ||
          alertsPayload?.fetched_at ||
          currentChannels?.[0]?.fetched_at ||
          new Date().toISOString()
      );

      if (includeStatistics) {
        try {
          const cnlNums = currentChannels
            .map((channel) => channel.cnl_num)
            .filter((cnlNum) => cnlNum !== null && cnlNum !== undefined);

          const statisticsItems = await fetchStatisticsSummary({ cnlNums });

          const nextStatisticsByCnlNum = {};

          for (const item of statisticsItems) {
            nextStatisticsByCnlNum[String(item.cnl_num)] = item;
          }

          setStatisticsByCnlNum(nextStatisticsByCnlNum);
        } catch (statisticsError) {
          setStatisticsErrorMessage(
            statisticsError.message ||
              "Αποτυχία φόρτωσης ιστορικών στατιστικών."
          );
        } finally {
          setStatisticsLoading(false);
        }
      }
    } catch (error) {
      setErrorMessage(
        error.message ||
          "Αποτυχία σύνδεσης με το backend. Έλεγξε ότι τρέχει το FastAPI."
      );
    } finally {
      if (!silent) {
        setLoading(false);
      }

      if (includeStatistics) {
        setStatisticsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!autoRefresh) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      loadData({ silent: true, includeStatistics: false });
    }, 30000);

    return () => window.clearInterval(intervalId);
  }, [autoRefresh, loadData]);

  const summary = useMemo(() => {
    return overview || buildFallbackOverview(channels, alerts);
  }, [overview, channels, alerts]);

  const alertsByCnlNum = useMemo(() => {
    return buildAlertsByCnlNum(alerts);
  }, [alerts]);

  const rows = useMemo(() => {
  return channels
    .map((channel) => ({
      ...channel,
      statistics: statisticsByCnlNum[String(channel.cnl_num)] || null,
      alert: alertsByCnlNum[String(channel.cnl_num)] || null,
    }))
    .filter((row) => matchesSearch(row, searchTerm))
    .filter((row) => matchesCategory(row, selectedCategory));
    }, [channels, statisticsByCnlNum, alertsByCnlNum, searchTerm, selectedCategory]);

  const rowsByCategory = useMemo(() => {
    return groupRowsByCategory(rows);
  }, [rows]);

  const visibleSections = useMemo(() => {
  if (selectedCategory === "all") {
    return CATEGORY_SECTIONS;
  }

  return CATEGORY_SECTIONS.filter((section) => section.key === selectedCategory);
    }, [selectedCategory]);

  const visibleRowsCount = rows.length;

  function toggleSection(sectionKey) {
    setOpenSections((current) => ({
      ...current,
      [sectionKey]: !current[sectionKey],
    }));
  }

  return (
    <section id="overview" className="page page--scada">
      <div className="scada-page-title">
        <div>
          <h2>Γενική Ανασκόπηση</h2>
          <p>SCADA-style operational view · read-only</p>
        </div>

        <div className="scada-toolbar">
          <label htmlFor="scada-search">Αναζήτηση</label>
          <input
            id="scada-search"
            type="search"
            value={searchTerm}
            placeholder="Κανάλι, εγκατάσταση, tag..."
            onChange={(event) => setSearchTerm(event.target.value)}
          />
        </div>
      </div>

      <SummaryStrip
        overview={summary}
        lastRefresh={lastRefresh}
        autoRefresh={autoRefresh}
        onAutoRefreshChange={setAutoRefresh}
        onRefresh={() => loadData()}
        loading={loading}
      />

      {loading && (
        <div className="state-box state-box--loading">
          Φόρτωση live δεδομένων από το backend...
        </div>
      )}

      {errorMessage && (
        <div className="state-box state-box--error">
          <strong>Σφάλμα σύνδεσης</strong>
          <span>{errorMessage}</span>
        </div>
      )}

      {statisticsLoading && !loading && (
        <div className="state-box state-box--loading">
          Φόρτωση ιστορικών στατιστικών...
        </div>
      )}

      {statisticsErrorMessage && (
        <div className="state-box state-box--error">
          <strong>Σφάλμα ιστορικών στατιστικών</strong>
          <span>{statisticsErrorMessage}</span>
        </div>
      )}

      {!loading && !errorMessage && (
        <>
          <AlertsTopTable alerts={alerts} />

            <CategoryFilterBar
            selectedCategory={selectedCategory}
            onChange={setSelectedCategory}
            visibleCount={visibleRowsCount}
            totalCount={channels.length}
            />

            {visibleSections.map((section) => (
            <CategoryDataTable
              key={section.key}
              section={section}
              rows={rowsByCategory[section.key] || []}
              isOpen={openSections[section.key]}
              onToggle={() => toggleSection(section.key)}
            />
          ))}
   

          {visibleRowsCount === 0 && (
            <div className="empty-operational-state">
              Δεν βρέθηκαν κανάλια με τα τρέχοντα φίλτρα.
            </div>
          )}
        </>
      )}
    </section>
  );
}