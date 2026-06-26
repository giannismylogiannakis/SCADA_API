import { apiDelete, apiGet, apiPost, apiPut } from "./client";

export async function fetchSettingsChannels({
  search = "",
  category = "all",
  onlyOverridden = false,
} = {}) {
  const params = new URLSearchParams();

  if (search.trim()) {
    params.set("search", search.trim());
  }

  if (category && category !== "all") {
    params.set("category", category);
  }

  if (onlyOverridden) {
    params.set("only_overridden", "true");
  }

  const queryString = params.toString();
  const path = queryString
    ? `/api/settings/channels?${queryString}`
    : "/api/settings/channels";

  return apiGet(path, {
    timeoutMs: 30000,
  });
}

export async function fetchSettingsChannel(cnlNum) {
  return apiGet(`/api/settings/channels/${cnlNum}`, {
    timeoutMs: 30000,
  });
}

export async function saveChannelSettings(cnlNum, payload) {
  return apiPut(`/api/settings/channels/${cnlNum}`, payload, {
    timeoutMs: 30000,
  });
}

export async function resetChannelSettings(cnlNum) {
  return apiDelete(`/api/settings/channels/${cnlNum}`, {
    timeoutMs: 30000,
  });
}

export async function reloadDashboardSettings() {
  return apiPost("/api/settings/reload", {}, {
    timeoutMs: 30000,
  });
}

export async function fetchSettingsRules({
  category = "all",
  onlyOverridden = false,
} = {}) {
  const params = new URLSearchParams();

  if (category && category !== "all") {
    params.set("category", category);
  }

  if (onlyOverridden) {
    params.set("only_overridden", "true");
  }

  const queryString = params.toString();
  const path = queryString
    ? `/api/settings/rules?${queryString}`
    : "/api/settings/rules";

  return apiGet(path, {
    timeoutMs: 30000,
  });
}