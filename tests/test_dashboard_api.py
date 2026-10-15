import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.app as dashboard
from backend.app import app


class DashboardApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_experiment_status_is_not_matched_as_an_experiment_id(self):
        response = self.client.get("/api/experiments/status")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["active"])

    def test_api_root_has_discovery_links(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["docs"], "/docs")
        self.assertEqual(response.json()["health"], "/api/health")

    def test_preview_validates_service_and_fault_without_running_it(self):
        valid = self.client.post("/api/experiments/preview", json={
            "service": "cartservice",
            "action": "pod-failure",
            "duration_s": 15,
            "environment": "simulated",
        })
        invalid = self.client.post("/api/experiments/preview", json={
            "service": "missing-service",
            "action": "pod-failure",
            "duration_s": 15,
            "environment": "simulated",
        })

        self.assertEqual(valid.status_code, 200)
        self.assertTrue(valid.json()["validated"])
        self.assertEqual(invalid.status_code, 422)

    def test_start_requires_confirmation_before_queuing(self):
        response = self.client.post("/api/experiments/start", json={
            "service": "cartservice",
            "action": "pod-failure",
            "duration_s": 15,
            "environment": "simulated",
        })

        self.assertEqual(response.status_code, 409)
        self.assertIn("confirm", response.json()["detail"].lower())

    def test_saved_run_detail_returns_every_recorded_weakness(self):
        result = {
            "run_id": "sample-run",
            "env": "kubernetes",
            "weaknesses": [
                {"service": "cartservice", "action": "network-delay", "score": 26.4},
                {"service": "productcatalogservice", "action": "pod-failure", "score": 47.5},
                {"service": "currencyservice", "action": "cpu-stress", "score": 75},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "results.json").write_text(json.dumps(result), encoding="utf-8")
            with patch.object(dashboard, "_run_dir", return_value=run_dir):
                response = self.client.get("/api/runs/sample-run")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["weaknesses"]), 3)


if __name__ == "__main__":
    unittest.main()
