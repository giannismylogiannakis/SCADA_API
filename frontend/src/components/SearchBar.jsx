const CATEGORY_OPTIONS = [
  { value: "all", label: "Όλες οι κατηγορίες" },
  { value: "flow", label: "Ροές" },
  { value: "cumulative_flow", label: "Υδρόμετρα / Σύνολα Ροής" },
  { value: "level", label: "Στάθμες" },
  { value: "quality", label: "Ποιότητα" },
  { value: "motor_current", label: "Αντλίες / Εντάσεις" },
  { value: "pressure", label: "Πίεση" },
  { value: "unknown", label: "Άγνωστα" },
];

export default function SearchBar({
  searchTerm,
  onSearchTermChange,
  statusFilter,
  onStatusFilterChange,
  categoryFilter,
  onCategoryFilterChange,
}) {
  return (
    <section className="filters-panel">
      <div className="field">
        <label htmlFor="channel-search">Αναζήτηση</label>
        <input
          id="channel-search"
          type="search"
          value={searchTerm}
          placeholder="Όνομα, tag, εγκατάσταση, device ή channel number..."
          onChange={(event) => onSearchTermChange(event.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="category-filter">Κατηγορία</label>
        <select
          id="category-filter"
          value={categoryFilter}
          onChange={(event) => onCategoryFilterChange(event.target.value)}
        >
          {CATEGORY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label htmlFor="status-filter">Επιχειρησιακή κατάσταση</label>
        <select
          id="status-filter"
          value={statusFilter}
          onChange={(event) => onStatusFilterChange(event.target.value)}
        >
          <option value="all">Όλες</option>
          <option value="normal">Κανονικά</option>
          <option value="warning">Προειδοποιήσεις</option>
          <option value="critical">Κρίσιμα</option>
          <option value="unknown">Άγνωστα</option>
        </select>
      </div>
    </section>
  );
}