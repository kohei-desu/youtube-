import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from downloader import DownloadCancelled, DownloadRequest, build_options, download, validate_url


class DownloaderTests(unittest.TestCase):
    def test_supported_urls(self):
        for url in ("https://www.youtube.com/watch?v=abc&list=xyz", "https://youtu.be/abc", "https://youtube.com/shorts/abc", "https://youtube.com/live/abc"):
            with self.subTest(url=url):
                self.assertEqual(validate_url(" " + url + " "), url)

    def test_reject_invalid_urls(self):
        for url in ("http://youtu.be/abc", "https://youtube.com.evil.com/watch?v=abc", "https://youtube.com/playlist?list=abc", "https://youtube.com/watch", "https://youtu.be/", "https://user@youtube.com/watch?v=abc", "https://youtube.com:123/watch?v=abc", "https://[broken"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)

    def test_video_options(self):
        options = build_options(DownloadRequest("", Path("/tmp")), lambda _: None)
        self.assertEqual(options["merge_output_format"], "mp4")
        self.assertIn("avc1", options["format"])
        self.assertTrue(options["noplaylist"])
        self.assertFalse(options["overwrites"])

    def test_audio_options(self):
        options = build_options(DownloadRequest("", Path("/tmp"), "audio"), lambda _: None)
        self.assertEqual(options["postprocessors"][0]["preferredcodec"], "mp3")

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            build_options(DownloadRequest("", Path("/tmp"), "invalid"), None)

    def perform(self, callback, cancel=None):
        events = []
        class Client:
            def __init__(self, options):
                self.options = options
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def download(self, urls):
                self.urls = urls
                return callback(self)
        with tempfile.TemporaryDirectory() as folder, patch("downloader.shutil.which", return_value="/usr/bin/ffmpeg"):
            request = DownloadRequest("https://youtu.be/abc", Path(folder) / "output")
            download(request, lambda k, v: events.append((k, v)), cancel or threading.Event(), Client)
            self.assertTrue(request.destination.is_dir())
        return events

    def test_progress_and_success(self):
        def callback(client):
            self.assertEqual(client.urls, ["https://youtu.be/abc"])
            client.options["progress_hooks"][0]({"status": "downloading", "total_bytes": 100, "downloaded_bytes": 25})
            return 0
        events = self.perform(callback)
        self.assertIn(("progress", 25), events)
        self.assertEqual(events[-1][0], "complete")

    def test_unknown_total(self):
        def callback(client):
            client.options["progress_hooks"][0]({"status": "downloading", "downloaded_bytes": 25})
            return 0
        self.assertIn(("progress", None), self.perform(callback))

    def test_download_failure(self):
        with self.assertRaises(RuntimeError):
            self.perform(lambda _: 1)

    def test_cancel_before_download(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(DownloadCancelled):
            self.perform(lambda _: self.fail("Must not start"), cancel)

    def test_cancel_during_download(self):
        cancel = threading.Event()
        def callback(client):
            cancel.set()
            client.options["progress_hooks"][0]({"status": "downloading"})
        with self.assertRaises(DownloadCancelled):
            self.perform(callback, cancel)

    def test_missing_ffmpeg(self):
        with patch("downloader.shutil.which", return_value=None), self.assertRaisesRegex(RuntimeError, "FFmpeg"):
            download(DownloadRequest("https://youtu.be/abc", Path("/tmp")), None, threading.Event())


if __name__ == "__main__":
    unittest.main()
