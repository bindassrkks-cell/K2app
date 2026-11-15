import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sqlite3

from fastapi.testclient import TestClient

import web

TOKEN = "12345:" + "A" * 30
OWNER = "8640134736"


class FakeApi:
    calls = []

    def __init__(self, token, base_url):
        self.token = token

    async def call(self, method, payload=None, **kwargs):
        self.calls.append((method, payload))
        if method == "getMe":
            return {"username": "k2app_test_bot"}
        return True

    async def close(self):
        pass


class WebhookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": TOKEN,
            "OWNER_CHAT_ID": OWNER,
            "BOT_STATE_FILE": str(Path(self.temp.name) / "state.sqlite3"),
            "PUBLIC_BASE_URL": "https://k2app.example.com",
            "WEBHOOK_SECRET": "test-secret-1234567890",
        }, clear=True)
        self.env.start()
        FakeApi.calls = []
        self.api_patch = patch.object(web, "TelegramApi", FakeApi)
        self.api_patch.start()
        self.client_context = TestClient(web.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.api_patch.stop()
        self.env.stop()
        self.temp.cleanup()

    def test_startup_registers_webhook_without_dropping_pending_updates(self):
        method, payload = FakeApi.calls[-1]
        self.assertEqual(method, "setWebhook")
        self.assertEqual(payload["url"], "https://k2app.example.com/telegram/webhook")
        self.assertEqual(payload["allowed_updates"], ["message", "callback_query"])
        self.assertEqual(payload["max_connections"], 1)
        self.assertFalse(payload["drop_pending_updates"])
        self.assertEqual(payload["secret_token"], "test-secret-1234567890")

    def test_health_and_status_are_minimal_and_public(self):
        for route in ("/health", "/api/status"):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {
                "service": "k2app", "mode": "webhook",
                "bot_username": "k2app_test_bot", "bot_url": "https://t.me/k2app_test_bot",
            })

    def test_secret_required_and_valid_update_persisted_before_ack(self):
        update = {"update_id": 42, "message": {"chat": {"id": int(OWNER), "type": "private"}, "text": "/start"}}
        self.assertEqual(self.client.post("/telegram/webhook", json=update).status_code, 403)
        headers = {"X-Telegram-Bot-Api-Secret-Token": "test-secret-1234567890"}
        response = self.client.post("/telegram/webhook", content=json.dumps(update), headers=headers)
        self.assertEqual(response.status_code, 200)
        duplicate = self.client.post("/telegram/webhook", json=update, headers=headers)
        self.assertEqual(duplicate.status_code, 200)

    def test_inline_callback_update_is_accepted(self):
        update = {
            "update_id": 43,
            "callback_query": {
                "id": "callback-1", "data": "k2:abc_123:0",
                "message": {"chat": {"id": int(OWNER), "type": "private"}},
            },
        }
        headers = {"X-Telegram-Bot-Api-Secret-Token": "test-secret-1234567890"}
        self.assertTrue(web._valid_update(update))
        self.assertEqual(self.client.post("/telegram/webhook", json=update, headers=headers).status_code, 200)

    def test_malformed_updates_and_oversized_content_are_rejected(self):
        headers = {"X-Telegram-Bot-Api-Secret-Token": "test-secret-1234567890"}
        self.assertEqual(self.client.post("/telegram/webhook", content=b"{", headers=headers).status_code, 400)
        self.assertEqual(self.client.post("/telegram/webhook", json={"update_id": "x"}, headers=headers).status_code, 400)
        response = self.client.post("/telegram/webhook", content=b" " * (web.MAX_BODY_BYTES + 1), headers=headers)
        self.assertEqual(response.status_code, 413)

    def test_chunked_oversized_body_is_rejected(self):
        headers = {"X-Telegram-Bot-Api-Secret-Token": "test-secret-1234567890", "Transfer-Encoding": "chunked"}
        response = self.client.post("/telegram/webhook", content=(b" " * 32 for _ in range(web.MAX_BODY_BYTES // 32 + 1)), headers=headers)
        self.assertEqual(response.status_code, 413)

    def test_lite_api_requires_bearer_token(self):
        response = self.client.post("/api/v1/jobs", json={"url": "https://example.com/video"})
        self.assertEqual(response.status_code, 401)

    def test_direct_lite_sessions_are_issued_without_telegram_pairing(self):
        first = self.client.post("/api/v1/auth/session")
        second = self.client.post("/api/v1/auth/session")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.headers["cache-control"], "no-store")
        self.assertEqual(first.json()["session_type"], "device")
        self.assertNotEqual(first.json()["access_token"], second.json()["access_token"])
        self.assertIsNotNone(self.client.app.state.lite_store.authenticate(first.json()["access_token"]))

    def test_legacy_telegram_pairing_is_disabled_for_lite(self):
        response = self.client.post("/api/v1/auth/pair", json={"code": "not-a-pair-code"})
        self.assertEqual(response.status_code, 410)

    def test_completed_payload_is_wiped_and_done_history_bounded(self):
        store = self.client.app.state.store
        for update_id in range(web.DONE_UPDATE_RETENTION + 3):
            self.assertTrue(store.insert({"update_id": update_id, "message": {"text": "private payload"}}))
            store.complete(update_id)
        with sqlite3.connect(store.path) as db:
            rows = db.execute("SELECT update_id,payload FROM webhook_updates ORDER BY update_id").fetchall()
        self.assertEqual(len(rows), web.DONE_UPDATE_RETENTION)
        self.assertEqual(rows[-1][1], "")


if __name__ == "__main__":
    unittest.main()
