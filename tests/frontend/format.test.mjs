import test from "node:test";
import assert from "node:assert/strict";
import {
  DASH, dayLabel, formatDate, formatHour, formatNumber, formatPercent, formatTemp, locationLabel,
  placeLabel, relativeAge, skyFor, uvLabel,
} from "../../frontend/js/format.js";
import { iconSvg } from "../../frontend/js/icons.js";

test("missing values show a dash, never zero", () => {
  assert.equal(formatTemp(null), DASH);
  assert.equal(formatTemp(undefined), DASH);
  assert.equal(formatPercent(null), DASH);
  assert.equal(formatNumber(null, 1), DASH);
  assert.equal(formatTemp(0), "0°"); // a real zero is still shown
  assert.equal(formatPercent(0), "0%");
});

test("temperature rounds", () => {
  assert.equal(formatTemp(21.6), "22°");
  assert.equal(formatTemp(-0.4), "0°"); // never show "-0°"
  assert.equal(formatTemp(-3.5), "-3°");
});

test("hours are read from the location's own clock, not the browser's", () => {
  assert.equal(formatHour("2026-10-12T14:00:00+03:00"), "14:00");
  assert.equal(formatHour("2027-01-15T09:30:00-05:00"), "09:30");
  assert.equal(formatHour(null), DASH);
});

test("dates and day labels", () => {
  assert.equal(formatDate("2026-10-12"), "12 Oct");
  assert.equal(dayLabel("2026-10-12", "2026-10-12", "Mon"), "Today");
  assert.equal(dayLabel("2026-10-13", "2026-10-12", "Tue"), "Tomorrow");
  assert.equal(dayLabel("2026-10-14", "2026-10-12", "Wed"), "Wed");
  assert.equal(dayLabel("2026-11-01", "2026-10-31", "Sun"), "Tomorrow"); // month rollover
  assert.equal(dayLabel("2027-01-01", "2026-12-31", "Fri"), "Tomorrow"); // year rollover
});

test("labels", () => {
  assert.equal(locationLabel({ name: "Nairobi", country: "Kenya", latitude: 0, longitude: 0 }), "Nairobi, Kenya");
  assert.equal(locationLabel({ name: null, country: null, latitude: -1.2921, longitude: 36.8219 }), "-1.29, 36.82");
  assert.equal(placeLabel({ name: "Paris", admin1: "Texas", country: "United States" }), "Paris, Texas, United States");
  assert.equal(placeLabel({ name: "Singapore", admin1: "Singapore", country: "Singapore" }), "Singapore, Singapore");
});

test("relative age of data", () => {
  const now = Date.parse("2026-10-12T12:00:00Z");
  assert.equal(relativeAge("2026-10-12T11:59:40Z", now), "just now");
  assert.equal(relativeAge("2026-10-12T11:55:00Z", now), "5 min ago");
  assert.equal(relativeAge("2026-10-12T09:30:00Z", now), "2 h 30 min ago");
});

test("uv labels follow the same thresholds as the backend", () => {
  assert.equal(uvLabel(null), DASH);
  assert.equal(uvLabel(2), "2 (Low)");
  assert.equal(uvLabel(6), "6 (High)");
  assert.equal(uvLabel(9), "9 (Very high)");
  assert.equal(uvLabel(12), "12 (Extreme)");
});

test("sky follows condition and real daylight, with manual override", () => {
  assert.deepEqual(skyFor("rain", true), { sky: "rain", night: false });
  assert.deepEqual(skyFor("clear", false), { sky: "clear", night: true });
  assert.deepEqual(skyFor("clear", null), { sky: "clear", night: false }); // unknown daylight -> day
  assert.deepEqual(skyFor("thunder", true), { sky: "storm", night: false });
  assert.deepEqual(skyFor("clear", true, "dark"), { sky: "clear", night: true });
  assert.deepEqual(skyFor("clear", false, "light"), { sky: "clear", night: false });
  assert.equal(skyFor("nonsense", true).sky, "cloudy");
});

test("every icon key renders an svg, including night variants and unknowns", () => {
  for (const key of ["clear", "partly", "cloudy", "fog", "drizzle", "rain", "snow", "thunder", "unknown", "???"]) {
    for (const day of [true, false]) assert.match(iconSvg(key, day), /^<svg [^>]*aria-hidden="true"/);
  }
  assert.notEqual(iconSvg("clear", true), iconSvg("clear", false));
});
