"""macOS-friendly Tk desktop application. Run: python app.py"""
import queue
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from downloader import DownloadRequest, DownloadCancelled, download, validate_url


class App:
    def __init__(self, root):
        self.root = root
        root.title("YouTube Downloader")
        root.geometry("680x440")
        root.minsize(580, 420)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.closing = False
        self.url = tk.StringVar()
        self.destination = tk.StringVar(value=str(Path.home() / "Downloads" / "YouTube"))
        self.mode = tk.StringVar(value="video")
        self.status = tk.StringVar(value="URLを入力して、保存形式を選んでください。")
        outer = ttk.Frame(root, padding=28)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        ttk.Label(outer, text="YouTube Downloader", font=("Helvetica", 23, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(outer, text="動画・音声を、Macの好きなフォルダへ。", foreground="#666666").grid(row=1, column=0, sticky="w", pady=(5, 20))
        ttk.Label(outer, text="動画のURL").grid(row=2, column=0, sticky="w")
        self.url_entry = ttk.Entry(outer, textvariable=self.url)
        self.url_entry.grid(row=3, column=0, sticky="ew", pady=(5, 16))
        self.url_entry.focus_set()
        formats = ttk.Frame(outer)
        formats.grid(row=4, column=0, sticky="w")
        self.radios = [ttk.Radiobutton(formats, text=label, variable=self.mode, value=value)
                       for label, value in (("動画（MP4）", "video"), ("音声（MP3）", "audio"))]
        for radio in self.radios:
            radio.pack(side="left", padx=(0, 20))
        ttk.Label(outer, text="保存先").grid(row=5, column=0, sticky="w", pady=(16, 5))
        folder = ttk.Frame(outer)
        folder.grid(row=6, column=0, sticky="ew")
        folder.columnconfigure(0, weight=1)
        self.folder_entry = ttk.Entry(folder, textvariable=self.destination, state="readonly")
        self.folder_entry.grid(row=0, column=0, sticky="ew")
        self.browse = ttk.Button(folder, text="選択…", command=self.choose_folder)
        self.browse.grid(row=0, column=1, padx=(8, 0))
        self.progress = ttk.Progressbar(outer, maximum=100)
        self.progress.grid(row=7, column=0, sticky="ew", pady=(20, 7))
        ttk.Label(outer, textvariable=self.status, wraplength=580).grid(row=8, column=0, sticky="w")
        actions = ttk.Frame(outer)
        actions.grid(row=9, column=0, sticky="ew", pady=(15, 0))
        self.start_button = ttk.Button(actions, text="ダウンロード", command=self.start)
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="キャンセル", command=self.cancel_download, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        ttk.Button(actions, text="保存先を開く", command=self.open_folder).pack(side="right")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="保存先を選択", initialdir=str(Path.home()))
        if folder:
            self.destination.set(folder)

    def open_folder(self):
        path = Path(self.destination.get()).expanduser()
        if not path.is_dir():
            messagebox.showinfo("保存先", "ダウンロードすると保存先が作成されます。", parent=self.root)
            return
        try:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
        except OSError as error:
            messagebox.showerror("フォルダを開けません", str(error), parent=self.root)

    def set_busy(self, busy):
        for widget in [self.url_entry, self.browse, self.start_button, *self.radios]:
            widget.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            url = validate_url(self.url.get())
        except ValueError as error:
            messagebox.showerror("URLを確認してください", str(error), parent=self.root)
            return
        request = DownloadRequest(url, Path(self.destination.get()).expanduser(), self.mode.get())
        self.cancel.clear()
        self.progress.stop()
        self.progress.configure(mode="indeterminate", value=0)
        self.progress.start(15)
        self.status.set("動画情報を取得中…")
        self.set_busy(True)
        self.worker = threading.Thread(target=self.run, args=(request,), daemon=True)
        self.worker.start()

    def run(self, request):
        try:
            download(request, lambda kind, value: self.events.put((kind, value)), self.cancel)
        except Exception as error:
            if self.cancel.is_set() or isinstance(error, DownloadCancelled):
                self.events.put(("cancelled", "キャンセルしました。一時ファイルは再開時に利用されます。"))
            else:
                self.events.put(("error", str(error)))
        finally:
            self.events.put(("idle", None))

    def cancel_download(self):
        self.cancel.set()
        self.cancel_button.configure(state="disabled")
        self.status.set("キャンセルを待っています…（通信・変換の終了まで時間がかかる場合があります）")

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    if value is not None:
                        self.progress.stop()
                        self.progress.configure(mode="determinate", value=value)
                elif kind == "idle":
                    self.progress.stop()
                    self.set_busy(False)
                    if self.closing:
                        self.root.destroy()
                        return
                elif kind in {"status", "complete", "cancelled", "error"}:
                    self.status.set(value if kind != "error" else "保存できませんでした。URLや通信環境を確認してください。")
                    if kind == "complete":
                        self.progress.stop()
                        self.progress.configure(mode="determinate", value=100)
                    if kind == "error" and not self.closing:
                        messagebox.showerror("ダウンロードエラー", value, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.worker and self.worker.is_alive():
            if messagebox.askyesno("終了", "ダウンロードをキャンセルして終了しますか？", parent=self.root):
                self.closing = True
                self.cancel_download()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
