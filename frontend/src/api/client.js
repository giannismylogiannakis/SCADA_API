function normalizeBaseUrl(value) {
  return value ? value.replace(/\/+$/, "") : "";
}

const API_BASE_URL = normalizeBaseUrl(
  import.meta.env.VITE_API_BASE_URL || window.location.origin
);

export function getApiBaseUrl() {
  return API_BASE_URL;
}

async function apiRequest(path, options = {}) {
  const timeoutMs = options.timeoutMs || 30000;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  try {
    const response = await fetch(`${API_BASE_URL}${normalizedPath}`, {
      method: options.method || "GET",
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });

    if (!response.ok) {
      let detail = "";

      try {
        const errorBody = await response.json();
        detail = errorBody.detail ? ` - ${errorBody.detail}` : "";
      } catch {
        // Ignore invalid error JSON.
      }

      throw new Error(`Το backend επέστρεψε HTTP ${response.status}${detail}`);
    }

    return await response.json();
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("Η σύνδεση με το backend άργησε υπερβολικά.");
    }

    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function apiGet(path, options = {}) {
  return apiRequest(path, {
    ...options,
    method: "GET",
  });
}

export async function apiPost(path, body = {}, options = {}) {
  return apiRequest(path, {
    ...options,
    method: "POST",
    body,
  });
}

export async function apiPut(path, body = {}, options = {}) {
  return apiRequest(path, {
    ...options,
    method: "PUT",
    body,
  });
}

export async function apiDelete(path, options = {}) {
  return apiRequest(path, {
    ...options,
    method: "DELETE",
  });
}
