import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCurrentChannels } from "../api/currentApi";
import { fetchOverview } from "../api/overviewApi";
import ChannelCard from "../components/ChannelCard";
import SearchBar from "../components/SearchBar";
import SummaryPanel from "../components/SummaryPanel";

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .trim();
}

function matchesSearch(channel, searchTerm) {
  const term = normalizeText(searchTerm);

  if (!term) {
    return true;
  }

  const searchableText = [
    channel.display_name,
    channel.name,
    channel.category_label,
    channel.installation,
    channel.tag_code,
    channel.device_name,
    channel.comm_line_name,
    channel.cnl_num,
  ]
    .map(normalizeText)
    .join(" ");

  return searchableText.includes(term);
}

function matchesStatusFilter(channel, statusFilter) {
  if (statusFilter === "all") {
    return true;
  }

  return channel.operational_status === statusFilter;
}

function matchesCategoryFilter(channel, categoryFilter) {
  if (categoryFilter === "all") {
    return true;
  }

  return channel.category === categoryFilter;
}

function buildFallbackOverview(channels) {
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
    scada_normal_count: channels.filter(
      (channel) => Number(channel.scada_status) === 1
    ).length,
    scada_abnormal_count: channels.filter(
      (channel) => Number(channel.scada_status) !== 1
    ).length,
    alerts_count: channels.filter(
      (channel) => channel.operational_status !== "normal"
    ).length,
  };
}

export default function GeneralOverview() {
  const [channels, setChannels] = useState([]);
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [lastRefresh, setLastRefresh] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadChannels = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setLoading(true);
    }

    setErrorMessage("");

    try {
      const [currentChannels, overviewPayload] = await Promise.all([
        fetchCurrentChannels(),
        fetchOverview(),
      ]);

      setChannels(currentChannels);
      setOverview(overviewPayload);

      setLastRefresh(
        overviewPayload?.last_refresh ||
          overviewPayload?.fetched_at ||
          currentChannels?.[0]?.fetched_at ||
          new Date().toISOString()
      );
    } catch (error) {
      setErrorMessage(
        error.message ||
          "Αποτυχία σύνδεσης με το backend. Έλεγξε ότι τρέχει το FastAPI."
      );
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadChannels();
  }, [loadChannels]);

  useEffect(() => {
    if (!autoRefresh) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      loadChannels({ silent: true });
    }, 10000);

    return () => window.clearInterval(intervalId);
  }, [autoRefresh, loadChannels]);

  const summary = useMemo(() => {
    return overview || buildFallbackOverview(channels);
  }, [overview, channels]);

  const visibleChannels = useMemo(() => {
    return channels.filter(
      (channel) =>
        matchesSearch(channel, searchTerm) &&
        matchesStatusFilter(channel, statusFilter) &&
        matchesCategoryFilter(channel, categoryFilter)
    );
  }, [channels, searchTerm, statusFilter, categoryFilter]);

  return (
    <section id="overview" className="page">
      <div className="page-title">
        <div>
          <p className="eyebrow">Γενική Ανασκόπηση</p>
          <h2>Current / live data καναλιών</h2>
        </div>

        <p className="page-title__description">
          Προβολή ενεργών καναλιών με επιχειρησιακή αξιολόγηση, metadata από BaseXML και live τιμές από Rapid SCADA API.
        </p>
      </div>

      <SummaryPanel
        overview={summary}
        lastRefresh={lastRefresh}
        autoRefresh={autoRefresh}
        onAutoRefreshChange={setAutoRefresh}
        onRefresh={() => loadChannels()}
        loading={loading}
      />

      <SearchBar
        searchTerm={searchTerm}
        onSearchTermChange={setSearchTerm}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        categoryFilter={categoryFilter}
        onCategoryFilterChange={setCategoryFilter}
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

      {!loading && !errorMessage && (
        <>
          <div className="results-meta">
            Εμφανίζονται {visibleChannels.length} από {channels.length} κανάλια.
          </div>

          <div className="channel-grid">
            {visibleChannels.map((channel) => (
              <ChannelCard key={channel.cnl_num} channel={channel} />
            ))}
          </div>

          {visibleChannels.length === 0 && (
            <div className="state-box">
              Δεν βρέθηκαν κανάλια με τα τρέχοντα φίλτρα.
            </div>
          )}
        </>
      )}
    </section>
  );
}