import { getApiBaseUrl } from "../api/client";

export default function Header() {
  return (
    <header className="app-header">
      <div>
        <p className="eyebrow">Rapid SCADA Telemetry Dashboard</p>
        <h1>Ελληνικό Local Dashboard Τηλεμετρίας</h1>
      </div>

    </header>
  );
}