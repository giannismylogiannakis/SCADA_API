import { useState } from "react";
import Layout from "./components/Layout";
import OperationalTablesPage from "./pages/OperationalTablesPage";
import SettingsPage from "./pages/SettingsPage";

const VIEWS = {
  overview: "overview",
  settings: "settings",
};

export default function App() {
  const [activeView, setActiveView] = useState(VIEWS.overview);

  return (
    <Layout>
      <div className="phase9-view-shell">
        <nav className="phase9-view-tabs" aria-label="Πλοήγηση dashboard">
          <button
            type="button"
            className={
              activeView === VIEWS.overview
                ? "phase9-view-tab phase9-view-tab--active"
                : "phase9-view-tab"
            }
            onClick={() => setActiveView(VIEWS.overview)}
          >
            Γενική Ανασκόπηση
          </button>

          <button
            type="button"
            className={
              activeView === VIEWS.settings
                ? "phase9-view-tab phase9-view-tab--active"
                : "phase9-view-tab"
            }
            onClick={() => setActiveView(VIEWS.settings)}
          >
            Ρυθμίσεις Ορίων
          </button>
        </nav>

        {activeView === VIEWS.overview ? (
          <OperationalTablesPage />
        ) : (
          <SettingsPage />
        )}
      </div>
    </Layout>
  );
}