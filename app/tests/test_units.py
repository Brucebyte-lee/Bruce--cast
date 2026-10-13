import pytest

from app.services.units import Units, c_to_f, compass, hpa_to_inhg, kmh_to_mph, mm_to_inches


def test_celsius_to_fahrenheit_known_values():
    assert c_to_f(0) == 32
    assert c_to_f(100) == 212
    assert c_to_f(-40) == -40


def test_other_conversions():
    assert kmh_to_mph(100) == pytest.approx(62.1371)
    assert mm_to_inches(25.4) == pytest.approx(1.0)
    assert hpa_to_inhg(1013.25) == pytest.approx(29.92, abs=0.01)


def test_missing_values_stay_missing_not_zero():
    units = Units("fahrenheit", "imperial")
    assert units.temp(None) is None
    assert units.wind(None) is None
    assert units.precip(None) is None
    assert units.pressure(None) is None
    assert compass(None) is None


def test_metric_celsius_is_passthrough_and_labels():
    units = Units()
    assert units.temp(21.04) == 21.0
    assert units.labels == {"temperature": "°C", "wind_speed": "km/h", "precipitation": "mm", "pressure": "hPa"}


def test_imperial_labels():
    assert Units("fahrenheit", "imperial").labels["wind_speed"] == "mph"


def test_temperature_delta_has_no_32_offset():
    assert Units("fahrenheit").temp_delta(5) == 9.0
    assert Units("celsius").temp_delta(5) == 5.0


@pytest.mark.parametrize(
    ("degrees", "label"), [(0, "N"), (90, "E"), (95, "E"), (180, "S"), (270, "W"), (359, "N"), (360, "N"), (225, "SW")]
)
def test_compass(degrees, label):
    assert compass(degrees) == label
