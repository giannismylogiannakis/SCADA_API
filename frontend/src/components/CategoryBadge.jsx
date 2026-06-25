export default function CategoryBadge({ channel }) {
  const category = channel.category || "unknown";
  const label = channel.category_label || "Άγνωστο";

  return (
    <span className={`category-badge category-badge--${category}`}>
      {label}
    </span>
  );
}