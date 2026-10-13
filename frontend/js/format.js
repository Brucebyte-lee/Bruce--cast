// Pure formatting helpers (no DOM, no network) so they can be unit-tested with Node.
// IMPORTANT: forecast timestamps arrive as ISO strings that already carry the LOCATION's
// local time ("2026-10-12T14:00:00+03:00"). We read hours/dates straight from the text so the
// browser's own timezone can never shift them.

export const DASH = "—";

export function isNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

export function formatNumber(value, digits = 0) {
  return isNumber(value) ? value.toFixed(digits) : DASH;
}

export function formatTemp(value) {
  return isNumber(value) ? `${Math.round(value)}°` : DASH;
}

export function formatPercent(value) {
  return isNumber(value) ? `${Math.round(value)}%` : DASH;
}

export function formatHour(iso) {
  return typeof iso === "string" && iso.length >= 16 ? iso.slice(11, 16) : DASH;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatDate(dateStr) {
  const [, month, day] = String(dateStr).split("-");
  return month ? `${Number(day)} ${MONTHS[Number(month) - 1]}` : DASH;
}

/** "Today" / "Tomorrow" / weekday abbreviation, judged against the LOCATION's today. */
export function dayLabel(dateStr, todayStr, weekday) {
  if (dateStr === todayStr) return "Today";
  const next = new Date(Date.UTC(...todayStr.split("-").map((n, i) => (i === 1 ? n - 1 : +n))) + 86400000);
  return dateStr === next.toISOString().slice(0, 10) ? "Tomorrow" : weekday;
}

export function locationLabel(loc) {
  if (!loc) return "";
  if (loc.name) return loc.country ? `${loc.name}, ${loc.country}` : loc.name;
  return `${loc.latitude.toFixed(2)}, ${loc.longitude.toFixed(2)}`;
}

export function placeLabel(place) {
  const parts = [place.name, place.admin1 && place.admin1 !== place.name ? place.admin1 : null, place.country];
  return parts.filter(Boolean).join(", ");
}

export function relativeAge(fetchedIso, nowMs = Date.now()) {
  const minutes = Math.max(0, Math.round((nowMs - Date.parse(fetchedIso)) / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${minutes % 60} min ago`;
}

export function uvLabel(uv) {
  if (!isNumber(uv)) return DASH;
  const level = uv >= 11 ? "Extreme" : uv >= 8 ? "Very high" : uv >= 6 ? "High" : uv >= 3 ? "Moderate" : "Low";
  return `${Math.round(uv)} (${level})`;
}

/** Choose the sky palette. theme: "system" follows the location's real daylight. */
export function skyFor(icon, isDay, theme = "system") {
  const night = theme === "dark" ? true : theme === "light" ? false : isDay === false;
  const sky = { clear: "clear", partly: "clear", cloudy: "cloudy", unknown: "cloudy", fog: "fog",
    drizzle: "rain", rain: "rain", snow: "snow", thunder: "storm" }[icon] ?? "cloudy";
  return { sky, night };
}
