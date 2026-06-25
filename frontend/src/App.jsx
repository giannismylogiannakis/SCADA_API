import { useState } from "react";
import Layout from "./components/Layout";
import AlertsPage from "./pages/AlertsPage";
import GeneralOverview from "./pages/GeneralOverview";

export default function App() {
  const [activePage, setActivePage] = useState("overview");

  return (
    <Layout activePage={activePage} onPageChange={setActivePage}>
      {activePage === "alerts" ? <AlertsPage /> : <GeneralOverview />}
    </Layout>
  );
}