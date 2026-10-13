from app.tests.conftest import NAIROBI, PARIS_FR, PARIS_TX

URL = "/api/v1/locations/search"


def test_successful_search(client, provider):
    body = client.get(URL, params={"q": "Nairobi"}).json()
    assert body["query"] == "Nairobi"
    first = body["results"][0]
    assert (first["name"], first["country"], first["timezone"]) == ("Nairobi", "Kenya", "Africa/Nairobi")


def test_unknown_location_returns_empty_results_not_an_error(client, provider):
    provider.geocoding = {"generationtime_ms": 0.4}  # Open-Meteo omits "results" when nothing matches
    response = client.get(URL, params={"q": "Zzzzxqwv"})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_city_and_country_filters_ambiguous_names(client, provider):
    provider.geocoding = {"results": [PARIS_FR, PARIS_TX]}
    assert [r["country"] for r in client.get(URL, params={"q": "Paris, Texas"}).json()["results"]] == ["United States"]
    assert [r["country_code"] for r in client.get(URL, params={"q": "Paris, FR"}).json()["results"]] == ["FR"]
    assert len(client.get(URL, params={"q": "Paris"}).json()["results"]) == 2


def test_country_hint_that_matches_nothing_is_empty(client, provider):
    provider.geocoding = {"results": [NAIROBI]}
    assert client.get(URL, params={"q": "Nairobi, Peru"}).json()["results"] == []


def test_coordinates_search_needs_no_provider_call(client, provider):
    body = client.get(URL, params={"q": "-1.2921, 36.8219"}).json()
    assert body["results"][0]["latitude"] == -1.2921
    assert provider.calls == []


def test_malformed_provider_entries_are_skipped(client, provider):
    provider.geocoding = {"results": [{"name": "Broken"}, NAIROBI]}
    assert [r["name"] for r in client.get(URL, params={"q": "Nairobi"}).json()["results"]] == ["Nairobi"]


def test_query_validation(client):
    for q in ("a", "x" * 101):
        response = client.get(URL, params={"q": q})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
    assert client.get(URL).status_code == 422


def test_geocoding_results_are_cached(client, provider):
    client.get(URL, params={"q": "Nairobi"})
    client.get(URL, params={"q": "nairobi"})
    assert len(provider.calls) == 1
