import httpx
import pytest

from app.tests.conftest import make_forecast

OVERVIEW = "/api/v1/weather/overview"
NAIROBI = {"latitude": -1.2833, "longitude": 36.8167, "name": "Nairobi", "country": "Kenya"}


def test_overview_has_real_provider_values(client):
    body = client.get(OVERVIEW, params=NAIROBI).json()
    assert body["location"]["name"] == "Nairobi"
    cur = body["current"]
    assert cur["temperature"] == 21.0 and cur["feels_like"] == 22.4 and cur["humidity"] == 58
    assert cur["condition"] == {"code": 2, "description": "Partly cloudy", "icon": "partly"}
    assert cur["wind_direction"] == "E" and cur["pressure"] == 1013.0
    assert (cur["temp_min"], cur["temp_max"], cur["uv_index"]) == (14.0, 24.0, 9.0)
    assert body["meta"]["provider"] == "Open-Meteo" and "CC BY 4.0" in body["meta"]["attribution"]
    assert body["meta"]["stale"] is False
    assert body["alerts"]["available"] is False


def test_hourly_window_is_24_hours_starting_at_current_local_hour(client):
    hourly = client.get(OVERVIEW, params=NAIROBI).json()["hourly"]
    assert len(hourly) == 24
    assert hourly[0]["time"].startswith("2026-10-12T14:00") and hourly[0]["time"].endswith("+03:00")
    assert hourly[-1]["time"].startswith("2026-10-13T13:00")


def test_seven_daily_entries_with_weekdays(client):
    daily = client.get(OVERVIEW, params=NAIROBI).json()["daily"]
    assert len(daily) == 7
    assert (daily[0]["date"], daily[0]["weekday"]) == ("2026-10-12", "Mon")  # 12 Oct 2026 is a Monday
    assert daily[2]["condition"]["description"] == "Light rain"


@pytest.mark.parametrize(
    ("tz", "current", "start", "offset", "expected"),
    [
        ("America/New_York", "2027-01-15T09:30", "2027-01-15", -18000, "-05:00"),
        ("Europe/London", "2026-07-01T12:00", "2026-07-01", 3600, "+01:00"),  # daylight saving
        ("Asia/Kolkata", "2026-10-12T20:10", "2026-10-12", 19800, "+05:30"),  # half-hour offset
    ],
)
def test_timestamps_use_the_locations_own_timezone(client, provider, tz, current, start, offset, expected):
    provider.forecast = make_forecast(tz=tz, current_time=current, start_date=start, offset=offset)
    body = client.get(OVERVIEW, params={"latitude": 10, "longitude": 10}).json()
    assert body["current"]["observed_at"].endswith(expected)
    assert body["location"]["timezone"] == tz
    assert body["daily"][0]["date"] == start
    assert body["current"]["observed_at"].startswith(current[:13])


def test_unit_conversion_through_the_api(client):
    body = client.get(OVERVIEW, params={**NAIROBI, "temperature_unit": "fahrenheit", "unit_system": "imperial"}).json()
    assert body["current"]["temperature"] == 69.8  # 21 C
    assert body["current"]["wind_speed"] == 11.2  # 18 km/h
    assert body["current"]["pressure"] == 29.91  # 1013 hPa
    assert body["units"] == {"temperature": "°F", "wind_speed": "mph", "precipitation": "in", "pressure": "inHg"}


def test_celsius_with_imperial_wind_is_allowed(client):
    body = client.get(OVERVIEW, params={**NAIROBI, "unit_system": "imperial"}).json()
    assert body["current"]["temperature"] == 21.0 and body["units"]["wind_speed"] == "mph"


def test_missing_optional_fields_become_null_never_zero(client, provider):
    provider.forecast = make_forecast(
        drop_current=("pressure_msl", "wind_gusts_10m", "relative_humidity_2m"),
        drop_hourly=("precipitation_probability",),
        drop_daily=("uv_index_max",),
    )
    body = client.get(OVERVIEW, params=NAIROBI).json()
    cur = body["current"]
    assert cur["pressure"] is None and cur["wind_gusts"] is None and cur["humidity"] is None
    assert cur["uv_index"] is None
    assert all(h["precipitation_probability"] is None for h in body["hourly"])
    assert not any(i["type"] in ("rain", "uv") for i in body["insights"])  # no claims without data


def test_null_values_inside_a_series_stay_null(client, provider):
    provider.forecast["hourly"]["temperature_2m"][14] = None
    provider.forecast["current"]["temperature_2m"] = None
    body = client.get(OVERVIEW, params=NAIROBI).json()
    assert body["hourly"][0]["temperature"] is None and body["current"]["temperature"] is None


def test_unknown_weather_code_is_labelled_honestly(client, provider):
    provider.forecast["current"]["weather_code"] = 1234
    cond = client.get(OVERVIEW, params=NAIROBI).json()["current"]["condition"]
    assert cond["description"] == "Conditions unavailable" and cond["icon"] == "unknown"


def test_insights_come_from_the_data(client, provider):
    provider.forecast = make_forecast(prob={16: 80})  # hour index 16 = 16:00 today
    insights = {i["type"]: i for i in client.get(OVERVIEW, params=NAIROBI).json()["insights"]}
    assert "16:00" in insights["rain"]["message"]
    assert "uv" in insights  # today's UV 9 -> very high


@pytest.mark.parametrize(
    "params",
    [
        {"latitude": 91, "longitude": 0}, {"latitude": -91, "longitude": 0},
        {"latitude": 0, "longitude": 181}, {"latitude": 0, "longitude": -181},
        {"latitude": "abc", "longitude": 0}, {"latitude": 0},
        {"latitude": 0, "longitude": 0, "temperature_unit": "kelvin"},
        {"latitude": 0, "longitude": 0, "unit_system": "martian"},
        {"latitude": 0, "longitude": 0, "name": "x" * 101},
    ],
)  # fmt: skip
def test_invalid_parameters_rejected(client, provider, params):
    response = client.get(OVERVIEW, params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert provider.calls == []


def test_valid_boundary_coordinates(client):
    assert client.get(OVERVIEW, params={"latitude": 90, "longitude": -180}).status_code == 200


@pytest.mark.parametrize(
    ("setup", "status", "code"),
    [
        (lambda p: setattr(p, "forecast_raise", httpx.ReadTimeout("slow")), 504, "provider_timeout"),
        (lambda p: setattr(p, "forecast_raise", httpx.ConnectError("dns")), 502, "provider_unavailable"),
        (lambda p: setattr(p, "forecast_status", 429), 503, "provider_rate_limited"),
        (lambda p: setattr(p, "forecast_status", 500), 502, "provider_unavailable"),
        (lambda p: setattr(p, "forecast_status", 400), 502, "provider_bad_response"),
        (lambda p: setattr(p, "forecast_text", "<html>not json"), 502, "provider_bad_response"),
        (lambda p: setattr(p, "forecast_text", "[1, 2, 3]"), 502, "provider_bad_response"),
        (lambda p: p.forecast.pop("daily"), 502, "provider_bad_response"),
        (lambda p: p.forecast["hourly"].update(time=[]), 502, "provider_bad_response"),
        (lambda p: p.forecast["current"].update(time="garbage"), 502, "provider_bad_response"),
    ],
)  # fmt: skip
def test_provider_failures_map_to_friendly_errors(client, provider, setup, status, code):
    setup(provider)
    response = client.get(OVERVIEW, params=NAIROBI)
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code and error["message"]
    assert "Traceback" not in response.text and "httpx" not in response.text


def test_forecast_is_cached_and_shared_across_unit_choices(client, provider):
    client.get(OVERVIEW, params=NAIROBI)
    client.get(OVERVIEW, params={**NAIROBI, "temperature_unit": "fahrenheit"})
    assert provider.forecast_calls == 1


def test_current_hourly_daily_endpoints_return_only_their_section(client):
    cur = client.get("/api/v1/weather/current", params=NAIROBI).json()
    hourly = client.get("/api/v1/weather/hourly", params=NAIROBI).json()
    daily = client.get("/api/v1/weather/daily", params=NAIROBI).json()
    assert "current" in cur and "hourly" not in cur
    assert len(hourly["hourly"]) == 24 and "daily" not in hourly
    assert len(daily["daily"]) == 7 and "current" not in daily


def test_alerts_endpoint_is_honest_about_availability(client):
    body = client.get("/api/v1/weather/alerts").json()
    assert body["available"] is False and body["items"] == []


LOC = {"name": "Nairobi", "country": "Kenya", "latitude": -1.28, "longitude": 36.81}


def test_compare_two_locations(client):
    body = client.post(
        "/api/v1/weather/compare", json={"locations": [LOC, {**LOC, "name": "Mombasa", "latitude": -4.04}]}
    ).json()
    assert [i["location"]["name"] for i in body["items"]] == ["Nairobi", "Mombasa"]
    assert all(i["current"]["temperature"] == 21.0 and i["error"] is None for i in body["items"])


def test_compare_survives_one_failing_city(client, provider):
    provider.failing_latitudes = {-4.04}
    items = client.post(
        "/api/v1/weather/compare", json={"locations": [LOC, {**LOC, "name": "Mombasa", "latitude": -4.04}]}
    ).json()["items"]
    assert items[0]["error"] is None and items[1]["current"] is None and items[1]["error"]


def test_compare_needs_two_to_five(client):
    assert client.post("/api/v1/weather/compare", json={"locations": [LOC]}).status_code == 422
    assert client.post("/api/v1/weather/compare", json={"locations": [LOC] * 6}).status_code == 422
