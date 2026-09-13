import json


class TestHealth:

    def test_health_reports_endpoints(self, client):
        response = client.get("/")
        assert response.status_code == 200
        body = response.get_json()
        assert body["status"] == "running"
        assert "/api/cross-language" in body["endpoints"]


class TestCrossLanguageRoute:

    def test_missing_code_returns_400(self, client):
        response = client.post(
            "/api/cross-language",
            json={"source_language": "python", "target_language": "java"},
        )
        assert response.status_code == 400
        assert response.get_json()["success"] is False

    def test_missing_target_language_returns_400(self, client):
        response = client.post("/api/cross-language", json={"code": "x = 1"})
        assert response.status_code == 400

    def test_unsupported_language_returns_400(self, client):
        response = client.post(
            "/api/cross-language",
            json={"code": "x = 1", "source_language": "rust", "target_language": "java"},
        )
        assert response.status_code == 400

    def test_successful_conversion_returns_data(self, client):
        response = client.post(
            "/api/cross-language",
            json={
                "code": "def add(a, b):\n    return a + b\n",
                "source_language": "python",
                "target_language": "java",
            },
        )
        assert response.status_code == 200
        body = response.get_json()
        assert body["success"] is True
        assert body["data"]["code"].strip()


class TestVersionUpgradeRoute:

    def test_missing_code_returns_400(self, client):
        response = client.post("/api/version-upgrade", json={"language": "python"})
        assert response.status_code == 400

    def test_missing_language_returns_400(self, client):
        response = client.post("/api/version-upgrade", json={"code": "print 'a'"})
        assert response.status_code == 400

    def test_python2_upgrade_succeeds(self, client):
        response = client.post(
            "/api/version-upgrade",
            json={"code": "def f():\n    print 'hi'\n", "language": "python"},
        )
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert "    print('hi')" in data["code"]
        assert data["detected_version"] == "Python 2.x"
        assert data["compile_success"] is True


class TestPayloadLimit:

    def test_oversized_body_is_rejected(self, client):
        oversized = json.dumps({"code": "x" * (2 * 1024 * 1024), "language": "python"})
        response = client.post(
            "/api/version-upgrade",
            data=oversized,
            content_type="application/json",
        )
        assert response.status_code == 413
