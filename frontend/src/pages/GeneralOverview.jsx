import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCurrentChannels } from "../api/currentApi";
import { fetchOverview } from "../api/overviewApi";
import { fetchStatisticsSummary } from "../api/statisticsApi";
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
  const [statisticsByCnlNum, setStatisticsByCnlNum] = useState({});
  const [statisticsLoading, setStatisticsLoading] = useState(false);
  const [statisticsErrorMessage, setStatisticsErrorMessage] = useState("");
  const [statisticsLoadedAt, setStatisticsLoadedAt] = useState(null);

  const loadChannels = useCallback(async ({ silent = false, includeStatistics = true } = {}) => {
  if (!silent) {
    setLoading(true);
  }

  setErrorMessage("");

  if (includeStatistics) {
    setStatisticsLoading(true);
    setStatisticsErrorMessage("");
  }

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
        setStatisticsLoadedAt(new Date().toISOString());
        setStatisticsErrorMessage("");
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
    loadChannels();
  }, [loadChannels]);

  useEffect(() => {
    if (!autoRefresh) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      loadChannels({ silent: true, includeStatistics: false });
    }, 30000);

    return () => window.clearInterval(intervalId);
  }, [autoRefresh, loadChannels]);

  const summary = useMemo(() => {
    return overview || buildFallbackOverview(channels);
  }, [overview, channels]);

  const channelsWithStatistics = useMemo(() => {
  return channels.map((channel) => ({
    ...channel,
    statistics: statisticsByCnlNum[String(channel.cnl_num)] || null,
  }));
  }, [channels, statisticsByCnlNum]);

  const visibleChannels = useMemo(() => {
  return channelsWithStatistics.filter(
    (channel) =>
      matchesSearch(channel, searchTerm) &&
      matchesStatusFilter(channel, statusFilter) &&
      matchesCategoryFilter(channel, categoryFilter)
  );
  }, [channelsWithStatistics, searchTerm, statusFilter, categoryFilter]);

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
          <div className="results-meta">
            Εμφανίζονται {visibleChannels.length} από {channels.length} κανάλια.
            {statisticsLoadedAt && " Τα ιστορικά στατιστικά φορτώθηκαν επιτυχώς."}
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