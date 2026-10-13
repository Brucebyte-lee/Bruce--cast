"""Live check against the REAL Open-Meteo API for Nairobi. Run on your own machine:

    python scripts/smoke_live.py

Automated tests never call the real API; this script is how you confirm real data works.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.core.cache import TTLCache  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.services.units import Units  # noqa: E402
from app.services.weather import WeatherService  # noqa: E402


async def main() -> None:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, connect=5)) as http:
        service = WeatherService(http, settings, TTLCache())
        places = await service.search_locations("Nairobi, Kenya")
        print(f"Search found {len(places)} place(s); first: {places[0].name}, {places[0].country} "
              f"({places[0].latitude}, {places[0].longitude}) tz={places[0].timezone}")
        o = await service.get_overview(places[0].latitude, places[0].longitude, Units(), places[0].name, places[0].country)
        c = o.current
        print(f"Now {c.observed_at:%Y-%m-%d %H:%M %z}: {c.temperature}{o.units.temperature}, {c.condition.description}, "
              f"humidity {c.humidity}%, wind {c.wind_speed} {o.units.wind_speed} {c.wind_direction}")
        print(f"Hourly entries: {len(o.hourly)}, daily entries: {len(o.daily)}")
        for day in o.daily:
            print(f"  {day.weekday} {day.date}: {day.temp_min}..{day.temp_max}{o.units.temperature} {day.condition.description}")
        for insight in o.insights:
            print("  insight:", insight.message)


asyncio.run(main())
