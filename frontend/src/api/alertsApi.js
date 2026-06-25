import { apiGet } from "./client";

export async function fetchAlerts({
  category = "all",
  severity = "all",
  includeNormal = false,
} = {}) {
  const params = new URLSearchParams();

  if (category && category !== "all") {
    params.set("category", category);
  }

  if (severity && severity !== "all") {
    params.set("severity", severity);
  }

  if (includeNormal) {
    params.set("include_normal", "true");
  }

  const queryString = params.toString();
  const path = queryString ? `/api/alerts?${queryString}` : "/api/alerts";

  return apiGet(path);
}