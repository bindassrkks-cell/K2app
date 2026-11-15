import os
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import lite_api
import web

TOKEN = "12345:" + "A" * 30
OWNER = "8640134736"
MEDIA = {
    "title": "Example clip",
    "duration_seconds": 42,
    "thumbnail_url": "https://cdn.example/preview.jpg",
    "extractor": "Example",
    "choices": [
        {
            "kind": "video",
            "label": "MP4 · 720p",
            "format_selector": "v1+a1",
            "height": 720,
        }
    ],
}


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


class LiteApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": TOKEN,
            "OWNER_CHAT_ID": OWNER,
            "BOT_STATE_FILE": str(Path(self.temp.name) / "telegram.sqlite3"),
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

    def new_session(self):
        response = self.client.post("/api/v1/auth/session")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def auth(self, token):
        return {"Authorization": f"Bearer {token}"}

    def create_job(self, token, media=None):
        async def resolve(_url):
            return media or MEDIA

        with patch.object(lite_api, "_resolve_media_with_deadline", resolve):
            return self.client.post(
                "/api/v1/jobs",
                json={"url": "https://example.com/video"},
                headers=self.auth(token),
            )

    def test_tokens_are_random_hashed_and_jobs_are_isolated_between_devices(self):
        token_a = self.new_session()
        token_b = self.new_session()
        self.assertNotEqual(token_a, token_b)
        self.assertIsNone(self.client.app.state.lite_store.authenticate("not-a-token"))

        response = self.create_job(token_a)
        self.assertEqual(response.status_code, 202, response.text)
        job_id = response.json()["job_id"]
        self.assertNotIn("chooser_url", response.json())
        self.assertEqual(self.client.get(f"/api/v1/jobs/{job_id}", headers=self.auth(token_b)).status_code, 404)
        self.assertEqual(
            self.client.post(
                f"/api/v1/jobs/{job_id}/choose",
                json={"choice_index": 0},
                headers=self.auth(token_b),
            ).status_code,
            404,
        )

        with self.client.app.state.lite_store._connect() as db:
            hashes = [row[0] for row in db.execute("SELECT token_hash FROM lite_sessions").fetchall()]
        self.assertTrue(hashes)
        self.assertNotIn(token_a, hashes)
        self.assertNotIn(token_b, hashes)

    def test_session_revocation_invalidates_all_api_access(self):
        token = self.new_session()
        session = self.client.get("/api/v1/auth/session", headers=self.auth(token))
        self.assertEqual(session.status_code, 200)
        self.assertTrue(session.json()["active"])
        job_response = self.create_job(token)
        self.assertEqual(job_response.status_code, 202, job_response.text)
        job_id = job_response.json()["job_id"]
        store = self.client.app.state.lite_store
        user_id = store.authenticate(token)
        output_dir = Path(self.client.app.state.lite_output_dir)
        job_dir = output_dir / job_id
        job_dir.mkdir(parents=True)
        (job_dir / "private.mp4").write_bytes(b"private")

        response = self.client.post("/api/v1/auth/revoke", headers=self.auth(token))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["revoked"])
        self.assertFalse(job_dir.exists())
        self.assertIsNone(store.get_job(job_id, user_id))
        self.assertEqual(
            self.client.post("/api/v1/jobs", json={"url": "https://example.com/video"}, headers=self.auth(token)).status_code,
            401,
        )

    def test_job_quota_is_per_device_and_session_creation_has_global_cap(self):
        store = self.client.app.state.lite_store
        token_a = self.new_session()
        user_a = store.authenticate(token_a)
        token_b = self.new_session()
        user_b = store.authenticate(token_b)
        for _ in range(lite_api.JOBS_PER_SESSION_PER_HOUR):
            self.assertIsNone(store.record_job_attempt(user_a))
        self.assertEqual(store.record_job_attempt(user_a), "rate_limited")
        self.assertIsNone(store.record_job_attempt(user_b))

        isolated_store = lite_api.LiteApiStore(Path(self.temp.name) / "quota-test.sqlite3")
        with patch.object(lite_api, "SESSION_CREATIONS_PER_HOUR", 1):
            self.assertIsNotNone(isolated_store.create_session())
            self.assertIsNone(isolated_store.create_session())

    def test_invalid_private_url_is_rejected_before_metadata_resolution(self):
        token = self.new_session()
        resolver = AsyncMock()
        with patch.object(lite_api, "_resolve_media_with_deadline", resolver):
            response = self.client.post(
                "/api/v1/jobs",
                json={"url": "http://127.0.0.1/admin"},
                headers=self.auth(token),
            )
        self.assertEqual(response.status_code, 400)
        resolver.assert_not_awaited()

    def test_download_is_saved_on_server_and_only_its_device_can_fetch_it(self):
        token_a = self.new_session()
        token_b = self.new_session()
        unsafe_title = "../../ Clip: City Lights?\r\n"
        media = {**MEDIA, "title": unsafe_title}
        response = self.create_job(token_a, media)
        self.assertEqual(response.status_code, 202, response.text)
        job_id = response.json()["job_id"]
        fake_api_methods_before = [method for method, _ in FakeApi.calls]

        async def fake_download(url, work_dir, mode, max_bytes, selector, audio_quality, progress_callback):
            source = Path(work_dir) / "source.mp4"
            source.write_bytes(b"source-video")
            await progress_callback("download", 12, 12, 100)
            return source, "unused-title"

        async def fake_split(input_path, output_dir, mode, profile, max_bytes, audio_bitrate):
            destination = Path(output_dir)
            destination.mkdir(parents=True, exist_ok=True)
            part = destination / "part.mp4"
            part.write_bytes(b"local device result")
            return [part]

        with patch.object(lite_api, "_download_with_deadline", fake_download), patch.object(
            lite_api, "_split_media_with_deadline", fake_split
        ):
            chosen = self.client.post(
                f"/api/v1/jobs/{job_id}/choose",
                json={"choice_index": 0},
                headers=self.auth(token_a),
            )
            self.assertEqual(chosen.status_code, 202, chosen.text)
            deadline = time.time() + 8
            status = None
            while time.time() < deadline:
                status = self.client.get(f"/api/v1/jobs/{job_id}", headers=self.auth(token_a))
                self.assertEqual(status.status_code, 200, status.text)
                if status.json()["status"] in {"done", "failed"}:
                    break
                time.sleep(0.03)

        self.assertEqual(status.json()["status"], "done", status.text)
        files = status.json()["files"]
        self.assertEqual(len(files), 1)
        filename = files[0]["name"]
        self.assertRegex(filename, re.compile(r"^[A-Za-z0-9_.-]{1,150}$"))
        self.assertNotIn("..", filename)
        self.assertEqual(
            self.client.get(files[0]["download_url"], headers=self.auth(token_b)).status_code,
            404,
        )
        downloaded = self.client.get(files[0]["download_url"], headers=self.auth(token_a))
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        self.assertEqual(downloaded.content, b"local device result")
        self.assertEqual(downloaded.headers["cache-control"], "private, no-store")
        fake_api_methods_after = [method for method, _ in FakeApi.calls]
        self.assertEqual(fake_api_methods_after, fake_api_methods_before)
        self.assertNotIn("sendVideo", fake_api_methods_after)
        self.assertNotIn("sendAudio", fake_api_methods_after)
        self.assertNotIn("sendDocument", fake_api_methods_after)

    def test_expired_jobs_and_files_are_removed_by_cleanup(self):
        token = self.new_session()
        store = self.client.app.state.lite_store
        user_id = store.authenticate(token)
        job_id, _ = store.create_job(user_id, "https://example.com/video", MEDIA)
        output_dir = Path(self.client.app.state.lite_output_dir)
        job_dir = output_dir / job_id
        job_dir.mkdir(parents=True)
        (job_dir / "expired.mp4").write_bytes(b"expired")
        with store._connect() as db:
            db.execute("UPDATE lite_jobs SET expires_at=? WHERE job_id=?", (int(time.time()) - 1, job_id))
        store.cleanup_expired(output_dir)
        self.assertFalse(job_dir.exists())
        self.assertIsNone(store.get_job(job_id, user_id))

    def test_revoke_releases_reservation_before_job_task_is_registered(self):
        token = self.new_session()
        store = self.client.app.state.lite_store
        user_id = store.authenticate(token)
        job_id, _ = store.create_job(user_id, "https://example.com/video", MEDIA)
        app_state = self.client.app.state
        app_state.api_job_reserved = True
        app_state.api_job_reserved_job = job_id

        response = self.client.post("/api/v1/auth/revoke", headers=self.auth(token))

        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(app_state.api_job_reserved)
        self.assertIsNone(app_state.api_job_reserved_job)
        self.assertIsNone(store.get_job(job_id, user_id))

    def test_old_pairing_route_is_gone_and_user_supplied_choice_is_bounded(self):
        self.assertEqual(
            self.client.post("/api/v1/auth/pair", json={"code": "12345678"}).status_code,
            410,
        )
        token = self.new_session()
        created = self.create_job(token)
        job_id = created.json()["job_id"]
        response = self.client.post(
            f"/api/v1/jobs/{job_id}/choose",
            json={"choice_index": 10000},
            headers=self.auth(token),
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
