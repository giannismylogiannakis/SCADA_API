export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar__title">Μενού</div>

      <nav className="sidebar__nav" aria-label="Κύριο μενού">
        <a className="sidebar__link sidebar__link--active" href="#overview">
          Γενική Ανασκόπηση
        </a>
      </nav>

      <div className="sidebar__note">
        Φάση 4: κατηγοριοποίηση καναλιών και καθαρές κάρτες χειριστή. Παραμένει αυστηρά read-only.
      </div>
    </aside>
  );
}