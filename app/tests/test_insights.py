from datetime import date, datetime

from app.services.insights import DayPoint, HourPoint, build_insights
from app.services.units import Units


def hours(probs=None, wind=10.0, n=24):
    return [
        HourPoint(datetime(2026, 10, 12, h % 24, 0), 20.0, None if probs is None else probs.get(h, 0), wind)
        for h in range(n)
    ]


def days(**kw):
    base = [(24, 14, 10, 5), (25, 13, 20, 8), (19, 12, 80, 4)]
    return [DayPoint(date(2026, 10, 12 + i), mx, mn, p, uv) for i, (mx, mn, p, uv) in enumerate(base)]


def types(insights):
    return [i.type for i in insights]


def test_rain_likely_names_first_hour():
    result = build_insights(hours({16: 70}), days(), Units())
    rain = next(i for i in result if i.type == "rain")
    assert "16:00" in rain.message and "70%" in rain.message and rain.severity == "notice"


def test_no_rain_and_outlook_for_wet_day_later():
    result = build_insights(hours({}), days(), Units())
    assert next(i for i in result if i.type == "rain").message == "No rain expected in the next 24 hours."
    assert "Wed 14 Oct" in next(i for i in result if i.type == "rain_outlook").message


def test_unknown_probability_makes_no_rain_claim():
    assert "rain" not in types(build_insights(hours(None), days(), Units()))


def test_small_chance_of_rain():
    rain = next(i for i in build_insights(hours({3: 30}), days(), Units()) if i.type == "rain")
    assert "small chance" in rain.message.lower()


def test_warmest_and_coolest_use_user_units():
    result = build_insights(hours({}), days(), Units("fahrenheit", "imperial"))
    assert "77°F" in next(i for i in result if i.type == "warmest").message  # 25 C
    assert "54°F" in next(i for i in result if i.type == "coolest").message  # 12 C


def test_big_temperature_change():
    d = days()
    d[1].temp_max = 31.0  # +7 C vs today's 24
    msg = next(i for i in build_insights(hours({}), d, Units()) if i.type == "temperature_change").message
    assert "7°C warmer" in msg


def test_uv_levels():
    d = days()
    d[0].uv_max = 9
    assert next(i for i in build_insights(hours({}), d, Units()) if i.type == "uv").severity == "warning"
    d[0].uv_max = 3
    assert "uv" not in types(build_insights(hours({}), d, Units()))


def test_strong_wind_converted_to_mph():
    result = build_insights(hours({}, wind=50.0), days(), Units("celsius", "imperial"))
    assert "31 mph" in next(i for i in result if i.type == "wind").message


def test_every_insight_explains_its_rule():
    assert all(i.rule for i in build_insights(hours({16: 70}, wind=70.0), days(), Units()))
