from api.app.routes.health import health


def test_health() -> None:
    response = health()
    assert response["status"] == "ok"
