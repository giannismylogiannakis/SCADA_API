export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar__title">Views</div>

      <nav className="sidebar__nav" aria-label="Κύριο μενού">
        <button
          type="button"
          className="sidebar__link sidebar__link--active"
        >
          Γενική Ανασκόπηση
        </button>
      </nav>

      <div className="sidebar__note">
        Φάση 7: compact SCADA-style πίνακες ανά κατηγορία. Μόνο ανάγνωση.
      </div>
    </aside>
  );
}