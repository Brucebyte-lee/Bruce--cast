// Weather icons as inline SVG. These strings are constants written by us (never user data),
// so assigning them with innerHTML is safe.

const CLOUD = '<path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>';
const SUN = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
const MOON = '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
const SMALL_CLOUD = '<g transform="translate(5 7) scale(.75)">' + CLOUD + "</g>";
const SMALL_SUN = '<g transform="translate(-3 -3) scale(.75)">' + SUN + "</g>";
const SMALL_MOON = '<g transform="translate(-1 -3) scale(.7)">' + MOON + "</g>";

const SHAPES = {
  clear_day: SUN,
  clear_night: MOON,
  partly_day: SMALL_SUN + SMALL_CLOUD,
  partly_night: SMALL_MOON + SMALL_CLOUD,
  cloudy: CLOUD,
  fog: '<path d="M20 12.6A5 5 0 0 0 18 3h-1.3A8 8 0 1 0 4 11.3"/><path d="M4 16h16M7 20h10"/>',
  drizzle: '<path d="M20 16.6A5 5 0 0 0 18 7h-1.3A8 8 0 1 0 4 15.3"/><path d="M8 19v2M8 13v2M16 19v2M16 13v2M12 21v2M12 15v2"/>',
  rain: '<path d="M20 16.6A5 5 0 0 0 18 7h-1.3A8 8 0 1 0 4 15.3"/><path d="M16 13v8M8 13v8M12 15v8"/>',
  snow: '<path d="M20 17.6A5 5 0 0 0 18 8h-1.3A8 8 0 1 0 4 16.3"/><path d="M8 16h.01M8 20h.01M12 18h.01M12 22h.01M16 16h.01M16 20h.01"/>',
  thunder: '<path d="M19 16.9A5 5 0 0 0 18 7h-1.3a8 8 0 1 0-11.6 9"/><path d="M13 11l-4 6h6l-4 6"/>',
  unknown: '<circle cx="12" cy="12" r="9"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/>',
};

export function iconSvg(icon, isDay = true) {
  const key = icon === "clear" || icon === "partly" ? `${icon}_${isDay === false ? "night" : "day"}` : icon;
  const shape = SHAPES[key] ?? SHAPES.unknown;
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${shape}</svg>`;
}
