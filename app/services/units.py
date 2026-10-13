"""Unit conversion. The provider data is always fetched in metric (Celsius, km/h, mm, hPa);
we convert here so one cached upstream response serves every unit preference.

Rule: a missing value (None) stays None. We never turn "unknown" into zero.
"""

from dataclasses import dataclass

_COMPASS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]  # fmt: skip


def c_to_f(celsius: float | None) -> float | None:
    return None if celsius is None else celsius * 9 / 5 + 32


def kmh_to_mph(kmh: float | None) -> float | None:
    return None if kmh is None else kmh * 0.621371


def mm_to_inches(mm: float | None) -> float | None:
    return None if mm is None else mm / 25.4


def hpa_to_inhg(hpa: float | None) -> float | None:
    return None if hpa is None else hpa * 0.02953


def compass(degrees: float | None) -> str | None:
    """Convert a wind direction in degrees (0 = from the north) to a compass label."""
    if degrees is None:
        return None
    return _COMPASS[int((degrees % 360) / 22.5 + 0.5) % 16]


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


@dataclass(frozen=True)
class Units:
    temperature: str = "celsius"  # "celsius" | "fahrenheit"
    system: str = "metric"  # "metric" | "imperial"

    @property
    def imperial(self) -> bool:
        return self.system == "imperial"

    def temp(self, celsius: float | None) -> float | None:
        return _round(c_to_f(celsius) if self.temperature == "fahrenheit" else celsius, 1)

    def temp_delta(self, celsius_delta: float | None) -> float | None:
        """Convert a temperature DIFFERENCE (no +32 offset)."""
        if celsius_delta is None:
            return None
        return _round(celsius_delta * 9 / 5 if self.temperature == "fahrenheit" else celsius_delta, 1)

    def wind(self, kmh: float | None) -> float | None:
        return _round(kmh_to_mph(kmh) if self.imperial else kmh, 1)

    def precip(self, mm: float | None) -> float | None:
        return _round(mm_to_inches(mm), 2) if self.imperial else _round(mm, 1)

    def pressure(self, hpa: float | None) -> float | None:
        return _round(hpa_to_inhg(hpa), 2) if self.imperial else _round(hpa, 1)

    @property
    def labels(self) -> dict[str, str]:
        return {
            "temperature": "°F" if self.temperature == "fahrenheit" else "°C",
            "wind_speed": "mph" if self.imperial else "km/h",
            "precipitation": "in" if self.imperial else "mm",
            "pressure": "inHg" if self.imperial else "hPa",
        }
