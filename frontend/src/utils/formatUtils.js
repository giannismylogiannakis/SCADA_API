export function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return new Intl.DateTimeFormat("el-GR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(date);
}

export function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }

  const numericValue = Number(value);

  if (Number.isFinite(numericValue)) {
    return Number.isInteger(numericValue)
      ? String(numericValue)
      : numericValue.toFixed(3);
  }

  return String(value);
}