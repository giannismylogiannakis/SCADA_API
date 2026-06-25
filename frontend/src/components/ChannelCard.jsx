import CategoryBadge from "./CategoryBadge";
import OperationalBadge from "./OperationalBadge";
import StatusBadge from "./StatusBadge";
import { formatDateTime, formatValue } from "../utils/formatUtils";

function getChannelTitle(channel) {
  return channel.display_name || channel.name || "Χωρίς όνομα καναλιού";
}

function getReadingTime(channel) {
  return channel.last_update || channel.fetched_at;
}

function formatValueWithUnit(channel) {
  const value = formatValue(channel.current_value);
  const unit = channel.unit ? ` ${channel.unit}` : "";

  return `${value}${unit}`;
}

function formatStatValue(value, unit = "") {
  const formattedValue = formatValue(value);

  if (formattedValue === "—") {
    return "—";
  }

  return unit ? `${formattedValue} ${unit}` : formattedValue;
}

function formatPercent(value) {
  const formattedValue = formatValue(value);

  if (formattedValue === "—") {
    return "—";
  }

  return `${formattedValue}%`;
}

function buildStatsForCard(channel) {
  const stats = channel.statistics;

  if (!stats || !stats.has_history) {
    return [];
  }

  const unit = channel.unit || "";

  if (channel.category === "flow") {
    return [
      {
        label: "Μ.Ο. 1 ώρας",
        value: formatStatValue(stats.avg_1h, unit),
      },
      {
        label: "Μ.Ο. 24ώρου",
        value: formatStatValue(stats.avg_24h, unit),
      },
      {
        label: "Μ.Ο. 7 ημερών",
        value: formatStatValue(stats.avg_7d, unit),
      },
      {
        label: "Απόκλιση 1ώρου",
        value: formatPercent(stats.deviation_percent_from_avg_1h),
      },
    ];
  }

  if (channel.category === "cumulative_flow") {
    return [
      {
        label: "Διαφορά 1ώρου",
        value: formatStatValue(stats.delta_1h, unit),
      },
      {
        label: "Διαφορά 24ώρου",
        value: formatStatValue(stats.delta_24h, unit),
      },
      {
        label: "Διαφορά 3ημέρου",
        value: formatStatValue(stats.delta_3d, unit),
      },
    ];
  }

  if (channel.category === "level") {
    return [
      {
        label: "Μ.Ο. 24ώρου",
        value: formatStatValue(stats.avg_24h, unit),
      },
      {
        label: "Ελάχιστο 24ώρου",
        value: formatStatValue(stats.min_24h, unit),
      },
      {
        label: "Μέγιστο 24ώρου",
        value: formatStatValue(stats.max_24h, unit),
      },
      {
        label: "Μεταβολή 1ώρου",
        value: formatStatValue(stats.delta_1h, unit),
      },
    ];
  }

  return [
    {
      label: "Μ.Ο. 1 ώρας",
      value: formatStatValue(stats.avg_1h, unit),
    },
    {
      label: "Μ.Ο. 24ώρου",
      value: formatStatValue(stats.avg_24h, unit),
    },
    {
      label: "Μ.Ο. 7 ημερών",
      value: formatStatValue(stats.avg_7d, unit),
    },
  ];
}

export default function ChannelCard({ channel }) {
  const readingTime = getReadingTime(channel);
  const hasAlert = Boolean(channel.alert_reason);
  const cardStats = buildStatsForCard(channel);

  return (
    <article className={`channel-card channel-card--${channel.operational_status || "unknown"}`}>
      <div className="channel-card__top">
        <div>
          <h3>{getChannelTitle(channel)}</h3>

          {channel.installation && (
            <p className="muted">Εγκατάσταση: {channel.installation}</p>
          )}
        </div>

        
      </div>

      <div className="channel-card__operator-main">
        <div className="channel-card__value-box">
          <span className="channel-card__label">Τρέχουσα τιμή</span>
          <strong className="channel-card__value">
            {formatValueWithUnit(channel)}
          </strong>
        </div>

        {hasAlert && (
          <div className={`channel-card__alert channel-card__alert--${channel.operational_status}`}>
            {channel.alert_reason}
          </div>
        )}

        <div className="channel-card__quick-info">

          {cardStats.length > 0 && (
          <div className="channel-card__stats">
            {cardStats.map((stat) => (
              <div className="channel-card__stat" key={stat.label}>
                <span>{stat.label}</span>
                <strong>{stat.value}</strong>
              </div>
            ))}
          </div>
        )}

          <div>
            <span>Τελευταία ανάγνωση</span>
            <strong>{formatDateTime(readingTime)}</strong>
          </div>
        </div>
      </div>

      
    </article>
  );
}