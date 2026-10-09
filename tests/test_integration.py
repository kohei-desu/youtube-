"""Exercise the real download engine and FFmpeg using locally generated media."""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from downloader import DownloadRequest, download


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and ffprobe required")
class MediaIntegrationTests(unittest.TestCase):
    def test_real_mp4_download_and_mp3_conversion(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "fixture.mp4"
            subprocess.run([
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x120:d=1",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:v", "mpeg4",
                "-c:a", "aac", "-shortest", str(source),
            ], check=True)
            server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=temp))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/fixture.mp4"
                for mode, extension, codec in (("video", ".mp4", "mpeg4"), ("audio", ".mp3", "mp3")):
                    with self.subTest(mode=mode):
                        events = []
                        output = base / mode
                        # Production accepts YouTube URLs only. Use a local fixture in this test.
                        with patch("downloader.validate_url", side_effect=lambda value: value):
                            download(DownloadRequest(url, output, mode), lambda k, v: events.append((k, v)), threading.Event())
                        files = list(output.glob("*" + extension))
                        self.assertEqual(len(files), 1)
                        result = subprocess.check_output([
                            "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(files[0]),
                        ], text=True)
                        self.assertIn(codec, [stream["codec_name"] for stream in json.loads(result)["streams"]])
                        self.assertEqual(events[-1][0], "complete")
                        if mode == "video":
                            self.assertEqual(files[0].read_bytes(), source.read_bytes())
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)
