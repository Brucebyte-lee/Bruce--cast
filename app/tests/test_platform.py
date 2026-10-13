"""Health, error-format, security and database-failure behaviour."""

from sqlalchemy.exc import OperationalError


def test_health_ok(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok" and body["database"] == "ok" and body["version"]


def test_health_reports_database_failure_without_leaking_details(make_client):
    from app.database.session import get_db

    class BrokenSession:
        def execute(self, *_):
            raise OperationalError("SELECT 1", {}, Exception("secret connection string"))

        def close(self):
            pass

    client = make_client()
    client.app.dependency_overrides[get_db] = lambda: BrokenSession()
    response = client.get("/api/v1/health")
    assert response.status_code == 503 and response.json()["status"] == "degraded"
    assert "secret" not in response.text


def test_provider_health_is_separate(client, provider):
    assert client.get("/api/v1/health/providers").json() == {"open_meteo": "reachable"}


def test_database_error_on_favorites_returns_safe_503(make_client):
    from app.database.session import get_db

    class Exploding:
        def scalars(self, *_):
            raise OperationalError("SELECT", {}, Exception("password=hunter2"))

        def close(self):
            pass

    client = make_client()
    client.app.dependency_overrides[get_db] = lambda: Exploding()
    response = client.get("/api/v1/favorites")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable" and "hunter2" not in response.text


def test_unknown_api_route_and_wrong_method_use_the_standard_error_shape(client):
    missing = client.get("/api/v1/nope")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
    wrong = client.post("/api/v1/health")
    assert wrong.status_code == 405 and wrong.json()["error"]["code"] == "method_not_allowed"


def test_unexpected_exception_returns_generic_500(make_client, provider):
    from app.api.deps import get_weather_service

    class Boom:
        async def get_overview(self, *a, **k):
            raise RuntimeError("internal secret detail")

    client = make_client()
    client.app.dependency_overrides[get_weather_service] = lambda: Boom()
    quiet = type(client)(client.app, raise_server_exceptions=False)
    response = quiet.get("/api/v1/weather/overview", params={"latitude": 1, "longitude": 1})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error" and "secret" not in response.text


def test_oversized_request_body_rejected(client):
    response = client.post("/api/v1/favorites", content=b"x" * 20_000, headers={"content-type": "application/json"})
    assert response.status_code == 413 and response.json()["error"]["code"] == "payload_too_large"


def test_rate_limit(make_client):
    client = make_client(rate_limit_per_minute=3)
    codes = [client.get("/api/v1/health").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    assert "retry-after" in client.get("/api/v1/health").headers


def test_security_headers(client):
    headers = client.get("/api/v1/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert "script-src 'self'" in headers["content-security-policy"]
    assert headers["x-frame-options"] == "DENY"


def test_openapi_docs_available(client):
    assert client.get("/openapi.json").json()["info"]["title"] == "SkyCast"
    assert client.get("/docs").status_code == 200


def test_production_cookie_is_secure(make_client):
    cookie = make_client(app_env="production").get("/api/v1/favorites").headers["set-cookie"].lower()
    assert "secure" in cookie
