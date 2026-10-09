# YouTube Downloader App

URLから動画（MP4）や音声（MP3、192 kbps）を保存する日本語GUIアプリです。YouTube Shortsにも対応します。再生リストのURLに動画IDが含まれていても、指定した1本だけを保存します。

## Macで起動

macOSで[Homebrew](https://brew.sh/)を導入した後、ターミナルで実行してください。

```bash
brew install python@3.12 python-tk@3.12 ffmpeg deno
cd /path/to/youtube-
"$(brew --prefix python@3.12)/bin/python3.12" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Python 3.12以降とTk、FFmpegが必要です。Denoはyt-dlpがYouTubeのJavaScriptチャレンジを処理するために使います。追加のAPIキーは必要ありません。

一度セットアップした後は `start.command` をダブルクリックして起動できます。実行権限がない場合は `chmod +x start.command` を実行してください。HomebrewのコマンドがGUI起動時に見つからない場合は、ターミナルから `./start.command` を実行してください。

1. 動画のURLを貼り付けます。
2. MP4またはMP3と保存先を選びます。
3. 「ダウンロード」をクリックします。進捗と速度を表示します。

初期保存先は `~/Downloads/YouTube`。動画名と動画IDをファイル名に使用します。同名ファイルは上書きしません。キャンセルは通信・変換処理の区切りで反映されるため、即時に停止しないことがあります。残った一時ファイルは同じURLの再実行に利用されます。不要なら保存先から削除できます。

Macで扱いやすいH.264のMP4を優先します。配信形式によって最高解像度が選ばれない場合があります。変換中には進捗が100%近くで止まって見えることがあります。

## トラブルシューティング

- YouTubeの変更で取得できない場合: `.venv/bin/python -m pip install --upgrade -r requirements.txt`
- FFmpegが見つからない場合: `brew install ffmpeg` を実行し、同じターミナルから起動してください。
- Tkのエラーが出る場合: `python-tk@3.12` と `python@3.12` を使って仮想環境を作り直してください。
- ログインが必要な動画、DRM保護された動画、地域・年齢制限のある動画は取得できない場合があります。Cookie入力や制限回避の機能はありません。

権利者の許可があるコンテンツなど、保存する権利を持つ動画に使用してください。

## 開発と検証

```bash
.venv/bin/python -m unittest discover -s tests -v
```

ダウンロードサービスはGUIから独立しています。自動テストはURL検証、形式設定、進捗、キャンセル、失敗時の処理を外部通信なしで検証します。統合テストではローカルHTTPサーバーのサンプル動画を実際のyt-dlpで保存し、FFmpegによるMP3変換結果をffprobeで確認します（FFmpegがなければ統合テストはスキップ）。実際のYouTube取得とmacOS上の画面操作は別途確認が必要です。
