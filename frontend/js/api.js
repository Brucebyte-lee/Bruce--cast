// The only file that talks to the SkyCast backend. The browser never calls Open-Meteo directly.

export class ApiError extends Error {
  constructor(message, code, status = 0) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request(path, { method = "GET", body, signal } = {}) {
  let response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      credentials: "same-origin",
      signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError("SkyCast can't be reached. Check your internet connection and try again.", "network");
  }
  if (response.status === 204) return null;
  let data = null;
  try {
    data = await response.json();
  } catch {
    /* non-JSON error body */
  }
  if (!response.ok) {
    const error = data && data.error;
    throw new ApiError(error?.message || "Something went wrong. Please try again.", error?.code || `http_${response.status}`, response.status);
  }
  return data;
}

const unitQuery = (prefs) => `temperature_unit=${prefs.temperature_unit}&unit_system=${prefs.unit_system}`;

export const api = {
  search: (q, signal) => request(`/locations/search?q=${encodeURIComponent(q)}`, { signal }),
  overview: (loc, prefs, signal) => {
    const params = new URLSearchParams({ latitude: loc.latitude, longitude: loc.longitude });
    if (loc.name) params.set("name", loc.name);
    if (loc.country) params.set("country", loc.country);
    return request(`/weather/overview?${params}&${unitQuery(prefs)}`, { signal });
  },
  compare: (locations, prefs) => request(`/weather/compare?${unitQuery(prefs)}`, { method: "POST", body: { locations } }),
  favorites: () => request("/favorites"),
  addFavorite: (loc) => request("/favorites", { method: "POST", body: loc }),
  removeFavorite: (id) => request(`/favorites/${id}`, { method: "DELETE" }),
  reorderFavorites: (ids) => request("/favorites/order", { method: "PUT", body: { ids } }),
  preferences: () => request("/preferences"),
  savePreferences: (prefs) => request("/preferences", { method: "PUT", body: prefs }),
};
