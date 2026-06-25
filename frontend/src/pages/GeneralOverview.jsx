import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCurrentChannels } from "../api/currentApi";
import ChannelCard from "../components/ChannelCard";
import SearchBar from "../components/SearchBar";
import SummaryPanel from "../components/SummaryPanel";
import { isNormalScadaStatus } from "../utils/statusUtils";

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
    channel.name,
    channel.tag_code,
    channel.device_name,
    channel.cnl_num,
  ]
    .map(normalizeText)
    .join(" ");

  return searchableText.includes(term);
}

function matchesStatusFilter(channel, statusFilter) {
  if (statusFilter === "normal") {
    return isNormalScadaStatus(channel);
  }

  if (statusFilter === "abnormal") {
    return !isNormalScadaStatus(channel);
  }

  return true;
}

export default function GeneralOverview() {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [lastRefresh, setLastRefresh] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadChannels = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setLoading(true);
    }

    setErrorMessage("");

    try {
      const currentChannels = await fetchCurrentChannels();
      setChannels(currentChannels);
      setLastRefresh(new Date());
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
    const normal = channels.filter(isNormalScadaStatus).length;

    return {
      total: channels.length,
      normal,
      abnormal: channels.length - normal,
    };
  }, [channels]);

  const visibleChannels = useMemo(() => {
    return channels.filter(
      (channel) =>
        matchesSearch(channel, searchTerm) &&
        matchesStatusFilter(channel, statusFilter)
    );
  }, [channels, searchTerm, statusFilter]);

  return (
    <section id="overview" className="page">
      <div className="page-title">
        <div>
          <p className="eyebrow">Γενική Ανασκόπηση</p>
          <h2>Current / live data καναλιών</h2>
        </div>

        <p className="page-title__description">
          Προβολή ενεργών καναλιών με metadata από BaseXML και live τιμές από Rapid SCADA API.
        </p>
      </div>

      <SummaryPanel
        total={summary.total}
        normal={summary.normal}
        abnormal={summary.abnormal}
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