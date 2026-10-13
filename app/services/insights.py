"""Weather insights: plain, transparent rules applied to the real forecast numbers.

No AI-generated text. Every insight carries the `rule` that produced it, so a user (or
you) can see exactly why a message appeared. Inputs are METRIC; messages are formatted
in the user's chosen units.
"""

from dataclasses import dataclass
from datetime import date, datetime

from app.schemas.weather import Insight
from app.services.units import Units

RAIN_LIKELY_PERCENT = 50
RAIN_POSSIBLE_PERCENT = 20
TEMP_CHANGE_CELSIUS = 5.0
UV_HIGH = 6
UV_VERY_HIGH = 8
WIND_STRONG_KMH = 40
WIND_VERY_STRONG_KMH = 60

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class HourPoint:
    time: datetime
    temperature: float | None
    precip_probability: float | None
    wind_kmh: float | None


@dataclass
class DayPoint:
    date: date
    temp_max: float | None
    temp_min: float | None
    precip_probability: float | None
    uv_max: float | None


def _day_label(d: date) -> str:
    return f"{_DAYS[d.weekday()]} {d.day} {_MONTHS[d.month - 1]}"


def build_insights(hours: list[HourPoint], days: list[DayPoint], units: Units) -> list[Insight]:
    insights: list[Insight] = []
    deg = units.labels["temperature"]
    wind_label = units.labels["wind_speed"]

    # --- Rain in the next 24 hours -------------------------------------------------
    known = [h for h in hours if h.precip_probability is not None]
    if known:
        peak = max(h.precip_probability for h in known)  # type: ignore[type-var]
        likely = next((h for h in known if h.precip_probability >= RAIN_LIKELY_PERCENT), None)  # type: ignore[operator]
        if likely:
            msg = f"Rain is likely around {likely.time:%H:%M} ({likely.precip_probability:.0f}% chance)."
            insights.append(
                Insight(
                    type="rain",
                    severity="notice",
                    message=msg,
                    rule=f"Any hour in the next 24 h with precipitation probability ≥ {RAIN_LIKELY_PERCENT}%",
                )
            )
        elif peak >= RAIN_POSSIBLE_PERCENT:
            insights.append(
                Insight(
                    type="rain",
                    severity="info",
                    message=f"A small chance of rain in the next 24 hours (up to {peak:.0f}%).",
                    rule=f"Peak precipitation probability between {RAIN_POSSIBLE_PERCENT}% and {RAIN_LIKELY_PERCENT}%",
                )
            )
        else:
            insights.append(
                Insight(
                    type="rain",
                    severity="info",
                    message="No rain expected in the next 24 hours.",
                    rule=f"Peak precipitation probability in the next 24 h is below {RAIN_POSSIBLE_PERCENT}%",
                )
            )
            wet_day = next(
                (
                    d
                    for d in days[1:]
                    if d.precip_probability is not None and d.precip_probability >= RAIN_LIKELY_PERCENT
                ),
                None,
            )
            if wet_day:
                insights.append(
                    Insight(
                        type="rain_outlook",
                        severity="info",
                        message=f"Rain is likely on {_day_label(wet_day.date)} ({wet_day.precip_probability:.0f}% chance).",
                        rule=f"First later day with daily precipitation probability ≥ {RAIN_LIKELY_PERCENT}%",
                    )
                )

    # --- Warmest / coolest -----------------------------------------------------------
    highs = [d for d in days if d.temp_max is not None]
    lows = [d for d in days if d.temp_min is not None]
    if highs:
        hot = max(highs, key=lambda d: d.temp_max)  # type: ignore[arg-type, return-value]
        insights.append(
            Insight(
                type="warmest",
                severity="info",
                message=f"Warmest day: {_day_label(hot.date)}, high of {units.temp(hot.temp_max):.0f}{deg}.",
                rule="Highest daily maximum temperature in the forecast",
            )
        )
    if lows:
        cold = min(lows, key=lambda d: d.temp_min)  # type: ignore[arg-type, return-value]
        insights.append(
            Insight(
                type="coolest",
                severity="info",
                message=f"Coolest night: {_day_label(cold.date)}, low of {units.temp(cold.temp_min):.0f}{deg}.",
                rule="Lowest daily minimum temperature in the forecast",
            )
        )

    # --- Significant change tomorrow ---------------------------------------------------
    if len(days) > 1 and days[0].temp_max is not None and days[1].temp_max is not None:
        delta = days[1].temp_max - days[0].temp_max
        if abs(delta) >= TEMP_CHANGE_CELSIUS:
            word = "warmer" if delta > 0 else "cooler"
            insights.append(
                Insight(
                    type="temperature_change",
                    severity="notice",
                    message=f"Tomorrow's high is {abs(units.temp_delta(delta)):.0f}{deg} {word} than today's.",  # type: ignore[arg-type]
                    rule=f"Day-to-day change in daily maximum of at least {TEMP_CHANGE_CELSIUS:.0f}°C",
                )
            )

    # --- UV ------------------------------------------------------------------------------
    uv = days[0].uv_max if days else None
    if uv is not None and uv >= UV_HIGH:
        level = "very high" if uv >= UV_VERY_HIGH else "high"
        insights.append(
            Insight(
                type="uv",
                severity="warning" if uv >= UV_VERY_HIGH else "notice",
                message=f"UV index peaks at {uv:.0f} today ({level}). Use sun protection around midday.",
                rule=f"Today's maximum UV index ≥ {UV_HIGH} (high) or ≥ {UV_VERY_HIGH} (very high)",
            )
        )

    # --- Wind in next 24 hours ---------------------------------------------------------------
    winds = [h for h in hours if h.wind_kmh is not None]
    if winds:
        windiest = max(winds, key=lambda h: h.wind_kmh)  # type: ignore[arg-type, return-value]
        if windiest.wind_kmh >= WIND_STRONG_KMH:  # type: ignore[operator]
            insights.append(
                Insight(
                    type="wind",
                    severity="warning" if windiest.wind_kmh >= WIND_VERY_STRONG_KMH else "notice",  # type: ignore[operator]
                    message=f"Strong wind up to {units.wind(windiest.wind_kmh):.0f} {wind_label} around {windiest.time:%H:%M}.",
                    rule=f"Hourly wind speed ≥ {WIND_STRONG_KMH} km/h in the next 24 h",
                )
            )
    return insights
