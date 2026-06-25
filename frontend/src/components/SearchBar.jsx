export default function SearchBar({
  searchTerm,
  onSearchTermChange,
  statusFilter,
  onStatusFilterChange,
}) {
  return (
    <section className="filters-panel">
      <div className="field">
        <label htmlFor="channel-search">Αναζήτηση</label>
        <input
          id="channel-search"
          type="search"
          value={searchTerm}
          placeholder="Όνομα, tag, device ή channel number..."
          onChange={(event) => onSearchTermChange(event.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="status-filter">SCADA status</label>
        <select
          id="status-filter"
          value={statusFilter}
          onChange={(event) => onStatusFilterChange(event.target.value)}
        >
          <option value="all">Όλα</option>
          <option value="normal">Κανονικά</option>
          <option value="abnormal">Μη κανονικά</option>
        </select>
      </div>
    </section>
  );
}