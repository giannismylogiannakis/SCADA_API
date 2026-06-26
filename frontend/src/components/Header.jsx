export default function Header() {
  return (
    <header className="app-header">
      <div className="app-header__brand">
        <span className="app-header__menu-icon">☰</span>
        <h1>Rapid SCADA</h1>
      </div>

      <div className="app-header__meta">
        <span>read-only telemetry dashboard</span>
      </div>
    </header>
  );
}