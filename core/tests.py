import os
import tempfile

from django.test import SimpleTestCase, override_settings


class ServeMediaTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.media_root = os.path.join(self.tmp.name, "media")
        os.makedirs(os.path.join(self.media_root, "videos"))
        with open(os.path.join(self.media_root, "videos", "clip.mp4"), "wb") as f:
            f.write(b"0123456789")
        with open(os.path.join(self.tmp.name, ".env"), "w") as f:
            f.write("SECRET_KEY=nope")
        self.override = override_settings(MEDIA_ROOT=self.media_root, ALLOWED_HOSTS=["testserver"])
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.tmp.cleanup()

    def test_serves_file(self):
        response = self.client.get("/media/videos/clip.mp4")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"0123456789")

    def test_range_request(self):
        response = self.client.get("/media/videos/clip.mp4", HTTP_RANGE="bytes=2-5")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response["Content-Range"], "bytes 2-5/10")

    def test_rejects_paths_outside_media_root(self):
        for path in ["/media/../.env", "/media/..%2f.env", "/media/videos/..%2f..%2f.env"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_missing_file(self):
        self.assertEqual(self.client.get("/media/videos/missing.mp4").status_code, 404)

    def test_health(self):
        self.assertEqual(self.client.get("/health/").json()["status"], "healthy")
