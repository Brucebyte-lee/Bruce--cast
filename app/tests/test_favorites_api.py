from fastapi.testclient import TestClient

FAV = "/api/v1/favorites"
NAIROBI = {
    "name": "Nairobi",
    "country": "Kenya",
    "latitude": -1.28333,
    "longitude": 36.81667,
    "timezone": "Africa/Nairobi",
}
MOMBASA = {"name": "Mombasa", "country": "Kenya", "latitude": -4.0435, "longitude": 39.6682}


def test_create_list_and_persist(client):
    created = client.post(FAV, json=NAIROBI)
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Nairobi" and body["latitude"] == -1.2833 and body["position"] == 0  # rounded to 4 dp
    assert [f["id"] for f in client.get(FAV).json()] == [body["id"]]


def test_duplicate_favorite_is_rejected(client):
    client.post(FAV, json=NAIROBI)
    again = client.post(FAV, json={**NAIROBI, "latitude": -1.283334})  # same place after rounding
    assert again.status_code == 409 and again.json()["error"]["code"] == "duplicate_favorite"
    assert len(client.get(FAV).json()) == 1


def test_delete_favorite(client):
    fav_id = client.post(FAV, json=NAIROBI).json()["id"]
    assert client.delete(f"{FAV}/{fav_id}").status_code == 204
    assert client.get(FAV).json() == []
    missing = client.delete(f"{FAV}/{fav_id}")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "favorite_not_found"


def test_visitors_cannot_see_or_delete_each_others_favorites(make_client):
    alice = make_client()
    alice_id = alice.post(FAV, json=NAIROBI).json()["id"]
    bob = TestClient(alice.app)  # a second browser (separate cookie jar) using the SAME app and database
    assert bob.get(FAV).json() == []
    assert bob.delete(f"{FAV}/{alice_id}").status_code == 404
    assert bob.put(f"{FAV}/order", json={"ids": [alice_id]}).status_code == 422
    assert len(alice.get(FAV).json()) == 1
    bob.close()


def test_tampered_cookie_gets_a_fresh_identity(client):
    client.post(FAV, json=NAIROBI)
    client.cookies.set("skycast_client", "not-a-uuid")
    assert client.get(FAV).json() == []


def test_cookie_is_httponly_and_samesite(make_client):
    response = make_client().get(FAV)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_reorder_favorites(client):
    a = client.post(FAV, json=NAIROBI).json()["id"]
    b = client.post(FAV, json=MOMBASA).json()["id"]
    reordered = client.put(f"{FAV}/order", json={"ids": [b, a]})
    assert [f["id"] for f in reordered.json()] == [b, a]
    assert [f["id"] for f in client.get(FAV).json()] == [b, a]


def test_reorder_must_list_every_favorite_once(client):
    a = client.post(FAV, json=NAIROBI).json()["id"]
    client.post(FAV, json=MOMBASA)
    for ids in ([a], [a, a], [a, 9999]):
        response = client.put(f"{FAV}/order", json={"ids": ids})
        assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_order"


def test_favorite_limit(make_client):
    client = make_client(max_favorites_per_client=2)
    client.post(FAV, json=NAIROBI), client.post(FAV, json=MOMBASA)
    response = client.post(FAV, json={"name": "Kisumu", "latitude": -0.09, "longitude": 34.77})
    assert response.status_code == 409 and response.json()["error"]["code"] == "favorite_limit_reached"


def test_validation(client):
    bad = [
        {**NAIROBI, "name": ""}, {**NAIROBI, "name": "x" * 101}, {**NAIROBI, "latitude": 95},
        {**NAIROBI, "longitude": -200}, {"name": "No coords"}, {**NAIROBI, "latitude": "north"},
    ]  # fmt: skip
    for payload in bad:
        response = client.post(FAV, json=payload)
        assert response.status_code == 422, payload
        assert response.json()["error"]["code"] == "validation_error"
    assert client.get(FAV).json() == []


def test_names_are_cleaned_of_control_characters(client):
    saved = client.post(FAV, json={**NAIROBI, "name": "  Nai\x00robi \n City "}).json()
    assert saved["name"] == "Nai robi City"


def test_html_in_names_is_stored_as_plain_text_for_the_frontend_to_escape(client):
    saved = client.post(FAV, json={**NAIROBI, "name": "<script>alert(1)</script>"}).json()
    assert saved["name"] == "<script>alert(1)</script>"  # frontend renders with textContent, never innerHTML


def test_preferences_defaults_and_save(client):
    assert client.get("/api/v1/preferences").json() == {
        "temperature_unit": "celsius",
        "unit_system": "metric",
        "theme": "system",
    }
    saved = client.put(
        "/api/v1/preferences", json={"temperature_unit": "fahrenheit", "unit_system": "imperial", "theme": "dark"}
    )
    assert saved.status_code == 200
    assert client.get("/api/v1/preferences").json()["temperature_unit"] == "fahrenheit"
    assert client.put("/api/v1/preferences", json={"theme": "neon"}).status_code == 422
