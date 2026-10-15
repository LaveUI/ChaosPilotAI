import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.public_demo import app


class PublicDemoTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_and_simulated_overview(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.get("/api/overview?demo=true").status_code, 200)

    def test_live_access_never_reaches_cluster(self):
        with patch("backend.app._live_snapshot") as live:
            for query in ["false", "0", "off", "no"]:
                self.assertEqual(self.client.get(f"/api/services?demo={query}").status_code, 403)
            self.assertEqual(self.client.get("/api/services?demo=false&demo=true").status_code, 403)
            live.assert_not_called()

    def test_mutations_never_start_a_worker(self):
        with patch("backend.app.threading.Thread") as worker:
            for endpoint in ["start", "stop", "preview"]:
                self.assertEqual(self.client.post(f"/api/experiments/{endpoint}", json={}).status_code, 403)
            worker.assert_not_called()

    def test_unknown_api_is_not_served_as_html(self):
        self.assertEqual(self.client.get("/api/missing").status_code, 404)
