from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_dist(root):
    dist = root / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa-shell</html>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")
    return dist


def test_mount_frontend_serves_assets_and_spa_routes(tmp_path):
    from app.main import mount_frontend

    dist = _build_dist(tmp_path)
    app = FastAPI()

    assert mount_frontend(app, dist) is True

    client = TestClient(app)
    assert client.get("/").text == "<html>spa-shell</html>"
    assert client.get("/assets/app.js").text == "console.log('ok')"
    assert client.get("/live-watch").text == "<html>spa-shell</html>"
    assert client.get("/api/not-a-real-endpoint").status_code == 404


def test_mount_frontend_skips_missing_build(tmp_path):
    from app.main import mount_frontend

    app = FastAPI()

    assert mount_frontend(app, tmp_path / "missing") is False
