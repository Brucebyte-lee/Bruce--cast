// SkyCast dashboard. Rule for safety: text from the API is ALWAYS inserted with textContent
// (never innerHTML), so a malicious city name can't inject HTML or scripts.

import { api, ApiError } from "./api.js";
import { iconSvg } from "./icons.js";
import {
  DASH, dayLabel, formatDate, formatHour, formatNumber, formatPercent, formatTemp, locationLabel,
  placeLabel, relativeAge, skyFor, uvLabel,
} from "./format.js";

const $ = (id) => document.getElementById(id);
const DEFAULT_PREFS = { temperature_unit: "celsius", unit_system: "metric", theme: "system" };

const state = { prefs: { ...DEFAULT_PREFS }, location: null, overview: null, favorites: [], loadToken: 0, results: [], active: -1 };

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined));
  return node;
}
const announce = (message) => { $("status").textContent = ""; setTimeout(() => ($("status").textContent = message), 50); };
const setView = (name) => { for (const id of ["empty", "skeleton", "error", "weather"]) $(id).hidden = id !== name; };
const store = {
  get: (k) => { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable: fine */ } },
};

/* ------------------------------------------------------------------ preferences */
function paintPrefs() {
  for (const button of document.querySelectorAll("[data-pref]")) {
    button.setAttribute("aria-checked", String(state.prefs[button.dataset.pref] === button.dataset.value));
    button.tabIndex = button.getAttribute("aria-checked") === "true" ? 0 : -1;
  }
}
async function setPref(key, value) {
  state.prefs = { ...state.prefs, [key]: value };
  paintPrefs();
  if (key === "theme" && state.overview) paintSky(state.overview.current);
  if (key !== "theme" && state.location) await loadWeather();
  try { await api.savePreferences(state.prefs); } catch { /* preferences still work for this session */ }
}

/* ------------------------------------------------------------------ search */
let searchTimer, searchController;
const input = $("search-input"), listbox = $("search-results");

function closeResults() {
  listbox.hidden = true; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); state.active = -1;
}
function renderResults(items, note) {
  listbox.replaceChildren();
  if (note) listbox.append(el("li", { class: "note", role: "presentation" }, note));
  items.forEach((place, i) => {
    const li = el("li", { role: "option", id: `opt-${i}`, "aria-selected": "false" },
      place.name, el("span", { class: "sub" }, placeLabel(place).slice(place.name.length).replace(/^, /, "") || (place.timezone ?? "")));
    li.addEventListener("mousedown", (e) => { e.preventDefault(); choose(place); });
    listbox.append(li);
  });
  listbox.hidden = false; input.setAttribute("aria-expanded", "true");
}
function highlight(index) {
  const options = [...listbox.querySelectorAll("[role=option]")];
  if (!options.length) return;
  state.active = (index + options.length) % options.length;
  options.forEach((o, i) => o.setAttribute("aria-selected", String(i === state.active)));
  input.setAttribute("aria-activedescendant", options[state.active].id);
  options[state.active].scrollIntoView({ block: "nearest" });
}
async function runSearch(query) {
  searchController?.abort();
  searchController = new AbortController();
  try {
    const { results } = await api.search(query, searchController.signal);
    state.results = results;
    if (!results.length) return renderResults([], `No places found for “${query}”. Check the spelling, or try “City, Country”.`);
    renderResults(results);
    announce(`${results.length} places found. Use the arrow keys to choose.`);
  } catch (err) {
    if (err.name !== "AbortError") renderResults([], err.message);
  }
}
function choose(place) {
  input.value = placeLabel(place);
  closeResults();
  selectLocation({ name: place.name, country: place.country ?? null, latitude: place.latitude, longitude: place.longitude, timezone: place.timezone ?? null });
}
input.addEventListener("input", () => {
  clearTimeout(searchTimer);
  const query = input.value.trim();
  if (query.length < 2) return closeResults();
  searchTimer = setTimeout(() => runSearch(query), 250);
});
input.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown") { e.preventDefault(); highlight(state.active + 1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); highlight(state.active - 1); }
  else if (e.key === "Escape") closeResults();
  else if (e.key === "Enter" && state.active >= 0) { e.preventDefault(); choose(state.results[state.active]); }
});
$("search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (state.active >= 0) return;
  const query = input.value.trim();
  if (query.length < 2) return;
  await runSearch(query);
  if (state.results.length === 1) choose(state.results[0]);
});
document.addEventListener("click", (e) => { if (!e.target.closest(".search-box")) closeResults(); });

$("geo-button").addEventListener("click", () => {
  if (!("geolocation" in navigator)) return showError("Location not supported", "This browser can't share a location. Search for a city instead.", false);
  announce("Requesting your location");
  navigator.geolocation.getCurrentPosition(
    (pos) => selectLocation({ name: "My location", country: null, // rounded to ~1 km: precise position is never needed
      latitude: Math.round(pos.coords.latitude * 100) / 100, longitude: Math.round(pos.coords.longitude * 100) / 100, timezone: null }),
    () => { showError("Location permission was not granted", "No problem. Search for a city above to see its forecast.", false); input.focus(); },
    { timeout: 10000, maximumAge: 600000 },
  );
});

/* ------------------------------------------------------------------ weather */
function showError(title, message, retry = true) {
  $("error-title").textContent = title; $("error-message").textContent = message;
  $("retry-button").hidden = !retry; setView("error"); announce(`${title}. ${message}`);
}
function selectLocation(loc) {
  state.location = loc; store.set("skycast:last", loc);
  return loadWeather();
}
async function loadWeather() {
  const token = ++state.loadToken;
  setView("skeleton");
  try {
    const data = await api.overview(state.location, state.prefs);
    if (token !== state.loadToken) return; // a newer request replaced this one
    state.overview = data; renderWeather(data); setView("weather");
    announce(`Weather loaded for ${locationLabel(state.location)}. ${formatTemp(data.current.temperature)} ${data.current.condition.description}.`);
    $("main").focus({ preventScroll: true });
  } catch (err) {
    if (token !== state.loadToken) return;
    const message = err instanceof ApiError ? err.message : "Something unexpected happened. Please try again.";
    showError("We couldn't load the weather", message);
  }
}
$("retry-button").addEventListener("click", () => state.location && loadWeather());

function paintSky(current) {
  const { sky, night } = skyFor(current.condition.icon, current.is_day, state.prefs.theme);
  document.body.dataset.sky = sky; document.body.dataset.night = String(night);
}
function metric(label, value, sub) {
  return el("div", { class: "metric" }, el("dt", {}, label), el("dd", {}, value, sub ? el("small", {}, sub) : null));
}
function renderWeather(o) {
  const c = o.current, u = o.units, today = o.daily[0];
  paintSky(c);
  $("place-name").textContent = locationLabel(o.location);
  $("place-sub").textContent = o.location.timezone.replaceAll("_", " ");
  $("hero-icon").innerHTML = iconSvg(c.condition.icon, c.is_day);
  $("temp-value").textContent = c.temperature === null ? DASH : String(Math.round(c.temperature));
  $("temp-unit").textContent = c.temperature === null ? "" : u.temperature;
  $("condition").textContent = c.condition.description;
  $("feels-like").textContent = `Feels like ${formatTemp(c.feels_like)}`;
  $("range").textContent = `Today ${formatTemp(c.temp_max)} high · ${formatTemp(c.temp_min)} low`;
  $("stale-badge").hidden = !o.meta.stale;
  $("observed").textContent = `Observed at ${formatHour(c.observed_at)} local time`;
  $("updated").textContent = o.meta.stale
    ? `Showing saved data from ${relativeAge(o.meta.fetched_at)} because the weather service is not responding.`
    : `Updated ${relativeAge(o.meta.fetched_at)}.`;

  const wind = c.wind_speed === null ? DASH : `${formatNumber(c.wind_speed)} ${u.wind_speed} ${c.wind_direction ?? ""}`.trim();
  $("details").replaceChildren(
    metric("Humidity", formatPercent(c.humidity)),
    metric("Wind", wind, c.wind_gusts === null ? null : `Gusts ${formatNumber(c.wind_gusts)} ${u.wind_speed}`),
    metric("Precipitation now", c.precipitation === null ? DASH : `${formatNumber(c.precipitation, u.precipitation === "in" ? 2 : 1)} ${u.precipitation}`,
      today.precipitation_probability === null ? null : `${formatPercent(today.precipitation_probability)} chance today`),
    metric("Pressure", c.pressure === null ? DASH : `${formatNumber(c.pressure, u.pressure === "inHg" ? 2 : 0)} ${u.pressure}`),
    metric("UV index", uvLabel(c.uv_index), "Today's peak"),
    metric("Sun", today.sunrise ? `↑ ${formatHour(today.sunrise)}` : DASH, today.sunset ? `↓ ${formatHour(today.sunset)}` : null),
  );

  $("insights").replaceChildren(...(o.insights.length
    ? o.insights.map((i) => el("li", { "data-severity": i.severity }, i.message, el("span", { class: "rule" }, `Rule: ${i.rule}`)))
    : [el("li", {}, "Not enough forecast data for insights right now.")]));
  $("alerts").textContent = o.alerts.available ? `${o.alerts.items.length} active alerts.` : o.alerts.message;

  $("hourly-list").replaceChildren(...o.hourly.map((h) => el("li", { class: "hour" },
    el("span", { class: "t" }, formatHour(h.time)), iconNode(h.condition, h.is_day),
    el("span", { class: "t" }, formatTemp(h.temperature)),
    el("span", { class: "p" }, h.precipitation_probability === null ? "" : `${formatPercent(h.precipitation_probability)} rain`),
    el("span", { class: "p" }, h.wind_speed === null ? "" : `${formatNumber(h.wind_speed)} ${u.wind_speed}`))));

  const todayDate = today.date;
  $("daily-list").replaceChildren(...o.daily.map((d) => el("li", {},
    el("span", { class: "day" }, dayLabel(d.date, todayDate, d.weekday), el("small", {}, formatDate(d.date))),
    iconNode(d.condition, true),
    el("span", { class: "desc" }, d.condition.description,
      el("small", {}, [d.precipitation_probability === null ? null : `${formatPercent(d.precipitation_probability)} rain`,
        d.wind_speed_max === null ? null : `wind to ${formatNumber(d.wind_speed_max)} ${u.wind_speed}`].filter(Boolean).join(" · "))),
    el("span", { class: "range" }, formatTemp(d.temp_max), " ", el("small", {}, formatTemp(d.temp_min))))));
  paintFavoriteButton();
}
function iconNode(condition, isDay) {
  const span = el("span", { role: "img", "aria-label": condition.description });
  span.innerHTML = iconSvg(condition.icon, isDay);
  return span;
}

/* ------------------------------------------------------------------ favorites */
const sameSpot = (a, b) => Math.abs(a.latitude - b.latitude) < 0.0002 && Math.abs(a.longitude - b.longitude) < 0.0002;
const currentFavorite = () => state.location && state.favorites.find((f) => sameSpot(f, state.location));

function paintFavoriteButton() {
  const saved = Boolean(currentFavorite());
  $("fav-button").setAttribute("aria-pressed", String(saved));
  $("fav-button").textContent = saved ? "Saved ✓" : "Save location";
}
function favMessage(text) { $("fav-message").textContent = text; }

function renderFavorites() {
  $("fav-empty").hidden = state.favorites.length > 0;
  $("fav-list").replaceChildren(...state.favorites.map((f, i) => {
    const label = locationLabel(f);
    return el("li", {},
      el("input", { type: "checkbox", "aria-label": `Compare ${label}`, "data-id": f.id, onchange: updateCompareButton }),
      el("button", { type: "button", class: "pick", onclick: () => selectLocation({ name: f.name, country: f.country, latitude: f.latitude, longitude: f.longitude, timezone: f.timezone }) }, label),
      el("button", { type: "button", class: "icon-btn", "aria-label": `Move ${label} up`, ...(i === 0 ? { disabled: "" } : {}), onclick: () => move(i, -1) }, "↑"),
      el("button", { type: "button", class: "icon-btn", "aria-label": `Move ${label} down`, ...(i === state.favorites.length - 1 ? { disabled: "" } : {}), onclick: () => move(i, 1) }, "↓"),
      el("button", { type: "button", class: "icon-btn", "aria-label": `Remove ${label} from favorites`, onclick: () => removeFavorite(f) }, "✕"));
  }));
  updateCompareButton(); paintFavoriteButton();
}
async function loadFavorites() {
  try { state.favorites = await api.favorites(); renderFavorites(); }
  catch (err) { favMessage(err.message); }
}
$("fav-button").addEventListener("click", async () => {
  const existing = currentFavorite();
  try {
    if (existing) { await api.removeFavorite(existing.id); favMessage(`${locationLabel(existing)} removed.`); }
    else {
      const loc = state.location;
      await api.addFavorite({ name: loc.name ?? `${loc.latitude.toFixed(2)}, ${loc.longitude.toFixed(2)}`, country: loc.country, latitude: loc.latitude, longitude: loc.longitude, timezone: state.overview?.location.timezone ?? loc.timezone });
      favMessage(`${locationLabel(loc)} saved.`);
    }
    await loadFavorites();
  } catch (err) { favMessage(err.message); }
});
async function removeFavorite(f) {
  try { await api.removeFavorite(f.id); favMessage(`${locationLabel(f)} removed.`); await loadFavorites(); } catch (err) { favMessage(err.message); }
}
async function move(index, delta) {
  const ids = state.favorites.map((f) => f.id);
  [ids[index], ids[index + delta]] = [ids[index + delta], ids[index]];
  try { state.favorites = await api.reorderFavorites(ids); renderFavorites(); } catch (err) { favMessage(err.message); }
}

/* ------------------------------------------------------------------ compare */
const checkedFavorites = () => [...$("fav-list").querySelectorAll("input:checked")].map((box) => state.favorites.find((f) => String(f.id) === box.dataset.id));
function updateCompareButton() { const n = checkedFavorites().length; $("compare-button").disabled = n < 2 || n > 5; }
$("compare-button").addEventListener("click", async () => {
  const picks = checkedFavorites().map((f) => ({ name: f.name, country: f.country, latitude: f.latitude, longitude: f.longitude, timezone: f.timezone }));
  $("compare-panel").hidden = false; $("compare-table").replaceChildren(el("caption", { class: "sr-only" }, "Loading comparison"), el("tbody", {}, el("tr", {}, el("td", {}, "Loading…"))));
  try {
    const { units, items } = await api.compare(picks, state.prefs);
    const head = el("thead", {}, el("tr", {}, ...["City", "Now", "Conditions", "High / low", "Rain chance", "Wind", "Humidity"].map((h) => el("th", { scope: "col" }, h))));
    const rows = items.map((item) => item.error
      ? el("tr", {}, el("th", { scope: "row" }, locationLabel(item.location)), el("td", { colspan: "6" }, item.error))
      : el("tr", {}, el("th", { scope: "row" }, locationLabel(item.location)), el("td", {}, formatTemp(item.current.temperature)),
          el("td", {}, item.current.condition.description), el("td", {}, `${formatTemp(item.today?.temp_max ?? null)} / ${formatTemp(item.today?.temp_min ?? null)}`),
          el("td", {}, formatPercent(item.today?.precipitation_probability ?? null)),
          el("td", {}, item.current.wind_speed === null ? DASH : `${formatNumber(item.current.wind_speed)} ${units.wind_speed}`), el("td", {}, formatPercent(item.current.humidity))));
    $("compare-table").replaceChildren(el("caption", { class: "sr-only" }, `Weather comparison in ${units.temperature}`), head, el("tbody", {}, ...rows));
    announce("Comparison ready.");
  } catch (err) { $("compare-table").replaceChildren(el("tbody", {}, el("tr", {}, el("td", {}, err.message)))); }
});

/* ------------------------------------------------------------------ startup */
document.querySelectorAll("[data-pref]").forEach((button) => button.addEventListener("click", () => setPref(button.dataset.pref, button.dataset.value)));
document.querySelectorAll(".segmented").forEach((group) => group.addEventListener("keydown", (e) => {
  const buttons = [...group.querySelectorAll("button")], i = buttons.indexOf(document.activeElement);
  if (i < 0 || !["ArrowRight", "ArrowLeft"].includes(e.key)) return;
  e.preventDefault(); const next = buttons[(i + (e.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length];
  next.focus(); next.click();
}));

(async function init() {
  paintPrefs();
  const [prefs] = await Promise.allSettled([api.preferences(), loadFavorites()]);
  if (prefs.status === "fulfilled") { state.prefs = { ...DEFAULT_PREFS, ...prefs.value }; paintPrefs(); }
  const last = store.get("skycast:last");
  if (last && Number.isFinite(last.latitude) && Number.isFinite(last.longitude)) selectLocation(last);
  else setView("empty");
})();
