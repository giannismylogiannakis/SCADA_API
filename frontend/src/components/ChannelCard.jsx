import CategoryBadge from "./CategoryBadge";
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

export default function ChannelCard({ channel }) {
  const readingTime = getReadingTime(channel);

  return (
    <article className="channel-card">
      <div className="channel-card__top">
        <div>
          <h3>{getChannelTitle(channel)}</h3>

          {channel.installation && (
            <p className="muted">Εγκατάσταση: {channel.installation}</p>
          )}
        </div>

        <div className="channel-card__badges">
          <CategoryBadge channel={channel} />
          <StatusBadge channel={channel} />
        </div>
      </div>

      <div className="channel-card__operator-main">
        <div className="channel-card__value-box">
          <span className="channel-card__label">Τρέχουσα τιμή</span>
          <strong className="channel-card__value">
            {formatValueWithUnit(channel)}
          </strong>
        </div>

        <div className="channel-card__quick-info">
          <div>
            <span>SCADA status</span>
            <strong>{channel.scada_status_text || channel.scada_status || "—"}</strong>
          </div>

          <div>
            <span>Τελευταία ανάγνωση</span>
            <strong>{formatDateTime(readingTime)}</strong>
          </div>
        </div>
      </div>

      <details className="channel-card__technical">
        <summary>Τεχνικές λεπτομέρειες</summary>

        <dl className="channel-card__technical-grid">
          <div>
            <dt>Channel number</dt>
            <dd>{channel.cnl_num ?? "—"}</dd>
          </div>

          <div>
            <dt>Device name</dt>
            <dd>{channel.device_name || "—"}</dd>
          </div>

          <div>
            <dt>Communication line</dt>
            <dd>{channel.comm_line_name || "—"}</dd>
          </div>

          <div>
            <dt>Tag code</dt>
            <dd>{channel.tag_code || "—"}</dd>
          </div>

          <div>
            <dt>scada_status</dt>
            <dd>{channel.scada_status ?? "—"}</dd>
          </div>

          <div>
            <dt>scada_status_text</dt>
            <dd>{channel.scada_status_text || "—"}</dd>
          </div>

          <div>
            <dt>scada_status_description</dt>
            <dd>{channel.scada_status_description || "—"}</dd>
          </div>

          <div>
            <dt>cnl_type_id</dt>
            <dd>{channel.cnl_type_id ?? "—"}</dd>
          </div>

          <div>
            <dt>format_id</dt>
            <dd>{channel.format_id ?? "—"}</dd>
          </div>

          <div>
            <dt>unit_id</dt>
            <dd>{channel.unit_id ?? "—"}</dd>
          </div>
        </dl>
      </details>
    </article>
  );
}