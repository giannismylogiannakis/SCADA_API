import Header from "./Header";
import Sidebar from "./Sidebar";

export default function Layout({ children, activePage, onPageChange }) {
  return (
    <div className="app-shell">
      <Header />

      <div className="app-body">
        <Sidebar activePage={activePage} onPageChange={onPageChange} />

        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}