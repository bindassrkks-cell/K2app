import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import lite_web


class LiteStandaloneWebTests(unittest.TestCase):
    def test_health_and_session_start_without_telegram_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {
                "LITE_API_DB_FILE": str(Path(temp_dir) / "lite.sqlite3"),
                "LITE_DOWNLOAD_DIR": str(Path(temp_dir) / "downloads"),
            }
            with patch.dict(os.environ, env, clear=True):
                self.assertNotIn("TELEGRAM_BOT_TOKEN", os.environ)
                self.assertNotIn("OWNER_CHAT_ID", os.environ)
                with TestClient(lite_web.app) as client:
                    health = client.get("/health")
                    self.assertEqual(health.status_code, 200)
                    self.assertEqual(
                        health.json(),
                        {"service": "k2app-lite-api", "mode": "api"},
                    )

                    session = client.post("/api/v1/auth/session")
                    self.assertEqual(session.status_code, 200, session.text)
                    self.assertEqual(session.json()["session_type"], "device")
                    self.assertEqual(session.json()["token_type"], "Bearer")
                    self.assertTrue(session.json()["access_token"])
                    self.assertEqual(
                        client.post("/telegram/webhook", json={}).status_code,
                        404,
                    )


if __name__ == "__main__":
    unittest.main()
