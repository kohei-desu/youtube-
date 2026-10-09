"""Download service, kept separate from the Tk user interface."""
from dataclasses import dataclass
from pathlib import Path
import shutil
import threading
from urllib.parse import urlsplit, parse_qs


class DownloadCancelled(Exception):
    pass


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    destination: Path
    mode: str = "video"


def validate_url(url: str) -> str:
    url = url.strip()
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as error:
        raise ValueError("URLの形式を確認してください。") from error
    if parsed.scheme != "https" or parsed.username or parsed.password or port not in (None, 443):
        raise ValueError("https:// で始まるYouTubeのURLを入力してください。")
    if host == "youtu.be":
        valid = bool(parsed.path.strip("/"))
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        valid = (parsed.path == "/watch" and bool(parse_qs(parsed.query).get("v", [""])[0])) or any(
            parsed.path.startswith(prefix) and bool(parsed.path[len(prefix):].strip("/"))
            for prefix in ("/shorts/", "/live/", "/embed/")
        )
    else:
        valid = False
    if not valid:
        raise ValueError("YouTubeの動画URLを入力してください（再生リストのみのURLは対象外です）。")
    return url


def build_options(request: DownloadRequest, hook):
    if request.mode not in {"video", "audio"}:
        raise ValueError("保存形式が不正です。")
    options = {
        "outtmpl": str(request.destination / "%(title).160B [%(id)s].%(ext)s"),
        "noplaylist": True,
        "overwrites": False,
        "continuedl": True,
        "quiet": True,
        "noprogress": True,
        "no_warnings": False,
        "progress_hooks": [hook],
        "postprocessor_hooks": [hook],
        "retries": 3,
        "socket_timeout": 30,
    }
    if request.mode == "audio":
        options.update(format="bestaudio/best", postprocessors=[{
            "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192",
        }])
    else:
        options.update(
            format="bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4][vcodec^=avc1]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            merge_output_format="mp4",
        )
    return options


def download(request: DownloadRequest, emit, cancel: threading.Event, factory=None):
    url = validate_url(request.url)
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpegが必要です。ターミナルで brew install ffmpeg を実行してください。")
    request.destination.mkdir(parents=True, exist_ok=True)

    def hook(data):
        if cancel.is_set():
            raise DownloadCancelled("キャンセルしました。")
        status = data.get("status")
        if data.get("postprocessor") or status == "finished":
            emit("status", "保存・変換処理中…")
        elif status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            done = data.get("downloaded_bytes", 0)
            emit("progress", min(100, done / total * 100) if total else None)
            speed = data.get("speed")
            emit("status", f"ダウンロード中… {speed / 1024 / 1024:.1f} MB/s" if speed else "ダウンロード中…")

    if cancel.is_set():
        raise DownloadCancelled("キャンセルしました。")
    if factory is None:
        from yt_dlp import YoutubeDL
        factory = YoutubeDL
    with factory(build_options(request, hook)) as client:
        result = client.download([url])
        if cancel.is_set():
            raise DownloadCancelled("キャンセルしました。")
        if result:
            raise RuntimeError("ダウンロードが完了しませんでした。URLとネットワークを確認してください。")
    emit("complete", "保存が完了しました。")
