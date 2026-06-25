export default function Sidebar({ activePage, onPageChange }) {
  return (
    <aside className="sidebar">
      <div className="sidebar__title">Μενού</div>

      <nav className="sidebar__nav" aria-label="Κύριο μενού">
        <button
          type="button"
          className={`sidebar__link ${
            activePage === "overview" ? "sidebar__link--active" : ""
          }`}
          onClick={() => onPageChange("overview")}
        >
          Γενική Ανασκόπηση
        </button>

        <button
          type="button"
          className={`sidebar__link ${
            activePage === "alerts" ? "sidebar__link--active" : ""
          }`}
          onClick={() => onPageChange("alerts")}
        >
          Προειδοποιήσεις
        </button>
      </nav>

      <div className="sidebar__note">
        Φάση 5: basic rules engine, επιχειρησιακά alerts και read-only dashboard.
      </div>
    </aside>
  );
}