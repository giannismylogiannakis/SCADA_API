import { apiGet } from "./client";

export async function fetchStatisticsSummary({ cnlNums, category } = {}) {
  const params = new URLSearchParams();

  if (Array.isArray(cnlNums) && cnlNums.length > 0) {
    params.set("cnl_nums", cnlNums.join(","));
  }

  if (category && category !== "all") {
    params.set("category", category);
  }

  const queryString = params.toString();
  const path = queryString
    ? `/api/statistics/summary?${queryString}`
    : "/api/statistics/summary";

  const payload = await apiGet(path, {
    timeoutMs: 30000,
  });

  return Array.isArray(payload?.items) ? payload.items : [];
}