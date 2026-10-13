# SkyCast

A weather forecasting web app: search any city, see current conditions, a 24-hour forecast and a 7-day forecast, save favorites, compare cities, and switch units. Real data comes from [Open-Meteo](https://open-meteo.com/).

## Features
- City search with suggestions (`Nairobi`, `Nairobi, Kenya`, or `-1.29, 36.82`), no-results state, optional "Use my location" (only on click; coordinates rounded to ~1 km)
- Current weather, hourly (next 24 h) and 7-day forecast, correct in each location's own timezone
- Insights generated from the numbers by visible rules (rain, warmest/coolest, big changes, UV, wind)
- °C/°F and metric/imperial, saved per browser
- Favorites saved in the database (add, remove, reorder), compare 2-5 cities
- Loading skeleton, empty state, friendly errors with retry, "older data" label when the provider is down
- Day/night sky themes, responsive layout, keyboard and screen-reader support, reduced-motion support

**Weather alerts:** Open-Meteo provides no official alerts, so the app says so honestly. A regional alert provider can be added in `app/services/`.

## Stack
FastAPI, Uvicorn, Pydantic, HTTPX, SQLAlchemy 2, Alembic, SQLite (dev) / PostgreSQL (prod), plain HTML/CSS/JS (ES modules).

## Architecture
```
Browser (frontend/) --> FastAPI /api/v1 --> routes -> services -> Open-Meteo
                                              \-> repositories -> database
```
| Folder | Job |
|---|---|
| `app/api/routes` | HTTP only: parse requests, return responses |
| `app/services` | Open-Meteo calls, response validation, unit conversion, insights |
| `app/repositories` | All database queries |
| `app/models`, `app/schemas` | Database tables / request-response shapes |
| `app/core` | Settings, logging, errors, cache, rate limiter |
| `alembic/` | Database migrations |
| `frontend/` | The dashboard, served by FastAPI at `/` |

Design choices: no accounts in v1. Favorites and preferences belong to a random id kept in an httpOnly cookie, so no personal data is collected (clearing cookies loses favorites). The forecast is cached in memory for 10 minutes (geocoding 24 h) in metric units, so changing units never re-calls the provider. Simultaneous identical requests share one upstream call. No Redis until you run several server instances.

## Prerequisites
Python 3.12+, Git. Optional: Node 20+ (frontend tests), Docker (PostgreSQL / container).

## Setup (Windows PowerShell; on Mac/Linux use `source .venv/bin/activate` and `cp`)
```powershell
cd skycast
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000 (dashboard) and http://127.0.0.1:8000/docs (interactive API docs).

If PowerShell blocks activation: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Configuration (`.env`)
See `.env.example`. Key variables: `APP_ENV` (`development`/`production`), `DATABASE_URL`, `CORS_ORIGINS`, `RATE_LIMIT_PER_MINUTE`, `OPENMETEO_*` URLs. Never commit `.env`.

## Database
`alembic upgrade head` creates the tables (SQLite file `skycast.db` by default). Change models, then `alembic revision --autogenerate -m "message"` and review the file before applying. PostgreSQL: set `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/skycast`.

## API (`/api/v1`)
`GET /health` · `GET /health/providers` · `GET /locations/search?q=` · `GET /weather/overview|current|hourly|daily?latitude=&longitude=&temperature_unit=&unit_system=` · `GET /weather/alerts` · `POST /weather/compare` · `GET|POST /favorites` · `PUT /favorites/order` · `DELETE /favorites/{id}` · `GET|PUT /preferences`. Full schemas at `/docs`. Every error uses `{"error": {"code", "message", "details?"}}`.

## Tests
```powershell
pytest                          # 97 backend tests, external API mocked
npm run test:frontend           # 13 frontend tests (needs Node)
ruff check .                    # lint
python scripts/smoke_live.py    # REAL Open-Meteo call for Nairobi (the one network check)
pip-audit -r requirements.txt --no-deps
```

## Troubleshooting
- `No module named app`: run commands from the `skycast` folder.
- `ZoneInfoNotFoundError`: `pip install tzdata`.
- "The weather service is unreachable": check your internet/firewall; run `python scripts/smoke_live.py`.
- Favorites vanish: browser cookies were cleared (by design, no accounts yet).
- Port busy: `uvicorn app.main:app --port 8001`.

## Deployment (example: Render, Railway or Fly.io, same idea)
1. Push to GitHub (`.env` is git-ignored).
2. Create a PostgreSQL database on the host; copy its connection string.
3. Create a Web Service from the repo using the Dockerfile (or build `pip install -r requirements.txt`, start `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`).
4. Set environment variables on the host: `APP_ENV=production`, `DATABASE_URL=postgresql+psycopg://...`, `CORS_ORIGINS=https://your-domain`.
5. Health check path: `/api/v1/health`. HTTPS is provided by the host; production mode adds HSTS and Secure cookies.

Local PostgreSQL: `$env:POSTGRES_PASSWORD="choose-one"; docker compose up --build`.

**Production checklist:** `APP_ENV=production` · strong DB password in host secrets · HTTPS on · CORS set to your domain only · `pip-audit` clean · scheduled database backups (managed Postgres snapshots, or `pg_dump -Fc skycast > backup.dump`; restore with `pg_restore -d skycast backup.dump`; test a restore) · logs monitored.

## Known limitations
- Rate limiting and cache are per-process memory (fine for one instance).
- No official weather alerts. No accounts. Favorites tied to a browser cookie.
- Not yet tested on a real PostgreSQL server, in Docker, or in browsers by the author of this scaffold: do the steps above and report issues.

## Future improvements
Accounts, alert provider, weather map, historical charts, air quality, PWA/offline, background refresh, translations, CI/CD.

## Data attribution and licensing
Weather data by [Open-Meteo.com](https://open-meteo.com/), licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); attribution is shown in the app footer. Open-Meteo's free API is for **non-commercial** use with fair-use limits; a commercial product needs one of their paid plans (set `OPENMETEO_API_KEY` and the customer API URLs).
