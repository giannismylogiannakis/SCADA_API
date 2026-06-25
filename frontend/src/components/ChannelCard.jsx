import StatusBadge from "./StatusBadge";
import { formatDateTime, formatValue } from "../utils/formatUtils";

export default function ChannelCard({ channel }) {
  return (
    <article className="channel-card">
      <div className="channel-card__top">
        <div>
          <h3>{channel.name || "Χωρίς όνομα καναλιού"}</h3>
          <p className="muted">Channel #{channel.cnl_num}</p>
        </div>

        <StatusBadge channel={channel} />
      </div>

      <dl className="channel-card__details">
        <div>
          <dt>Τρέχουσα τιμή</dt>
          <dd className="channel-card__value">{formatValue(channel.current_value)}</dd>
        </div>

        <div>
          <dt>SCADA status</dt>
          <dd>{channel.scada_status ?? "—"}</dd>
        </div>

        <div>
          <dt>Status text</dt>
          <dd>{channel.scada_status_text || "—"}</dd>
        </div>

        <div>
          <dt>Περιγραφή status</dt>
          <dd>{channel.scada_status_description || "—"}</dd>
        </div>

        <div>
          <dt>Device</dt>
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
          <dt>Τελευταία ανάγνωση</dt>
          <dd>{formatDateTime(channel.fetched_at || channel.last_update)}</dd>
        </div>
      </dl>
    </article>
  );
}