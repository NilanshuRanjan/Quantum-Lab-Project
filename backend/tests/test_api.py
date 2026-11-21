import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


class TestFastAPIIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

    def test_summary_endpoint(self) -> None:
        response = self.client.get('/api/summary')
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()['appliance_count'], 0)

    def test_browser_optional_resources_do_not_return_not_found(self) -> None:
        self.assertEqual(self.client.get('/favicon.ico').status_code, 204)
        self.assertEqual(
            self.client.get('/.well-known/appspecific/com.chrome.devtools.json').status_code,
            204,
        )

    def test_optimize_endpoint_runs_classical_suite(self) -> None:
        response = self.client.post('/api/optimize', json={'method': 'all'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('results', payload)
        self.assertEqual(len(payload['results']), 3)
        self.assertTrue(all(item['feasible'] for item in payload['results']))


if __name__ == '__main__':
    unittest.main()
