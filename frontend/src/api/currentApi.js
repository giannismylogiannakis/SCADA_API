import { apiGet } from "./client";

export async function fetchCurrentChannels() {
  const payload = await apiGet("/api/current");
  return normalizeCurrentResponse(payload);
}

function normalizeCurrentResponse(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }

  const topLevelFetchedAt = payload?.fetched_at || null;

  const items =
    payload?.items ||
    payload?.channels ||
    payload?.data ||
    [];

  if (!Array.isArray(items)) {
    return [];
  }

  return items.map((item) => ({
    ...item,
    fetched_at: item.fetched_at || topLevelFetchedAt,
  }));
}