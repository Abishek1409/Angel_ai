from unittest.mock import patch

from django.db.utils import OperationalError
from django.test import TestCase


class DbHealthCheckTests(TestCase):
    def test_returns_ok_when_database_answers(self):
        response = self.client.get("/health/db/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy", "database": "ok"})

    def test_head_request_also_checks_database(self):
        self.assertEqual(self.client.head("/health/db/").status_code, 200)

    @patch("config.health.connection")
    def test_returns_503_without_details_when_database_is_down(self, mock_connection):
        mock_connection.cursor.side_effect = OperationalError("connection to server at secret-host failed")
        with self.assertLogs("config.health", level="ERROR"):
            response = self.client.get("/health/db/")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret-host", response.content.decode())
